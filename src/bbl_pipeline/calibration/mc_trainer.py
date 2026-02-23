"""
MC Calibrator Training Module.

Backtests MC predictions against actual match outcomes from Cricsheet
JSON files and fits a Platt-scaling calibrator to correct systematic
biases in the resource_win_prob heuristic.

Integration:
    CLI:  ``bbl-pipeline calibrate-mc --json-dir <dir> --model-dir <dir>``
    Code: ``MCCalibratorTrainer(json_dir, model_dir).run()``

The trainer:
  1. Scans a directory of Cricsheet JSON match files
  2. For each completed match, replays innings 2 ball-by-ball
  3. At each over boundary, runs a short MC simulation to get raw probability
  4. Collects (raw_mc_prob, actual_outcome) pairs
  5. Splits 80/20, fits Platt scaling on train, evaluates on val
  6. Saves ``mc_calibrator.pkl`` to the model directory
"""

from __future__ import annotations

import glob
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import numpy as np
import structlog

from bbl_pipeline.calibration.mc_calibrator import MCCalibrator, InningsMCCalibrators
from bbl_pipeline.simulation.state import MatchState
from bbl_pipeline.simulation.engine import simulate

logger = structlog.get_logger()


def _count_legal(delivery: dict) -> int:
    """Return 1 for a legal delivery, 0 for wide/no-ball."""
    extras = delivery.get("extras", {})
    if "wides" in extras or "noballs" in extras:
        return 0
    return 1


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


@dataclass
class MCTrainerResult:
    """Result of MC calibrator training."""

    calibrator: MCCalibrator
    output_path: str
    n_matches: int
    n_predictions: int
    n_train: int
    n_val: int
    raw_brier: float
    cal_brier: float
    raw_ece: float
    cal_ece: float
    elapsed_seconds: float
    reliability: list = field(default_factory=list)

    @property
    def brier_improvement(self) -> float:
        return self.raw_brier - self.cal_brier

    @property
    def ece_improvement(self) -> float:
        return self.raw_ece - self.cal_ece

    def summary(self) -> str:
        lines = [
            f"MC Calibrator Training Summary",
            f"{'='*50}",
            f"  Matches analyzed:   {self.n_matches}",
            f"  Prediction points:  {self.n_predictions}",
            f"  Train/Val split:    {self.n_train}/{self.n_val}",
            f"  Elapsed:            {self.elapsed_seconds:.1f}s",
            f"",
            f"  Validation Metrics:",
            f"  {'Metric':<12} {'Raw':>10} {'Calibrated':>10} {'Delta':>10}",
            f"  {'-'*42}",
            f"  {'Brier':<12} {self.raw_brier:>10.4f} {self.cal_brier:>10.4f} {self.cal_brier - self.raw_brier:>+10.4f}",
            f"  {'ECE':<12} {self.raw_ece:>10.4f} {self.cal_ece:>10.4f} {self.cal_ece - self.raw_ece:>+10.4f}",
            f"",
            f"  Output: {self.output_path}",
        ]
        return "\n".join(lines)


