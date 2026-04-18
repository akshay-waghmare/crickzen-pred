"""
Alpha sweep for market ensemble blending.

Reads data/ipl_model_vs_market.parquet and sweeps alpha from 0.0 to 1.0
to find optimal blending weight between model and market probabilities.

Output: data/ipl_alpha_sweep.json
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

INPUT_FILE = DATA_DIR / "ipl_model_vs_market.parquet"
OUTPUT_FILE = DATA_DIR / "ipl_alpha_sweep.json"


def main():
    if not INPUT_FILE.exists():
        print(f"[ERROR] Input file not found: {INPUT_FILE}")
        sys.exit(1)

    df = pd.read_parquet(INPUT_FILE)
    print(f"Loaded {len(df)} rows from {INPUT_FILE}")

    required_cols = {"model_p_t1", "market_p_t1", "actual_t1_wins"}
    missing = required_cols - set(df.columns)
    if missing:
        print(f"[ERROR] Missing columns: {missing}")
        sys.exit(1)

    # Drop rows with NaN in market_p_t1
    valid = df.dropna(subset=["model_p_t1", "market_p_t1", "actual_t1_wins"])
    print(f"Valid rows (non-NaN market): {len(valid)} / {len(df)}")

    model_p = valid["model_p_t1"].values
    market_p = valid["market_p_t1"].values
    actual = valid["actual_t1_wins"].values

    alphas = np.arange(0.0, 1.001, 0.05)
    results = []

    print(f"\n{'Alpha':>7} | {'Brier':>8} | {'Improvement vs model':>22}")
    print("-" * 45)

    model_only_brier = None

    for alpha in alphas:
        alpha = round(alpha, 2)
        blended = alpha * model_p + (1 - alpha) * market_p
        brier = float(np.mean((blended - actual) ** 2))
        results.append({"alpha": alpha, "brier": brier})

        if alpha == 1.0:
            model_only_brier = brier

    # Print results table
    for r in results:
        improvement = ""
        if model_only_brier is not None:
            pct = (model_only_brier - r["brier"]) / model_only_brier * 100
            improvement = f"{pct:+.2f}%"
        print(f"{r['alpha']:7.2f} | {r['brier']:.6f} | {improvement:>22}")

    # Find optimal
    best = min(results, key=lambda x: x["brier"])
    print(f"\nOptimal alpha: {best['alpha']:.2f} (Brier: {best['brier']:.6f})")

    if model_only_brier is not None:
        improvement_pct = (model_only_brier - best["brier"]) / model_only_brier * 100
        print(f"Model-only Brier (alpha=1.0): {model_only_brier:.6f}")
        print(f"Improvement: {improvement_pct:.2f}%")

    # Save results
    output = {
        "input_file": str(INPUT_FILE),
        "total_rows": len(df),
        "valid_rows": len(valid),
        "results": results,
        "optimal_alpha": best["alpha"],
        "optimal_brier": best["brier"],
        "model_only_brier": model_only_brier,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
