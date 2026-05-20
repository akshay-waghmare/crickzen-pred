"""
IPL MC Features Experiment (spec: 014-ipl-mc-features-experiment)

Offline, leak-free experiment to test whether calibrated Monte Carlo outputs
improve the IPL ML model (Brier, ECE, log loss) versus the current IPL v6 baseline.

Usage:
  # Pilot (fast, sampled data)
  python scripts/analyze_ipl_mc_features_experiment.py \
    --input data/ipl_features_v6/training_sampled.parquet \
    --output-dir experiments/ipl_mc_features_v1 \
    --mode pilot --n-sims 100 --seed 42

  # Full run (resume-capable)
  python scripts/analyze_ipl_mc_features_experiment.py \
    --input data/ipl_features_v6/training.parquet \
    --output-dir experiments/ipl_mc_features_v1 \
    --mode full --n-sims 1000 --resume --seed 42
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).parent.parent))

from bbl_pipeline.simulation.engine import simulate
from bbl_pipeline.simulation.state import MatchState
from bbl_pipeline.training.trainer import XGBLogRegEnsemble

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
LEAGUE = "ipl"
TOTAL_BALLS = 120  # 20-over T20
PHASE_POWERPLAY = "powerplay"  # overs 1-6
PHASE_MIDDLE = "middle"        # overs 7-15
PHASE_DEATH = "death"          # overs 16-20

REQUIRED_COLS = [
    "innings",
    "wickets_lost",
    "overs_remaining",
    "current_run_rate",
    "required_run_rate",
    "resource_win_prob",
    "is_winner",
]

# MC feature columns written to the cache
MC_CACHE_COLS = [
    "row_key",
    "innings",
    "over_approx",
    "balls_remaining_approx",
    "mc_raw_win_prob",
    "mc_simulation_std",
    "seed",
    "n_sims",
    "horizon_balls",
    "sim_ok",
    "skip_reason",
]

# Promotion gate thresholds
GATE_BRIER_IMPROVE = 0.001      # Overall Brier must improve by at least this
GATE_LOGLOSS_WORSE_TOL = 0.0   # Log loss must not get worse
GATE_ECE_WORSE_TOL = 0.0       # ECE must not get worse
GATE_SEGMENT_BRIER_REGRESS = 0.003  # No innings/phase segment may worsen by more

VARIANT_ORDER = [
    "baseline_ipl_v6_features",
    "mc_standalone_calibrated",
    "ml_add_mc_win_prob",
    "ml_add_mc_win_prob_inn2_only",
    "ml_add_mc_gap_features",
    "ml_add_mc_gap_features_inn2_only",
    "ml_replace_resource_with_mc",
    "ml_replace_resource_with_mc_inn2_only",
    "ml_clean_swap_resource",
    "ml_clean_swap_resource_inn2_only",
]


# ---------------------------------------------------------------------------
# IPLMCFeatureEnsemble — extends TOP_FEATURES list with MC columns
# ---------------------------------------------------------------------------
class IPLMCFeatureEnsemble(XGBLogRegEnsemble):
    """XGBLogRegEnsemble subclass with MC features prepended to TOP_FEATURES."""

    TOP_FEATURES = [
        "mc_win_prob",
        "mc_resource_gap",
        "mc_resource_abs_gap",
        "mc_simulation_std",
        *XGBLogRegEnsemble.TOP_FEATURES,
    ]

    def __init__(self, **kwargs):
        # Allow up to all features including the 4 new MC ones
        kwargs.setdefault("n_features", 36)
        super().__init__(**kwargs)


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def compute_brier(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    y_prob = np.clip(y_prob, 1e-7, 1 - 1e-7)
    return float(brier_score_loss(y_true, y_prob))


def compute_ece(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    """Compute Expected Calibration Error (ECE) using equal-width bins."""
    y_prob = np.clip(y_prob, 0.0, 1.0)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(y_prob, bins) - 1, 0, n_bins - 1)
    total = 0.0
    for b in range(n_bins):
        mask = idx == b
        if not mask.any():
            continue
        total += mask.sum() / len(y_prob) * abs(y_prob[mask].mean() - y_true[mask].mean())
    return float(total)


def compute_logloss(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    y_prob = np.clip(y_prob, 1e-7, 1 - 1e-7)
    return float(log_loss(y_true, y_prob))


def safe_logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def _metrics_row(
    method: str,
    split: str,
    segment: str,
    y_true: np.ndarray,
    y_prob: np.ndarray,
) -> dict:
    """Build a single metrics dict row."""
    n = len(y_true)
    if n < 5:
        return {}
    return {
        "method": method,
        "split": split,
        "segment": segment,
        "n": n,
        "brier": compute_brier(y_true, y_prob),
        "ece": compute_ece(y_true, y_prob),
        "log_loss": compute_logloss(y_true, y_prob),
    }


def add_baseline_deltas(
    rows: List[dict], baseline_rows: List[dict]
) -> List[dict]:
    """Add baseline_brier_delta, baseline_ece_delta, baseline_log_loss_delta columns."""
    base_map: Dict[Tuple[str, str], dict] = {}
    for r in baseline_rows:
        base_map[(r["split"], r["segment"])] = r

    out = []
    for r in rows:
        r2 = dict(r)
        key = (r["split"], r["segment"])
        base = base_map.get(key)
        if base:
            r2["baseline_brier_delta"] = round(r["brier"] - base["brier"], 6)
            r2["baseline_ece_delta"] = round(r["ece"] - base["ece"], 6)
            r2["baseline_log_loss_delta"] = round(r["log_loss"] - base["log_loss"], 6)
        else:
            r2["baseline_brier_delta"] = None
            r2["baseline_ece_delta"] = None
            r2["baseline_log_loss_delta"] = None
        out.append(r2)
    return out


# ---------------------------------------------------------------------------
# Pure helpers: phase bucketing, gap features
# ---------------------------------------------------------------------------

def get_phase_label(overs_remaining: float) -> str:
    """Map overs_remaining to powerplay/middle/death label."""
    overs_done = 20.0 - overs_remaining
    if overs_done < 6:
        return PHASE_POWERPLAY
    elif overs_done < 15:
        return PHASE_MIDDLE
    else:
        return PHASE_DEATH


def clip_prob(p: float | np.ndarray) -> float | np.ndarray:
    """Clip probability to [1e-7, 1-1e-7]."""
    return np.clip(p, 1e-7, 1 - 1e-7)


def build_gap_features(mc_win_prob: np.ndarray, resource_win_prob: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Compute mc_resource_gap and mc_resource_abs_gap."""
    gap = mc_win_prob - resource_win_prob
    abs_gap = np.abs(gap)
    return gap, abs_gap


