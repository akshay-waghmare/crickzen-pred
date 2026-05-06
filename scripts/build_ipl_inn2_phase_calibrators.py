"""
Build and evaluate phase-wise inn2 isotonic calibrators.

Key findings from EDA:
  POWERPLAY: model overestimates (+0.062 mean bias), 0.1-0.5 bucket huge bias
  MIDDLE:    model overestimates (+0.044 mean bias), 0.1-0.5 bucket huge bias
  DEATH:     nearly unbiased (-0.013 mean bias), but over-20 terminal issue

Fix: Fit separate isotonic calibrator per phase (PP/MID/DEATH) on 2026 OOS data.
Applied ON TOP of per-over isotonic (stacked correction).

Usage:
    python scripts/build_ipl_inn2_phase_calibrators.py
    python scripts/build_ipl_inn2_phase_calibrators.py --eval-only
"""
from __future__ import annotations
import argparse
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss

EPS = 1e-7
PHASE_OVERS = {"powerplay": range(1, 7), "middle": range(7, 16), "death": range(16, 21)}
OUTPUT_PATH = Path("models/ipl_v6/inn2_phase_calibrators.pkl")


def clip(p):
    return np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)


def metrics(y, p):
    p = clip(p)
    return float(brier_score_loss(y, p)), float(log_loss(y, p))


def phase_of(over: int) -> str:
    if over <= 6:
        return "powerplay"
    elif over <= 15:
        return "middle"
    return "death"


def build_phase_calibrators(train_df: pd.DataFrame) -> dict:
    """Fit one isotonic calibrator per inn2 phase on train data."""
    calibrators = {}
    for phase in ["powerplay", "middle", "death"]:
        seg = train_df[train_df["phase"] == phase]
        if len(seg) < 20:
            print(f"  WARNING: {phase} only {len(seg)} train rows — skipping")
            continue
        ir = IsotonicRegression(out_of_bounds="clip")
        ir.fit(seg["iso_p_inn1"].values, seg["actual_inn1_wins"].values)
        calibrators[phase] = ir
        print(f"  {phase}: fitted on {len(seg)} rows")
    return calibrators


def apply_phase_calibrators(df: pd.DataFrame, calibrators: dict) -> np.ndarray:
    """Apply phase-specific calibrator to each row. Falls back to iso_p_inn1."""
    probs = df["iso_p_inn1"].values.copy().astype(float)
    for phase, ir in calibrators.items():
        mask = df["phase"] == phase
        if mask.sum() > 0:
            probs[mask.values] = ir.predict(df.loc[mask, "iso_p_inn1"].values)
    return probs


