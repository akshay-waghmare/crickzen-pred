"""Chronological promotion gate for generalized innings-2 phase candidates.

Trains both the complete-base and phase candidate on seasons before 2025,
then compares raw OOS Brier by phase and gender. This deliberately avoids
using the all-data champion artifact for promotion decisions.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import brier_score_loss

sys.path.insert(0, "src")
from bbl_pipeline.training.blend_model import XGBLRBlend

from build_league_phase_features import load_training_data, safe_X


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--phase-dir", required=True)
    ap.add_argument("--features", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    phase_dir = Path(args.phase_dir)
    with open(phase_dir / "routing_config.json", encoding="utf-8") as f:
        cfg = json.load(f)
    ranges = {k: tuple(v) for k, v in cfg["phase_ranges"].items()}
    df = load_training_data(Path(args.features))
    train = df[df["season"] < "2025"].copy()
    test = df[df["season"] >= "2025"].copy()
    base_model = joblib.load(Path(f"models/{args.league}_{args.version}") / "champion_model.joblib")
    base_features = list(base_model.feature_order or base_model.selected_features_)
    rows = []
    for phase, (lo, hi) in ranges.items():
        tr = train[(train["over"] >= lo) & (train["over"] <= hi)]
        te = test[(test["over"] >= lo) & (test["over"] <= hi)]
        candidate = joblib.load(phase_dir / f"champion_model_{phase}.joblib")
        phase_features = json.load(open(phase_dir / "phase_features.json", encoding="utf-8"))[phase]
        Xtr_base, _ = safe_X(tr, base_features); Xte_base, _ = safe_X(te, base_features)
        Xtr_phase, _ = safe_X(tr, phase_features); Xte_phase, _ = safe_X(te, phase_features)
        base_fit = XGBLRBlend(); base_fit.fit(Xtr_base, tr["is_winner"].values)
        phase_fit = XGBLRBlend(); phase_fit.fit(Xtr_phase, tr["is_winner"].values)
        base_p = base_fit.predict_proba(Xte_base)[:, 1]
        phase_p = phase_fit.predict_proba(Xte_phase)[:, 1]
        for gender, mask in [("all", pd.Series(True, index=te.index)), ("male", te.get("gender_female", 0) == 0), ("female", te.get("gender_female", 0) == 1)]:
            if int(mask.sum()) == 0: continue
            y = te.loc[mask, "is_winner"]
            b = brier_score_loss(y, base_p[mask.to_numpy()]); c = brier_score_loss(y, phase_p[mask.to_numpy()])
            rows.append({"phase": phase, "gender": gender, "n": int(mask.sum()), "base_brier": b, "candidate_brier": c, "delta_pct": (c-b)/b*100})
    out = pd.DataFrame(rows); Path(args.output).parent.mkdir(parents=True, exist_ok=True); out.to_csv(args.output, index=False)
    decisions = {}
    for phase, group in out.groupby("phase"):
        required = group[group["gender"].isin(["all", "male", "female"])]
        decisions[phase] = {
            "promote": bool((required["delta_pct"] < 0).all()),
            "reason": "candidate beats base for all, male, and female OOS slices" if bool((required["delta_pct"] < 0).all()) else "retain complete innings model; candidate regresses at least one required OOS slice",
        }
    with open(Path(args.output).with_name("promotion_decision.json"), "w", encoding="utf-8") as f:
        json.dump({"league": args.league, "version": args.version, "gate": "all/male/female OOS delta < 0", "phases": decisions}, f, indent=2)
    print(out.to_string(index=False))


if __name__ == "__main__": main()