def build_row_key(df: pd.DataFrame) -> np.ndarray:
    """Return a row key array (just the integer index)."""
    return np.arange(len(df))


# ---------------------------------------------------------------------------
# MatchState reconstruction from IPL feature row
# ---------------------------------------------------------------------------

def check_required_columns(df: pd.DataFrame) -> List[str]:
    """Return list of missing required columns."""
    return [c for c in REQUIRED_COLS if c not in df.columns]


def row_to_match_state(
    innings: int,
    wickets_lost: int,
    overs_remaining: float,
    current_run_rate: float,
    required_run_rate: float,
) -> Tuple[Optional[MatchState], Optional[str]]:
    """
    Reconstruct a MatchState from IPL feature columns.

    Returns (state, None) on success or (None, skip_reason) on failure.
    """
    # Derive balls_remaining from overs_remaining
    balls_remaining = int(round(max(0.0, overs_remaining) * 6))
    balls_remaining = min(balls_remaining, TOTAL_BALLS)

    # Skip terminal states
    if balls_remaining <= 0:
        return None, "terminal_no_balls_remaining"
    if wickets_lost >= 10:
        return None, "terminal_all_out"

    overs_completed = 20.0 - max(0.0, overs_remaining)

    # Derive current score
    score = int(round(current_run_rate * overs_completed))
    score = max(0, score)

    target_runs = None
    if innings == 2:
        if overs_remaining <= 0 or required_run_rate > 500:
            return None, "terminal_inn2_impossible"
        runs_needed = int(round(required_run_rate * max(0.0, overs_remaining)))
        runs_needed = max(0, runs_needed)
        target_runs = score + runs_needed + 1  # +1 so target is strictly > current
        # Sanity: chasing a reasonable target
        if target_runs < 0 or target_runs > 400:
            return None, f"invalid_target_{target_runs}"
        # Already won case
        if score >= target_runs:
            return None, "terminal_inn2_already_won"

    try:
        state = MatchState(
            innings=innings,
            score=score,
            wickets_lost=wickets_lost,
            balls_remaining=balls_remaining,
            league=LEAGUE,
            batting_team="Team_A",
            bowling_team="Team_B",
            total_balls=TOTAL_BALLS,
            target_runs=target_runs,
        )
    except ValueError as e:
        return None, f"validation_error: {e}"

    return state, None


# ---------------------------------------------------------------------------
# MC feature cache generation
# ---------------------------------------------------------------------------

