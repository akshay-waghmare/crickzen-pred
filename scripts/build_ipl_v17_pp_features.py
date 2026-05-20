"""
IPL v17 PP-Improved Features Build
====================================

Changes vs v15:
  PP phase only:
    - 14 high-signal features added (chase-difficulty, momentum, feasibility signals)
    - XGB hyperparams tuned: max_depth=4, min_child_weight=15, reg_alpha=1.0, reg_lambda=2.0
    - Per-cell calibration: 18 calibrators (6 overs × 3 chase categories {-1,0,1})
    - apply_calibration=True  (replaces PostModelCalibrationRouter for PP)
    - PostModelCalibrationRouter disabled

  MID and DEATH phases: identical to v15

Motivation:
  Inn2 PP underprediction for par/above-par chases. Adding chase-difficulty and
  momentum features and segmenting calibration by chase_category reduces systematic
  bias across all chase types.

OOF evaluation (5-fold season-CV, 43,551 PP rows):
  v15 baseline (per-over cal):  brier=0.17032
  v17 std cal (per-over):       brier=0.17004  (-0.16%)
  v17 cell cal (per-cell):      brier=0.16753  (-1.64%)
"""
from __future__ import annotations

import json
import pickle
import shutil
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss

sys.path.insert(0, "src")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ipl_v13_mid_split_common import (  # noqa: E402
    CAL_METHODS_V12,
    PHASE_RANGES_V12,
    XGBLRBlend,
    apply_calibrator_bundle,
    evaluate_oos,
    fit_calibrator_bundle,
    load_training_data,
    oof_phase_predictions,
    ordered_unique,
    phase_slice,
    safe_X,
    train_champion_models,
)

OUT_DIR = Path("models/ipl_v17_pp_features")
V15_MODEL_DIR = Path("models/ipl_v15_wicket_features")

# Import v15 feature engineering helpers (v14 pitch + v15 wicket context)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_ipl_v15_wicket_features import add_v14_pitch_features, add_v15_wicket_features  # noqa: E402

# ── 14 new high-signal PP features (corr 0.26–0.38 with PP outcome) ────────
V17_PP_NEW_FEATURES = [
    "late_mid_urgency",
    "death_feasibility",
    "finish_quality_zone",
    "chase_on_track_score",
    "chase_run_buffer",
    "svp_x_chase_cat",
    "momentum_under_pressure",
    "required_rpb",
    "early_mid_rrr_vs_venue_avg",
    "chase_difficulty",
    "score_per_wicket",
    "wickets_times_balls",
    "wickets_last_30",
    "balls_since_wicket",
]

# Tuned XGB params for PP (max_depth=4 reduces overfitting on 84 features)
PP_XGB_PARAMS = {
    "max_depth": 4,
    "min_child_weight": 15,
    "reg_alpha": 1.0,
    "reg_lambda": 2.0,
}


# ── helpers ──────────────────────────────────────────────────────────────────

def pct_change(new_value: float, old_value: float) -> str:
    if old_value == 0:
        return "n/a"
    return f"{(new_value - old_value) / old_value * 100:+.2f}%"


def fit_cell_calibrators(
    raw: np.ndarray,
    y: np.ndarray,
    overs: np.ndarray,
    categories: np.ndarray,
    min_rows: int = 30,
) -> dict[tuple[int, int], IsotonicRegression]:
    """Fit one isotonic calibrator per (over, chase_category) cell."""
    cals: dict[tuple[int, int], IsotonicRegression] = {}
    for ov in sorted(np.unique(overs)):
        for cat in sorted(np.unique(categories)):
            mask = (overs == ov) & (categories == cat)
            if mask.sum() < min_rows:
                continue
            iso = IsotonicRegression(out_of_bounds="clip")
            iso.fit(raw[mask], y[mask])
            cals[(int(ov), int(cat))] = iso
    return cals


def apply_cell_calibrators(
    raw: np.ndarray,
    overs: np.ndarray,
    categories: np.ndarray,
    cals: dict[tuple[int, int], IsotonicRegression],
    fallback_cal: IsotonicRegression,
) -> np.ndarray:
    out = np.empty_like(raw)
    for ov in np.unique(overs):
        for cat in np.unique(categories):
            mask = (overs == ov) & (categories == cat)
            if not mask.any():
                continue
            key = (int(ov), int(cat))
            c = cals.get(key, fallback_cal)
            out[mask] = c.predict(raw[mask])
    return out