def collect_predictions_from_match(
    filepath: str,
    league: str = "bbl",
    n_sims: int = 200,
    model_dir: str = "models/t20_male_v2",
    innings_filter: Optional[int] = None,
) -> List[dict]:
    """Run MC predictions at each over-end and return (pred, outcome) pairs.

    Collects predictions from both innings by default.  Set
    ``innings_filter=1`` or ``innings_filter=2`` to restrict to a single
    innings.

    Parameters
    ----------
    filepath : str
        Path to a Cricsheet JSON file.
    league : str
        League code for sampler distributions.
    n_sims : int
        Number of MC simulations per checkpoint.
    model_dir : str
        Model directory for sampler/evaluator.
    innings_filter : int, optional
        If set, only collect from this innings (1 or 2). Default collects both.

    Returns
    -------
    list[dict]
        Each dict has keys: ``pred``, ``actual``, ``innings``, ``total_overs``.
    """
    with open(filepath) as f:
        data = json.load(f)

    info = data["info"]
    outcome = info.get("outcome", {})
    innings_data = data.get("innings", [])
    if len(innings_data) < 2:
        return []

    winner = outcome.get("winner")
    teams = info["teams"]
    if not winner or winner not in teams:
        return []

    # --- Innings 2 metadata (needed for both innings) ---
    target_info = innings_data[1].get("target", {})
    target_overs = target_info.get("overs", 20)
    target_runs = target_info.get("runs")
    if target_runs is None:
        return []

    # Match-level overs (used for innings 1)
    match_overs = info.get("overs", target_overs)
    total_balls_inn1 = match_overs * 6
    total_balls_inn2 = target_overs * 6

    if total_balls_inn2 < 6 or total_balls_inn2 > 120 or total_balls_inn2 % 6 != 0:
        return []
    if total_balls_inn1 < 6 or total_balls_inn1 > 120 or total_balls_inn1 % 6 != 0:
        return []

    results: List[dict] = []

    # ---- Innings 1 predictions ----
    if innings_filter is None or innings_filter == 1:
        inn1_batting = innings_data[0]["team"]
        inn1_bowling = [t for t in teams if t != inn1_batting][0]
        batting_first_won = 1 if winner == inn1_batting else 0

        score = 0
        wickets = 0
        legal_balls = 0

        for ov in innings_data[0]["overs"]:
            for d in ov["deliveries"]:
                runs = d["runs"]["total"]
                is_wkt = bool(d.get("wickets"))
                legal_balls += _count_legal(d)
                score += runs
                if is_wkt:
                    wickets += 1

                balls_remaining = max(0, total_balls_inn1 - legal_balls)

                # Checkpoint at end of each over
                if legal_balls % 6 == 0 and balls_remaining > 0:
                    try:
                        state = MatchState(
                            innings=1,
                            score=score,
                            wickets_lost=min(wickets, 9),
                            balls_remaining=balls_remaining,
                            batting_team=inn1_batting,
                            bowling_team=inn1_bowling,
                            league=league,
                            total_balls=total_balls_inn1,
                        )
                        result = simulate(
                            state,
                            horizon=6,
                            n_simulations=n_sims,
                            model_dir=model_dir,
                        )
                        results.append({
                            "pred": result.mean_prob,
                            "actual": batting_first_won,
                            "innings": 1,
                            "total_overs": match_overs,
                        })
                    except Exception:
                        pass

    # ---- Innings 2 predictions ----
    if innings_filter is None or innings_filter == 2:
        inn2_batting = innings_data[1]["team"]
        inn2_bowling = [t for t in teams if t != inn2_batting][0]
        batting_second_won = 1 if winner == inn2_batting else 0

        score = 0
        wickets = 0
        legal_balls = 0

        for ov in innings_data[1]["overs"]:
            for d in ov["deliveries"]:
                runs = d["runs"]["total"]
                is_wkt = bool(d.get("wickets"))
                legal_balls += _count_legal(d)
                score += runs
                if is_wkt:
                    wickets += 1

                balls_remaining = max(0, total_balls_inn2 - legal_balls)

                # Checkpoint at end of each over
                if legal_balls % 6 == 0 and balls_remaining > 0 and score < target_runs:
                    try:
                        state = MatchState(
                            innings=2,
                            score=score,
                            wickets_lost=min(wickets, 9),
                            balls_remaining=balls_remaining,
                            target_runs=target_runs,
                            batting_team=inn2_batting,
                            bowling_team=inn2_bowling,
                            league=league,
                            total_balls=total_balls_inn2,
                        )
                        result = simulate(
                            state,
                            horizon=6,
                            n_simulations=n_sims,
                            model_dir=model_dir,
                        )
                        results.append({
                            "pred": result.mean_prob,
                            "actual": batting_second_won,
                            "innings": 2,
                            "total_overs": target_overs,
                        })
                    except Exception:
                        pass

    return results