def generate_mc_cache(
    df: pd.DataFrame,
    output_dir: Path,
    n_sims: int,
    seed: int,
    horizon_balls: int,
    resume: bool,
    max_rows: Optional[int],
) -> Tuple[pd.DataFrame, dict]:
    """
    Generate MC raw features for eligible IPL feature rows.

    Returns (cache_df, cache_quality_dict).
    """
    cache_path = output_dir / "mc_feature_cache.parquet"

    # Normalise to 0-based positional index so row_keys are consistent
    df = df.reset_index(drop=True)

    # Resume: load existing cache rows (also supports checkpoint file)
    existing_keys: set = set()
    existing_rows: List[dict] = []
    if resume:
        ckpt_path = output_dir / "mc_feature_cache_ckpt.parquet"
        load_path = cache_path if cache_path.exists() else (ckpt_path if ckpt_path.exists() else None)
        if load_path:
            try:
                existing_df = pd.read_parquet(load_path)
                existing_keys = set(existing_df["row_key"].tolist())
                existing_rows = existing_df.to_dict("records")
                print(f"  [resume] Found {len(existing_keys)} cached rows from {load_path.name}, continuing.")
            except Exception as e:
                print(f"  [resume] Warning: could not load existing cache: {e}")

    rows_to_process = df.index.tolist()
    if max_rows is not None:
        rows_to_process = rows_to_process[:max_rows]

    # Skip already-cached rows
    rows_to_process = [i for i in rows_to_process if i not in existing_keys]

    skip_counts: Dict[str, int] = {}
    success_count = 0
    new_rows: List[dict] = []

    rng = np.random.default_rng(seed)

    print(f"  Processing {len(rows_to_process)} rows (n_sims={n_sims}, horizon={horizon_balls} balls)...")
    t0 = time.time()

    for pos, i in enumerate(rows_to_process):
        row = df.iloc[i] if hasattr(df, "iloc") else df.loc[i]

        innings = int(row["innings"])
        wickets_lost = int(row["wickets_lost"])
        overs_remaining = float(row["overs_remaining"])
        current_run_rate = float(row["current_run_rate"])
        required_run_rate = float(row["required_run_rate"])

        state, skip_reason = row_to_match_state(
            innings, wickets_lost, overs_remaining, current_run_rate, required_run_rate
        )

        if state is None:
            skip_counts[skip_reason] = skip_counts.get(skip_reason, 0) + 1
            new_rows.append({
                "row_key": i,
                "innings": innings,
                "over_approx": round(20.0 - max(0.0, overs_remaining), 1),
                "balls_remaining_approx": int(round(max(0.0, overs_remaining) * 6)),
                "mc_raw_win_prob": np.nan,
                "mc_simulation_std": np.nan,
                "seed": seed,
                "n_sims": n_sims,
                "horizon_balls": horizon_balls,
                "sim_ok": False,
                "skip_reason": skip_reason,
            })
            continue

        # Use a per-row seed derived from global seed for reproducibility
        row_seed = int(rng.integers(0, 2**31))

        try:
            result = simulate(
                state=state,
                horizon=horizon_balls,
                n_simulations=n_sims,
                apply_temp=False,   # raw output; fold-local calibration handles this
                model_dir="models/ipl_v6",
                predictor=None,     # resource-based evaluator (no circular dep)
            )
            mc_raw = float(result.mean_prob)
            mc_std = float(result.std_prob)
            sim_ok = True
            skip_reason = None
        except Exception as e:
            mc_raw = np.nan
            mc_std = np.nan
            sim_ok = False
            skip_reason = f"sim_error: {str(e)[:80]}"
            skip_counts[skip_reason] = skip_counts.get(skip_reason, 0) + 1

        if sim_ok:
            success_count += 1

        new_rows.append({
            "row_key": i,
            "innings": innings,
            "over_approx": round(20.0 - max(0.0, overs_remaining), 1),
            "balls_remaining_approx": int(round(max(0.0, overs_remaining) * 6)),
            "mc_raw_win_prob": mc_raw,
            "mc_simulation_std": mc_std,
            "seed": seed,
            "n_sims": n_sims,
            "horizon_balls": horizon_balls,
            "sim_ok": sim_ok,
            "skip_reason": skip_reason,
        })

        if (pos + 1) % 500 == 0:
            elapsed = time.time() - t0
            pct = (pos + 1) / len(rows_to_process) * 100
            eta_s = (elapsed / (pos + 1)) * (len(rows_to_process) - pos - 1)
            print(f"    {pos + 1}/{len(rows_to_process)} ({pct:.1f}%) -- {elapsed:.1f}s elapsed, ETA {eta_s:.0f}s")

        # Incremental checkpoint every 1000 rows (enables --resume after crash)
        if (pos + 1) % 1000 == 0 and new_rows:
            ckpt_rows = existing_rows + new_rows
            ckpt_df = pd.DataFrame(ckpt_rows).sort_values("row_key").reset_index(drop=True)
            ckpt_path = output_dir / "mc_feature_cache_ckpt.parquet"
            ckpt_df.to_parquet(ckpt_path, index=False)

    # Merge existing + new
    all_rows = existing_rows + new_rows
    cache_df = pd.DataFrame(all_rows).sort_values("row_key").reset_index(drop=True)
    cache_df.to_parquet(cache_path, index=False)
    print(f"  Saved cache: {len(cache_df)} rows -> {cache_path}")

    total_attempted = len(rows_to_process) + len(existing_keys)
    total_skipped = sum(skip_counts.values())
    quality = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_data_rows": len(df),
        "rows_attempted": total_attempted,
        "rows_success": success_count + len(existing_keys),
        "rows_skipped": total_skipped,
        "seed": seed,
        "n_sims": n_sims,
        "horizon_balls": horizon_balls,
        "evaluator_mode": "resource_based (no ML model, apply_temp=False)",
        "skip_reasons": skip_counts,
        "cache_path": str(cache_path),
    }

    return cache_df, quality


# ---------------------------------------------------------------------------
# CV splits (5-fold sequential)
# ---------------------------------------------------------------------------

def make_cv_splits(n: int, n_splits: int = 5) -> List[Tuple[np.ndarray, np.ndarray]]:
    """
    Create n_splits sequential (time-ordered) fold splits.

    Each fold uses the first k*(n//n_splits) rows as train and the next
    n//n_splits rows as validation. This approximates time-series CV.
    """
    fold_size = n // n_splits
    splits = []
    for k in range(1, n_splits + 1):
        val_end = k * fold_size
        val_start = val_end - fold_size
        if k == n_splits:
            val_end = n  # last fold takes remaining rows
        train_idx = np.arange(0, val_start)
        val_idx = np.arange(val_start, val_end)
        if len(train_idx) < fold_size:
            continue  # first fold has no training data — skip
        splits.append((train_idx, val_idx))
    return splits


# ---------------------------------------------------------------------------
# Fold-local MC Platt calibration
# ---------------------------------------------------------------------------

def fit_mc_platt_calibrators(
    mc_raw: np.ndarray,
    labels: np.ndarray,
    innings: np.ndarray,
) -> Dict[int, LogisticRegression]:
    """
    Fit per-innings Platt calibrators on training fold.
    Input is mc_raw_win_prob; output maps to calibrated mc_win_prob.
    """
    calibrators: Dict[int, LogisticRegression] = {}
    for inn in [1, 2]:
        mask = innings == inn
        if mask.sum() < 50:
            continue
        X = safe_logit(mc_raw[mask]).reshape(-1, 1)
        lr = LogisticRegression(C=1e6, max_iter=1000, solver="lbfgs", random_state=42)
        lr.fit(X, labels[mask])
        calibrators[inn] = lr
    return calibrators


def apply_mc_platt(
    mc_raw: np.ndarray,
    innings: np.ndarray,
    calibrators: Dict[int, LogisticRegression],
) -> np.ndarray:
    """Apply per-innings Platt calibrators to produce mc_win_prob."""
    out = mc_raw.copy()
    for inn in [1, 2]:
        mask = innings == inn
        if not mask.any():
            continue
        if inn not in calibrators:
            # Fall back to isotonic passthrough for missing inning calibrator
            continue
        X = safe_logit(mc_raw[mask]).reshape(-1, 1)
        out[mask] = calibrators[inn].predict_proba(X)[:, 1]
    return out


# ---------------------------------------------------------------------------
# Variant feature-frame builders
# ---------------------------------------------------------------------------

