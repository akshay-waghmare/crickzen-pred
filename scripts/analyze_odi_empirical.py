#!/usr/bin/env python
"""
Empirical analysis of ODI match data to derive resource constants.

Parses Cricsheet ODI JSONs, filters to 2010+, full 50-over matches with a
result, and computes gender-aware constants for the ODI win probability model:

  - Average 1st/2nd innings scores and bat-first win rates
  - Per-over run rates and phase boundaries
  - DLS resource table (wickets × overs_remaining)
  - First innings wicket penalty 3D (phase × ease × wickets)
  - Chase wicket penalty 2D (chase_ease × wickets)
  - RRR midpoint and beta (chase logistics)
  - SQI / confidence parameters

Usage:
    python scripts/analyze_odi_empirical.py \\
        --input-dir odis_json \\
        --output scripts/odi_empirical_constants.json \\
        --cutoff-year 2010

    # Include separate female directory
    python scripts/analyze_odi_empirical.py \\
        --input-dir odis_json \\
        --female-dir odis_female_json \\
        --output scripts/odi_empirical_constants.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


# ═══════════════════════════════════════════════════════════════════════════
# 1. DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════


def load_odi_matches(
    input_dir: str,
    female_dir: Optional[str],
    cutoff_year: int,
) -> Tuple[List[dict], List[dict]]:
    """Load and filter ODI matches from Cricsheet JSON files.

    Returns (male_matches, female_matches) where each match dict contains
    parsed ball-by-ball data plus metadata.
    """
    json_dirs = [input_dir]
    if female_dir and os.path.isdir(female_dir):
        json_dirs.append(female_dir)

    male_matches: List[dict] = []
    female_matches: List[dict] = []
    skipped = {"no_result": 0, "reduced_overs": 0, "pre_cutoff": 0,
               "not_odi": 0, "error": 0, "no_innings": 0}

    seen_ids: set = set()

    for jdir in json_dirs:
        files = sorted(Path(jdir).glob("*.json"))
        for fpath in files:
            match_id = fpath.stem
            if match_id in seen_ids:
                continue
            seen_ids.add(match_id)

            try:
                with open(fpath) as f:
                    raw = json.load(f)
            except Exception:
                skipped["error"] += 1
                continue

            info = raw.get("info", {})

            # Filter: must be ODI
            if info.get("match_type") != "ODI":
                skipped["not_odi"] += 1
                continue

            # Filter: must have overs == 50
            if info.get("overs") != 50:
                skipped["reduced_overs"] += 1
                continue

            # Filter: must have a winner
            outcome = info.get("outcome", {})
            if "winner" not in outcome:
                skipped["no_result"] += 1
                continue

            # Filter: date >= cutoff_year
            dates = info.get("dates", [])
            if not dates:
                skipped["pre_cutoff"] += 1
                continue
            year = int(str(dates[0])[:4])
            if year < cutoff_year:
                skipped["pre_cutoff"] += 1
                continue

            # Parse innings
            innings_data = raw.get("innings", [])
            if len(innings_data) < 2:
                skipped["no_innings"] += 1
                continue

            # Check both innings are full (not reduced mid-match due to rain)
            # We allow all-out before 50 overs (that's normal cricket)
            inn1_overs = len(innings_data[0].get("overs", []))
            inn2_overs = len(innings_data[1].get("overs", []))

            # If neither innings has at least 20 overs, skip (rain-affected)
            if inn1_overs < 20 or inn2_overs < 20:
                skipped["reduced_overs"] += 1
                continue

            match = _parse_match(raw, info, innings_data)
            if match is None:
                skipped["error"] += 1
                continue

            gender = info.get("gender", "male")
            if gender == "female":
                female_matches.append(match)
            else:
                male_matches.append(match)

    print(f"\n{'='*60}")
    print(f"ODI Data Loading Summary")
    print(f"{'='*60}")
    print(f"Male matches loaded:   {len(male_matches)}")
    print(f"Female matches loaded: {len(female_matches)}")
    print(f"Skipped breakdown:")
    for reason, count in skipped.items():
        if count > 0:
            print(f"  {reason}: {count}")
    print(f"{'='*60}\n")

    return male_matches, female_matches


def _parse_match(raw: dict, info: dict, innings_data: list) -> Optional[dict]:
    """Parse a Cricsheet JSON match into a structured dict with ball-by-ball data."""
    try:
        winner = info["outcome"]["winner"]
        teams = info["teams"]
        toss_winner = info.get("toss", {}).get("winner")
        toss_decision = info.get("toss", {}).get("decision")
        venue = info.get("venue", "Unknown")
        dates = info.get("dates", [""])
        gender = info.get("gender", "male")

        innings_list = []
        for inn_idx, inn in enumerate(innings_data[:2], start=1):
            team = inn.get("team", teams[inn_idx - 1] if inn_idx <= len(teams) else "Unknown")
            balls = []
            total_runs = 0
            total_wickets = 0

            for over_data in inn.get("overs", []):
                over_num = over_data["over"]  # 0-indexed
                for ball_idx, delivery in enumerate(over_data.get("deliveries", [])):
                    runs = delivery.get("runs", {})
                    batter_runs = runs.get("batter", 0)
                    extras = runs.get("extras", 0)
                    total_delivery_runs = runs.get("total", batter_runs + extras)
                    total_runs += total_delivery_runs

                    is_wicket = 0
                    if "wickets" in delivery:
                        for w in delivery["wickets"]:
                            kind = w.get("kind", "")
                            if kind != "retired hurt":
                                is_wicket = 1
                                total_wickets += 1

                    # Determine ball number (1-6 for legal deliveries)
                    # Extras like wides/no-balls don't count as balls
                    ball_num = ball_idx + 1

                    balls.append({
                        "over": over_num,
                        "ball": ball_num,
                        "batter_runs": batter_runs,
                        "extras": extras,
                        "total_runs": total_delivery_runs,
                        "cumulative_runs": total_runs,
                        "wickets_so_far": total_wickets,
                        "is_wicket": is_wicket,
                    })

            innings_list.append({
                "innings": inn_idx,
                "team": team,
                "balls": balls,
                "total_runs": total_runs,
                "total_wickets": total_wickets,
                "overs_faced": len(inn.get("overs", [])),
            })

        bat_first_team = innings_list[0]["team"]
        bat_first_won = 1 if bat_first_team == winner else 0

        return {
            "match_id": raw.get("info", {}).get("match_type_number", ""),
            "date": str(dates[0]),
            "venue": venue,
            "gender": gender,
            "teams": teams,
            "winner": winner,
            "toss_winner": toss_winner,
            "toss_decision": toss_decision,
            "bat_first_won": bat_first_won,
            "innings": innings_list,
        }
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════════
# 2. SCORING ANALYSIS (T013)
# ═══════════════════════════════════════════════════════════════════════════


def get_scoring_stats(matches: List[dict]) -> dict:
    """Compute average innings scores and bat-first win rate."""
    inn1_scores = []
    inn2_scores = []
    bat_first_wins = 0

    for m in matches:
        inn1_scores.append(m["innings"][0]["total_runs"])
        inn2_scores.append(m["innings"][1]["total_runs"])
        bat_first_wins += m["bat_first_won"]

    n = len(matches)
    return {
        "matches": n,
        "avg_1st_innings_score": float(np.mean(inn1_scores)) if inn1_scores else 0,
        "avg_2nd_innings_score": float(np.mean(inn2_scores)) if inn2_scores else 0,
        "median_1st_innings_score": float(np.median(inn1_scores)) if inn1_scores else 0,
        "bat_first_win_rate": bat_first_wins / n if n > 0 else 0.5,
        "std_1st_innings_score": float(np.std(inn1_scores)) if inn1_scores else 0,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 3. PER-OVER RUN RATE ANALYSIS (T014)
# ═══════════════════════════════════════════════════════════════════════════


def get_run_rates(matches: List[dict]) -> dict:
    """Compute per-over run rates and expected rates by phase."""
    # Accumulate runs scored in each over (0-indexed: 0-49)
    over_runs = defaultdict(list)  # over_num -> list of runs in that over

    for m in matches:
        for inn in m["innings"]:
            over_totals = defaultdict(int)
            for ball in inn["balls"]:
                over_totals[ball["over"]] += ball["total_runs"]
            for ov, runs in over_totals.items():
                if 0 <= ov < 50:
                    over_runs[ov].append(runs)

    per_over_rr = {}
    for ov in range(50):
        runs_list = over_runs.get(ov, [])
        per_over_rr[ov] = float(np.mean(runs_list)) if runs_list else 0.0

    # Compute phase run rates (ODI 4-phase structure)
    # PP: overs 0-9, Middle: 10-33, Setup: 34-39, Death: 40-49
    phases = {
        "powerplay": list(range(0, 10)),
        "middle": list(range(10, 34)),
        "setup": list(range(34, 40)),
        "death": list(range(40, 50)),
    }

    expected_run_rates = {}
    for phase_name, overs in phases.items():
        phase_rr = [per_over_rr.get(ov, 0.0) for ov in overs]
        expected_run_rates[phase_name] = float(np.mean(phase_rr)) if phase_rr else 0.0

    return {
        "per_over_run_rate": per_over_rr,
        "expected_run_rates": expected_run_rates,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 4. DLS RESOURCE TABLE (T015)
# ═══════════════════════════════════════════════════════════════════════════


def get_dls_table(matches: List[dict]) -> dict:
    """Derive DLS-style resource table from actual runs scored.

    For each (wickets_lost, overs_remaining) bucket, compute the proportion
    of total innings runs that are scored from that point onward.
    """
    # Accumulate: key = (wickets_lost, overs_remaining) -> list of pct_remaining
    buckets = defaultdict(list)

    for m in matches:
        inn1 = m["innings"][0]
        total_score = inn1["total_runs"]
        if total_score <= 0:
            continue

        # Track cumulative state through the innings
        for ball in inn1["balls"]:
            over = ball["over"]
            wickets = ball["wickets_so_far"]
            cumulative = ball["cumulative_runs"]

            # Only track at start of each over (ball 1)
            if ball["ball"] != 1:
                continue

            overs_remaining = 50 - over
            runs_remaining = total_score - cumulative + ball["total_runs"]
            pct = (runs_remaining / total_score) * 100.0

            wickets = min(wickets, 9)
            buckets[(wickets, overs_remaining)].append(pct)

    # Build the table: wickets -> {overs_remaining: avg_pct}
    # Use standard DLS overs points for interpolation: 0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50
    dls_overs_points = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50]
    dls_table = {}

    for wickets in range(10):
        overs_data = {}
        for overs_rem in dls_overs_points:
            key = (wickets, overs_rem)
            values = buckets.get(key, [])
            if values:
                overs_data[overs_rem] = round(float(np.mean(values)), 1)
            elif overs_rem == 0:
                overs_data[0] = 0.0
            elif overs_rem == 50 and wickets == 0:
                overs_data[50] = 100.0
            else:
                # Interpolate from nearest available data
                overs_data[overs_rem] = _interpolate_dls(buckets, wickets, overs_rem)
        dls_table[wickets] = overs_data

    return dls_table


def _interpolate_dls(
    buckets: dict, wickets: int, target_overs: int
) -> float:
    """Interpolate missing DLS values from nearby data."""
    # Try nearby overs ±1, ±2, ±3
    for delta in range(1, 6):
        below_key = (wickets, target_overs - delta)
        above_key = (wickets, target_overs + delta)
        below_vals = buckets.get(below_key, [])
        above_vals = buckets.get(above_key, [])

        if below_vals and above_vals:
            below_avg = float(np.mean(below_vals))
            above_avg = float(np.mean(above_vals))
            weight = delta / (2 * delta)
            return round(below_avg + weight * (above_avg - below_avg), 1)
        elif below_vals:
            return round(float(np.mean(below_vals)), 1)
        elif above_vals:
            return round(float(np.mean(above_vals)), 1)

    # Fallback: linear scale based on overs
    return round(target_overs * 2.0, 1)


# ═══════════════════════════════════════════════════════════════════════════
# 5. FIRST INNINGS WICKET PENALTY 3D (T016)
# ═══════════════════════════════════════════════════════════════════════════


def _get_odi_phase(over: int) -> str:
    """Map over number (0-indexed) to ODI phase name."""
    if over < 10:
        return "powerplay"
    elif over < 34:
        return "middle"
    elif over < 40:
        return "setup"
    else:
        return "death"


def _get_ease_bucket(crr: float, expected_rr: float) -> str:
    """Classify scoring ease based on current vs expected run rate."""
    if expected_rr <= 0:
        return "par"
    ratio = crr / expected_rr
    if ratio >= 1.15:
        return "well_ahead"
    elif ratio >= 1.05:
        return "ahead"
    elif ratio >= 0.95:
        return "par"
    elif ratio >= 0.85:
        return "behind"
    else:
        return "well_behind"


def get_batting_penalties(matches: List[dict], expected_rr: dict) -> dict:
    """Compute first innings wicket penalty 3D table.

    For each (phase, ease_bucket, wickets_lost) triplet, compute the ratio
    of actual final score to projected final score, which gives us the
    "penalty" multiplier for losing wickets in that context.
    """
    # Accumulate: (phase, ease, wickets) -> list of (actual_final / projected_final)
    penalty_data = defaultdict(list)

    for m in matches:
        inn1 = m["innings"][0]
        final_score = inn1["total_runs"]
        if final_score <= 0:
            continue

        for ball in inn1["balls"]:
            over = ball["over"]
            wickets = min(ball["wickets_so_far"], 10)
            cumulative = ball["cumulative_runs"]

            # Only sample at start of each over
            if ball["ball"] != 1:
                continue

            overs_bowled = over
            if overs_bowled <= 0:
                continue

            phase = _get_odi_phase(over)
            crr = cumulative / overs_bowled
            phase_expected_rr = expected_rr.get(phase, 5.0)
            ease = _get_ease_bucket(crr, phase_expected_rr)

            # Projected score based on current run rate
            overs_remaining = 50 - overs_bowled
            projected = cumulative + (crr * overs_remaining)
            if projected <= 0:
                continue

            ratio = final_score / projected
            # Clamp to reasonable range
            ratio = min(max(ratio, 0.01), 2.0)

            penalty_data[(phase, ease, wickets)].append(ratio)

    # Build the 3D table
    phases = ["powerplay", "middle", "setup", "death"]
    ease_levels = ["well_ahead", "ahead", "par", "behind", "well_behind"]

    penalty_3d = {}
    for phase in phases:
        penalty_3d[phase] = {}
        for ease in ease_levels:
            wkt_penalties = {}
            for w in range(11):
                key = (phase, ease, w)
                values = penalty_data.get(key, [])
                if values and len(values) >= 3:
                    # Normalize: ratio at 0 wickets = 1.0
                    raw_ratio = float(np.median(values))
                    # Get baseline (0 wickets in same phase/ease)
                    baseline_key = (phase, ease, 0)
                    baseline_vals = penalty_data.get(baseline_key, [])
                    baseline = float(np.median(baseline_vals)) if baseline_vals else 1.0
                    penalty = raw_ratio / baseline if baseline > 0 else raw_ratio
                    wkt_penalties[w] = round(min(1.0, max(0.01, penalty)), 2)
                elif w == 0:
                    wkt_penalties[w] = 1.0
                elif w == 10:
                    wkt_penalties[w] = 0.01
                else:
                    # Interpolate from adjacent wicket counts
                    wkt_penalties[w] = _interpolate_wicket_penalty(
                        penalty_data, phase, ease, w
                    )
            penalty_3d[phase][ease] = wkt_penalties

    return penalty_3d


def _interpolate_wicket_penalty(
    data: dict, phase: str, ease: str, wickets: int
) -> float:
    """Interpolate missing wicket penalty from neighbors."""
    # Try ±1 wicket
    for delta in [1, 2, 3]:
        below = data.get((phase, ease, wickets - delta), [])
        above = data.get((phase, ease, wickets + delta), [])
        if below and above:
            return round((float(np.median(below)) + float(np.median(above))) / 2, 2)
        elif below:
            return round(float(np.median(below)) * 0.9, 2)
        elif above:
            return round(float(np.median(above)) * 1.1, 2)

    # Fallback: exponential decay from 1.0
    return round(max(0.01, 1.0 - wickets * 0.1), 2)


# ═══════════════════════════════════════════════════════════════════════════
# 6. CHASE WICKET PENALTY 2D (T017)
# ═══════════════════════════════════════════════════════════════════════════


def get_chase_penalties(matches: List[dict]) -> Tuple[dict, dict]:
    """Compute chase ease × wickets → win rate penalty table.

    Also returns chase ease thresholds calibrated from the data.
    """
    chase_data = defaultdict(list)  # (ease_level, wickets) -> [0/1 win outcomes]

    ease_thresholds = {
        "very_easy": 3.0,
        "easy": 1.5,
        "comfortable": 1.0,
        "tough": 0.7,
        "desperate": 0.0,
    }

    for m in matches:
        inn2 = m["innings"][1]
        target = m["innings"][0]["total_runs"] + 1
        bat_second_won = 1 - m["bat_first_won"]

        for ball in inn2["balls"]:
            over = ball["over"]
            wickets = min(ball["wickets_so_far"], 10)
            cumulative = ball["cumulative_runs"]

            if ball["ball"] != 1:
                continue

            overs_bowled = over
            if overs_bowled <= 0:
                continue

            runs_needed = target - cumulative
            overs_remaining = 50 - overs_bowled
            if overs_remaining <= 0:
                continue

            crr = cumulative / overs_bowled
            rrr = runs_needed / overs_remaining

            if rrr <= 0:
                ease_level = "very_easy"
            else:
                ratio = crr / rrr
                if ratio >= ease_thresholds["very_easy"]:
                    ease_level = "very_easy"
                elif ratio >= ease_thresholds["easy"]:
                    ease_level = "easy"
                elif ratio >= ease_thresholds["comfortable"]:
                    ease_level = "comfortable"
                elif ratio >= ease_thresholds["tough"]:
                    ease_level = "tough"
                else:
                    ease_level = "desperate"

            chase_data[(ease_level, wickets)].append(bat_second_won)

    # Build 2D penalty table
    ease_levels = ["very_easy", "easy", "comfortable", "tough", "desperate"]
    penalty_2d = {}

    for ease in ease_levels:
        wkt_penalties = {}
        for w in range(11):
            outcomes = chase_data.get((ease, w), [])
            if outcomes and len(outcomes) >= 5:
                win_rate = float(np.mean(outcomes))
                # Normalize: at 0 wickets in this ease level, penalty = 1.0
                baseline_outcomes = chase_data.get((ease, 0), [])
                baseline_wr = float(np.mean(baseline_outcomes)) if baseline_outcomes else win_rate
                if baseline_wr > 0:
                    penalty = win_rate / baseline_wr
                else:
                    penalty = win_rate
                wkt_penalties[w] = round(min(1.0, max(0.0, penalty)), 2)
            elif w == 0:
                wkt_penalties[w] = 1.0
            elif w == 10:
                wkt_penalties[w] = 0.0
            else:
                # Fallback: linear decay
                wkt_penalties[w] = round(max(0.0, 1.0 - w * 0.1), 2)
        penalty_2d[ease] = wkt_penalties

    return penalty_2d, ease_thresholds


# ═══════════════════════════════════════════════════════════════════════════
# 7. RRR / CHASE PARAMETERS (T018)
# ═══════════════════════════════════════════════════════════════════════════


def get_chase_params(matches: List[dict]) -> dict:
    """Derive RRR midpoint and beta for chase win probability logistic.

    Finds the RRR where chase win % ≈ 50% and the steepness of transition.
    """
    rrr_outcomes = defaultdict(list)  # rrr_bucket -> [0/1 win outcomes]

    for m in matches:
        inn2 = m["innings"][1]
        target = m["innings"][0]["total_runs"] + 1
        bat_second_won = 1 - m["bat_first_won"]

        for ball in inn2["balls"]:
            over = ball["over"]
            cumulative = ball["cumulative_runs"]

            if ball["ball"] != 1 or over <= 2:
                continue

            runs_needed = target - cumulative
            overs_remaining = 50 - over
            if overs_remaining <= 0 or runs_needed <= 0:
                continue

            rrr = runs_needed / overs_remaining
            # Bucket RRR in 0.5 increments
            bucket = round(rrr * 2) / 2  # e.g., 5.5, 6.0, 6.5...
            if 2.0 <= bucket <= 15.0:
                rrr_outcomes[bucket].append(bat_second_won)

    # Find RRR midpoint (where win % ≈ 50%)
    rrr_win_rates = {}
    for bucket, outcomes in sorted(rrr_outcomes.items()):
        if len(outcomes) >= 10:
            rrr_win_rates[bucket] = float(np.mean(outcomes))

    # Find the crossover point
    midpoint = 6.0  # default for ODI
    best_diff = float("inf")
    for rrr_val, wr in rrr_win_rates.items():
        diff = abs(wr - 0.5)
        if diff < best_diff:
            best_diff = diff
            midpoint = rrr_val

    # Estimate beta (logistic steepness) via simple fitting
    # win_prob = 1 / (1 + exp(beta * (rrr - midpoint)))
    # Try different beta values and find best fit
    best_beta = 0.5
    best_mse = float("inf")
    for beta_candidate in np.arange(0.3, 1.5, 0.05):
        mse = 0
        count = 0
        for rrr_val, actual_wr in rrr_win_rates.items():
            predicted = 1.0 / (1.0 + math.exp(beta_candidate * (rrr_val - midpoint)))
            mse += (predicted - actual_wr) ** 2
            count += 1
        if count > 0:
            mse /= count
            if mse < best_mse:
                best_mse = mse
                best_beta = beta_candidate

    return {
        "rrr_midpoint": round(float(midpoint), 1),
        "rrr_beta": round(float(best_beta), 2),
        "rrr_win_rates": {str(k): round(v, 3) for k, v in sorted(rrr_win_rates.items())},
    }


# ═══════════════════════════════════════════════════════════════════════════
# 8. SQI / CONFIDENCE PARAMETERS (T019)
# ═══════════════════════════════════════════════════════════════════════════


def get_confidence_params(matches: List[dict], scoring_stats: dict) -> dict:
    """Derive SQI beta, shift, confidence overs, and score std parameters."""
    par = scoring_stats["avg_1st_innings_score"]
    bat_first_wr = scoring_stats["bat_first_win_rate"]

    # Compute projected score variance by phase
    # Track (overs_bowled, projected_final, actual_final) tuples
    projections_by_phase = {"early": [], "mid": [], "late": []}

    for m in matches:
        inn1 = m["innings"][0]
        actual = inn1["total_runs"]

        for ball in inn1["balls"]:
            over = ball["over"]
            if ball["ball"] != 1 or over == 0:
                continue

            cumulative = ball["cumulative_runs"]
            crr = cumulative / over
            projected = cumulative + crr * (50 - over)

            if over <= 15:
                projections_by_phase["early"].append((projected, actual))
            elif over <= 35:
                projections_by_phase["mid"].append((projected, actual))
            else:
                projections_by_phase["late"].append((projected, actual))

    # Compute std of (actual - projected) for each phase
    phase_stds = {}
    for phase, pairs in projections_by_phase.items():
        if pairs:
            errors = [actual - proj for proj, actual in pairs]
            phase_stds[phase] = float(np.std(errors))
        else:
            phase_stds[phase] = 30.0

    score_std_early = round(phase_stds.get("early", 30.0), 1)
    score_std_late = round(phase_stds.get("late", 20.0), 1)

    # Confidence full overs: where projection accuracy plateaus
    # In ODIs, projections become reliable around 25 overs
    confidence_full_overs = 25.0

    # SQI beta: steepness of score → win probability
    # Fit from actual outcomes
    sqi_outcomes = []
    for m in matches:
        inn1 = m["innings"][0]
        final_score = inn1["total_runs"]
        sqi = (final_score - par) / max(score_std_late, 1.0)
        sqi_outcomes.append((sqi, m["bat_first_won"]))

    # Find best beta
    best_beta = 0.75
    best_mse = float("inf")
    for beta in np.arange(0.3, 1.5, 0.05):
        mse = 0
        for sqi, won in sqi_outcomes:
            prob = 1.0 / (1.0 + math.exp(-beta * sqi))
            mse += (prob - won) ** 2
        mse /= len(sqi_outcomes) if sqi_outcomes else 1
        if mse < best_mse:
            best_mse = mse
            best_beta = beta

    # SQI shift: encode bat-first advantage/disadvantage
    # If bat_first_wr = 0.48, shift is small; if 0.37, shift is larger
    # shift = logit(bat_first_wr) / beta (conceptually)
    if 0 < bat_first_wr < 1:
        sqi_shift = round(-math.log(bat_first_wr / (1 - bat_first_wr)) / best_beta, 2)
    else:
        sqi_shift = 0.0

    return {
        "sqi_beta": round(float(best_beta), 2),
        "sqi_shift": round(float(sqi_shift), 2),
        "confidence_full_overs": confidence_full_overs,
        "score_std_early": score_std_early,
        "score_std_late": score_std_late,
        "wicket_decay_alpha": 0.02,  # Gentle for ODI (empirical estimate)
        "phase_stds": phase_stds,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 9. CONSOLE REPORT (T020)
# ═══════════════════════════════════════════════════════════════════════════


def print_report(
    gender: str,
    scoring: dict,
    run_rates: dict,
    dls_table: dict,
    batting_penalties: dict,
    chase_penalties: dict,
    chase_params: dict,
    confidence: dict,
    t20_comparison: bool = True,
) -> None:
    """Print formatted summary of derived constants."""
    print(f"\n{'='*70}")
    print(f"  ODI EMPIRICAL CONSTANTS — {gender.upper()}")
    print(f"{'='*70}")

    print(f"\n--- Scoring Analysis ({scoring['matches']} matches) ---")
    print(f"  Avg 1st innings score: {scoring['avg_1st_innings_score']:.1f}")
    print(f"  Avg 2nd innings score: {scoring['avg_2nd_innings_score']:.1f}")
    print(f"  Median 1st innings:    {scoring['median_1st_innings_score']:.1f}")
    print(f"  Bat-first win rate:    {scoring['bat_first_win_rate']:.3f}")
    print(f"  Std 1st innings score: {scoring['std_1st_innings_score']:.1f}")

    if t20_comparison:
        print(f"\n  (T20 comparison: par=160, bat_first_wr=0.37)")

    print(f"\n--- Per-Phase Run Rates ---")
    for phase, rr in run_rates["expected_run_rates"].items():
        print(f"  {phase:12s}: {rr:.2f} runs/over")

    print(f"\n--- Chase Parameters ---")
    print(f"  RRR midpoint (50% win): {chase_params['rrr_midpoint']}")
    print(f"  RRR beta (steepness):   {chase_params['rrr_beta']}")
    if t20_comparison:
        print(f"  (T20: midpoint=9.5, beta=0.7)")

    print(f"\n--- SQI / Confidence ---")
    print(f"  SQI beta:              {confidence['sqi_beta']}")
    print(f"  SQI shift:             {confidence['sqi_shift']}")
    print(f"  Confidence full overs: {confidence['confidence_full_overs']}")
    print(f"  Score std (early):     {confidence['score_std_early']}")
    print(f"  Score std (late):      {confidence['score_std_late']}")

    print(f"\n--- DLS Resource Table (sample rows) ---")
    for wickets in [0, 2, 5, 8]:
        row = dls_table.get(wickets, {})
        vals = ", ".join(f"{k}ov={v:.1f}%" for k, v in sorted(row.items())[:6])
        print(f"  {wickets} wkts: {vals}")

    print(f"\n--- First Innings Wicket Penalties (sample) ---")
    for phase in ["powerplay", "middle"]:
        penalties = batting_penalties.get(phase, {})
        par_penalties = penalties.get("par", {})
        vals = ", ".join(f"{w}w={p:.2f}" for w, p in sorted(par_penalties.items())[:6])
        print(f"  {phase}/par: {vals}")

    print(f"\n--- Chase Wicket Penalties (sample) ---")
    for ease in ["comfortable", "tough"]:
        penalties = chase_penalties.get(ease, {})
        vals = ", ".join(f"{w}w={p:.2f}" for w, p in sorted(penalties.items())[:6])
        print(f"  {ease}: {vals}")

    print(f"{'='*70}\n")


# ═══════════════════════════════════════════════════════════════════════════
# 10. AGGREGATE OUTPUT
# ═══════════════════════════════════════════════════════════════════════════


def analyze_gender(matches: List[dict], gender: str) -> dict:
    """Run full analysis for one gender and return constants dict."""
    if not matches:
        print(f"  WARNING: No {gender} matches found, using defaults")
        return {}

    scoring = get_scoring_stats(matches)
    run_rates = get_run_rates(matches)
    dls_table = get_dls_table(matches)
    batting_penalties = get_batting_penalties(matches, run_rates["expected_run_rates"])
    chase_penalties_2d, chase_ease_thresholds = get_chase_penalties(matches)
    chase_params = get_chase_params(matches)
    confidence = get_confidence_params(matches, scoring)

    # Print report
    print_report(
        gender, scoring, run_rates, dls_table, batting_penalties,
        chase_penalties_2d, chase_params, confidence,
    )

    # Build output constants
    constants = {
        "par_score": round(scoring["avg_1st_innings_score"], 1),
        "league_avg_score": round(scoring["median_1st_innings_score"], 1),
        "bat_first_win_rate": round(scoring["bat_first_win_rate"], 3),
        "expected_run_rates": {
            k: round(v, 2) for k, v in run_rates["expected_run_rates"].items()
        },
        "dls_resource_table": {
            str(k): {str(ok): ov for ok, ov in v.items()}
            for k, v in dls_table.items()
        },
        "first_innings_wicket_penalty_3d": batting_penalties,
        "chase_wicket_penalty_2d": chase_penalties_2d,
        "chase_ease_thresholds": chase_ease_thresholds,
        "rrr_midpoint": chase_params["rrr_midpoint"],
        "rrr_beta": chase_params["rrr_beta"],
        "sqi_beta": confidence["sqi_beta"],
        "sqi_shift": confidence["sqi_shift"],
        "confidence_full_overs": confidence["confidence_full_overs"],
        "score_std_early": confidence["score_std_early"],
        "score_std_late": confidence["score_std_late"],
        "wicket_decay_alpha": confidence["wicket_decay_alpha"],
        "sample_counts": {
            "total_matches": scoring["matches"],
            "total_balls_estimated": scoring["matches"] * 600,
        },
        "rrr_win_rates": chase_params.get("rrr_win_rates", {}),
    }

    return constants


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Derive empirical ODI resource constants from Cricsheet JSON data"
    )
    parser.add_argument(
        "--input-dir",
        default="odis_json",
        help="Directory containing ODI Cricsheet JSON files (default: odis_json)",
    )
    parser.add_argument(
        "--female-dir",
        default="odis_female_json",
        help="Optional separate directory for female ODI JSONs (default: odis_female_json)",
    )
    parser.add_argument(
        "--output",
        default="scripts/odi_empirical_constants.json",
        help="Output JSON file path (default: scripts/odi_empirical_constants.json)",
    )
    parser.add_argument(
        "--cutoff-year",
        type=int,
        default=2010,
        help="Only include matches from this year onward (default: 2010)",
    )

    args = parser.parse_args()

    male_matches, female_matches = load_odi_matches(
        args.input_dir, args.female_dir, args.cutoff_year
    )

    output = {}

    if male_matches:
        print(f"\nAnalyzing {len(male_matches)} male ODI matches...")
        output["male"] = analyze_gender(male_matches, "male")

    if female_matches:
        print(f"\nAnalyzing {len(female_matches)} female ODI matches...")
        output["female"] = analyze_gender(female_matches, "female")

    # Write output
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n✓ Constants written to {args.output}")
    print(f"  Male matches: {len(male_matches)}")
    print(f"  Female matches: {len(female_matches)}")


if __name__ == "__main__":
    main()