def train_mc_calibrator(
    json_dir: str,
    model_dir: str,
    league: str = "bbl",
    max_matches: int = 200,
    n_sims: int = 200,
    seed: int = 42,
    output_path: Optional[str] = None,
) -> MCTrainerResult:
    """Train an MC Platt calibrator from match JSON files.

    Parameters
    ----------
    json_dir : str
        Directory containing Cricsheet JSON match files.
    model_dir : str
        Model directory (also where ``mc_calibrator.pkl`` is saved).
    league : str
        League code for MC sampler distributions.
    max_matches : int
        Maximum number of matches to use.
    n_sims : int
        MC simulations per checkpoint.
    seed : int
        Random seed for reproducibility.
    output_path : str, optional
        Override output path. Default: ``{model_dir}/mc_calibrator.pkl``.

    Returns
    -------
    MCTrainerResult
        Training result with metrics and the fitted calibrator.

    Raises
    ------
    ValueError
        If too few prediction points are collected.
    """
    rng = np.random.RandomState(seed)

    if output_path is None:
        output_path = str(Path(model_dir) / "mc_calibrator.pkl")

    # Find all completed matches
    all_json = sorted(glob.glob(f"{json_dir}/*.json"))
    valid = []
    for f in all_json:
        with open(f) as fh:
            d = json.load(fh)
        if d.get("info", {}).get("outcome", {}).get("winner") and len(d.get("innings", [])) >= 2:
            valid.append(f)

    selected = valid[:max_matches]
    logger.info(
        "MC calibrator training started",
        json_dir=json_dir,
        available_matches=len(valid),
        selected_matches=len(selected),
        n_sims=n_sims,
    )

    # Collect predictions (innings 2 only for backward compatibility)
    all_results = []
    t0 = time.time()
    for i, fp in enumerate(selected):
        results = collect_predictions_from_match(
            fp, league=league, n_sims=n_sims, model_dir=model_dir,
            innings_filter=2,
        )
        all_results.extend(results)
        if (i + 1) % 20 == 0:
            elapsed = time.time() - t0
            logger.info(
                "MC calibrator training progress",
                matches=f"{i+1}/{len(selected)}",
                predictions=len(all_results),
                elapsed=f"{elapsed:.0f}s",
            )

    elapsed_total = time.time() - t0
    logger.info(
        "MC prediction collection complete",
        matches=len(selected),
        predictions=len(all_results),
        elapsed=f"{elapsed_total:.0f}s",
    )

    if len(all_results) < 50:
        raise ValueError(
            f"Too few prediction points ({len(all_results)}) to train calibrator. "
            f"Need at least 50. Check that {json_dir} contains completed matches."
        )

    preds = np.array([r["pred"] for r in all_results])
    actuals = np.array([r["actual"] for r in all_results])

    # Train/val split (80/20)
    n = len(preds)
    perm = rng.permutation(n)
    split = int(n * 0.8)
    train_idx, val_idx = perm[:split], perm[split:]

    # Fit calibrator on training set
    calibrator = MCCalibrator()
    calibrator.fit(preds[train_idx], actuals[train_idx])

    # Validate
    val_preds = preds[val_idx]
    val_acts = actuals[val_idx]
    val_cal = calibrator.calibrate_batch(val_preds)

    raw_brier = float(np.mean((val_preds - val_acts) ** 2))
    cal_brier = float(np.mean((val_cal - val_acts) ** 2))
    raw_ece = float(_compute_ece(val_preds, val_acts))
    cal_ece = float(_compute_ece(val_cal, val_acts))

    # Reliability bins
    reliability = []
    bin_edges = np.linspace(0, 1, 11)
    for i in range(10):
        mask = (val_cal >= bin_edges[i]) & (val_cal < bin_edges[i + 1])
        if mask.sum() >= 3:
            reliability.append({
                "bin": f"{bin_edges[i]:.1f}-{bin_edges[i+1]:.1f}",
                "n": int(mask.sum()),
                "pred": float(val_cal[mask].mean()),
                "actual": float(val_acts[mask].mean()),
                "gap": float(val_acts[mask].mean() - val_cal[mask].mean()),
            })

    # Save
    calibrator.save(output_path)
    logger.info("MC calibrator saved", path=output_path)

    # Clear engine cache so new calibrator is picked up
    from bbl_pipeline.simulation.engine import _MC_CALIBRATOR_CACHE
    _MC_CALIBRATOR_CACHE.clear()

    return MCTrainerResult(
        calibrator=calibrator,
        output_path=output_path,
        n_matches=len(selected),
        n_predictions=len(all_results),
        n_train=len(train_idx),
        n_val=len(val_idx),
        raw_brier=raw_brier,
        cal_brier=cal_brier,
        raw_ece=raw_ece,
        cal_ece=cal_ece,
        elapsed_seconds=elapsed_total,
        reliability=reliability,
    )


