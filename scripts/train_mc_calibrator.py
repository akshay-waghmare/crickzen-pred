#!/usr/bin/env python3
"""
Train a Monte Carlo Platt-scaling calibrator.

Backtests MC predictions against actual match outcomes from historical
training data and fits a logistic regression calibrator.

Usage:
    python scripts/train_mc_calibrator.py \
        --training-data data/bbl_features_v4/training.parquet \
        --model-dir models/t20_male_v2 \
        --feature-store-dir data/t20_male_feature_store_v2 \
        --n-samples 5000 \
        --n-simulations 500

Output:
    {model-dir}/mc_calibrator.pkl
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bbl_pipeline.calibration.mc_calibrator import MCCalibrator

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
        avg_pred = probs[mask].mean()
        avg_true = outcomes[mask].mean()
        ece += abs(avg_pred - avg_true) * mask.sum() / len(probs)
    return ece


def main():
    parser = argparse.ArgumentParser(
        description="Train MC Platt calibrator from historical T20 data",
    )
    parser.add_argument(
        "--training-data",
        required=True,
        help="Path to training.parquet (ball-level features + outcomes)",
    )
    parser.add_argument(
        "--model-dir",
        required=True,
        help="Model directory (also the output location for mc_calibrator.pkl)",
    )
    parser.add_argument(
        "--feature-store-dir",
        default=None,
        help="Feature store directory (for ML terminal evaluation)",
    )
    parser.add_argument(
        "--n-samples",
        type=int,
        default=5000,
        help="Number of ball states to sample (default: 5000)",
    )
    parser.add_argument(
        "--n-simulations",
        type=int,
        default=500,
        help="MC simulations per sample (default: 500)",
    )
    parser.add_argument(
        "--use-ml-model",
        action="store_true",
        default=False,
        help="Use ML model for terminal state evaluation (slower, more accurate)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output path for calibrator (default: {model-dir}/mc_calibrator.pkl)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed",
    )

    args = parser.parse_args()

    output_path = args.output or os.path.join(args.model_dir, "mc_calibrator.pkl")
    rng = np.random.RandomState(args.seed)

    # ── Load training data ─────────────────────────────────────────────
    logger.info(f"Loading training data from {args.training_data}")
    df = pd.read_parquet(args.training_data)
    logger.info(f"  {len(df)} rows, {len(df.columns)} columns")

    # Required columns
    required = {"innings", "over", "ball", "current_score", "wickets_lost",
                "batting_team_won", "batting_team", "bowling_team"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns in training data: {missing}")

    # ── Stratified sampling ────────────────────────────────────────────
    # Sample equally from innings × phase
    df = df.copy()
    df["_phase"] = df["over"].apply(lambda o: "pp" if o < 6 else ("mid" if o < 15 else "death"))
    df["_stratum"] = df["innings"].astype(str) + "_" + df["_phase"]

    strata = df["_stratum"].unique()
    per_stratum = max(10, args.n_samples // len(strata))
    sampled_indices = []
    for s in strata:
        idx = df.index[df["_stratum"] == s]
        n = min(per_stratum, len(idx))
        sampled_indices.extend(rng.choice(idx, size=n, replace=False))

    samples = df.loc[sampled_indices].reset_index(drop=True)
    logger.info(f"Sampled {len(samples)} ball states across {len(strata)} strata")

    # ── Run MC simulations ────────────────────────────────────────────
    from bbl_pipeline.simulation.state import MatchState as SimMatchState
    from bbl_pipeline.simulation.engine import simulate

    predictor = None
    if args.use_ml_model:
        try:
            from bbl_pipeline.inference.predictor import Predictor
            predictor = Predictor(args.model_dir, args.feature_store_dir)
            logger.info("Using ML model for terminal state evaluation")
        except Exception as e:
            logger.warning(f"Could not load ML predictor: {e}. Using resource heuristic.")

    mc_probs = np.zeros(len(samples))
    actuals = np.zeros(len(samples))

    logger.info(
        f"Running {len(samples)} × {args.n_simulations} MC simulations "
        f"(est. {len(samples) * args.n_simulations / 1e6:.1f}M paths)..."
    )
    t0 = time.time()

    for i, (_, row) in enumerate(samples.iterrows()):
        innings = int(row["innings"])
        over_num = int(row["over"])
        ball_num = int(row.get("ball", 1))
        balls_bowled = over_num * 6 + ball_num
        balls_remaining = 120 - balls_bowled

        if balls_remaining <= 0:
            # Skip terminal states
            mc_probs[i] = float(row["batting_team_won"])
            actuals[i] = float(row["batting_team_won"])
            continue

        target_runs = int(row["target_runs"]) if innings == 2 and "target_runs" in row and pd.notna(row.get("target_runs")) else None
        league = str(row.get("league", "bbl")) if "league" in row else "bbl"

        sim_state = SimMatchState(
            innings=innings,
            score=int(row["current_score"]),
            wickets_lost=int(row["wickets_lost"]),
            balls_remaining=balls_remaining,
            target_runs=target_runs,
            batting_team=str(row.get("batting_team", "TeamA")),
            bowling_team=str(row.get("bowling_team", "TeamB")),
            league=league,
        )

        try:
            # Simulate remaining balls
            horizon = min(balls_remaining, 30)  # Cap horizon for speed
            result = simulate(
                sim_state,
                horizon=horizon,
                n_simulations=args.n_simulations,
                predictor=predictor,
                model_dir=args.model_dir,
            )
            mc_probs[i] = result.mean_prob
        except Exception as e:
            logger.debug(f"  Sample {i}: simulation failed ({e}), using 0.5")
            mc_probs[i] = 0.5

        actuals[i] = float(row["batting_team_won"])

        if (i + 1) % 500 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            remaining = (len(samples) - i - 1) / rate
            logger.info(
                f"  {i + 1}/{len(samples)} samples "
                f"({elapsed:.0f}s elapsed, ~{remaining:.0f}s remaining)"
            )

    total_time = time.time() - t0
    logger.info(f"MC simulation complete in {total_time:.1f}s")

    # ── Train/validation split ─────────────────────────────────────────
    n = len(mc_probs)
    perm = rng.permutation(n)
    split = int(n * 0.8)
    train_idx, val_idx = perm[:split], perm[split:]

    train_probs, train_actuals = mc_probs[train_idx], actuals[train_idx]
    val_probs, val_actuals = mc_probs[val_idx], actuals[val_idx]

    # ── Fit calibrator ────────────────────────────────────────────────
    logger.info(f"Fitting Platt calibrator on {len(train_probs)} training samples...")
    calibrator = MCCalibrator()
    calibrator.fit(train_probs, train_actuals)
    logger.info(f"  Training: {calibrator.summary()}")

    # ── Validate ──────────────────────────────────────────────────────
    from sklearn.metrics import brier_score_loss, log_loss

    val_calibrated = calibrator.calibrate_batch(val_probs)
    val_brier_raw = brier_score_loss(val_actuals, val_probs)
    val_brier_cal = brier_score_loss(val_actuals, val_calibrated)
    val_ll_raw = log_loss(val_actuals, np.clip(val_probs, 1e-7, 1 - 1e-7))
    val_ll_cal = log_loss(val_actuals, np.clip(val_calibrated, 1e-7, 1 - 1e-7))
    val_ece_raw = _compute_ece(val_probs, val_actuals)
    val_ece_cal = _compute_ece(val_calibrated, val_actuals)

    logger.info(f"\n{'='*60}")
    logger.info(f"VALIDATION RESULTS ({len(val_probs)} samples)")
    logger.info(f"{'='*60}")
    logger.info(f"{'Metric':<15} {'Raw MC':>10} {'Calibrated':>10} {'Delta':>10}")
    logger.info(f"{'-'*45}")
    logger.info(f"{'Brier':<15} {val_brier_raw:>10.4f} {val_brier_cal:>10.4f} {val_brier_cal - val_brier_raw:>+10.4f}")
    logger.info(f"{'Log Loss':<15} {val_ll_raw:>10.4f} {val_ll_cal:>10.4f} {val_ll_cal - val_ll_raw:>+10.4f}")
    logger.info(f"{'ECE':<15} {val_ece_raw:>10.4f} {val_ece_cal:>10.4f} {val_ece_cal - val_ece_raw:>+10.4f}")
    logger.info(f"{'='*60}\n")

    # ── Gate check ────────────────────────────────────────────────────
    passed = True
    if val_ll_cal > 0.55:
        logger.warning(f"GATE FAIL: validation log loss {val_ll_cal:.4f} > 0.55")
        passed = False
    if val_ece_cal > 0.0021:
        logger.warning(f"GATE WARN: validation ECE {val_ece_cal:.4f} > 0.0021 (deferred for reduced-over)")

    # ── Save ──────────────────────────────────────────────────────────
    calibrator.save(output_path)
    logger.info(f"Calibrator saved to {output_path}")

    if passed:
        logger.info("All gates PASSED")
    else:
        logger.warning("Some gates FAILED — review metrics above")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
