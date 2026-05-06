"""
Phase-wise Temperature Scaling for IPL inn2.

Why temperature instead of isotonic:
  - Isotonic overfit: +27% worse on holdout (fitted on 428 rows, tested on 167)
  - Temperature scaling uses ONLY 1 parameter per phase (T)
  - Much more regularized, generalizes better with limited OOS data

Temperature scaling: logit(p_new) = logit(iso_p) / T
  - T > 1: softer predictions (toward 0.5)
  - T < 1: sharper predictions (away from 0.5)

The calibration shows model too compressed around 0.5 for inn2.
Both low (0.2-0.4) and high (0.6-0.8) buckets need sharpening → T < 1.

Usage:
    python scripts/build_ipl_inn2_temperature_calibrators.py
"""
from __future__ import annotations
import argparse
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar, minimize
from sklearn.metrics import brier_score_loss, log_loss

EPS = 1e-7
OUTPUT_PATH = Path("models/ipl_v6/inn2_temperature_calibrators.pkl")


def clip(p):
    return np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)


def logit(p):
    p = clip(p)
    return np.log(p / (1.0 - p))


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def apply_temperature(p: np.ndarray, T: float, b: float = 0.0) -> np.ndarray:
    """Platt scaling: p_new = sigmoid(logit(p) / T + b)"""
    return sigmoid(logit(p) / T + b)


def fit_temperature(p_train: np.ndarray, y_train: np.ndarray,
                    metric: str = "brier") -> tuple[float, float]:
    """Find T, b minimising Brier or LogLoss on train data."""
    def loss(params):
        T, b = params[0], params[1]
        if T < 0.05 or T > 5.0:
            return 1e9
        p_cal = clip(apply_temperature(p_train, T, b))
        if metric == "brier":
            return brier_score_loss(y_train, p_cal)
        return log_loss(y_train, p_cal)

    # Grid search for T, then refine
    best = (1.0, 0.0, 1e9)
    for T_init in [0.3, 0.5, 0.7, 1.0, 1.3, 1.5, 2.0]:
        for b_init in [-0.5, -0.3, -0.1, 0.0, 0.1, 0.3, 0.5]:
            v = loss([T_init, b_init])
            if v < best[2]:
                best = (T_init, b_init, v)

    res = minimize(loss, x0=[best[0], best[1]], method="Nelder-Mead",
                   options={"xatol": 1e-5, "fatol": 1e-6, "maxiter": 2000})
    T_opt, b_opt = res.x[0], res.x[1]
    T_opt = max(0.05, min(5.0, T_opt))
    return float(T_opt), float(b_opt)