@dataclass
class InningsMCTrainerResult:
    """Result of innings-specific MC calibrator training."""

    calibrators: InningsMCCalibrators
    output_path: str
    n_matches: int
    n_predictions_inn1: int
    n_predictions_inn2: int
    elapsed_seconds: float
    # Per-innings validation metrics
    inn1_raw_brier: float = 0.0
    inn1_cal_brier: float = 0.0
    inn1_raw_ece: float = 0.0
    inn1_cal_ece: float = 0.0
    inn2_raw_brier: float = 0.0
    inn2_cal_brier: float = 0.0
    inn2_raw_ece: float = 0.0
    inn2_cal_ece: float = 0.0

    def summary(self) -> str:
        lines = [
            f"MC Innings-Specific Calibrator Training Summary",
            f"{'='*60}",
            f"  Matches analyzed:   {self.n_matches}",
            f"  Inn1 predictions:   {self.n_predictions_inn1}",
            f"  Inn2 predictions:   {self.n_predictions_inn2}",
            f"  Elapsed:            {self.elapsed_seconds:.1f}s",
            f"",
            f"  Innings 1 Validation:",
            f"  {'Metric':<12} {'Raw':>10} {'Calibrated':>10} {'Delta':>10}",
            f"  {'-'*42}",
            f"  {'Brier':<12} {self.inn1_raw_brier:>10.4f} {self.inn1_cal_brier:>10.4f} {self.inn1_cal_brier - self.inn1_raw_brier:>+10.4f}",
            f"  {'ECE':<12} {self.inn1_raw_ece:>10.4f} {self.inn1_cal_ece:>10.4f} {self.inn1_cal_ece - self.inn1_raw_ece:>+10.4f}",
            f"",
            f"  Innings 2 Validation:",
            f"  {'Metric':<12} {'Raw':>10} {'Calibrated':>10} {'Delta':>10}",
            f"  {'-'*42}",
            f"  {'Brier':<12} {self.inn2_raw_brier:>10.4f} {self.inn2_cal_brier:>10.4f} {self.inn2_cal_brier - self.inn2_raw_brier:>+10.4f}",
            f"  {'ECE':<12} {self.inn2_raw_ece:>10.4f} {self.inn2_cal_ece:>10.4f} {self.inn2_cal_ece - self.inn2_raw_ece:>+10.4f}",
            f"",
            f"  Output: {self.output_path}",
        ]
        return "\n".join(lines)


def _find_valid_matches(json_dir: str, max_matches: int) -> List[str]:
    """Find completed matches with a winner and 2 innings."""
    all_json = sorted(glob.glob(f"{json_dir}/*.json"))
    valid = []
    for f in all_json:
        with open(f) as fh:
            d = json.load(fh)
        if d.get("info", {}).get("outcome", {}).get("winner") and len(d.get("innings", [])) >= 2:
            valid.append(f)
    return valid[:max_matches]