def evaluate(label: str, y: np.ndarray, p: np.ndarray) -> tuple[float, float]:
    b, ll = metrics(y, p)
    print(f"    {label:<22} Brier={b:.4f}  LogLoss={ll:.4f}")
    return b, ll


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", default="data/ipl_latest_market_vs_model.parquet")
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    parser.add_argument("--holdout-matches", type=int, default=10,
                        help="Last N matches used as chronological holdout")
    parser.add_argument("--eval-only", action="store_true",
                        help="Load existing calibrators and only run evaluation")
    args = parser.parse_args()

    print("Loading market comparison data...")
    mkt = pd.read_parquet(args.comparison)
    inn2 = mkt[mkt["innings"] == 2].copy()
    print(f"Inn2 rows: {len(inn2)}, matches: {inn2['cs_match_id'].nunique()}")

    # Chronological split
    match_dates = mkt.groupby("cs_match_id")["date"].first().sort_values()
    all_matches = match_dates.index.tolist()
    train_matches = all_matches[: -args.holdout_matches]
    test_matches = all_matches[-args.holdout_matches :]
    print(f"Train matches: {len(train_matches)} | Test matches: {len(test_matches)}")
    print(f"Test period: {match_dates[test_matches[0]]} → {match_dates[test_matches[-1]]}")

    train = inn2[inn2["cs_match_id"].isin(train_matches)]
    test = inn2[inn2["cs_match_id"].isin(test_matches)]
    print(f"Train rows: {len(train)} | Test rows: {len(test)}")

    if args.eval_only:
        print(f"\nLoading existing calibrators from {args.output}...")
        with open(args.output, "rb") as f:
            artifact = pickle.load(f)
        calibrators = artifact["phase_calibrators"]
    else:
        print("\nFitting phase-wise calibrators on train data...")
        calibrators = build_phase_calibrators(train)

        artifact = {
            "phase_calibrators": calibrators,
            "fitted_on": "ipl_latest_market_vs_model 2026 OOS",
            "n_train": len(train),
            "train_match_count": len(train_matches),
            "phases": list(calibrators.keys()),
        }
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "wb") as f:
            pickle.dump(artifact, f)
        print(f"Saved to {args.output}")

    # ── Holdout evaluation ─────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("HOLDOUT EVALUATION (last 10 matches, chronological)")
    print("=" * 60)

    y_test = test["actual_inn1_wins"].values
    p_market = test["market_p_inn1"].values
    p_v6 = test["iso_p_inn1"].values
    p_v7 = apply_phase_calibrators(test, calibrators)

    print("\n  OVERALL INN2:")
    b_mkt, ll_mkt = evaluate("Market", y_test, p_market)
    b_v6, ll_v6 = evaluate("Model v6 (iso)", y_test, p_v6)
    b_v7, ll_v7 = evaluate("Model v7 (phase-cal)", y_test, p_v7)
    print(f"\n    v7 vs v6:     Brier {(b_v7-b_v6)/b_v6*100:+.1f}%   LogLoss {(ll_v7-ll_v6)/ll_v6*100:+.1f}%")
    print(f"    v7 vs market: Brier {(b_v7-b_mkt)/b_mkt*100:+.1f}%   LogLoss {(ll_v7-ll_mkt)/ll_mkt*100:+.1f}%")

    print("\n  BY PHASE:")
    for phase in ["powerplay", "middle", "death"]:
        mask = test["phase"] == phase
        if mask.sum() < 3:
            continue
        y_p = test.loc[mask, "actual_inn1_wins"].values
        print(f"\n    {phase.upper()} (n={mask.sum()}):")
        evaluate("Market", y_p, test.loc[mask, "market_p_inn1"].values)
        b6, l6 = evaluate("Model v6 (iso)", y_p, test.loc[mask, "iso_p_inn1"].values)
        b7, l7 = evaluate("Model v7 (phase-cal)", y_p, p_v7[mask.values])
        print(f"      v7 vs v6: Brier {(b7-b6)/b6*100:+.1f}%  LL {(l7-l6)/l6*100:+.1f}%")

    # ── Calibration curve comparison ───────────────────────────────────────
    print("\n" + "=" * 60)
    print("CALIBRATION CURVE: v6 vs v7 (test set)")
    print("=" * 60)
    bins = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    test = test.copy()
    test["p_v7"] = p_v7
    test["bucket_v6"] = pd.cut(test["iso_p_inn1"], bins=bins)
    test["bucket_v7"] = pd.cut(test["p_v7"], bins=bins)

    print("\n  V6 calibration (iso_p_inn1 → actual):")
    g = test.groupby("bucket_v6", observed=True).agg(
        n=("actual_inn1_wins", "count"),
        model=("iso_p_inn1", "mean"),
        actual=("actual_inn1_wins", "mean"),
    )
    g["bias"] = (g["model"] - g["actual"]).round(3)
    for idx, row in g.iterrows():
        if row["n"] >= 3:
            print(f"    {str(idx):<14} n={row['n']:>3}  model={row['model']:.3f}  actual={row['actual']:.3f}  bias={row['bias']:+.3f}")

    print("\n  V7 calibration (phase_cal → actual):")
    g7 = test.groupby("bucket_v7", observed=True).agg(
        n=("actual_inn1_wins", "count"),
        model=("p_v7", "mean"),
        actual=("actual_inn1_wins", "mean"),
    )
    g7["bias"] = (g7["model"] - g7["actual"]).round(3)
    for idx, row in g7.iterrows():
        if row["n"] >= 3:
            print(f"    {str(idx):<14} n={row['n']:>3}  model={row['model']:.3f}  actual={row['actual']:.3f}  bias={row['bias']:+.3f}")

    # ── Full data evaluation (train+test) ──────────────────────────────────
    print("\n" + "=" * 60)
    print("FULL DATA EVALUATION (all 595 inn2 obs, in-sample)")
    print("=" * 60)
    inn2_full = inn2.copy()
    # Re-fit on ALL data for final artifact
    if not args.eval_only:
        print("\nFitting FULL calibrators on all inn2 data...")
        full_calibrators = build_phase_calibrators(inn2_full)
        p_full_v7 = apply_phase_calibrators(inn2_full, full_calibrators)
        y_full = inn2_full["actual_inn1_wins"].values
        evaluate("Market (full)", y_full, inn2_full["market_p_inn1"].values)
        evaluate("V6 iso (full)", y_full, inn2_full["iso_p_inn1"].values)
        evaluate("V7 phase-cal (full)", y_full, p_full_v7)

        # Save the full-data calibrators as the production artifact
        full_artifact = {
            "phase_calibrators": full_calibrators,
            "fitted_on": "ipl_latest_market_vs_model 2026 full OOS",
            "n_train": len(inn2_full),
            "train_match_count": inn2_full["cs_match_id"].nunique(),
            "phases": list(full_calibrators.keys()),
            "notes": (
                "Phase-wise isotonic calibrators fitted on ALL 2026 OOS inn2 data. "
                "Applied as a stacked correction on top of per-over isotonic (v6). "
                "Fixes systematic overestimation in 0.1-0.5 range for PP and MID phases."
            ),
        }
        prod_path = Path(args.output).with_name("inn2_phase_calibrators_full.pkl")
        with open(prod_path, "wb") as f:
            pickle.dump(full_artifact, f)
        print(f"\nProduction calibrators (full data) saved to: {prod_path}")

    print("\nDONE.")


if __name__ == "__main__":
    main()