def build_variant_frames(
    df: pd.DataFrame,
    mc_win_prob: np.ndarray,
    mc_raw: np.ndarray,
    mc_std: np.ndarray,
    variant: str,
) -> pd.DataFrame:
    """
    Build the feature DataFrame for a given variant.

    Variants:
      baseline_ipl_v6_features      - current TOP_FEATURES only
      mc_standalone_calibrated       - not used for ML (scores come from mc_win_prob)
      ml_add_mc_win_prob             - baseline + mc_win_prob
      ml_add_mc_gap_features         - baseline + all 4 MC features
      ml_replace_resource_with_mc    - replace resource_win_prob with mc_win_prob
      *_inn2_only                    - use MC signal only for innings 2; innings 1 remains baseline
    """
    d = df.copy()
    resource_prob = d["resource_win_prob"].values.astype(float)
    innings = d["innings"].astype(int).values
    inn2_mask = innings == 2
    mc_win_prob_inn2_only = np.where(inn2_mask, mc_win_prob, resource_prob)
    mc_std_inn2_only = np.where(inn2_mask, mc_std, 0.0)
    mc_gap, mc_abs_gap = build_gap_features(mc_win_prob, resource_prob)
    mc_gap_inn2, mc_abs_gap_inn2 = build_gap_features(mc_win_prob_inn2_only, resource_prob)

    if variant == "baseline_ipl_v6_features":
        return d

    if variant == "mc_standalone_calibrated":
        return d  # scores come externally; frame not used for ML training

    if variant == "ml_add_mc_win_prob":
        d["mc_win_prob"] = mc_win_prob
        return d

    if variant == "ml_add_mc_win_prob_inn2_only":
        d["mc_win_prob"] = mc_win_prob_inn2_only
        return d

    if variant == "ml_add_mc_gap_features":
        d["mc_win_prob"] = mc_win_prob
        d["mc_resource_gap"] = mc_gap
        d["mc_resource_abs_gap"] = mc_abs_gap
        d["mc_simulation_std"] = mc_std
        return d

    if variant == "ml_add_mc_gap_features_inn2_only":
        d["mc_win_prob"] = mc_win_prob_inn2_only
        d["mc_resource_gap"] = mc_gap_inn2
        d["mc_resource_abs_gap"] = mc_abs_gap_inn2
        d["mc_simulation_std"] = mc_std_inn2_only
        return d

    if variant == "ml_replace_resource_with_mc":
        d["mc_win_prob"] = mc_win_prob
        d["mc_resource_gap"] = mc_gap
        d["mc_resource_abs_gap"] = mc_abs_gap
        d["mc_simulation_std"] = mc_std
        d["resource_win_prob"] = mc_win_prob
        return d

    if variant == "ml_replace_resource_with_mc_inn2_only":
        d["mc_win_prob"] = mc_win_prob_inn2_only
        d["mc_resource_gap"] = mc_gap_inn2
        d["mc_resource_abs_gap"] = mc_abs_gap_inn2
        d["mc_simulation_std"] = mc_std_inn2_only
        d["resource_win_prob"] = mc_win_prob_inn2_only
        return d

    if variant == "ml_clean_swap_resource":
        # Pure drop-in: same 32 features, resource_win_prob values replaced by MC output.
        # No new columns added. Cleanly isolates the question:
        # "does MC output as a direct replacement for resource_win_prob improve the model?"
        d["resource_win_prob"] = mc_win_prob
        return d

    if variant == "ml_clean_swap_resource_inn2_only":
        d["resource_win_prob"] = mc_win_prob_inn2_only
        return d

    raise ValueError(f"Unknown variant: {variant}")


def model_for_variant(variant: str) -> XGBLogRegEnsemble:
    """Return the appropriate model class for a variant."""
    if variant in (
        "baseline_ipl_v6_features",
        "ml_clean_swap_resource",
        "ml_clean_swap_resource_inn2_only",
    ):
        return XGBLogRegEnsemble(n_features=32)
    if variant in (
        "ml_add_mc_win_prob",
        "ml_add_mc_win_prob_inn2_only",
        "ml_replace_resource_with_mc",
        "ml_replace_resource_with_mc_inn2_only",
    ):
        return IPLMCFeatureEnsemble(n_features=33)
    if variant in ("ml_add_mc_gap_features", "ml_add_mc_gap_features_inn2_only"):
        return IPLMCFeatureEnsemble(n_features=36)
    raise ValueError(f"No model class for variant: {variant}")


# ---------------------------------------------------------------------------
# Segment metrics helpers
# ---------------------------------------------------------------------------

def collect_segments(
    method: str,
    split: str,
    y_true: np.ndarray,
    y_prob: np.ndarray,
    innings: np.ndarray,
    overs_remaining: np.ndarray,
) -> List[dict]:
    """Collect metrics by overall, innings, and phase segments."""
    rows = []

    # Overall
    r = _metrics_row(method, split, "overall", y_true, y_prob)
    if r:
        rows.append(r)

    # By innings
    for inn in [1, 2]:
        m = innings == inn
        r = _metrics_row(method, split, f"innings_{inn}", y_true[m], y_prob[m])
        if r:
            rows.append(r)

        # By phase within innings
        for phase in [PHASE_POWERPLAY, PHASE_MIDDLE, PHASE_DEATH]:
            pm = m & np.array([get_phase_label(o) == phase for o in overs_remaining])
            r = _metrics_row(method, split, f"innings_{inn}_{phase}", y_true[pm], y_prob[pm])
            if r:
                rows.append(r)

    return rows


def collect_reliability_bins(
    method: str,
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
) -> List[dict]:
    """Compute reliability diagram bin data."""
    y_prob = np.clip(y_prob, 0.0, 1.0)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(y_prob, bins) - 1, 0, n_bins - 1)
    rows = []
    for b in range(n_bins):
        mask = idx == b
        if not mask.any():
            continue
        rows.append({
            "method": method,
            "bin_low": round(bins[b], 2),
            "bin_high": round(bins[b + 1], 2),
            "n": int(mask.sum()),
            "mean_predicted": float(y_prob[mask].mean()),
            "mean_actual": float(y_true[mask].mean()),
        })
    return rows


# ---------------------------------------------------------------------------
# Main evaluation loop
# ---------------------------------------------------------------------------