def train_pp_champion(df: pd.DataFrame, feats: list[str]) -> tuple[XGBLRBlend, list[str]]:
    """Train PP champion model with custom XGB params."""
    pf = phase_slice(df, PHASE_RANGES_V12["pp"])
    X, avail = safe_X(pf, feats)
    y = pf["is_winner"].values
    model = XGBLRBlend(xgb_params=PP_XGB_PARAMS)
    model.fit(X, y)
    return model, avail


def summarize_phase(eval_result: dict, phase: str) -> dict:
    phase_result = eval_result["phases"][phase]
    return {
        "n": int(phase_result["n"]),
        "brier_raw": float(phase_result["brier_raw"]),
        "brier_cal": float(phase_result["brier_cal"]),
    }


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading inn2 data and adding v14/v15 engineered features...")
    df = load_training_data()
    df = add_v14_pitch_features(df)
    df = add_v15_wicket_features(df)

    # v17 feature lists: PP has 14 new features; MID/DEATH are unchanged from v15
    with open(V15_MODEL_DIR / "phase_features.json", encoding="utf-8") as f:
        v15_feats = json.load(f)

    all_cols = set(df.columns)
    available_new = [f for f in V17_PP_NEW_FEATURES if f in all_cols]
    missing = [f for f in V17_PP_NEW_FEATURES if f not in all_cols]
    if missing:
        print(f"  WARNING: {len(missing)} v17 PP features not in training data: {missing}")

    v17_feats = {
        "pp":    ordered_unique(v15_feats["pp"] + available_new),
        "mid":   v15_feats["mid"],
        "death": v15_feats["death"],
    }
    print(
        f"  Inn2 rows: {len(df):,} | "
        f"PP features: {len(v15_feats['pp'])} → {len(v17_feats['pp'])} "
        f"(+{len(v17_feats['pp'])-len(v15_feats['pp'])} new)"
    )

    # ── Step 1: OOF calibrators ───────────────────────────────────────────────
    print("\nStep 1: OOF season-fold CV for v17 calibrators...")
    phase_oof_cals: dict = {}
    oof_rows = []

    for phase, over_range in PHASE_RANGES_V12.items():
        pf = phase_slice(df, over_range)
        xgb_p = PP_XGB_PARAMS if phase == "pp" else None
        oof = oof_phase_predictions(pf, v17_feats[phase], xgb_params=xgb_p)
        bundle = fit_calibrator_bundle(oof["raw"], oof["y"], oof["over"], CAL_METHODS_V12[phase])
        cal_std = apply_calibrator_bundle(oof["raw"], oof["over"], bundle)
        brier_raw = float(brier_score_loss(oof["y"], oof["raw"]))
        brier_std = float(brier_score_loss(oof["y"], cal_std))

        if phase == "pp":
            # Per-cell calibration for PP
            cats = pf["chase_category"].values.astype(int)
            cell_cals = fit_cell_calibrators(oof["raw"], oof["y"], oof["over"], cats)
            cal_cell = apply_cell_calibrators(
                oof["raw"], oof["over"], cats, cell_cals, bundle["phase_iso"]
            )
            brier_cell = float(brier_score_loss(oof["y"], cal_cell))
            bundle["per_cell"] = cell_cals
            print(
                f"  {phase.upper():<5} rows={len(pf):>6,} feats={len(v17_feats[phase]):>2} "
                f"raw={brier_raw:.5f} std_cal={brier_std:.5f} cell_cal={brier_cell:.5f}"
                f"  ({pct_change(brier_cell, 0.17032)} vs v15 baseline)"
            )
            oof_rows.append({
                "phase": phase, "n_rows": len(pf), "n_features": len(v17_feats[phase]),
                "oof_brier_raw": round(brier_raw, 5), "oof_brier_std_cal": round(brier_std, 5),
                "oof_brier_cell_cal": round(brier_cell, 5),
            })
        else:
            brier_cal = float(brier_score_loss(oof["y"], cal_std))
            print(
                f"  {phase.upper():<5} rows={len(pf):>6,} feats={len(v17_feats[phase]):>2} "
                f"raw={brier_raw:.5f} cal={brier_cal:.5f}"
            )
            oof_rows.append({
                "phase": phase, "n_rows": len(pf), "n_features": len(v17_feats[phase]),
                "oof_brier_raw": round(brier_raw, 5), "oof_brier_std_cal": round(brier_cal, 5),
                "oof_brier_cell_cal": None,
            })

        phase_oof_cals[phase] = bundle

    with open(OUT_DIR / "phase_oof_calibrators.pkl", "wb") as f:
        pickle.dump(phase_oof_cals, f)
    print(f"  Saved: {OUT_DIR / 'phase_oof_calibrators.pkl'} (PP has {len(phase_oof_cals['pp']['per_cell'])} cell calibrators)")

    # ── Step 2: Train champion models ─────────────────────────────────────────
    print("\nStep 2: Training v17 champion models on ALL data...")

    # PP with custom XGB params
    pp_model, pp_feats = train_pp_champion(df, v17_feats["pp"])
    joblib.dump(pp_model, OUT_DIR / "champion_model_pp.joblib")
    print(f"  Saved champion_model_pp.joblib ({len(pp_feats)} features, depth=4/minwt=15)")

    # MID and DEATH: re-use v15 models directly (unchanged)
    for phase in ["mid", "death"]:
        src_path = V15_MODEL_DIR / f"champion_model_{phase}.joblib"
        dst_path = OUT_DIR / f"champion_model_{phase}.joblib"
        shutil.copy2(src_path, dst_path)
        print(f"  Copied champion_model_{phase}.joblib from v15 ({len(v17_feats[phase])} features)")

    # Feature manifest (PP updated, MID/DEATH same as v15)
    phase_features_out = {
        "pp":    pp_feats,
        "mid":   v17_feats["mid"],
        "death": v17_feats["death"],
    }
    with open(OUT_DIR / "phase_features.json", "w", encoding="utf-8") as f:
        json.dump(phase_features_out, f, indent=2)
    print(f"  Saved: {OUT_DIR / 'phase_features.json'}")

    # Copy venue baselines from v15 (unchanged)
    shutil.copy2(V15_MODEL_DIR / "venue_pitch_baselines.json", OUT_DIR / "venue_pitch_baselines.json")
    print("  Copied venue_pitch_baselines.json from v15")

    # ── Step 3: Routing config ────────────────────────────────────────────────
    routing_config = {
        "type": "inn2_phase_router",
        "description": (
            "ipl_v17_pp_features: v15 + 14 high-signal PP features + per-cell calibration "
            "(6 overs × 3 chase_categories). PP XGB: depth=4, minwt=15. "
            "MID and DEATH phases identical to v15."
        ),
        "inn1_model_dir": "models/ipl_v7",
        "inn2_phase_model_dir": str(OUT_DIR).replace("\\", "/"),
        "apply_calibration": True,
        "post_model_calibration": {
            "enabled": False,
            "reason": "Per-cell calibration in phase_oof_calibrators.pkl replaces post_model_calibration_router.",
        },
        "pp_low_fallback_model_dir": "models/ipl_v12",
        "pp_low_fallback_rule": "phase == pp and target_above_par < -20 uses models/ipl_v12 raw probability",
        "inn2_changes_vs_v15": {
            "pp": V17_PP_NEW_FEATURES,
            "mid": [],
            "death": [],
        },
        "calibration": {
            "pp": "per_cell_isotonic (6 overs × 3 chase_categories = 18 calibrators)",
            "mid": "per_over_isotonic",
            "death": "per_over_isotonic",
        },
        "oof_brier": {
            "pp_v15_baseline": 0.17032,
            "pp_v17_cell_cal": round(brier_cell, 5),
            "pp_v17_improvement_pct": pct_change(brier_cell, 0.17032),
        },
    }
    with open(OUT_DIR / "routing_config.json", "w", encoding="utf-8") as f:
        json.dump(routing_config, f, indent=2)
    print(f"  Saved: {OUT_DIR / 'routing_config.json'}")

    # ── Step 4: OOS comparison (train < 2025, test = 2025+2026) ───────────────
    print("\nStep 3: True OOS evaluation (train: pre-2025, test: 2025+2026)...")
    v15_oos = evaluate_oos(df, PHASE_RANGES_V12, v15_feats, CAL_METHODS_V12)
    v17_oos_pp = _evaluate_oos_pp(df, v17_feats["pp"])

    v15_oos_pp = v15_oos["phases"].get("pp", {})
    print(f"\n{'Metric':<28} {'v15 OOS':>12} {'v17 OOS':>12} {'Change':>10}")
    print("-" * 65)
    if v15_oos_pp and v17_oos_pp["n"] > 0:
        v15b = v15_oos_pp["brier_cal"]
        v17b = v17_oos_pp["brier_cell_cal"]
        print(
            f"{'PP brier (OOS test 2025-26)':<28} {v15b:>12.5f} {v17b:>12.5f} "
            f"{pct_change(v17b, v15b):>10}  n={v17_oos_pp['n']}"
        )

    # Save OOF results
    pd.DataFrame(oof_rows).to_csv(OUT_DIR / "oof_results.csv", index=False)
    print(f"\n  Saved: {OUT_DIR / 'oof_results.csv'}")

    print("\n" + "=" * 60)
    print("IPL v17 PP BUILD COMPLETE")
    print("=" * 60)
    print(f"  PP OOF brier (cell cal):  {brier_cell:.5f} ({pct_change(brier_cell, 0.17032)} vs v15 OOF baseline)")
    if v17_oos_pp["n"] > 0:
        print(f"  PP OOS brier (cell cal):  {v17_oos_pp['brier_cell_cal']:.5f} (n={v17_oos_pp['n']} 2025-26 rows)")
    print(f"  PP features: {len(v15_feats['pp'])} (v15) → {len(v17_feats['pp'])} (v17)")
    print(f"  PP cell calibrators: {len(phase_oof_cals['pp']['per_cell'])}")
    print(f"  Artifacts saved: {OUT_DIR}")


