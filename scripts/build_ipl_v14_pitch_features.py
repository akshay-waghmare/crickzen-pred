"""
IPL v14 Pitch-Feature Production Build
======================================

Changes vs v12:
  1. PP: add venue-relative inn1 PP/death context.
  2. MID: add pp_wkts_vs_venue.
  3. DEATH: add inn1_pp_wickets plus selective v15 death-pitch boundary features.

This script does not modify v12. It trains a separate candidate under
models/ipl_v14_pitch_features and compares it with v12 on the standard
train<2025, test=2025+2026 OOS split.
"""
from __future__ import annotations

import json
import os
import pickle
import sys
from pathlib import Path

import joblib
import numpy as np
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
    load_v12_features,
    oof_phase_predictions,
    ordered_unique,
    phase_slice,
    train_champion_models,
)


OUT_DIR = Path("models/ipl_v14_pitch_features")
ALL_FEATURES_PATH = Path("data/ipl_features_v10/training.parquet")

PP_PITCH_FEATURES = [
    "pp_score_vs_venue",
    "pp_wkts_vs_venue",
    "death_rr_vs_venue",
    "death_wkts_vs_venue",
]
MID_PITCH_FEATURES = ["pp_wkts_vs_venue"]
DEATH_PITCH_FEATURES = [
    "inn1_pp_wickets",
    "mid_avg_boundary18_vs_venue",
    "avg_boundary18_vs_venue",
]


def pct_change(new_value: float, old_value: float) -> str:
    if old_value == 0:
        return "n/a"
    return f"{(new_value - old_value) / old_value * 100:+.2f}%"


def venue_short(venue: object) -> str:
    if not isinstance(venue, str) or not venue:
        return "Unknown"
    return venue.split(",")[0].strip()


def build_venue_map() -> dict[str, str]:
    import glob

    venue_map: dict[str, str] = {}
    json_files = (
        glob.glob("ipl_male_json\\*.json")
        + glob.glob("ipl_json_full\\*.json")
        + glob.glob("ipl_json\\*.json")
    )
    for path in json_files:
        try:
            with open(path, encoding="utf-8") as f:
                payload = json.load(f)
            match_id = os.path.splitext(os.path.basename(path))[0]
            venue_map[match_id] = venue_short(payload.get("info", {}).get("venue"))
        except Exception:
            continue
    return venue_map


def build_inn1_pitch_summary() -> pd.DataFrame:
    all_df = pd.read_parquet(ALL_FEATURES_PATH)
    all_df["season"] = all_df["season"].astype(str)
    inn1 = all_df[all_df["innings"] == 1].copy()

    inn1 = inn1.sort_values(["match_id", "over", "ball"])

    pp_end = (
        inn1[inn1["over"] == 5]
        .sort_values(["match_id", "over", "ball"])
        .groupby("match_id")
        .last()
        .reset_index()
    )
    pp_end["actual_inn1_pp_runs"] = pp_end["current_run_rate"] * 6.0
    pp_end["inn1_pp_wickets"] = pp_end["wickets_lost"]

    over14 = (
        inn1[inn1["over"] == 14]
        .sort_values(["match_id", "over", "ball"])
        .groupby("match_id")
        .last()[["wickets_lost", "current_run_rate"]]
        .rename(columns={"wickets_lost": "wkts_14", "current_run_rate": "crr_14"})
    )
    over19 = (
        inn1[inn1["over"] == 19]
        .sort_values(["match_id", "over", "ball"])
        .groupby("match_id")
        .last()[["wickets_lost", "current_run_rate", "season"]]
        .rename(columns={"wickets_lost": "wkts_19", "current_run_rate": "crr_19"})
    )
    death = over14.join(over19, how="inner")
    death["inn1_death_wickets"] = death["wkts_19"] - death["wkts_14"]
    death["actual_inn1_death_rr"] = (
        (death["crr_19"] * 20.0) - (death["crr_14"] * 15.0)
    ) / 5.0

    boundary = inn1.groupby("match_id").agg(
        avg_boundary18=("boundary_pct_last_18", "mean"),
    )
    mid_boundary = inn1[inn1["over"].between(6, 14)].groupby("match_id").agg(
        mid_avg_boundary18=("boundary_pct_last_18", "mean"),
    )

    summary = pp_end[
        ["match_id", "actual_inn1_pp_runs", "inn1_pp_wickets"]
    ].merge(
        death[["inn1_death_wickets", "actual_inn1_death_rr", "season"]].reset_index(),
        on="match_id",
        how="inner",
    )
    summary = summary.merge(boundary.reset_index(), on="match_id", how="left")
    summary = summary.merge(mid_boundary.reset_index(), on="match_id", how="left")
    venue_map = build_venue_map()
    summary["venue_key"] = summary["match_id"].astype(str).map(venue_map).fillna("Unknown")
    return summary