def train_mc_calibrator_by_innings(
    json_dir: str,
    model_dir: str,
    league: str = "bbl",
    max_matches: int = 200,
    n_sims: int = 200,
    seed: int = 42,
    output_path: Optional[str] = None,
) -> InningsMCTrainerResult:
    """Train innings-specific MC Platt calibrators from match JSON files.

    Trains two separate calibrators — one for innings 1 (batting first)
    and one for innings 2 (chasing). This corrects the systematic bias
    where a single calibrator trained on innings 2 data worsens
    innings 1 predictions.

    Parameters
    ----------
    json_dir : str
        Directory containing Cricsheet JSON match files.
    model_dir : str
        Model directory (output: ``mc_calibrators_innings.pkl``).
    league : str
        League code for MC sampler distributions.
    max_matches : int
        Maximum number of matches to use.
    n_sims : int
        MC simulations per checkpoint.
    seed : int
        Random seed for reproducibility.
    output_path : str, optional
        Override output path. Default: ``{model_dir}/mc_calibrators_innings.pkl``.

    Returns
    -------
    InningsMCTrainerResult
        Training result with per-innings metrics.
    """
    rng = np.random.RandomState(seed)

    if output_path is None:
        output_path = str(Path(model_dir) / "mc_calibrators_innings.pkl")

    # Disable any existing MC calibrator in engine so raw preds are collected
    from bbl_pipeline.simulation.engine import _MC_CALIBRATOR_CACHE
    _MC_CALIBRATOR_CACHE.clear()
    _MC_CALIBRATOR_CACHE[model_dir] = None

    selected = _find_valid_matches(json_dir, max_matches)
    logger.info(
        "MC innings-specific calibrator training started",
        json_dir=json_dir,
        selected_matches=len(selected),
        n_sims=n_sims,
    )

    # Collect predictions from both innings
    all_results: List[dict] = []
    t0 = time.time()
    for i, fp in enumerate(selected):
        results = collect_predictions_from_match(
            fp, league=league, n_sims=n_sims, model_dir=model_dir,
            innings_filter=None,  # both innings
        )
        all_results.extend(results)
        if (i + 1) % 20 == 0:
            elapsed = time.time() - t0
            inn1_count = sum(1 for r in all_results if r["innings"] == 1)
            inn2_count = sum(1 for r in all_results if r["innings"] == 2)
            logger.info(
                "MC innings calibrator progress",
                matches=f"{i+1}/{len(selected)}",
                total=len(all_results),
                inn1=inn1_count,
                inn2=inn2_count,
                elapsed=f"{elapsed:.0f}s",
            )

    elapsed_total = time.time() - t0

    # Split by innings
    inn1_results = [r for r in all_results if r["innings"] == 1]
    inn2_results = [r for r in all_results if r["innings"] == 2]

    logger.info(
        "MC prediction collection complete",
        matches=len(selected),
        inn1_predictions=len(inn1_results),
        inn2_predictions=len(inn2_results),
        elapsed=f"{elapsed_total:.0f}s",
    )

    def _train_single(results_list, label):
        """Train and validate a single calibrator from a list of results."""
        if len(results_list) < 30:
            logger.warning(
                f"Too few {label} predictions ({len(results_list)}), skipping",
            )
            return None, 0.0, 0.0, 0.0, 0.0

        preds = np.array([r["pred"] for r in results_list])
        actuals = np.array([r["actual"] for r in results_list])

        n = len(preds)
        perm = rng.permutation(n)
        split = int(n * 0.8)
        train_idx, val_idx = perm[:split], perm[split:]

        cal = MCCalibrator()
        cal.fit(preds[train_idx], actuals[train_idx])

        val_preds = preds[val_idx]
        val_acts = actuals[val_idx]
        val_cal = cal.calibrate_batch(val_preds)

        raw_brier = float(np.mean((val_preds - val_acts) ** 2))
        cal_brier = float(np.mean((val_cal - val_acts) ** 2))
        raw_ece = float(_compute_ece(val_preds, val_acts))
        cal_ece = float(_compute_ece(val_cal, val_acts))

        logger.info(
            f"MC {label} calibrator trained",
            samples=len(results_list),
            train=len(train_idx),
            val=len(val_idx),
            raw_brier=f"{raw_brier:.4f}",
            cal_brier=f"{cal_brier:.4f}",
            raw_ece=f"{raw_ece:.4f}",
            cal_ece=f"{cal_ece:.4f}",
            coef=f"{cal.model.coef_[0][0]:.4f}",
            intercept=f"{cal.model.intercept_[0]:.4f}",
        )
        return cal, raw_brier, cal_brier, raw_ece, cal_ece

    inn1_cal, inn1_rb, inn1_cb, inn1_re, inn1_ce = _train_single(inn1_results, "inn1")
    inn2_cal, inn2_rb, inn2_cb, inn2_re, inn2_ce = _train_single(inn2_results, "inn2")

    # Build container
    calibrators = InningsMCCalibrators(inn1=inn1_cal, inn2=inn2_cal)
    calibrators.save(output_path)
    logger.info("MC innings-specific calibrators saved", path=output_path)

    # Clear cache so new calibrators are picked up
    _MC_CALIBRATOR_CACHE.clear()

    return InningsMCTrainerResult(
        calibrators=calibrators,
        output_path=output_path,
        n_matches=len(selected),
        n_predictions_inn1=len(inn1_results),
        n_predictions_inn2=len(inn2_results),
        elapsed_seconds=elapsed_total,
        inn1_raw_brier=inn1_rb,
        inn1_cal_brier=inn1_cb,
        inn1_raw_ece=inn1_re,
        inn1_cal_ece=inn1_ce,
        inn2_raw_brier=inn2_rb,
        inn2_cal_brier=inn2_cb,
        inn2_raw_ece=inn2_re,
        inn2_cal_ece=inn2_ce,
    )
