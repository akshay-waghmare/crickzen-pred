#!/usr/bin/env python3
"""
Train innings × phase MC Platt-scaling calibrators (6 total).

Samples ball states from historical training data, runs MC simulations
in parallel, and fits separate Platt calibrators for each of the 6
innings × phase buckets (inn1_pp, inn1_mid, inn1_death, inn2_pp, inn2_mid, inn2_death).

Usage:
    python scripts/train_mc_calibrator_innings_phase.py \
        --training-data data/t20_international_male_features_v1/training.parquet \
        --model-dir models/t20_international_male_v1 \
        --n-samples 6000 \
        --n-simulations 300 \
        --workers 8

Output:
    {model-dir}/mc_calibrators_innings_phase.pkl
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bbl_pipeline.calibration.mc_calibrator import (
    MCCalibrator,
    InningsPhaseCalibrators,
    PHASE_PP,
    PHASE_MID,
    PHASE_DEATH,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def _compute_ece(probs: np.ndarray, outcomes: np.ndarray, n_bins: int = 10) -> float:
    """Compute Expected Calibration Error."""
    bin_edges = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for lo, hi in zip(bin_edges[:-1], bin_edges[1:]):
        mask = (probs >= lo) & (probs < hi)
        if mask.sum() == 0:
            continue
        ece += abs(probs[mask].mean() - outcomes[mask].mean()) * mask.sum() / len(probs)
    return ece


def _over_to_phase(over: int) -> str:
    if over < 6:
        return PHASE_PP
    if over < 15:
        return PHASE_MID
    return PHASE_DEATH


def run_mc_for_row(row_dict: dict, n_sims: int = 300, horizon: int = 6) -> float:
    """Run MC simulation for a single ball state. Designed for multiprocessing."""
    from bbl_pipeline.simulation.state import MatchState as SimMatchState
    from bbl_pipeline.simulation.engine import simulate

    innings = int(row_dict.get("innings", 2))

    if "overs_remaining" in row_dict:
        overs_bowled = 20 - row_dict["overs_remaining"]
        over = int(overs_bowled)
        ball = int(round((overs_bowled - over) * 6)) + 1
    else:
        over = int(row_dict.get("over", 10))
        ball = int(row_dict.get("ball", 1))

    balls_remaining = (20 - over) * 6 - ball + 1
    balls_remaining = max(1, min(120, balls_remaining))

    overs_remaining = row_dict.get("overs_remaining", balls_remaining / 6)
    overs_bowled = 20 - overs_remaining

    if "current_score" in row_dict:
        score = int(row_dict["current_score"])
    elif "score" in row_dict:
        score = int(row_dict["score"])
    elif "total_score" in row_dict:
        score = int(row_dict["total_score"])
    elif "current_run_rate" in row_dict and overs_bowled > 0:
        score = int(row_dict["current_run_rate"] * overs_bowled)
    else:
        score = 100

    wickets = int(
        row_dict.get(
            "wickets_lost",
            row_dict.get("wickets", row_dict.get("total_wickets", 3)),
        )
    )

    target = None
    if innings == 2:
        if "target_runs" in row_dict:
            target = int(row_dict["target_runs"])
        elif "target" in row_dict:
            target = int(row_dict["target"])
        elif "target_score" in row_dict:
            target = int(row_dict["target_score"])
        elif "required_run_rate" in row_dict and overs_remaining > 0:
            runs_needed = row_dict["required_run_rate"] * overs_remaining
            target = int(score + runs_needed)
        else:
            target = 160

    state = SimMatchState(
        innings=innings,
        score=score,
        wickets_lost=wickets,
        balls_remaining=balls_remaining,
        target_runs=target,
        league="t20i",
        batting_team="Team A",
        bowling_team="Team B",
    )

    result = simulate(
        state=state,
        horizon=horizon,
        n_simulations=n_sims,
        predictor=None,
        apply_temp=False,
    )
    return float(result.mean_prob)


def main():
    parser = argparse.ArgumentParser(
        description="Train innings × phase MC Platt calibrators (6 total)",
    )
    parser.add_argument(
        "--training-data",
        required=True,
        help="Path to training.parquet",
    )
    parser.add_argument(
        "--model-dir",
        required=True,
        help="Model directory (output location for mc_calibrators_innings_phase.pkl)",
    )
    parser.add_argument(
        "--n-samples",
        type=int,
        default=6000,
        help="Total ball states to sample (1000 per bucket, default: 6000)",
    )
    parser.add_argument(
        "--n-simulations",
        type=int,
        default=300,
        help="MC simulations per sample (default: 300)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=max(1, (os.cpu_count() or 8) - 1),
        help="Parallel workers",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output path (default: {model-dir}/mc_calibrators_innings_phase.pkl)",
    )
    args = parser.parse_args()

    output_path = args.output or os.path.join(
        args.model_dir, "mc_calibrators_innings_phase.pkl"
    )
    rng = np.random.RandomState(args.seed)

    # ── Load training data ─────────────────────────────────────────────
    logger.info(f"Loading training data from {args.training_data}")
    df = pd.read_parquet(args.training_data)
    logger.info(f"  {len(df):,} rows, {len(df.columns)} columns")

    # Compute over & phase
    if "overs_remaining" in df.columns and "over" not in df.columns:
        df["over"] = (20 - df["overs_remaining"]).round().astype(int)
    df["_phase"] = df["over"].apply(_over_to_phase)
    df["_stratum"] = df["innings"].astype(str) + "_" + df["_phase"]

    # ── Stratified sampling ────────────────────────────────────────────
    strata = sorted(df["_stratum"].unique())
    per_stratum = max(50, args.n_samples // len(strata))
    sampled_indices = []
    for s in strata:
        idx = df.index[df["_stratum"] == s].values
        n = min(per_stratum, len(idx))
        sampled_indices.extend(rng.choice(idx, size=n, replace=False))

    samples = df.loc[sampled_indices].reset_index(drop=True)
    logger.info(
        f"Sampled {len(samples):,} ball states across {len(strata)} strata "
        f"({per_stratum} per stratum)"
    )
    for s in strata:
        count = (samples["_stratum"] == s).sum()
        logger.info(f"  {s}: {count}")

    # ── Run parallel MC simulations ───────────────────────────────────
    logger.info(
        f"Running {len(samples):,} × {args.n_simulations} MC simulations "
        f"(workers={args.workers})..."
    )
    t0 = time.time()

    row_dicts = [r.to_dict() for _, r in samples.iterrows()]
    mc_probs = np.zeros(len(samples), dtype=float)

    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(run_mc_for_row, rd, args.n_simulations, 6): i
            for i, rd in enumerate(row_dicts)
        }
        done = 0
        for future in as_completed(futures):
            i = futures[future]
            try:
                mc_probs[i] = future.result()
            except Exception as e:
                logger.debug(f"  Sample {i}: simulation failed ({e}), using 0.5")
                mc_probs[i] = 0.5
            done += 1
            if done % 200 == 0:
                elapsed = time.time() - t0
                rate = done / max(elapsed, 1e-9)
                eta = (len(samples) - done) / max(rate, 1e-9)
                logger.info(
                    f"  [{done}/{len(samples)}] {rate:.1f} states/s, ETA {eta:.0f}s"
                )

    sim_time = time.time() - t0
    logger.info(f"MC simulation complete in {sim_time:.1f}s")

    samples["mc_raw_prob"] = mc_probs
    # Outcome column: 'is_winner' for processed features, 'batting_team_won' for raw
    outcome_col = "is_winner" if "is_winner" in samples.columns else "batting_team_won"
    actuals = samples[outcome_col].values.astype(float)

    # ── Fit per-bucket calibrators ────────────────────────────────────
    container = InningsPhaseCalibrators()

    print(f"\n{'='*70}")
    print("TRAINING  INNINGS × PHASE  MC PLATT CALIBRATORS")
    print(f"{'='*70}")
    print(
        f"{'Bucket':<16} | {'N_train':>7} | {'N_val':>6} | "
        f"{'Raw Brier':>10} | {'Cal Brier':>10} | {'Raw ECE':>8} | {'Cal ECE':>8}"
    )
    print("-" * 70)

    for innings in [1, 2]:
        for phase in [PHASE_PP, PHASE_MID, PHASE_DEATH]:
            key = f"inn{innings}_{phase}"
            mask = (samples["innings"] == innings) & (samples["_phase"] == phase)
            bucket = samples[mask]

            if len(bucket) < 30:
                logger.warning(f"  {key}: only {len(bucket)} samples, skipping")
                continue

            probs = bucket["mc_raw_prob"].values
            outcomes = actuals[mask.values]

            # 80/20 split
            perm = rng.permutation(len(probs))
            split = int(len(probs) * 0.8)
            tr_idx, va_idx = perm[:split], perm[split:]

            cal = MCCalibrator()
            cal.fit(probs[tr_idx], outcomes[tr_idx])

            # Validate
            va_raw = probs[va_idx]
            va_cal = cal.calibrate_batch(va_raw)
            va_out = outcomes[va_idx]

            raw_brier = brier_score_loss(va_out, va_raw)
            cal_brier = brier_score_loss(va_out, va_cal)
            raw_ece = _compute_ece(va_raw, va_out)
            cal_ece = _compute_ece(va_cal, va_out)

            print(
                f"{key:<16} | {len(tr_idx):>7} | {len(va_idx):>6} | "
                f"{raw_brier:>10.4f} | {cal_brier:>10.4f} | "
                f"{raw_ece:>8.4f} | {cal_ece:>8.4f}"
            )

            container.set(innings, phase, cal)

    # ── Save ──────────────────────────────────────────────────────────
    container.save(output_path)
    logger.info(f"\nSaved InningsPhaseCalibrators to {output_path}")
    print(f"\n{container.summary()}")

    total = time.time() - t0
    logger.info(f"Total elapsed: {total:.1f}s")

    return 0


if __name__ == "__main__":
    sys.exit(main())
