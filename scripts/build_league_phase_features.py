"""
Reusable Phase-Split Model Builder
====================================

Build PP/MID/DEATH phase-split innings-2 models for any T20 league.
Usage:
    python scripts/build_league_phase_features.py --league ntb --version v1
    python scripts/build_league_phase_features.py --league ipl --version v18

Prerequisites:
    - Base model trained via: bbl-pipeline retrain --league <league> --version <version>
    - Feature parquet at: data/<league>_features_<version>/training.parquet

Architecture:
    - Innings 1: Uses base model from models/<league>_<version>/champion_model.joblib
    - Innings 2 PP (overs 1-6): XGBLRBlend + per-over isotonic calibration
    - Innings 2 MID (overs 7-15): XGBLRBlend + per-over platt calibration
    - Innings 2 DEATH (overs 16-20): XGBLRBlend + per-over isotonic calibration
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss

sys.path.insert(0, "src")

from bbl_pipeline.training.blend_model import XGBLRBlend
from bbl_pipeline.training.calibration import PlattCalibrator

PHASE_RANGES = {"pp": (1, 6), "mid": (7, 15), "death": (16, 20)}
CAL_METHODS = {"pp": "isotonic", "mid": "platt", "death": "isotonic"}

# ── Core feature candidates (taken from IPL v17 + NTB v1 best performers) ────
CORE_FEATURES = {
    "pp": [
        "resource_win_prob", "expected_final_score", "score_vs_par",
        "dls_pressure_index", "projected_score", "projected_vs_venue_avg",
        "is_powerplay", "score_per_wicket", "run_rate_diff",
        "current_run_rate", "required_run_rate", "target_above_par",
        "chase_difficulty", "resources_remaining", "overs_remaining",
        "wickets_remaining", "momentum_score", "momentum_under_pressure",
        "scoring_rate_gap", "crr_vs_rrr_ratio", "pressure_index",
        "wickets_lost", "runs_last_12", "runs_last_30",
        "wickets_last_6", "wickets_last_30", "boundary_pct_last_18",
        "venue_win_rate_chasing", "venue_avg_score",
        "target_clarity_index", "chase_on_track_score",
        "early_settle_flag", "wicket_budget_remaining",
        "pp_ease_score", "pp_rrr_ease", "chase_ease_x_venue",
        "runs_per_wkt_rem", "wr_x_rrr", "comfortable_wicket_zone",
        "wickets_x_high_chase", "wicket_resource_buffer", "high_chase_wickets_flag",
    ],
    "mid": [
        "resource_win_prob", "expected_final_score", "score_vs_par",
        "dls_pressure_index", "projected_score", "projected_vs_venue_avg",
        "is_powerplay", "score_per_wicket", "run_rate_diff",
        "current_run_rate", "required_run_rate", "target_above_par",
        "chase_difficulty", "resources_remaining", "overs_remaining",
        "wickets_remaining", "momentum_score", "momentum_under_pressure",
        "scoring_rate_gap", "crr_vs_rrr_ratio", "pressure_index",
        "wickets_lost", "runs_last_12", "runs_last_30",
        "wickets_last_6", "wickets_last_30", "boundary_pct_last_18",
        "venue_win_rate_chasing", "venue_avg_score",
        "target_clarity_index", "chase_on_track_score",
        "wicket_budget_remaining", "late_mid_urgency", "late_mid_run_gap",
        "momentum_shift_flag", "acceleration_zone", "late_wkt_collapse_risk",
        "finish_quality_zone", "runs_per_wkt_rem",
        "wickets_x_high_chase", "wicket_resource_buffer", "high_chase_wickets_flag",
    ],
    "death": [
        "resource_win_prob", "expected_final_score", "score_vs_par",
        "dls_pressure_index", "projected_score", "projected_vs_venue_avg",
        "is_powerplay", "score_per_wicket", "run_rate_diff",
        "current_run_rate", "required_run_rate", "target_above_par",
        "chase_difficulty", "resources_remaining", "overs_remaining",
        "wickets_remaining", "momentum_score", "momentum_under_pressure",
        "scoring_rate_gap", "crr_vs_rrr_ratio", "pressure_index",
        "wickets_lost", "runs_last_12", "runs_last_30",
        "wickets_last_6", "wickets_last_30", "boundary_pct_last_18",
        "venue_win_rate_chasing", "venue_avg_score",
        "late_mid_urgency", "finish_quality_zone",
        "runs_per_wkt_rem", "wickets_x_high_chase",
        "wicket_resource_buffer", "high_chase_wickets_flag",
    ],
}


def ordered_unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            out.append(item)
            seen.add(item)
    return out


def load_training_data(data_path: Path) -> pd.DataFrame:
    df = pd.read_parquet(data_path)
    df = df.sort_values(["match_id", "innings", "over", "ball"]).reset_index(drop=True)
    df = df[df["innings"] == 2].copy()
    df["season"] = df["season"].astype(str)
    df = _add_chase_features(df)
    return df


def _add_chase_features(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    rrr = d.get("required_run_rate", pd.Series(0.1, index=d.index)).fillna(0.1).clip(lower=0.1)
    tap = d.get("target_above_par", pd.Series(0.0, index=d.index)).fillna(0.0)
    vcs = d.get("venue_chase_success", pd.Series(0.5, index=d.index)).fillna(0.5)
    res = d.get("resources_remaining", pd.Series(0.0, index=d.index)).fillna(0.0)
    overs_remaining = d.get("overs_remaining", pd.Series(0.0, index=d.index)).fillna(0.0)
    wickets_lost = d.get("wickets_lost", pd.Series(0.0, index=d.index)).fillna(0.0)
    wickets_remaining = d.get("wickets_remaining", 10 - wickets_lost).fillna(10 - wickets_lost)
    required_run_rate = d.get("required_run_rate", pd.Series(0.0, index=d.index)).fillna(0.0)
    score_vs_par = d.get("score_vs_par", pd.Series(0.0, index=d.index)).fillna(0.0)
    resources_remaining = d.get("resources_remaining", pd.Series(0.0, index=d.index)).fillna(0.0)
    runs_last_12 = d.get("runs_last_12", pd.Series(0.0, index=d.index)).fillna(0.0)
    momentum_score = d.get("momentum_score", pd.Series(0.0, index=d.index)).fillna(0.0)
    scoring_rate_gap = d.get("scoring_rate_gap", pd.Series(0.0, index=d.index)).fillna(0.0)
    crr_vs_rrr_ratio = d.get("crr_vs_rrr_ratio", pd.Series(1.0, index=d.index)).fillna(1.0)
    wickets_last_6 = d.get("wickets_last_6", pd.Series(0.0, index=d.index)).fillna(0.0)
    projected_score = d.get("projected_score", pd.Series(160.0, index=d.index)).fillna(160.0)
    projected_vs_venue_avg = d.get("projected_vs_venue_avg", pd.Series(0.0, index=d.index)).fillna(0.0)
    venue_avg_score = (projected_score - projected_vs_venue_avg).replace(0, np.nan).fillna(projected_score.clip(lower=120.0))

    d["pp_ease_score"] = (-tap) / rrr
    d["pp_rrr_ease"] = 10.0 - rrr
    d["chase_ease_x_venue"] = (-tap.clip(upper=0)) * vcs
    d["low_target_strong_venue"] = (tap < -15).astype(float) * vcs
    d["pp_resources_adj_ease"] = (-tap) * res
    d["target_clarity_index"] = tap / (overs_remaining + 1.0)
    d["early_mid_rrr_vs_venue_avg"] = (required_run_rate / venue_avg_score.replace(0, np.nan) * 20.0).fillna(0.0)
    d["wicket_budget_remaining"] = wickets_remaining - (overs_remaining * 0.4)
    d["chase_on_track_score"] = score_vs_par * (resources_remaining + 0.01)
    d["early_settle_flag"] = ((wickets_lost <= 2) & (score_vs_par >= 0)).astype(float)
    d["late_mid_urgency"] = required_run_rate * (1.0 + wickets_lost / 10.0)
    d["late_mid_run_gap"] = runs_last_12 - (required_run_rate * 2.0)
    d["momentum_shift_flag"] = ((momentum_score > 0.5) & (scoring_rate_gap < 0)).astype(float)
    d["acceleration_zone"] = ((overs_remaining <= 4) & (crr_vs_rrr_ratio >= 0.9)).astype(float)
    d["late_wkt_collapse_risk"] = ((wickets_last_6 >= 2) & (required_run_rate > 9)).astype(float)
    d["finish_quality_zone"] = wickets_remaining * (1.0 / (required_run_rate + 0.1))

    try:
        from bbl_pipeline.features.inn2_engineering import engineer_inn2_features
        engineered = engineer_inn2_features(d)
        for col in ["runs_per_wkt_rem", "wr_x_rrr", "comfortable_wicket_zone",
                     "wickets_x_high_chase", "wicket_resource_buffer", "high_chase_wickets_flag"]:
            if col in engineered.columns and col not in d.columns:
                d[col] = engineered[col].values
    except ImportError:
        pass
    return d


def phase_slice(df: pd.DataFrame, over_range: tuple[int, int]) -> pd.DataFrame:
    lo, hi = over_range
    return df[(df["over"] >= lo) & (df["over"] <= hi)].copy().reset_index(drop=True)


def safe_X(df_s: pd.DataFrame, feats: list[str]) -> tuple[np.ndarray, list[str]]:
    avail = [f for f in feats if f in df_s.columns]
    if not avail:
        raise ValueError("No requested features are available")
    med = df_s[avail].median(numeric_only=True)
    return df_s[avail].fillna(med).values, avail


def season_folds(seasons: list[str], n_folds: int = 5) -> list[list[str]]:
    seasons = sorted([str(s) for s in seasons])
    if not seasons:
        return []
    fold_size = max(1, len(seasons) // n_folds)
    folds: list[list[str]] = []
    for fold in range(n_folds):
        start = fold * fold_size
        stop = (fold + 1) * fold_size if fold < n_folds - 1 else len(seasons)
        val = seasons[start:stop]
        if val:
            folds.append(val)
    return folds


def oof_phase_predictions(
    phase_df: pd.DataFrame, feats: list[str], n_folds: int = 5, xgb_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    phase_df = phase_df.reset_index(drop=True)
    raw = np.zeros(len(phase_df), dtype=float)
    y = phase_df["is_winner"].values.astype(float)
    overs = phase_df["over"].values.astype(int)
    seasons = sorted(phase_df["season"].astype(str).unique().tolist())
    folds = season_folds(seasons, n_folds=n_folds)
    for val_seasons in folds:
        tr_mask = ~phase_df["season"].isin(val_seasons)
        va_mask = phase_df["season"].isin(val_seasons)
        if tr_mask.sum() == 0 or va_mask.sum() == 0:
            continue
        X_tr, avail = safe_X(phase_df[tr_mask], feats)
        X_va, _ = safe_X(phase_df[va_mask], feats)
        y_tr = phase_df.loc[tr_mask, "is_winner"].values
        model = XGBLRBlend(xgb_params=xgb_params)
        model.fit(X_tr, y_tr)
        raw[va_mask.values] = model.predict_proba(X_va)[:, 1]
    return {"raw": raw, "y": y, "over": overs, "brier": float(brier_score_loss(y, raw)), "n": len(phase_df)}


def make_calibrator(method: str):
    return PlattCalibrator(C=1.0) if method == "platt" else IsotonicRegression(out_of_bounds="clip")


def fit_calibrator_bundle(raw: np.ndarray, y: np.ndarray, overs: np.ndarray, method: str) -> dict[str, Any]:
    phase_iso = make_calibrator(method)
    phase_iso.fit(raw, y)
    per_over: dict[int, Any] = {}
    for ov in sorted(np.unique(overs)):
        mask = overs == ov
        if mask.sum() >= 40:
            cal = make_calibrator(method)
            cal.fit(raw[mask], y[mask])
            per_over[int(ov)] = cal
    return {"per_over": per_over, "phase_iso": phase_iso}


def apply_calibrator_bundle(raw: np.ndarray, overs: np.ndarray, bundle: dict[str, Any]) -> np.ndarray:
    out = np.empty_like(raw)
    phase_iso = bundle.get("phase_iso")
    per_over = bundle.get("per_over", {})
    for ov in np.unique(overs):
        mask = overs == ov
        cal = per_over.get(int(ov), phase_iso)
        out[mask] = raw[mask] if cal is None else cal.transform(raw[mask])
    return out


def train_champion_models(df: pd.DataFrame, phase_features: dict[str, list[str]]) -> dict[str, tuple[XGBLRBlend, list[str]]]:
    models: dict[str, tuple[XGBLRBlend, list[str]]] = {}
    for phase, over_range in PHASE_RANGES.items():
        pf = phase_slice(df, over_range)
        X, avail = safe_X(pf, phase_features[phase])
        y = pf["is_winner"].values
        model = XGBLRBlend()
        model.fit(X, y)
        models[phase] = (model, avail)
    return models


def evaluate_oos(df: pd.DataFrame, phase_features: dict[str, list[str]]) -> dict[str, Any]:
    train_seasons = {s for s in sorted(df["season"].unique()) if s < "2025"}
    test_seasons = {s for s in sorted(df["season"].unique()) if s >= "2025"}
    phase_outputs: dict[str, Any] = {}
    all_raw, all_cal, all_y = [], [], []

    for phase, over_range in PHASE_RANGES.items():
        pf = phase_slice(df, over_range)
        pf_tr = pf[pf["season"].isin(train_seasons)].copy().reset_index(drop=True)
        pf_te = pf[pf["season"].isin(test_seasons)].copy().reset_index(drop=True)
        if pf_te.empty:
            continue
        train_oof = oof_phase_predictions(pf_tr, phase_features[phase])
        bundle = fit_calibrator_bundle(train_oof["raw"], train_oof["y"], train_oof["over"], CAL_METHODS[phase])
        X_tr, avail = safe_X(pf_tr, phase_features[phase])
        X_te, _ = safe_X(pf_te, phase_features[phase])
        y_tr = pf_tr["is_winner"].values
        y_te = pf_te["is_winner"].values
        over_te = pf_te["over"].values.astype(int)
        model = XGBLRBlend()
        model.fit(X_tr, y_tr)
        raw_te = model.predict_proba(X_te)[:, 1]
        cal_te = apply_calibrator_bundle(raw_te, over_te, bundle)
        phase_outputs[phase] = {"raw": raw_te, "cal": cal_te, "y": y_te, "over": over_te,
                                 "n": int(len(y_te)), "brier_raw": float(brier_score_loss(y_te, raw_te)),
                                 "brier_cal": float(brier_score_loss(y_te, cal_te)), "features": avail}
        all_raw.extend(raw_te.tolist())
        all_cal.extend(cal_te.tolist())
        all_y.extend(y_te.tolist())

    all_raw_arr, all_cal_arr, all_y_arr = np.array(all_raw), np.array(all_cal), np.array(all_y)
    return {"train_seasons": sorted(train_seasons), "test_seasons": sorted(test_seasons),
            "phases": phase_outputs,
            "overall_raw": float(brier_score_loss(all_y_arr, all_raw_arr)) if len(all_y_arr) > 0 else float("nan"),
            "overall_cal": float(brier_score_loss(all_y_arr, all_cal_arr)) if len(all_y_arr) > 0 else float("nan")}


def pct_change(new_value: float, old_value: float) -> str:
    if old_value == 0:
        return "n/a"
    return f"{(new_value - old_value) / old_value * 100:+.2f}%"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build phase-split model for any T20 league")
    parser.add_argument("--league", required=True, help="League slug (e.g., ntb, ipl, psl, sa20)")
    parser.add_argument("--version", required=True, help="Model version (e.g., v1, v2)")
    parser.add_argument("--features-version", default=None,
                        help="Features data version (defaults to same as --version)")
    args = parser.parse_args()

    league = args.league
    version = args.version
    features_ver = args.features_version or version

    data_path = Path(f"data/{league}_features_{features_ver}/training.parquet")
    out_dir = Path(f"models/{league}_{version}_phase")
    base_model_dir = Path(f"models/{league}_{version}")

    if not data_path.exists():
        print(f"ERROR: Training data not found at {data_path}")
        print(f"Run: bbl-pipeline retrain --league {league} --version {version}")
        return

    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print(f"{league.upper()} {version} Phase-Split Model Build")
    print("=" * 70)
    print(f"  Data:      {data_path}")
    print(f"  Output:    {out_dir}")
    print(f"  Base model:{base_model_dir}")

    print("\nLoading inn2 data and adding chase features...")
    df = load_training_data(data_path)

    all_cols = set(df.columns)
    phase_feats: dict[str, list[str]] = {}
    for phase, feats in CORE_FEATURES.items():
        available = [f for f in feats if f in all_cols]
        missing = [f for f in feats if f not in all_cols]
        if missing:
            print(f"  NOTE: {len(missing)}/{len(feats)} {phase} features not in data (normal for new leagues)")
        phase_feats[phase] = ordered_unique(available)

    print(f"  Inn2 rows: {len(df):,}")
    print(f"  Seasons: {sorted(df['season'].unique())}")
    print(f"  Features: PP={len(phase_feats['pp'])} MID={len(phase_feats['mid'])} DEATH={len(phase_feats['death'])}")

    # ── Step 1: OOF calibrators ────────────────────────────────────────────────
    print("\nStep 1: OOF season-fold CV for calibrators...")
    phase_oof_cals: dict = {}
    oof_rows = []

    for phase, over_range in PHASE_RANGES.items():
        pf = phase_slice(df, over_range)
        oof = oof_phase_predictions(pf, phase_feats[phase])
        bundle = fit_calibrator_bundle(oof["raw"], oof["y"], oof["over"], CAL_METHODS[phase])
        cal = apply_calibrator_bundle(oof["raw"], oof["over"], bundle)
        oof_brier_cal = float(brier_score_loss(oof["y"], cal))
        phase_oof_cals[phase] = bundle
        oof_rows.append({"phase": phase, "n_rows": len(pf), "n_features": len(phase_feats[phase]),
                          "oof_brier_raw": round(oof["brier"], 5), "oof_brier_cal": round(oof_brier_cal, 5)})
        print(f"  {phase.upper():<5} rows={len(pf):>6,} feats={len(phase_feats[phase]):>2} "
              f"raw={oof['brier']:.5f} cal={oof_brier_cal:.5f}")

    with open(out_dir / "phase_oof_calibrators.pkl", "wb") as f:
        pickle.dump(phase_oof_cals, f)
    print(f"  Saved: {out_dir / 'phase_oof_calibrators.pkl'}")

    # ── Step 2: Train champion models ──────────────────────────────────────────
    print("\nStep 2: Training champion models on ALL data...")
    champion_models = train_champion_models(df, phase_feats)
    for phase, (model, feats) in champion_models.items():
        joblib.dump(model, out_dir / f"champion_model_{phase}.joblib")
        print(f"  Saved champion_model_{phase}.joblib ({len(feats)} features)")

    with open(out_dir / "phase_features.json", "w", encoding="utf-8") as f:
        json.dump({phase: feats for phase, (_, feats) in champion_models.items()}, f, indent=2)
    print(f"  Saved: {out_dir / 'phase_features.json'}")

    # ── Routing config ─────────────────────────────────────────────────────────
    routing_config = {
        "type": "inn2_phase_router",
        "description": f"{league}_{version}_phase: Phase-split innings-2 model (PP/MID/DEATH) via XGBLRBlend + per-over calibration.",
        "inn1_model_dir": str(base_model_dir).replace("\\", "/"),
        "inn2_phase_model_dir": str(out_dir).replace("\\", "/"),
        "apply_calibration": True,
        "post_model_calibration": {"enabled": False},
        "calibration": {"pp": "per_over_isotonic", "mid": "per_over_platt", "death": "per_over_isotonic"},
    }
    with open(out_dir / "routing_config.json", "w", encoding="utf-8") as f:
        json.dump(routing_config, f, indent=2)
    print(f"  Saved: {out_dir / 'routing_config.json'}")

    # ── Step 3: OOS evaluation ─────────────────────────────────────────────────
    print("\nStep 3: True OOS evaluation (train<2025, test=2025+)...")
    oos = evaluate_oos(df, phase_feats)

    print(f"\nTrain seasons: {oos['train_seasons']}")
    print(f"Test seasons : {oos['test_seasons']}")
    print(f"\n{'Phase':<10} {'raw':>10} {'cal':>10} {'n':>8}")
    print("-" * 50)
    oos_rows = []
    for phase in ["pp", "mid", "death"]:
        if phase in oos["phases"]:
            p = oos["phases"][phase]
            oos_rows.append({"phase": phase, "oos_brier_raw": round(p["brier_raw"], 5),
                              "oos_brier_cal": round(p["brier_cal"], 5), "n": p["n"]})
            print(f"{phase.upper():<10} {p['brier_raw']:>10.5f} {p['brier_cal']:>10.5f} {p['n']:>8,}")

    if oos_rows:
        total_n = sum(r["n"] for r in oos_rows)
        print("-" * 50)
        print(f"{'OVERALL':<10} {oos['overall_raw']:>10.5f} {oos['overall_cal']:>10.5f} {total_n:>8,}")

    pd.DataFrame(oos_rows).to_csv(out_dir / "oos_comparison.csv", index=False)
    pd.DataFrame(oof_rows).to_csv(out_dir / "oof_results.csv", index=False)

    print(f"\n{'=' * 60}")
    print(f"{league.upper()} {version} PHASE BUILD COMPLETE")
    print("=" * 60)
    print(f"  Artifacts saved: {out_dir}")
    print(f"  OOF results: {out_dir / 'oof_results.csv'}")
    print(f"  OOS comparison: {out_dir / 'oos_comparison.csv'}")


if __name__ == "__main__":
    main()