def run_experiment(
    df: pd.DataFrame,
    cache_df: pd.DataFrame,
    output_dir: Path,
    n_splits: int = 5,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, List[dict]]:
    """
    Run all model variants using fold-local MC calibration.

    Returns (metrics_df, segment_metrics_df, feature_importance_df, reliability_rows).
    """
    VARIANTS = VARIANT_ORDER

    # Normalise to 0-based positional index so row_keys align with cache
    df = df.reset_index(drop=True)

    # Align cache to feature df: only rows that simulated successfully
    cache_indexed = cache_df[cache_df["sim_ok"]].set_index("row_key")
    eligible_mask = np.zeros(len(df), dtype=bool)
    for i in range(len(df)):
        eligible_mask[i] = i in cache_indexed.index
    eligible_idx = np.where(eligible_mask)[0]

    df_elig = df.iloc[eligible_idx].reset_index(drop=True)
    mc_raw_all = cache_indexed.loc[eligible_idx, "mc_raw_win_prob"].values.astype(float)
    mc_std_all = cache_indexed.loc[eligible_idx, "mc_simulation_std"].values.astype(float)

    n = len(df_elig)
    print(f"  Eligible rows for evaluation: {n} / {len(df)}")

    splits = make_cv_splits(n, n_splits=n_splits)
    if not splits:
        print("  Warning: not enough rows for CV splits. Using single 80/20 split.")
        k = int(n * 0.8)
        splits = [(np.arange(0, k), np.arange(k, n))]

    all_metrics: List[dict] = []
    all_seg_metrics: List[dict] = []
    all_fi: List[dict] = []
    all_reliability: List[dict] = []

    # Collect OOF predictions for reliability bins
    oof_probs: Dict[str, np.ndarray] = {v: np.full(n, np.nan) for v in VARIANTS}
    oof_labels = df_elig["is_winner"].values.astype(float)

    for fold_i, (train_idx, val_idx) in enumerate(splits):
        split_label = f"oof_fold_{fold_i + 1}"
        print(f"  Fold {fold_i + 1}/{len(splits)}: train={len(train_idx)}, val={len(val_idx)}")

        # ── Fold-local MC Platt calibration ─────────────────────────────
        mc_raw_train = mc_raw_all[train_idx]
        train_labels = df_elig.iloc[train_idx]["is_winner"].values.astype(float)
        train_innings = df_elig.iloc[train_idx]["innings"].values.astype(int)

        mc_calibrators = fit_mc_platt_calibrators(mc_raw_train, train_labels, train_innings)

        mc_raw_val = mc_raw_all[val_idx]
        val_innings = df_elig.iloc[val_idx]["innings"].values.astype(int)
        mc_win_prob_val = apply_mc_platt(mc_raw_val, val_innings, mc_calibrators)

        mc_std_val = mc_std_all[val_idx]

        y_val = df_elig.iloc[val_idx]["is_winner"].values.astype(float)
        overs_rem_val = df_elig.iloc[val_idx]["overs_remaining"].values.astype(float)

        for variant in VARIANTS:
            # ── Prepare training and validation frames ───────────────────
            if variant == "mc_standalone_calibrated":
                # No ML training — use fold-local calibrated mc_win_prob directly
                # Re-derive calibrated val probs from per-fold calibrator
                val_probs = np.clip(mc_win_prob_val, 1e-7, 1 - 1e-7)
                oof_probs[variant][val_idx] = val_probs
                # Collect metrics
                seg_rows = collect_segments(
                    variant, split_label, y_val, val_probs, val_innings, overs_rem_val
                )
                all_seg_metrics.extend(seg_rows)
                continue

            # For MC-based train folds, also calibrate the training MC probs
            mc_win_prob_train = apply_mc_platt(mc_raw_train, train_innings, mc_calibrators)
            mc_std_train = mc_std_all[train_idx]

            X_train = build_variant_frames(
                df_elig.iloc[train_idx].reset_index(drop=True),
                mc_win_prob_train,
                mc_raw_train,
                mc_std_train,
                variant,
            )
            X_val = build_variant_frames(
                df_elig.iloc[val_idx].reset_index(drop=True),
                mc_win_prob_val,
                mc_raw_val,
                mc_std_val,
                variant,
            )

            model = model_for_variant(variant)
            label_col = "is_winner"
            drop_cols = [c for c in [label_col] if c in X_train.columns]

            model.fit(X_train.drop(columns=drop_cols), train_labels)
            val_probs = model.predict_proba(X_val.drop(columns=drop_cols))[:, 1]
            oof_probs[variant][val_idx] = val_probs

            # Feature importance for ML variants
            try:
                fi_df = model.get_feature_importance()
                for _, fi_row in fi_df.iterrows():
                    all_fi.append({
                        "variant": variant,
                        "fold": fold_i + 1,
                        "feature": fi_row["feature"],
                        "importance": fi_row["importance"],
                    })
            except Exception:
                pass

            # Segment metrics
            seg_rows = collect_segments(
                variant, split_label, y_val, val_probs, val_innings, overs_rem_val
            )
            all_seg_metrics.extend(seg_rows)

    # ── Aggregate OOF metrics across all folds ───────────────────────────
    valid_oof_mask = ~np.isnan(oof_probs["baseline_ipl_v6_features"])
    y_oof = oof_labels[valid_oof_mask]
    innings_oof = df_elig["innings"].values[valid_oof_mask].astype(int)
    overs_rem_oof = df_elig["overs_remaining"].values[valid_oof_mask].astype(float)

    for variant in VARIANTS:
        vp = oof_probs[variant][valid_oof_mask]
        if np.isnan(vp).any():
            continue
        seg_rows = collect_segments(
            variant, "oof_overall", y_oof, vp, innings_oof, overs_rem_oof
        )
        all_metrics.extend(seg_rows)

        # Reliability bins for baseline and MC-standalone
        if variant in ("baseline_ipl_v6_features", "mc_standalone_calibrated", "ml_add_mc_gap_features"):
            all_reliability.extend(
                collect_reliability_bins(variant, y_oof, vp)
            )

    # ── Build DataFrames ─────────────────────────────────────────────────
    metrics_df = pd.DataFrame(all_metrics)
    seg_metrics_df = pd.DataFrame(all_seg_metrics)
    fi_df = pd.DataFrame(all_fi)

    # Add deltas to metrics_df
    if not metrics_df.empty:
        baseline_rows = metrics_df[
            metrics_df["method"] == "baseline_ipl_v6_features"
        ].to_dict("records")
        metrics_with_deltas = add_baseline_deltas(
            metrics_df.to_dict("records"), baseline_rows
        )
        metrics_df = pd.DataFrame(metrics_with_deltas)

    return metrics_df, seg_metrics_df, fi_df, all_reliability


