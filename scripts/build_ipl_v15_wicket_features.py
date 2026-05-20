"""
IPL v15 Wicket-Context Features Build
======================================

Changes vs v14:
  All phases: add wicket × chase-difficulty interaction features
    - runs_per_wkt_rem     (existing, was only in DEATH; now in PP + MID too)
    - wr_x_rrr             (existing, was only in DEATH; now in PP)
    - comfortable_wicket_zone (existing, was only in DEATH; now in PP)
    - wickets_x_high_chase (NEW: wickets_remaining × is_high_chase)
    - wicket_resource_buffer (NEW: wickets_remaining/10 − resource_win_prob)
    - high_chase_wickets_flag (NEW: is_high_chase AND wickets_remaining ≥ 8)

Motivation: v14 PP model underestimates win probability for high-chase PP
scenarios (e.g. chasing 220 at 0/0) because resource_win_prob (DLS-based)
dominates but completely ignores wickets in hand.  These features explicitly
encode the wicket buffer that makes high-RRR chases tractable early.
"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import brier_score_loss

sys.path.insert(0, "src")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ipl_v13_mid_split_common import (  # noqa: E402
    CAL_METHODS_V12,
    PHASE_RANGES_V12,
    apply_calibrator_bundle,
    evaluate_oos,
    fit_calibrator_bundle,
    load_training_data,
    oof_phase_predictions,
    ordered_unique,
    phase_slice,
    train_champion_models,
)

OUT_DIR = Path("models/ipl_v15_wicket_features")
ALL_FEATURES_PATH = Path("data/ipl_features_v10/training.parquet")

# v14 pitch features (carried forward unchanged)
V14_PP_EXTRAS = [
    "pp_score_vs_venue",
    "pp_wkts_vs_venue",
    "death_rr_vs_venue",
    "death_wkts_vs_venue",
]
V14_MID_EXTRAS = ["pp_wkts_vs_venue"]
V14_DEATH_EXTRAS = [
    "inn1_pp_wickets",
    "mid_avg_boundary18_vs_venue",
    "avg_boundary18_vs_venue",
]

# New v15 wicket-context features (added to all phases)
V15_WICKET_FEATURES = [
    "runs_per_wkt_rem",
    "wickets_x_high_chase",
    "wicket_resource_buffer",
    "high_chase_wickets_flag",
]
# PP additionally gets these (were only in DEATH in v12/v14)
V15_PP_EXTRA_WICKET = [
    "wr_x_rrr",
    "comfortable_wicket_zone",
]

PP_NEW_FEATURES   = V14_PP_EXTRAS    + V15_WICKET_FEATURES + V15_PP_EXTRA_WICKET
MID_NEW_FEATURES  = V14_MID_EXTRAS   + V15_WICKET_FEATURES
DEATH_NEW_FEATURES = V14_DEATH_EXTRAS + V15_WICKET_FEATURES


def pct_change(new_value: float, old_value: float) -> str:
    if old_value == 0:
        return "n/a"
    return f"{(new_value - old_value) / old_value * 100:+.2f}%"


def add_v14_pitch_features(df: pd.DataFrame) -> pd.DataFrame:
    """Re-use v14 pitch feature computation (venue-relative inn1 stats)."""
    import glob as glob_mod
    import os
    import json as json_mod

    def venue_short(venue: object) -> str:
        if not isinstance(venue, str) or not venue:
            return "Unknown"
        return venue.split(",")[0].strip()

    def build_venue_map() -> dict:
        venue_map: dict = {}
        for pattern in ["ipl_male_json\\*.json", "ipl_json_full\\*.json", "ipl_json\\*.json"]:
            for path in glob_mod.glob(pattern):
                try:
                    with open(path, encoding="utf-8") as f:
                        payload = json_mod.load(f)
                    match_id = os.path.splitext(os.path.basename(path))[0]
                    venue_map[match_id] = venue_short(payload.get("info", {}).get("venue"))
                except Exception:
                    continue
        return venue_map

    import numpy as np

    all_df = pd.read_parquet(ALL_FEATURES_PATH)
    all_df["season"] = all_df["season"].astype(str)
    inn1 = all_df[all_df["innings"] == 1].copy()
    inn1 = inn1.sort_values(["match_id", "over", "ball"])

    pp_end = (
        inn1[inn1["over"] == 5]
        .sort_values(["match_id", "over", "ball"])
        .groupby("match_id").last().reset_index()
    )
    pp_end["actual_inn1_pp_runs"] = pp_end["current_run_rate"] * 6.0
    pp_end["inn1_pp_wickets"] = pp_end["wickets_lost"]

    over14 = (
        inn1[inn1["over"] == 14].sort_values(["match_id", "over", "ball"])
        .groupby("match_id").last()[["wickets_lost", "current_run_rate"]]
        .rename(columns={"wickets_lost": "wkts_14", "current_run_rate": "crr_14"})
    )
    over19 = (
        inn1[inn1["over"] == 19].sort_values(["match_id", "over", "ball"])
        .groupby("match_id").last()[["wickets_lost", "current_run_rate", "season"]]
        .rename(columns={"wickets_lost": "wkts_19", "current_run_rate": "crr_19"})
    )
    death = over14.join(over19, how="inner")
    death["inn1_death_wickets"] = death["wkts_19"] - death["wkts_14"]
    death["actual_inn1_death_rr"] = (
        (death["crr_19"] * 20.0) - (death["crr_14"] * 15.0)
    ) / 5.0

    boundary = inn1.groupby("match_id").agg(avg_boundary18=("boundary_pct_last_18", "mean"))
    mid_boundary = inn1[inn1["over"].between(6, 14)].groupby("match_id").agg(
        mid_avg_boundary18=("boundary_pct_last_18", "mean")
    )

    summary = pp_end[["match_id", "actual_inn1_pp_runs", "inn1_pp_wickets"]].merge(
        death[["inn1_death_wickets", "actual_inn1_death_rr", "season"]].reset_index(),
        on="match_id", how="inner"
    )
    summary = summary.merge(boundary.reset_index(), on="match_id", how="left")
    summary = summary.merge(mid_boundary.reset_index(), on="match_id", how="left")
    venue_map = build_venue_map()
    summary["venue_key"] = summary["match_id"].astype(str).map(venue_map).fillna("Unknown")

    baseline = summary[summary["season"].astype(str) < "2025"].copy()
    if baseline.empty:
        baseline = summary.copy()

    venue_stats = baseline.groupby("venue_key").agg(
        venue_pp_avg=("actual_inn1_pp_runs", "mean"),
        venue_pp_wickets_avg=("inn1_pp_wickets", "mean"),
        venue_death_rr_avg=("actual_inn1_death_rr", "mean"),
        venue_death_wickets_avg=("inn1_death_wickets", "mean"),
        venue_avg_boundary18=("avg_boundary18", "mean"),
        venue_mid_avg_boundary18=("mid_avg_boundary18", "mean"),
    )
    fallback = {
        "venue_pp_avg": float(baseline["actual_inn1_pp_runs"].mean()),
        "venue_pp_wickets_avg": float(baseline["inn1_pp_wickets"].mean()),
        "venue_death_rr_avg": float(baseline["actual_inn1_death_rr"].mean()),
        "venue_death_wickets_avg": float(baseline["inn1_death_wickets"].mean()),
        "venue_avg_boundary18": float(baseline["avg_boundary18"].mean()),
        "venue_mid_avg_boundary18": float(baseline["mid_avg_boundary18"].mean()),
    }

    summary = summary.merge(venue_stats.reset_index(), on="venue_key", how="left")
    for col, value in fallback.items():
        summary[col] = summary[col].fillna(value)

    summary["pp_score_vs_venue"]    = summary["actual_inn1_pp_runs"] - summary["venue_pp_avg"]
    summary["pp_wkts_vs_venue"]     = summary["inn1_pp_wickets"]     - summary["venue_pp_wickets_avg"]
    summary["death_rr_vs_venue"]    = summary["actual_inn1_death_rr"]    - summary["venue_death_rr_avg"]
    summary["death_wkts_vs_venue"]  = summary["inn1_death_wickets"]  - summary["venue_death_wickets_avg"]
    summary["avg_boundary18_vs_venue"] = summary["avg_boundary18"] - summary["venue_avg_boundary18"]
    summary["mid_avg_boundary18_vs_venue"] = summary["mid_avg_boundary18"] - summary["venue_mid_avg_boundary18"]

    keep = [
        "match_id", "inn1_pp_wickets", "inn1_death_wickets",
        "pp_score_vs_venue", "pp_wkts_vs_venue",
        "death_rr_vs_venue", "death_wkts_vs_venue",
        "avg_boundary18_vs_venue", "mid_avg_boundary18_vs_venue",
    ]
    return df.merge(summary[keep], on="match_id", how="left")


def add_v15_wicket_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute new wicket-context features via inn2_engineering (works on inn2 slice)."""
    from bbl_pipeline.features.inn2_engineering import engineer_inn2_features
    engineered = engineer_inn2_features(df)
    # Copy only the new columns back (avoid duplicating existing columns)
    new_cols = [c for c in [
        "runs_per_wkt_rem", "wr_x_rrr", "comfortable_wicket_zone",
        "wickets_x_high_chase", "wicket_resource_buffer", "high_chase_wickets_flag",
    ] if c in engineered.columns and c not in df.columns]
    for col in new_cols:
        df[col] = engineered[col].values
    return df


