"""
IPL v13 Champion Build Script
=============================
Changes vs v12:
  1. MID split into Early-MID (7-11) and Late-MID (12-15)
  2. PP / Death stay unchanged from v12
  3. Early-MID and Late-MID each get their own feature selection + Platt calibrators

Strategy:
  - Train champion models on ALL data
  - OOF calibrators from 5-fold season CV
  - True OOS eval: train<2025, test=2025+2026
  - Compare v12 shared MID baseline vs v13 split MID

Output: models/ipl_v13/
  champion_model_pp.joblib
  champion_model_early_mid.joblib
  champion_model_late_mid.joblib
  champion_model_death.joblib
  phase_oof_calibrators.pkl
  phase_features.json
  oof_results.csv
  OOS_COMPARISON.md
  routing_config.json
"""
import warnings; warnings.filterwarnings("ignore")
import sys
from pathlib import Path

sys.path.insert(0, "src")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import json
import pickle

import joblib
import pandas as pd

from ipl_v13_mid_split_common import (
    CAL_METHODS_V12,
    CAL_METHODS_V13,
    PHASE_RANGES_V12,
    PHASE_RANGES_V13,
    V13_DIR,
    apply_calibrator_bundle,
    build_mid_split_analysis,
    evaluate_oos,
    fit_calibrator_bundle,
    load_training_data,
    load_v12_features,
    oof_phase_predictions,
    ordered_unique,
    phase_slice,
    summarize_segment,
    train_champion_models,
    weighted_mid_summary,
)


def pct_change(new_value: float, old_value: float) -> str:
    if old_value == 0:
        return "n/a"
    return f"{(new_value - old_value) / old_value * 100:+.2f}%"


def phase_label(phase: str) -> str:
    return {
        "pp": "PP",
        "early_mid": "Early-MID",
        "late_mid": "Late-MID",
        "mid_combined": "Combined MID",
        "death": "Death",
        "overall": "Overall",
    }[phase]