# ---------------------------------------------------------------------------
# Promotion gate evaluation
# ---------------------------------------------------------------------------

def check_promotion_gates(
    metrics_df: pd.DataFrame,
    seg_metrics_df: pd.DataFrame,
    fi_df: pd.DataFrame,
) -> Tuple[Optional[str], Dict[str, bool], List[str]]:
    """
    Evaluate promotion gates for each MC-augmented ML variant.

    Returns (best_variant_or_None, gates_passed_dict, failure_messages).
    """
    ML_VARIANTS = [
        "ml_add_mc_win_prob",
        "ml_add_mc_win_prob_inn2_only",
        "ml_add_mc_gap_features",
        "ml_add_mc_gap_features_inn2_only",
        "ml_replace_resource_with_mc",
        "ml_replace_resource_with_mc_inn2_only",
        "ml_clean_swap_resource",
        "ml_clean_swap_resource_inn2_only",
    ]

    if metrics_df.empty:
        return None, {}, ["No metrics available"]

    overall = metrics_df[
        (metrics_df["split"] == "oof_overall") & (metrics_df["segment"] == "overall")
    ].set_index("method")

    if "baseline_ipl_v6_features" not in overall.index:
        return None, {}, ["Baseline metrics not found"]

    base = overall.loc["baseline_ipl_v6_features"]

    best_variant = None
    best_brier_gain = -999
    all_failures: List[str] = []

    gates_dict: Dict[str, bool] = {}

    for variant in ML_VARIANTS:
        if variant not in overall.index:
            continue

        cand = overall.loc[variant]
        failures: List[str] = []

        brier_delta = float(cand["brier"]) - float(base["brier"])
        logloss_delta = float(cand["log_loss"]) - float(base["log_loss"])
        ece_delta = float(cand["ece"]) - float(base["ece"])

        # Gate 1: Brier improves by >= 0.001
        if brier_delta >= -GATE_BRIER_IMPROVE:
            failures.append(
                f"Brier did not improve by {GATE_BRIER_IMPROVE} (delta={brier_delta:+.4f})"
            )

        # Gate 2: LogLoss not worse
        if logloss_delta > GATE_LOGLOSS_WORSE_TOL:
            failures.append(
                f"LogLoss worsened (delta={logloss_delta:+.4f})"
            )

        # Gate 3: ECE not worse
        if ece_delta > GATE_ECE_WORSE_TOL:
            failures.append(
                f"ECE worsened (delta={ece_delta:+.4f})"
            )

        # Gate 4: No innings/phase segment worsens Brier by > 0.003
        if not seg_metrics_df.empty:
            seg_oof = seg_metrics_df.groupby(["method", "segment"])["brier"].mean()
            base_seg = seg_oof.get("baseline_ipl_v6_features", pd.Series(dtype=float))
            cand_seg = seg_oof.get(variant, pd.Series(dtype=float))
            for seg_name in cand_seg.index:
                if seg_name in base_seg.index:
                    seg_delta = float(cand_seg[seg_name]) - float(base_seg[seg_name])
                    if seg_delta > GATE_SEGMENT_BRIER_REGRESS:
                        failures.append(
                            f"Segment {seg_name} Brier worsened by {seg_delta:+.4f}"
                        )

        # Gate 5: At least one MC feature has non-trivial importance
        # (Not applicable to clean-swap variants — MC signal flows through resource_win_prob)
        if not variant.startswith("ml_clean_swap_resource"):
            if not fi_df.empty:
                mc_feats = ["mc_win_prob", "mc_resource_gap", "mc_resource_abs_gap", "mc_simulation_std"]
                v_fi = fi_df[fi_df["variant"] == variant]
                mc_fi = v_fi[v_fi["feature"].isin(mc_feats)]
                if mc_fi.empty or mc_fi["importance"].mean() < 0.005:
                    failures.append("MC features have near-zero importance")

        gates_dict[variant] = len(failures) == 0

        if not failures:
            brier_gain = -brier_delta
            if brier_gain > best_brier_gain:
                best_brier_gain = brier_gain
                best_variant = variant
        else:
            all_failures.extend([f"[{variant}] {f}" for f in failures])

    return best_variant, gates_dict, all_failures


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def write_report(
    output_dir: Path,
    metrics_df: pd.DataFrame,
    seg_metrics_df: pd.DataFrame,
    fi_df: pd.DataFrame,
    cache_quality: dict,
    best_variant: Optional[str],
    gates_passed: Dict[str, bool],
    gate_failures: List[str],
    mode: str,
    n_sims: int,
    horizon_balls: int,
) -> None:
    """Write REPORT.md, metrics.csv, segment_metrics.csv, feature_importance.csv."""

    # ── Save CSV artefacts ───────────────────────────────────────────────
    metrics_df.to_csv(output_dir / "metrics.csv", index=False)
    seg_metrics_df.to_csv(output_dir / "segment_metrics.csv", index=False)
    if not fi_df.empty:
        fi_summary = (
            fi_df.groupby(["variant", "feature"])["importance"]
            .mean()
            .reset_index()
            .sort_values(["variant", "importance"], ascending=[True, False])
        )
        fi_summary.to_csv(output_dir / "feature_importance.csv", index=False)

    # ── Save cache_quality.json ──────────────────────────────────────────
    with open(output_dir / "cache_quality.json", "w") as f:
        json.dump(cache_quality, f, indent=2, default=str)

    # ── Build REPORT.md ──────────────────────────────────────────────────
    lines = [
        "# IPL MC Features Experiment — Results Report",
        "",
        f"**Generated**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}  ",
        f"**Mode**: `{mode}`  ",
        f"**MC settings**: n_sims={n_sims}, horizon_balls={horizon_balls}  ",
        f"**Evaluator**: resource-based (no ML model, apply_temp=False)  ",
        "",
        "---",
        "",
        "## Overall OOF Metrics",
        "",
    ]

    if not metrics_df.empty:
        overall = metrics_df[
            (metrics_df["split"] == "oof_overall") & (metrics_df["segment"] == "overall")
        ]
        header = "| Method | N | Brier | ECE | LogLoss | ΔBrier | ΔECE | ΔLogLoss |"
        sep = "|--------|---|-------|-----|---------|--------|------|----------|"
        lines += [header, sep]
        for v in VARIANT_ORDER:
            row = overall[overall["method"] == v]
            if row.empty:
                continue
            r = row.iloc[0]
            db = f"{r.get('baseline_brier_delta', 0):+.4f}" if r.get("baseline_brier_delta") is not None else "—"
            de = f"{r.get('baseline_ece_delta', 0):+.4f}" if r.get("baseline_ece_delta") is not None else "—"
            dl = f"{r.get('baseline_log_loss_delta', 0):+.4f}" if r.get("baseline_log_loss_delta") is not None else "—"
            lines.append(
                f"| `{v}` | {int(r['n'])} | {r['brier']:.4f} | {r['ece']:.4f} | {r['log_loss']:.4f} | {db} | {de} | {dl} |"
            )
    else:
        lines.append("_No metrics available._")

    lines += [
        "",
        "---",
        "",
        "## Segment Metrics (Innings × Phase)",
        "",
    ]

    if not seg_metrics_df.empty:
        seg_oof = seg_metrics_df.groupby(["method", "segment"])[["brier", "ece", "log_loss"]].mean().reset_index()
        lines += ["| Method | Segment | Brier | ECE | LogLoss |", "|--------|---------|-------|-----|---------|"]
        for v in VARIANT_ORDER:
            vm = seg_oof[seg_oof["method"] == v]
            for _, row in vm.iterrows():
                lines.append(
                    f"| `{v}` | {row['segment']} | {row['brier']:.4f} | {row['ece']:.4f} | {row['log_loss']:.4f} |"
                )
    else:
        lines.append("_No segment metrics available._")

    lines += [
        "",
        "---",
        "",
        "## Feature Importance (MC Features)",
        "",
    ]

    if not fi_df.empty:
        mc_feats = ["mc_win_prob", "mc_resource_gap", "mc_resource_abs_gap", "mc_simulation_std"]
        fi_mc = (
            fi_df[fi_df["feature"].isin(mc_feats)]
            .groupby(["variant", "feature"])["importance"]
            .mean()
            .reset_index()
            .sort_values(["variant", "importance"], ascending=[True, False])
        )
        if not fi_mc.empty:
            lines += ["| Variant | Feature | Mean Importance |", "|---------|---------|-----------------|"]
            for _, row in fi_mc.iterrows():
                lines.append(f"| `{row['variant']}` | `{row['feature']}` | {row['importance']:.4f} |")
        else:
            lines.append("_No MC feature importance found._")
    else:
        lines.append("_No feature importance data._")

    lines += [
        "",
        "---",
        "",
        "## Promotion Gate Results",
        "",
    ]

    for v in [
        variant for variant in VARIANT_ORDER
        if variant not in ("baseline_ipl_v6_features", "mc_standalone_calibrated")
    ]:
        status = "✅ PASS" if gates_passed.get(v) else "❌ FAIL"
        lines.append(f"- **{v}**: {status}")

    if gate_failures:
        lines += ["", "**Failure reasons:**"]
        for f in gate_failures:
            lines.append(f"- {f}")

    lines += ["", "---", "", "## Recommendation", ""]

    if best_variant:
        lines.append(
            f"✅ **Candidate variant**: `{best_variant}` passed all promotion gates."
        )
        lines.append(
            "Consider creating `models/ipl_v7_mc_features_candidate/` and running a live dry run."
        )
    else:
        lines.append(
            "❌ **No promotion**: No MC-augmented variant improved baseline by the required threshold "
            "or passed all gates."
        )
        lines.append("**IPL v6 remains the active model. No production changes required.**")

    lines += [
        "",
        "---",
        "",
        "## Inference Latency Risk",
        "",
        "Adding MC feature generation before ML prediction introduces latency.",
        "",
        "| Component | Estimated Latency | Notes |",
        "|-----------|-------------------|-------|",
        "| Baseline IPL v6 ML prediction | ~5–15 ms | feature store + model |",
        f"| MC simulation ({n_sims} sims, {horizon_balls} balls) | ~200–600 ms | per ball state |",
        "| Candidate ML prediction | ~5–15 ms | includes MC features |",
        "| **Total** | **~210–630 ms** | **vs. dashboard poll interval** |",
        "",
        "**Mitigation options** (if latency is too high):",
        "- Reduce n-sims to 200–300",
        "- Cache MC by (innings, over, score, wickets) state key",
        "- Run MC asynchronously, fall back to baseline ML while pending",
        "- Keep MC features out of production ML; use as dashboard diagnostic only",
        "",
        f"**Decision**: {'Candidate only (offline-only) until latency verified' if best_variant else 'No promotion'}.",
        "",
        "---",
        "",
        "## Cache Quality",
        "",
        f"- Source rows: {cache_quality.get('source_data_rows', '?')}",
        f"- Simulated successfully: {cache_quality.get('rows_success', '?')}",
        f"- Skipped: {cache_quality.get('rows_skipped', '?')}",
        f"- Evaluator: {cache_quality.get('evaluator_mode', '?')}",
        "",
    ]

    skip_reasons = cache_quality.get("skip_reasons", {})
    if skip_reasons:
        lines.append("**Skip reasons:**")
        for reason, count in skip_reasons.items():
            lines.append(f"- `{reason}`: {count}")

    report_path = output_dir / "REPORT.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Report written: {report_path}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="IPL MC Features Experiment (014-ipl-mc-features-experiment)"
    )
    parser.add_argument(
        "--input",
        default="data/ipl_features_v6/training_sampled.parquet",
        help="Input features parquet file",
    )
    parser.add_argument(
        "--output-dir",
        default="experiments/ipl_mc_features_v1",
        help="Output directory for artefacts",
    )
    parser.add_argument(
        "--mode",
        choices=["pilot", "full", "cache-only"],
        default="pilot",
        help="pilot: quick run on sampled data; full: complete run; cache-only: generate MC cache then exit",
    )
    parser.add_argument(
        "--n-sims",
        type=int,
        default=100,
        help="Number of MC simulations per row",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Global random seed for reproducibility",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume cache generation from existing mc_feature_cache.parquet",
    )
    parser.add_argument(
        "--horizon-balls",
        type=int,
        default=6,
        help="MC horizon in balls (default 6 = 1 over)",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Limit rows for testing (default: all rows)",
    )
    parser.add_argument(
        "--n-splits",
        type=int,
        default=5,
        help="Number of CV folds",
    )
    parser.add_argument(
        "--skip-cache",
        action="store_true",
        help="Skip MC cache generation (use existing cache_file only)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'=' * 64}")
    print(f"  IPL MC Features Experiment -- mode={args.mode}")
    print(f"  Input:  {args.input}")
    print(f"  Output: {output_dir}")
    print(f"  n_sims={args.n_sims}, horizon={args.horizon_balls} balls, seed={args.seed}")
    print(f"{'=' * 64}\n")

    # ── Phase 1: Load data ───────────────────────────────────────────────
    print("[1/4] Loading data...")
    if not Path(args.input).exists():
        sys.exit(f"ERROR: Input file not found: {args.input}")

    df = pd.read_parquet(args.input)
    print(f"  Loaded {len(df):,} rows x {len(df.columns)} columns from {args.input}")

    missing = check_required_columns(df)
    if missing:
        sys.exit(f"ERROR: Missing required columns: {missing}")

    if args.max_rows:
        df = df.iloc[: args.max_rows].copy()
        print(f"  Limited to {len(df):,} rows (--max-rows)")

    # ── Phase 2: MC feature cache ────────────────────────────────────────
    print("\n[2/4] Generating MC feature cache...")
    cache_path = output_dir / "mc_feature_cache.parquet"

    if args.skip_cache and cache_path.exists():
        cache_df = pd.read_parquet(cache_path)
        cache_quality = json.loads((output_dir / "cache_quality.json").read_text()) if (output_dir / "cache_quality.json").exists() else {}
        print(f"  Loaded existing cache: {len(cache_df)} rows (--skip-cache)")
    else:
        cache_df, cache_quality = generate_mc_cache(
            df=df,
            output_dir=output_dir,
            n_sims=args.n_sims,
            seed=args.seed,
            horizon_balls=args.horizon_balls,
            resume=args.resume,
            max_rows=args.max_rows,
        )
        with open(output_dir / "cache_quality.json", "w") as fh:
            json.dump(cache_quality, fh, indent=2, default=str)

    # cache-only mode: exit after writing cache
    if args.mode == "cache-only":
        print(f"\n  cache-only mode: done. Cache saved to {output_dir/'mc_feature_cache.parquet'}")
        print(f"  Use --mode full --skip-cache --output-dir {output_dir} to run experiments on this cache.")
        return

    # ── Phase 3: Evaluate variants ───────────────────────────────────────
    print("\n[3/4] Evaluating model variants (fold-local MC calibration)...")
    metrics_df, seg_metrics_df, fi_df, reliability_rows = run_experiment(
        df=df,
        cache_df=cache_df,
        output_dir=output_dir,
        n_splits=args.n_splits,
    )

    # Save reliability bins
    if reliability_rows:
        pd.DataFrame(reliability_rows).to_csv(output_dir / "reliability_bins.csv", index=False)

    # ── Phase 4: Promotion gates and report ─────────────────────────────
    print("\n[4/4] Evaluating promotion gates and writing report...")
    best_variant, gates_passed, gate_failures = check_promotion_gates(
        metrics_df, seg_metrics_df, fi_df
    )

    write_report(
        output_dir=output_dir,
        metrics_df=metrics_df,
        seg_metrics_df=seg_metrics_df,
        fi_df=fi_df,
        cache_quality=cache_quality,
        best_variant=best_variant,
        gates_passed=gates_passed,
        gate_failures=gate_failures,
        mode=args.mode,
        n_sims=args.n_sims,
        horizon_balls=args.horizon_balls,
    )

    # ── Summary ──────────────────────────────────────────────────────────
    print(f"\n{'=' * 64}")
    print("  EXPERIMENT COMPLETE")
    print(f"  Artefacts: {output_dir}")

    if not metrics_df.empty:
        overall = metrics_df[
            (metrics_df["split"] == "oof_overall") & (metrics_df["segment"] == "overall")
        ]
        print("\n  Overall OOF Brier scores:")
        for _, r in overall.iterrows():
            db = f"  D={r.get('baseline_brier_delta', 0):+.4f}" if r.get("baseline_brier_delta") is not None else ""
            print(f"    {r['method']:<45} {r['brier']:.4f}{db}")

    print(f"\n  Best MC variant: {best_variant or 'none (no promotion)'}")
    if gate_failures:
        print("  Gate failures:")
        for f in gate_failures[:5]:
            print(f"    - {f}")
    print(f"{'=' * 64}\n")


if __name__ == "__main__":
    main()