def load_v14_features() -> dict[str, list[str]]:
    """Load v14 phase feature lists from its phase_features.json."""
    with open("models/ipl_v14_pitch_features/phase_features.json", encoding="utf-8") as f:
        return json.load(f)


def summarize_phase(eval_result: dict, phase: str) -> dict:
    phase_result = eval_result["phases"][phase]
    return {
        "n": int(phase_result["n"]),
        "brier_raw": float(phase_result["brier_raw"]),
        "brier_cal": float(phase_result["brier_cal"]),
    }


def save_venue_pitch_baselines(df: pd.DataFrame, out_dir: Path) -> None:
    """Save venue baselines needed by live inference (same format as v14)."""
    from pathlib import Path as P
    import shutil
    # v15 uses the same venue baselines as v14 (pitch features unchanged)
    src = P("models/ipl_v14_pitch_features/venue_pitch_baselines.json")
    dst = out_dir / "venue_pitch_baselines.json"
    shutil.copy2(src, dst)
    print(f"  Copied venue_pitch_baselines.json from v14")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading inn2 data, adding v14 pitch + v15 wicket features...")
    df = load_training_data()
    df = add_v14_pitch_features(df)
    df = add_v15_wicket_features(df)

    v14_feats = load_v14_features()
    v15_feats = {
        "pp":    ordered_unique(v14_feats["pp"]    + PP_NEW_FEATURES),
        "mid":   ordered_unique(v14_feats["mid"]   + MID_NEW_FEATURES),
        "death": ordered_unique(v14_feats["death"] + DEATH_NEW_FEATURES),
    }
    # Remove features that might not be in training data
    all_cols = set(df.columns)
    for phase in v15_feats:
        missing = [f for f in v15_feats[phase] if f not in all_cols]
        if missing:
            print(f"  WARNING: dropping missing {phase} features: {missing}")
            v15_feats[phase] = [f for f in v15_feats[phase] if f in all_cols]

    print(f"  Inn2 rows: {len(df):,}")
    print(
        "  Feature counts: "
        f"PP {len(v14_feats['pp'])}->{len(v15_feats['pp'])}, "
        f"MID {len(v14_feats['mid'])}->{len(v15_feats['mid'])}, "
        f"DEATH {len(v14_feats['death'])}->{len(v15_feats['death'])}"
    )

    print("\nStep 1: OOF season-fold CV for v15 calibrators...")
    phase_oof_cals = {}
    oof_rows = []
    for phase, over_range in PHASE_RANGES_V12.items():
        pf = phase_slice(df, over_range)
        oof = oof_phase_predictions(pf, v15_feats[phase])
        bundle = fit_calibrator_bundle(oof["raw"], oof["y"], oof["over"], CAL_METHODS_V12[phase])
        cal = apply_calibrator_bundle(oof["raw"], oof["over"], bundle)
        oof_brier_cal = float(brier_score_loss(oof["y"], cal))
        phase_oof_cals[phase] = bundle
        oof_rows.append({
            "phase": phase,
            "n_rows": len(pf),
            "n_features": len(v15_feats[phase]),
            "oof_brier_raw": round(oof["brier"], 5),
            "oof_brier_cal": round(oof_brier_cal, 5),
        })
        print(
            f"  {phase.upper():<5} rows={len(pf):>6,} feats={len(v15_feats[phase]):>2} "
            f"raw={oof['brier']:.5f} cal={oof_brier_cal:.5f}"
        )

    with open(OUT_DIR / "phase_oof_calibrators.pkl", "wb") as f:
        pickle.dump(phase_oof_cals, f)

    print("\nStep 2: Training v15 champion models on ALL data...")
    champion_models = train_champion_models(df, PHASE_RANGES_V12, v15_feats)
    for phase, (model, feats) in champion_models.items():
        joblib.dump(model, OUT_DIR / f"champion_model_{phase}.joblib")
        print(f"  Saved champion_model_{phase}.joblib ({len(feats)} features)")

    with open(OUT_DIR / "phase_features.json", "w", encoding="utf-8") as f:
        json.dump({phase: feats for phase, (_, feats) in champion_models.items()}, f, indent=2)
    save_venue_pitch_baselines(df, OUT_DIR)

    routing_config = {
        "type": "inn2_phase_router",
        "description": (
            "ipl_v15_wicket_features: v14 + wicket×chase interaction features "
            "(runs_per_wkt_rem, wickets_x_high_chase, wicket_resource_buffer, "
            "high_chase_wickets_flag) added to all phases."
        ),
        "inn1_model_dir": "models/ipl_v7",
        "inn2_phase_model_dir": str(OUT_DIR).replace("\\", "/"),
        "apply_calibration": False,
        "post_model_calibration": {
            "enabled": True,
            "artifact": "post_model_calibration_router.pkl",
            "description": "Copy post-model calibration router from v14.",
        },
        "pp_low_fallback_model_dir": "models/ipl_v12",
        "pp_low_fallback_rule": "phase == pp and target_above_par < -20 uses models/ipl_v12 champion_model_pp raw probability",
        "inn2_changes_vs_v14": {
            "pp":    PP_NEW_FEATURES,
            "mid":   MID_NEW_FEATURES,
            "death": DEATH_NEW_FEATURES,
        },
        "routing_brier_oof": None,
    }
    with open(OUT_DIR / "routing_config.json", "w", encoding="utf-8") as f:
        json.dump(routing_config, f, indent=2)

    # Copy post-model calibration router from v14 (unchanged)
    import shutil
    shutil.copy2(
        "models/ipl_v14_pitch_features/post_model_calibration_router.pkl",
        OUT_DIR / "post_model_calibration_router.pkl",
    )
    print("  Copied post_model_calibration_router.pkl from v14")

    print("\nStep 3: True OOS evaluation (train<2025, test=2025+2026)...")
    print("  Building v14 baseline...")
    v14_oos = evaluate_oos(df, PHASE_RANGES_V12, v14_feats, CAL_METHODS_V12)
    print("  Building v15 candidate...")
    v15_oos = evaluate_oos(df, PHASE_RANGES_V12, v15_feats, CAL_METHODS_V12)

    rows = []
    print("\n" + "=" * 96)
    print("IPL v15 Wicket Features - OOS COMPARISON  (train: pre-2025, test: 2025+2026)")
    print("=" * 96)
    print(f"Train seasons: {v15_oos['train_seasons']}")
    print(f"Test seasons : {v15_oos['test_seasons']}")
    print(f"\n{'Phase':<10} {'v14 cal':>10} {'v15 cal':>10} {'Change':>10} {'v14 raw':>10} {'v15 raw':>10} {'n':>8}")
    print("-" * 78)
    for phase in ["pp", "mid", "death"]:
        base = summarize_phase(v14_oos, phase)
        new  = summarize_phase(v15_oos, phase)
        rows.append({
            "phase": phase,
            "v14_oos_brier_raw": round(base["brier_raw"], 5),
            "v14_oos_brier_cal": round(base["brier_cal"], 5),
            "v15_oos_brier_raw": round(new["brier_raw"], 5),
            "v15_oos_brier_cal": round(new["brier_cal"], 5),
            "delta_pct": pct_change(new["brier_cal"], base["brier_cal"]),
            "n": new["n"],
        })
        print(
            f"{phase.upper():<10} {base['brier_cal']:>10.5f} {new['brier_cal']:>10.5f} "
            f"{pct_change(new['brier_cal'], base['brier_cal']):>10} "
            f"{base['brier_raw']:>10.5f} {new['brier_raw']:>10.5f} {new['n']:>8,}"
        )

    overall_row = {
        "phase": "overall",
        "v14_oos_brier_raw": round(v14_oos["overall_raw"], 5),
        "v14_oos_brier_cal": round(v14_oos["overall_cal"], 5),
        "v15_oos_brier_raw": round(v15_oos["overall_raw"], 5),
        "v15_oos_brier_cal": round(v15_oos["overall_cal"], 5),
        "delta_pct": pct_change(v15_oos["overall_cal"], v14_oos["overall_cal"]),
        "n": sum(r["n"] for r in rows),
    }
    rows.append(overall_row)
    print("-" * 78)
    print(
        f"{'OVERALL':<10} {v14_oos['overall_cal']:>10.5f} {v15_oos['overall_cal']:>10.5f} "
        f"{pct_change(v15_oos['overall_cal'], v14_oos['overall_cal']):>10} "
        f"{v14_oos['overall_raw']:>10.5f} {v15_oos['overall_raw']:>10.5f} {overall_row['n']:>8,}"
    )

    pd.DataFrame(rows).to_csv(OUT_DIR / "oos_comparison.csv", index=False)
    pd.DataFrame(oof_rows).to_csv(OUT_DIR / "oof_results.csv", index=False)

    promote = v15_oos["overall_cal"] < v14_oos["overall_cal"]
    verdict = "PROMOTE v15 candidate" if promote else "KEEP v14"
    print(f"\nVerdict: {verdict}")
    print(f"  Saved: {OUT_DIR / 'oos_comparison.csv'}")
    print(f"  Saved: {OUT_DIR / 'oof_results.csv'}")
    print(f"  Saved: {OUT_DIR / 'routing_config.json'}")
    print(f"  Saved: {OUT_DIR / 'phase_features.json'}")


if __name__ == "__main__":
    main()