def metrics(y, p):
    p = clip(p)
    return float(brier_score_loss(y, p)), float(log_loss(y, p))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", default="data/ipl_latest_market_vs_model.parquet")
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    parser.add_argument("--holdout-matches", type=int, default=10)
    parser.add_argument("--metric", default="brier", choices=["brier", "logloss"])
    args = parser.parse_args()

    print("Loading market comparison data...")
    mkt = pd.read_parquet(args.comparison)
    inn2 = mkt[mkt["innings"] == 2].copy()
    print(f"Inn2: {len(inn2)} rows, {inn2['cs_match_id'].nunique()} matches\n")

    # Chronological split
    match_dates = mkt.groupby("cs_match_id")["date"].first().sort_values()
    all_matches = match_dates.index.tolist()
    train_matches = all_matches[: -args.holdout_matches]
    test_matches  = all_matches[-args.holdout_matches:]
    print(f"Train: {len(train_matches)} matches | Test: {len(test_matches)} matches")
    print(f"Test period: {match_dates[test_matches[0]]} → {match_dates[test_matches[-1]]}\n")

    train = inn2[inn2["cs_match_id"].isin(train_matches)]
    test  = inn2[inn2["cs_match_id"].isin(test_matches)]

    # ── Fit per-phase temperature parameters ─────────────────────────────
    print("=" * 60)
    print(f"Fitting temperature scaling per phase (metric={args.metric})")
    print("=" * 60)

    temp_params: dict[str, dict] = {}
    for phase in ["powerplay", "middle", "death"]:
        seg = train[train["phase"] == phase]
        if len(seg) < 15:
            print(f"  {phase}: too few rows ({len(seg)}), using T=1.0, b=0.0")
            temp_params[phase] = {"T": 1.0, "b": 0.0}
            continue
        T, b = fit_temperature(seg["iso_p_inn1"].values,
                               seg["actual_inn1_wins"].values,
                               args.metric)
        # Sanity: check it actually improves train
        p_orig = clip(seg["iso_p_inn1"].values)
        p_cal  = clip(apply_temperature(seg["iso_p_inn1"].values, T, b))
        y      = seg["actual_inn1_wins"].values
        b_orig, ll_orig = metrics(y, p_orig)
        b_cal,  ll_cal  = metrics(y, p_cal)
        temp_params[phase] = {"T": T, "b": b}
        print(f"  {phase:10s}: T={T:.4f}  b={b:+.4f}  "
              f"| train Brier {b_orig:.4f} → {b_cal:.4f} ({(b_cal-b_orig)/b_orig*100:+.1f}%)")

    # ── Holdout evaluation ────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("HOLDOUT EVALUATION (last 10 matches, chronological)")
    print("=" * 60)

    # Apply temperature per phase
    test = test.copy()
    test["p_v7_temp"] = test["iso_p_inn1"].values.copy()
    for phase, params in temp_params.items():
        mask = test["phase"] == phase
        test.loc[mask, "p_v7_temp"] = apply_temperature(
            test.loc[mask, "iso_p_inn1"].values, params["T"], params["b"]
        )

    y_test = test["actual_inn1_wins"].values
    p_mkt  = test["market_p_inn1"].values
    p_v6   = test["iso_p_inn1"].values
    p_v7   = test["p_v7_temp"].values

    def print_row(label, y, p):
        b, ll = metrics(y, p)
        print(f"    {label:<25} Brier={b:.4f}  LogLoss={ll:.4f}")
        return b, ll

    print("\n  OVERALL INN2:")
    bm, lm = print_row("Market", y_test, p_mkt)
    b6, l6 = print_row("Model v6 (iso)", y_test, p_v6)
    b7, l7 = print_row("Model v7 (temp)", y_test, p_v7)
    print(f"\n    v7 vs v6:     Brier {(b7-b6)/b6*100:+.1f}%   LogLoss {(l7-l6)/l6*100:+.1f}%")
    print(f"    v7 vs market: Brier {(b7-bm)/bm*100:+.1f}%   LogLoss {(l7-lm)/lm*100:+.1f}%")

    print("\n  BY PHASE:")
    for phase in ["powerplay", "middle", "death"]:
        mask = test["phase"] == phase
        if mask.sum() < 3:
            continue
        y_p = test.loc[mask, "actual_inn1_wins"].values
        T   = temp_params[phase]["T"]
        b   = temp_params[phase]["b"]
        print(f"\n    {phase.upper()} (n={mask.sum()}, T={T:.4f}, b={b:+.4f}):")
        print_row("Market", y_p, test.loc[mask, "market_p_inn1"].values)
        bv6, lv6 = print_row("Model v6 (iso)", y_p, test.loc[mask, "iso_p_inn1"].values)
        bv7, lv7 = print_row("Model v7 (temp)", y_p, test.loc[mask, "p_v7_temp"].values)
        print(f"      v7 vs v6: Brier {(bv7-bv6)/bv6*100:+.1f}%  LL {(lv7-lv6)/lv6*100:+.1f}%")

    # ── Calibration curve comparison ──────────────────────────────────────
    print()
    print("=" * 60)
    print("CALIBRATION CURVE v6 vs v7 (test set)")
    print("=" * 60)
    bins = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    test["bkt_v6"] = pd.cut(test["iso_p_inn1"], bins=bins)
    test["bkt_v7"] = pd.cut(test["p_v7_temp"], bins=bins)

    print("\n  V6 model → actual win rate:")
    for bkt, grp in test.groupby("bkt_v6", observed=True):
        if len(grp) < 3: continue
        print(f"    {str(bkt):<14} n={len(grp):>3}  model={grp['iso_p_inn1'].mean():.3f}  "
              f"actual={grp['actual_inn1_wins'].mean():.3f}  "
              f"bias={grp['iso_p_inn1'].mean()-grp['actual_inn1_wins'].mean():+.3f}")
    print("\n  V7 temp → actual win rate:")
    for bkt, grp in test.groupby("bkt_v7", observed=True):
        if len(grp) < 3: continue
        print(f"    {str(bkt):<14} n={len(grp):>3}  model={grp['p_v7_temp'].mean():.3f}  "
              f"actual={grp['actual_inn1_wins'].mean():.3f}  "
              f"bias={grp['p_v7_temp'].mean()-grp['actual_inn1_wins'].mean():+.3f}")

    # ── Save artifact ─────────────────────────────────────────────────────
    print()
    verdict = b7 < b6 and l7 < l6
    print("=" * 60)
    print(f"VERDICT: v7 temperature scaling {'✓ BETTER' if verdict else '✗ NOT better'} than v6 on holdout")
    print("=" * 60)

    # Refit on ALL data for production
    print("\nFitting production calibrators on ALL inn2 data...")
    prod_params: dict[str, dict] = {}
    for phase in ["powerplay", "middle", "death"]:
        seg = inn2[inn2["phase"] == phase]
        T, b = fit_temperature(seg["iso_p_inn1"].values,
                               seg["actual_inn1_wins"].values, args.metric)
        prod_params[phase] = {"T": T, "b": b}
        print(f"  {phase:10s}: T={T:.4f}  b={b:+.4f}  (n={len(seg)})")

    # In-sample check
    inn2_copy = inn2.copy()
    inn2_copy["p_prod"] = inn2_copy["iso_p_inn1"].values.copy()
    for phase, params in prod_params.items():
        mask = inn2_copy["phase"] == phase
        inn2_copy.loc[mask, "p_prod"] = apply_temperature(
            inn2_copy.loc[mask, "iso_p_inn1"].values, params["T"], params["b"]
        )
    y_all = inn2_copy["actual_inn1_wins"].values
    b_v6_all, l_v6_all = metrics(y_all, inn2_copy["iso_p_inn1"].values)
    b_prod,   l_prod   = metrics(y_all, inn2_copy["p_prod"].values)
    print(f"\n  In-sample (all 595): v6 Brier={b_v6_all:.4f}  v7 Brier={b_prod:.4f}")

    artifact = {
        "phase_temperature_params": prod_params,
        "fitted_on":  "ipl_latest_market_vs_model 2026 full OOS (595 rows, 33 matches)",
        "metric":     args.metric,
        "n_total":    len(inn2),
        "holdout_result": {
            "v6_brier":  b6,  "v7_brier":  b7,
            "v6_ll":     l6,  "v7_ll":     l7,
            "brier_delta_pct": (b7 - b6) / b6 * 100,
            "verdict": "PASS" if verdict else "FAIL",
        },
        "notes": (
            "Phase-wise temperature/Platt scaling for IPL inn2. "
            "Applied after per-over isotonic calibration. "
            "Formula: p_new = sigmoid(logit(iso_p) / T + b). "
            "Preferred over isotonic for limited OOS data (only 1-2 params per phase)."
        ),
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "wb") as f:
        pickle.dump(artifact, f)
    print(f"\nSaved to: {args.output}")

    # Print final summary
    print("\n" + "=" * 60)
    print("FINAL TEMPERATURE PARAMETERS (production)")
    print("=" * 60)
    for phase, params in prod_params.items():
        T, b = params["T"], params["b"]
        # Show example transformations
        examples = [0.1, 0.3, 0.5, 0.7, 0.9]
        transformed = [f"{apply_temperature(np.array([p]), T, b)[0]:.3f}" for p in examples]
        print(f"  {phase:10s}: T={T:.4f}  b={b:+.4f}")
        print(f"    0.1→{transformed[0]}  0.3→{transformed[1]}  0.5→{transformed[2]}  0.7→{transformed[3]}  0.9→{transformed[4]}")


if __name__ == "__main__":
    main()