def _evaluate_oos_pp(df: pd.DataFrame, feats: list[str]) -> dict:
    """OOS evaluation for PP: train on pre-2025, test on 2025+2026."""
    from ipl_v13_mid_split_common import phase_slice, safe_X
    pf = phase_slice(df, PHASE_RANGES_V12["pp"])
    train_mask = ~pf["season"].isin(["2025", "2026"])
    test_mask = pf["season"].isin(["2025", "2026"])
    if test_mask.sum() == 0:
        return {"n": 0, "brier_raw": None, "brier_cell_cal": None}

    X_tr, avail = safe_X(pf[train_mask], feats)
    X_te, _ = safe_X(pf[test_mask], feats)
    y_tr = pf.loc[train_mask, "is_winner"].values
    y_te = pf.loc[test_mask, "is_winner"].values

    model = XGBLRBlend(xgb_params=PP_XGB_PARAMS)
    model.fit(X_tr, y_tr)
    raw_te = model.predict_proba(X_te)[:, 1]

    overs_te = pf.loc[test_mask, "over"].values.astype(int)
    cats_te = pf.loc[test_mask, "chase_category"].values.astype(int)

    # Fit cell calibrators on training set
    overs_tr = pf.loc[train_mask, "over"].values.astype(int)
    cats_tr = pf.loc[train_mask, "chase_category"].values.astype(int)
    raw_tr = model.predict_proba(X_tr)[:, 1]
    cell_cals = fit_cell_calibrators(raw_tr, y_tr, overs_tr, cats_tr)

    # Fallback: phase-level iso fit on training
    phase_iso = IsotonicRegression(out_of_bounds="clip")
    phase_iso.fit(raw_tr, y_tr)

    cal_te = apply_cell_calibrators(raw_te, overs_te, cats_te, cell_cals, phase_iso)

    return {
        "n": int(test_mask.sum()),
        "brier_raw": float(brier_score_loss(y_te, raw_te)),
        "brier_cell_cal": float(brier_score_loss(y_te, cal_te)),
    }


if __name__ == "__main__":
    main()