def main():
    out_dir = Path("models/ipl_v13")
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading data...")
    df = load_training_data()
    v12_feats = load_v12_features()
    analysis = build_mid_split_analysis(df, v12_feats["mid"])

    early_remove_candidates = analysis["recommended_removals"]["early_mid"]
    late_remove_candidates = analysis["recommended_removals"]["late_mid"]
    early_remove: list[str] = []
    late_remove: list[str] = []
    early_add = analysis["recommended_additions"]["early_mid"]
    late_add = analysis["recommended_additions"]["late_mid"][:3]

    v13_feats = {
        "pp": list(v12_feats["pp"]),
        "early_mid": ordered_unique([f for f in v12_feats["mid"] if f not in early_remove] + early_add),
        "late_mid": ordered_unique([f for f in v12_feats["mid"] if f not in late_remove] + late_add),
        "death": list(v12_feats["death"]),
    }

    print(f"  Inn2 rows: {len(df):,}")
    print(f"  EDA EARLY remove candidates ({len(early_remove_candidates)}): {early_remove_candidates}")
    print(f"  EDA LATE  remove candidates ({len(late_remove_candidates)}): {late_remove_candidates}")
    print(f"  FINAL EARLY remove ({len(early_remove)}): {early_remove}")
    print(f"  FINAL LATE  remove ({len(late_remove)}): {late_remove}")
    print(f"  EARLY MID add ({len(early_add)}): {early_add}")
    print(f"  LATE MID  add ({len(late_add)}): {late_add}")
    print(f"  Feature counts -> PP={len(v13_feats['pp'])}, Early-MID={len(v13_feats['early_mid'])}, Late-MID={len(v13_feats['late_mid'])}, Death={len(v13_feats['death'])}")

    print("\nStep 1: OOF season-fold CV for calibrators...")
    phase_oof_cals = {}
    oof_rows = []
    for phase, over_range in PHASE_RANGES_V13.items():
        pf = phase_slice(df, over_range)
        feats = v13_feats[phase]
        oof = oof_phase_predictions(pf, feats)
        bundle = fit_calibrator_bundle(oof["raw"], oof["y"], oof["over"], CAL_METHODS_V13[phase])
        cal = apply_calibrator_bundle(oof["raw"], oof["over"], bundle)
        oof_brier_cal = float(pd.Series((oof["y"] - cal) ** 2).mean())
        phase_oof_cals[phase] = bundle
        oof_rows.append(
            {
                "phase": phase,
                "n_rows": len(pf),
                "n_features": len(v13_feats[phase]),
                "oof_brier_raw": round(oof["brier"], 5),
                "oof_brier_cal": round(oof_brier_cal, 5),
            }
        )
        print(
            f"  {phase.upper():<10} rows={len(pf):>6,} feats={len(v13_feats[phase]):>2} "
            f"raw={oof['brier']:.5f} cal={oof_brier_cal:.5f}"
        )

    with open(out_dir / "phase_oof_calibrators.pkl", "wb") as f:
        pickle.dump(phase_oof_cals, f)
    print(f"  Saved: {out_dir / 'phase_oof_calibrators.pkl'}")

    print("\nStep 2: Training champion models on ALL data...")
    champion_models = train_champion_models(df, PHASE_RANGES_V13, v13_feats)
    for phase, (model, feats) in champion_models.items():
        joblib.dump(model, out_dir / f"champion_model_{phase}.joblib")
        print(f"  {phase.upper():<10} rows={len(phase_slice(df, PHASE_RANGES_V13[phase])):>6,} feats={len(feats):>2} -> champion_model_{phase}.joblib")

    with open(out_dir / "phase_features.json", "w", encoding="utf-8") as f:
        json.dump({phase: feats for phase, (_, feats) in champion_models.items()}, f, indent=2)
    print(f"  Saved: {out_dir / 'phase_features.json'}")

    routing_config = {
        "version": "v13",
        "inn2_phase_model_dir": "models/ipl_v13",
        "phases": {
            "pp": {"over_range": [1, 6]},
            "early_mid": {"over_range": [7, 11]},
            "late_mid": {"over_range": [12, 15]},
            "death": {"over_range": [16, 20]},
        },
        "notes": "v13: MID split into early_mid(7-11) and late_mid(12-15). PP/Death unchanged from v12.",
    }
    with open(out_dir / "routing_config.json", "w", encoding="utf-8") as f:
        json.dump(routing_config, f, indent=2)
    print(f"  Saved: {out_dir / 'routing_config.json'}")

    print("\nStep 3: True OOS evaluation (train<2025, test=2025+2026)...")
    print("  Building v12 baseline...")
    v12_oos = evaluate_oos(
        df,
        PHASE_RANGES_V12,
        {"pp": v12_feats["pp"], "mid": v12_feats["mid"], "death": v12_feats["death"]},
        CAL_METHODS_V12,
    )
    print("  Building v13 split model...")
    v13_oos = evaluate_oos(df, PHASE_RANGES_V13, v13_feats, CAL_METHODS_V13)

    v12_segments = {
        "pp": summarize_segment(v12_oos, "pp"),
        "early_mid": summarize_segment(v12_oos, "mid", (7, 11)),
        "late_mid": summarize_segment(v12_oos, "mid", (12, 15)),
        "mid_combined": summarize_segment(v12_oos, "mid"),
        "death": summarize_segment(v12_oos, "death"),
        "overall": {"n": 0, "brier_raw": v12_oos["overall_raw"], "brier_cal": v12_oos["overall_cal"]},
    }
    v13_segments = {
        "pp": summarize_segment(v13_oos, "pp"),
        "early_mid": summarize_segment(v13_oos, "early_mid"),
        "late_mid": summarize_segment(v13_oos, "late_mid"),
        "mid_combined": weighted_mid_summary([
            summarize_segment(v13_oos, "early_mid"),
            summarize_segment(v13_oos, "late_mid"),
        ]),
        "death": summarize_segment(v13_oos, "death"),
        "overall": {"n": 0, "brier_raw": v13_oos["overall_raw"], "brier_cal": v13_oos["overall_cal"]},
    }

    print("\n" + "=" * 100)
    print("IPL v13 BUILD — OOS COMPARISON  (train: pre-2025, test: 2025+2026)")
    print("=" * 100)
    print(f"Train seasons: {v13_oos['train_seasons']}")
    print(f"Test seasons : {v13_oos['test_seasons']}")
    print(f"\n{'Segment':<14} {'Baseline v12':>12} {'v13 split':>12} {'Delta':>10} {'v12 raw':>12} {'v13 raw':>12} {'n':>8}")
    print("-" * 86)
    for key in ["pp", "early_mid", "late_mid", "mid_combined", "death", "overall"]:
        base = v12_segments[key]
        new = v13_segments[key]
        n_value = new["n"] if new["n"] else v12_segments.get(key, {}).get("n", 0)
        print(
            f"{phase_label(key):<14} {base['brier_cal']:>12.5f} {new['brier_cal']:>12.5f} "
            f"{pct_change(new['brier_cal'], base['brier_cal']):>10} {base['brier_raw']:>12.5f} {new['brier_raw']:>12.5f} {n_value:>8,}"
        )

    mid_win = v13_segments["mid_combined"]["brier_cal"] < v12_segments["mid_combined"]["brier_cal"]
    print(
        f"\nCombined MID verdict: {'✅ improved' if mid_win else '❌ regressed'} "
        f"({pct_change(v13_segments['mid_combined']['brier_cal'], v12_segments['mid_combined']['brier_cal'])})"
    )

    for row in oof_rows:
        phase = row["phase"]
        compare_key = phase
        row["v12_oos_brier_cal"] = round(v12_segments[compare_key]["brier_cal"], 5) if compare_key in v12_segments else float("nan")
        row["v13_oos_brier_cal"] = round(v13_segments[compare_key]["brier_cal"], 5) if compare_key in v13_segments else float("nan")
        row["delta_vs_v12_pct"] = pct_change(v13_segments[compare_key]["brier_cal"], v12_segments[compare_key]["brier_cal"]) if compare_key in v12_segments else "n/a"

    oof_rows.extend([
        {
            "phase": "mid_combined",
            "n_rows": v13_segments["mid_combined"]["n"],
            "n_features": len(v13_feats["early_mid"]) + len(v13_feats["late_mid"]),
            "oof_brier_raw": None,
            "oof_brier_cal": None,
            "v12_oos_brier_cal": round(v12_segments["mid_combined"]["brier_cal"], 5),
            "v13_oos_brier_cal": round(v13_segments["mid_combined"]["brier_cal"], 5),
            "delta_vs_v12_pct": pct_change(v13_segments["mid_combined"]["brier_cal"], v12_segments["mid_combined"]["brier_cal"]),
        },
        {
            "phase": "overall",
            "n_rows": len(df[(df["over"] >= 1) & (df["over"] <= 20)]),
            "n_features": None,
            "oof_brier_raw": None,
            "oof_brier_cal": None,
            "v12_oos_brier_cal": round(v12_oos["overall_cal"], 5),
            "v13_oos_brier_cal": round(v13_oos["overall_cal"], 5),
            "delta_vs_v12_pct": pct_change(v13_oos["overall_cal"], v12_oos["overall_cal"]),
        },
    ])
    pd.DataFrame(oof_rows).to_csv(out_dir / "oof_results.csv", index=False)
    print(f"\n  Saved: {out_dir / 'oof_results.csv'}")

    md_lines = [
        "# IPL v13 — OOS Comparison Report\n\n",
        f"**Train seasons:** {v13_oos['train_seasons']}\n",
        f"**Test seasons:** {v13_oos['test_seasons']}\n\n",
        "## v13 feature updates\n",
        f"- **EDA early removal candidates ({len(early_remove_candidates)}):** {', '.join(early_remove_candidates) if early_remove_candidates else 'None'}\n",
        f"- **EDA late removal candidates ({len(late_remove_candidates)}):** {', '.join(late_remove_candidates) if late_remove_candidates else 'None'}\n",
        f"- **Final Early-MID removals ({len(early_remove)}):** {', '.join(early_remove) if early_remove else 'None (OOS screening kept the baseline MID core)'}\n",
        f"- **Early-MID additions ({len(early_add)}):** {', '.join(early_add) if early_add else 'None'}\n",
        f"- **Final Late-MID removals ({len(late_remove)}):** {', '.join(late_remove) if late_remove else 'None (OOS screening kept the baseline MID core)'}\n",
        f"- **Late-MID additions ({len(late_add)}):** {', '.join(late_add) if late_add else 'None'}\n\n",
        "## OOS segment comparison\n\n",
        "| Segment | v12 baseline | v13 split | Delta | v12 raw | v13 raw | n |\n",
        "|---------|-------------:|----------:|------:|--------:|--------:|--:|\n",
    ]
    for key in ["pp", "early_mid", "late_mid", "mid_combined", "death", "overall"]:
        base = v12_segments[key]
        new = v13_segments[key]
        n_value = new["n"] if new["n"] else v12_segments.get(key, {}).get("n", 0)
        md_lines.append(
            f"| {phase_label(key)} | {base['brier_cal']:.5f} | {new['brier_cal']:.5f} | {pct_change(new['brier_cal'], base['brier_cal'])} | {base['brier_raw']:.5f} | {new['brier_raw']:.5f} | {n_value:,} |\n"
        )
    md_lines.append(
        f"\n**Combined MID verdict:** {'Improved' if mid_win else 'Regressed'} ({pct_change(v13_segments['mid_combined']['brier_cal'], v12_segments['mid_combined']['brier_cal'])})\n"
    )
    (out_dir / "OOS_COMPARISON.md").write_text("".join(md_lines), encoding="utf-8")
    print(f"  Saved: {out_dir / 'OOS_COMPARISON.md'}")

    print(f"\nArtifacts ready in: {out_dir}")
    print("DONE.")


if __name__ == "__main__":
    main()