def add_pitch_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add the v14 candidate pitch features.

    Venue baselines are estimated from the OOS training era only (<2025) to keep
    the comparison conservative and avoid leaking 2025/2026 venue conditions
    into the test split.
    """
    pitch = build_inn1_pitch_summary()
    baseline = pitch[pitch["season"].astype(str) < "2025"].copy()
    if baseline.empty:
        baseline = pitch.copy()

    venue_stats = baseline.groupby("venue_key").agg(
        venue_pp_avg=("actual_inn1_pp_runs", "mean"),
        venue_pp_wickets_avg=("inn1_pp_wickets", "mean"),
        venue_death_rr_avg=("actual_inn1_death_rr", "mean"),
        venue_death_wickets_avg=("inn1_death_wickets", "mean"),
        venue_avg_boundary18=("avg_boundary18", "mean"),
        venue_mid_avg_boundary18=("mid_avg_boundary18", "mean"),
    )
    fallback = {
        "venue_pp_avg": baseline["actual_inn1_pp_runs"].mean(),
        "venue_pp_wickets_avg": baseline["inn1_pp_wickets"].mean(),
        "venue_death_rr_avg": baseline["actual_inn1_death_rr"].mean(),
        "venue_death_wickets_avg": baseline["inn1_death_wickets"].mean(),
        "venue_avg_boundary18": baseline["avg_boundary18"].mean(),
        "venue_mid_avg_boundary18": baseline["mid_avg_boundary18"].mean(),
    }

    pitch = pitch.merge(venue_stats.reset_index(), on="venue_key", how="left")
    for col, value in fallback.items():
        pitch[col] = pitch[col].fillna(value)

    pitch["pp_score_vs_venue"] = pitch["actual_inn1_pp_runs"] - pitch["venue_pp_avg"]
    pitch["pp_wkts_vs_venue"] = pitch["inn1_pp_wickets"] - pitch["venue_pp_wickets_avg"]
    pitch["death_rr_vs_venue"] = pitch["actual_inn1_death_rr"] - pitch["venue_death_rr_avg"]
    pitch["death_wkts_vs_venue"] = (
        pitch["inn1_death_wickets"] - pitch["venue_death_wickets_avg"]
    )
    pitch["avg_boundary18_vs_venue"] = pitch["avg_boundary18"] - pitch["venue_avg_boundary18"]
    pitch["mid_avg_boundary18_vs_venue"] = (
        pitch["mid_avg_boundary18"] - pitch["venue_mid_avg_boundary18"]
    )

    keep = [
        "match_id",
        "inn1_pp_wickets",
        "inn1_death_wickets",
        "pp_score_vs_venue",
        "pp_wkts_vs_venue",
        "death_rr_vs_venue",
        "death_wkts_vs_venue",
        "avg_boundary18_vs_venue",
        "mid_avg_boundary18_vs_venue",
    ]
    return df.merge(pitch[keep], on="match_id", how="left")


def save_venue_pitch_baselines(out_dir: Path) -> None:
    """Save venue baselines needed by live inference for v14 relative features."""
    pitch = build_inn1_pitch_summary()
    baseline = pitch[pitch["season"].astype(str) < "2025"].copy()
    if baseline.empty:
        baseline = pitch.copy()

    venue_stats = baseline.groupby("venue_key").agg(
        venue_pp_avg=("actual_inn1_pp_runs", "mean"),
        venue_pp_wickets_avg=("inn1_pp_wickets", "mean"),
        venue_death_rr_avg=("actual_inn1_death_rr", "mean"),
        venue_death_wickets_avg=("inn1_death_wickets", "mean"),
        venue_avg_boundary18=("avg_boundary18", "mean"),
        venue_mid_avg_boundary18=("mid_avg_boundary18", "mean"),
    )
    global_stats = {
        "venue_pp_avg": float(baseline["actual_inn1_pp_runs"].mean()),
        "venue_pp_wickets_avg": float(baseline["inn1_pp_wickets"].mean()),
        "venue_death_rr_avg": float(baseline["actual_inn1_death_rr"].mean()),
        "venue_death_wickets_avg": float(baseline["inn1_death_wickets"].mean()),
        "venue_avg_boundary18": float(baseline["avg_boundary18"].mean()),
        "venue_mid_avg_boundary18": float(baseline["mid_avg_boundary18"].mean()),
    }
    payload = {
        "description": "IPL v14 venue baselines for live first-innings pitch-relative features; fitted on seasons <2025.",
        "global": global_stats,
        "venues": {
            venue: {k: float(v) for k, v in row.items()}
            for venue, row in venue_stats.to_dict(orient="index").items()
        },
    }
    with open(out_dir / "venue_pitch_baselines.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def summarize_phase(eval_result: dict, phase: str) -> dict[str, float]:
    phase_result = eval_result["phases"][phase]
    return {
        "n": int(phase_result["n"]),
        "brier_raw": float(phase_result["brier_raw"]),
        "brier_cal": float(phase_result["brier_cal"]),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading v12 inn2 data and adding pitch features...")
    df = load_training_data()
    df = add_pitch_features(df)
    v12_feats = load_v12_features()
    v14_feats = {
        "pp": ordered_unique(v12_feats["pp"] + PP_PITCH_FEATURES),
        "mid": ordered_unique(v12_feats["mid"] + MID_PITCH_FEATURES),
        "death": ordered_unique(v12_feats["death"] + DEATH_PITCH_FEATURES),
    }

    print(f"  Inn2 rows: {len(df):,}")
    print(
        "  Feature counts: "
        f"PP {len(v12_feats['pp'])}->{len(v14_feats['pp'])}, "
        f"MID {len(v12_feats['mid'])}->{len(v14_feats['mid'])}, "
        f"DEATH {len(v12_feats['death'])}->{len(v14_feats['death'])}"
    )

    print("\nStep 1: OOF season-fold CV for v14 calibrators...")
    phase_oof_cals = {}
    oof_rows = []
    for phase, over_range in PHASE_RANGES_V12.items():
        pf = phase_slice(df, over_range)
        oof = oof_phase_predictions(pf, v14_feats[phase])
        bundle = fit_calibrator_bundle(oof["raw"], oof["y"], oof["over"], CAL_METHODS_V12[phase])
        cal = apply_calibrator_bundle(oof["raw"], oof["over"], bundle)
        oof_brier_cal = float(brier_score_loss(oof["y"], cal))
        phase_oof_cals[phase] = bundle
        oof_rows.append(
            {
                "phase": phase,
                "n_rows": len(pf),
                "n_features": len(v14_feats[phase]),
                "oof_brier_raw": round(oof["brier"], 5),
                "oof_brier_cal": round(oof_brier_cal, 5),
            }
        )
        print(
            f"  {phase.upper():<5} rows={len(pf):>6,} feats={len(v14_feats[phase]):>2} "
            f"raw={oof['brier']:.5f} cal={oof_brier_cal:.5f}"
        )

    with open(OUT_DIR / "phase_oof_calibrators.pkl", "wb") as f:
        pickle.dump(phase_oof_cals, f)
    print(f"  Saved: {OUT_DIR / 'phase_oof_calibrators.pkl'}")

    print("\nStep 2: Training v14 champion models on ALL data...")
    champion_models = train_champion_models(df, PHASE_RANGES_V12, v14_feats)
    for phase, (model, feats) in champion_models.items():
        joblib.dump(model, OUT_DIR / f"champion_model_{phase}.joblib")
        print(f"  Saved champion_model_{phase}.joblib ({len(feats)} features)")

    with open(OUT_DIR / "phase_features.json", "w", encoding="utf-8") as f:
        json.dump({phase: feats for phase, (_, feats) in champion_models.items()}, f, indent=2)
    print(f"  Saved: {OUT_DIR / 'phase_features.json'}")
    save_venue_pitch_baselines(OUT_DIR)
    print(f"  Saved: {OUT_DIR / 'venue_pitch_baselines.json'}")

    routing_config = {
        "type": "inn2_phase_router",
        "description": "ipl_v14_pitch_features production router: v12 + phase-specific first-innings pitch/venue-relative features.",
        "inn1_model_dir": "models/ipl_v7",
        "inn2_phase_model_dir": str(OUT_DIR).replace("\\", "/"),
        "apply_calibration": False,
        "post_model_calibration": {
            "enabled": True,
            "artifact": "post_model_calibration_router.pkl",
            "description": (
                "Guardrailed IPL post-model calibration router. Inn1 corrects p<0.50 "
                "downward; Inn2 sharpens easy-chase 50-85 and par PP/Mid 50-80. "
                "Fit on 2025 OOS, validated on 2026 holdout against raw v14."
            ),
        },
        "pp_low_fallback_model_dir": "models/ipl_v12",
        "pp_low_fallback_rule": "phase == pp and target_above_par < -20 uses models/ipl_v12 champion_model_pp raw probability",
        "inn2_changes_vs_v12": {
            "pp": PP_PITCH_FEATURES,
            "mid": MID_PITCH_FEATURES,
            "death": DEATH_PITCH_FEATURES,
        },
        "routing_brier_oof": None,
    }
    with open(OUT_DIR / "routing_config.json", "w", encoding="utf-8") as f:
        json.dump(routing_config, f, indent=2)
    print(f"  Saved: {OUT_DIR / 'routing_config.json'}")

    print("\nStep 3: True OOS evaluation (train<2025, test=2025+2026)...")
    print("  Building v12 baseline...")
    v12_oos = evaluate_oos(df, PHASE_RANGES_V12, v12_feats, CAL_METHODS_V12)
    print("  Building v14 pitch candidate...")
    v14_oos = evaluate_oos(df, PHASE_RANGES_V12, v14_feats, CAL_METHODS_V12)

    rows = []
    print("\n" + "=" * 96)
    print("IPL v14 Pitch Features - OOS COMPARISON  (train: pre-2025, test: 2025+2026)")
    print("=" * 96)
    print(f"Train seasons: {v14_oos['train_seasons']}")
    print(f"Test seasons : {v14_oos['test_seasons']}")
    print(f"\n{'Phase':<10} {'v12 cal':>10} {'v14 cal':>10} {'Change':>10} {'v12 raw':>10} {'v14 raw':>10} {'n':>8}")
    print("-" * 78)
    for phase in ["pp", "mid", "death"]:
        base = summarize_phase(v12_oos, phase)
        new = summarize_phase(v14_oos, phase)
        rows.append(
            {
                "phase": phase,
                "v12_oos_brier_raw": round(base["brier_raw"], 5),
                "v12_oos_brier_cal": round(base["brier_cal"], 5),
                "v14_oos_brier_raw": round(new["brier_raw"], 5),
                "v14_oos_brier_cal": round(new["brier_cal"], 5),
                "delta_pct": pct_change(new["brier_cal"], base["brier_cal"]),
                "n": new["n"],
            }
        )
        print(
            f"{phase.upper():<10} {base['brier_cal']:>10.5f} {new['brier_cal']:>10.5f} "
            f"{pct_change(new['brier_cal'], base['brier_cal']):>10} "
            f"{base['brier_raw']:>10.5f} {new['brier_raw']:>10.5f} {new['n']:>8,}"
        )

    overall_row = {
        "phase": "overall",
        "v12_oos_brier_raw": round(v12_oos["overall_raw"], 5),
        "v12_oos_brier_cal": round(v12_oos["overall_cal"], 5),
        "v14_oos_brier_raw": round(v14_oos["overall_raw"], 5),
        "v14_oos_brier_cal": round(v14_oos["overall_cal"], 5),
        "delta_pct": pct_change(v14_oos["overall_cal"], v12_oos["overall_cal"]),
        "n": sum(r["n"] for r in rows),
    }
    rows.append(overall_row)
    print("-" * 78)
    print(
        f"{'OVERALL':<10} {v12_oos['overall_cal']:>10.5f} {v14_oos['overall_cal']:>10.5f} "
        f"{pct_change(v14_oos['overall_cal'], v12_oos['overall_cal']):>10} "
        f"{v12_oos['overall_raw']:>10.5f} {v14_oos['overall_raw']:>10.5f} {overall_row['n']:>8,}"
    )

    pd.DataFrame(rows).to_csv(OUT_DIR / "oos_comparison.csv", index=False)
    pd.DataFrame(oof_rows).to_csv(OUT_DIR / "oof_results.csv", index=False)

    promote = v14_oos["overall_cal"] < v12_oos["overall_cal"]
    verdict = "PROMOTE v14 candidate" if promote else "KEEP v12"
    print(f"\nVerdict: {verdict}")
    print(f"  Saved: {OUT_DIR / 'oos_comparison.csv'}")
    print(f"  Saved: {OUT_DIR / 'oof_results.csv'}")


if __name__ == "__main__":
    main()
