#!/usr/bin/env python
"""
Derive IPL-specific wicket penalty tables from training data.

Reads ``data/ipl_features_v1/training.parquet`` and computes two penalty
structures:

1. **2nd innings (chase) penalties** – keyed by chase-ease level ×
   wickets_lost.  Chase ease is derived from ``current_run_rate /
   required_run_rate``.

2. **1st innings penalties** – keyed by phase × ease_bucket ×
   wickets_lost.  Phase is derived from ``overs_remaining``; ease
   bucket compares ``current_run_rate`` against per-phase expected
   rates.

Both tables are written as JSON to ``data/ipl_derived_penalties.json``.

FR-002 constraint
-----------------
For wickets 4-8, every IPL *chase* penalty value must be **strictly less
than** the corresponding T20 base value.  If empirical data doesn't
satisfy this, values are adjusted downward.

Usage::

    python scripts/derive_ipl_wicket_penalties.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

# ═══════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════

INPUT_PATH = Path("data/ipl_features_v1/training.parquet")
OUTPUT_PATH = Path("data/ipl_derived_penalties.json")

MIN_OBS = 30  # minimum observations per cell before smoothing

# T20 base chase penalty table (reference for FR-002)
T20_BASE_CHASE: Dict[str, Dict[int, float]] = {
    "very_easy": {0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 1.00,
                  5: 0.88, 6: 0.76, 7: 0.56, 8: 0.24, 9: 0.05, 10: 0.00},
    "easy":      {0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 1.00,
                  5: 1.00, 6: 1.00, 7: 1.00, 8: 0.44, 9: 0.22, 10: 0.00},
    "comfortable": {0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 1.00,
                    5: 1.00, 6: 1.00, 7: 1.00, 8: 0.62, 9: 0.74, 10: 0.00},
    "tough":     {0: 1.00, 1: 0.93, 2: 0.90, 3: 0.88, 4: 0.76,
                  5: 0.79, 6: 0.71, 7: 0.70, 8: 0.34, 9: 0.05, 10: 0.00},
    "desperate": {0: 1.00, 1: 0.72, 2: 0.46, 3: 0.35, 4: 0.21,
                  5: 0.21, 6: 0.15, 7: 0.08, 8: 0.05, 9: 0.01, 10: 0.00},
}

# Chase-ease thresholds (CRR / RRR)
CHASE_EASE_THRESHOLDS: List[Tuple[str, float]] = [
    ("very_easy", 3.0),
    ("easy", 1.5),
    ("comfortable", 1.0),
    ("tough", 0.7),
]
CHASE_EASE_DEFAULT = "desperate"

# Phase definitions (overs_remaining boundaries)
PHASE_DEFS: List[Tuple[str, float, float]] = [
    ("powerplay", 14.0, 20.0),
    ("middle", 6.0, 14.0),
    ("death", 2.0, 6.0),
    ("final", 0.0, 2.0),
]

# Expected run rates per phase for 1st-innings ease bucketing
EXPECTED_CRR: Dict[str, float] = {
    "powerplay": 7.53,
    "middle": 7.51,
    "death": 9.02,
    "final": 10.68,
}

# 1st innings ease thresholds (CRR / expected_crr)
INN1_EASE_THRESHOLDS: List[Tuple[str, float]] = [
    ("well_ahead", 1.15),
    ("ahead", 1.05),
    ("par", 0.95),
    ("behind", 0.85),
]
INN1_EASE_DEFAULT = "well_behind"


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def classify_chase_ease(ratio: float) -> str:
    """Map CRR/RRR ratio to a chase-ease label."""
    for label, threshold in CHASE_EASE_THRESHOLDS:
        if ratio >= threshold:
            return label
    return CHASE_EASE_DEFAULT


def classify_phase(overs_rem: float) -> str:
    """Map overs_remaining to a phase label."""
    for phase, lo, hi in PHASE_DEFS:
        if lo < overs_rem <= hi:
            return phase
    # Edge cases: very start of innings or negative remainders
    if overs_rem > 20.0:
        return "powerplay"
    return "final"


def classify_inn1_ease(crr: float, phase: str) -> str:
    """Map CRR / expected-rate ratio to a 1st-innings ease bucket."""
    expected = EXPECTED_CRR.get(phase, 7.51)
    if expected <= 0:
        return "par"
    ratio = crr / expected
    for label, threshold in INN1_EASE_THRESHOLDS:
        if ratio >= threshold:
            return label
    return INN1_EASE_DEFAULT


def smooth_cell(
    table: Dict[str, Dict[int, float]],
    counts: Dict[str, Dict[int, int]],
    ordered_keys: List[str],
) -> Dict[str, Dict[int, float]]:
    """Fill cells with < MIN_OBS from adjacent groups (average of neighbours)."""
    for wk in range(0, 11):
        for idx, key in enumerate(ordered_keys):
            if counts.get(key, {}).get(wk, 0) >= MIN_OBS:
                continue
            neighbours: List[float] = []
            if idx > 0 and counts.get(ordered_keys[idx - 1], {}).get(wk, 0) >= MIN_OBS:
                neighbours.append(table[ordered_keys[idx - 1]][wk])
            if idx < len(ordered_keys) - 1 and counts.get(ordered_keys[idx + 1], {}).get(wk, 0) >= MIN_OBS:
                neighbours.append(table[ordered_keys[idx + 1]][wk])
            if neighbours:
                table[key][wk] = round(float(np.mean(neighbours)), 2)
            # If no valid neighbours, keep the empirical (possibly noisy) value
    return table


def smooth_3d_table(
    table: Dict[str, Dict[str, Dict[int, float]]],
    counts: Dict[str, Dict[str, Dict[int, int]]],
    phase_order: List[str],
    ease_order: List[str],
) -> Dict[str, Dict[str, Dict[int, float]]]:
    """Smooth 3D table (phase × ease × wicket) from adjacent ease buckets."""
    for phase in phase_order:
        phase_table = table.get(phase, {})
        phase_counts = counts.get(phase, {})
        for wk in range(0, 11):
            for idx, ease in enumerate(ease_order):
                if phase_counts.get(ease, {}).get(wk, 0) >= MIN_OBS:
                    continue
                neighbours: List[float] = []
                if idx > 0 and phase_counts.get(ease_order[idx - 1], {}).get(wk, 0) >= MIN_OBS:
                    neighbours.append(phase_table[ease_order[idx - 1]][wk])
                if idx < len(ease_order) - 1 and phase_counts.get(ease_order[idx + 1], {}).get(wk, 0) >= MIN_OBS:
                    neighbours.append(phase_table[ease_order[idx + 1]][wk])
                if neighbours:
                    phase_table.setdefault(ease, {})[wk] = round(float(np.mean(neighbours)), 2)
    return table


def enforce_boundaries(table: Dict[str, Dict[int, float]]) -> Dict[str, Dict[int, float]]:
    """Enforce penalty[any][0] = 1.0 and penalty[any][10] = 0.0."""
    for key in table:
        table[key][0] = 1.0
        table[key][10] = 0.0
    return table


def enforce_boundaries_3d(
    table: Dict[str, Dict[str, Dict[int, float]]],
) -> Dict[str, Dict[str, Dict[int, float]]]:
    """Enforce boundary constraints on 3D table."""
    for phase in table:
        for ease in table[phase]:
            table[phase][ease][0] = 1.0
            table[phase][ease][10] = 0.0
    return table


def enforce_monotonicity(table: Dict[str, Dict[int, float]]) -> Dict[str, Dict[int, float]]:
    """Ensure penalties decrease (or stay equal) as wickets increase."""
    for key in table:
        for wk in range(1, 11):
            if table[key][wk] > table[key][wk - 1]:
                table[key][wk] = table[key][wk - 1]
    return table


def enforce_monotonicity_3d(
    table: Dict[str, Dict[str, Dict[int, float]]],
) -> Dict[str, Dict[str, Dict[int, float]]]:
    for phase in table:
        for ease in table[phase]:
            for wk in range(1, 11):
                if table[phase][ease][wk] > table[phase][ease][wk - 1]:
                    table[phase][ease][wk] = table[phase][ease][wk - 1]
    return table


def enforce_fr002(
    ipl_table: Dict[str, Dict[int, float]],
) -> Tuple[Dict[str, Dict[int, float]], int]:
    """FR-002: For wickets 4-8, IPL value must be strictly < T20 base.

    Returns the adjusted table and number of cells adjusted.
    """
    adjusted = 0
    for ease in ipl_table:
        if ease not in T20_BASE_CHASE:
            continue
        for wk in range(4, 9):
            base_val = T20_BASE_CHASE[ease][wk]
            if ipl_table[ease][wk] >= base_val:
                # Set to 95% of base (or base - 0.01, whichever is lower)
                new_val = min(round(base_val * 0.95, 2), round(base_val - 0.01, 2))
                new_val = max(new_val, 0.0)
                ipl_table[ease][wk] = new_val
                adjusted += 1
    return ipl_table, adjusted


# ═══════════════════════════════════════════════════════════════════════════
# Core derivation
# ═══════════════════════════════════════════════════════════════════════════


def derive_chase_penalties(df_inn2: pd.DataFrame) -> Tuple[Dict, Dict]:
    """Derive 2nd-innings chase penalties from innings-2 data.

    Returns (penalty_table, count_table).
    """
    print("\n=== 2nd Innings (Chase) Penalties ===")

    # Compute CRR/RRR ratio, guarding against div-by-zero / inf
    df = df_inn2.copy()
    df["rrr_safe"] = df["required_run_rate"].replace(0, np.nan)
    df["crr_rrr_ratio"] = df["current_run_rate"] / df["rrr_safe"]
    df = df.dropna(subset=["crr_rrr_ratio"])
    df = df[np.isfinite(df["crr_rrr_ratio"])]
    print(f"  Rows after filtering inf/NaN ratios: {len(df):,}")

    df["chase_ease"] = df["crr_rrr_ratio"].apply(classify_chase_ease)

    ease_order = ["very_easy", "easy", "comfortable", "tough", "desperate"]
    for ease in ease_order:
        n = len(df[df["chase_ease"] == ease])
        print(f"  {ease:>12s}: {n:>7,} rows")

    # Compute win rates per (ease, wickets_lost)
    penalty: Dict[str, Dict[int, float]] = {}
    counts: Dict[str, Dict[int, int]] = {}

    for ease in ease_order:
        penalty[ease] = {}
        counts[ease] = {}
        subset = df[df["chase_ease"] == ease]
        for wk in range(0, 11):
            cell = subset[subset["wickets_lost"] == wk]
            n = len(cell)
            counts[ease][wk] = n
            if n > 0:
                penalty[ease][wk] = round(float(cell["is_winner"].mean()), 2)
            else:
                penalty[ease][wk] = 0.0

    # Smooth sparse cells
    penalty = smooth_cell(penalty, counts, ease_order)
    # Enforce boundaries and monotonicity
    penalty = enforce_boundaries(penalty)
    penalty = enforce_monotonicity(penalty)

    return penalty, counts


def derive_inn1_penalties(df_inn1: pd.DataFrame) -> Tuple[Dict, Dict]:
    """Derive 1st-innings penalties from innings-1 data.

    Returns (penalty_table, count_table).
    """
    print("\n=== 1st Innings Penalties ===")

    df = df_inn1.copy()
    df["phase"] = df["overs_remaining"].apply(classify_phase)
    df["ease_bucket"] = df.apply(
        lambda r: classify_inn1_ease(r["current_run_rate"], r["phase"]),
        axis=1,
    )

    phase_order = ["powerplay", "middle", "death", "final"]
    ease_order = ["well_ahead", "ahead", "par", "behind", "well_behind"]

    for phase in phase_order:
        n = len(df[df["phase"] == phase])
        print(f"  {phase:>10s}: {n:>7,} rows")

    penalty: Dict[str, Dict[str, Dict[int, float]]] = {}
    counts: Dict[str, Dict[str, Dict[int, int]]] = {}

    for phase in phase_order:
        penalty[phase] = {}
        counts[phase] = {}
        phase_df = df[df["phase"] == phase]

        for ease in ease_order:
            penalty[phase][ease] = {}
            counts[phase][ease] = {}
            subset = phase_df[phase_df["ease_bucket"] == ease]

            for wk in range(0, 11):
                cell = subset[subset["wickets_lost"] == wk]
                n = len(cell)
                counts[phase][ease][wk] = n
                if n > 0:
                    penalty[phase][ease][wk] = round(float(cell["is_winner"].mean()), 2)
                else:
                    penalty[phase][ease][wk] = 0.0

    # Smooth sparse cells
    penalty = smooth_3d_table(penalty, counts, phase_order, ease_order)
    # Enforce boundaries and monotonicity
    penalty = enforce_boundaries_3d(penalty)
    penalty = enforce_monotonicity_3d(penalty)

    return penalty, counts


# ═══════════════════════════════════════════════════════════════════════════
# Validation
# ═══════════════════════════════════════════════════════════════════════════


def validate_chase(table: Dict[str, Dict[int, float]]) -> bool:
    """Validate chase penalty table structure and values."""
    ok = True
    ease_keys = {"very_easy", "easy", "comfortable", "tough", "desperate"}
    if set(table.keys()) != ease_keys:
        print(f"  [FAIL] Missing ease keys: {ease_keys - set(table.keys())}")
        ok = False

    for ease, wickets in table.items():
        # Check boundary constraints
        if wickets.get(0) != 1.0:
            print(f"  [FAIL] {ease}[0] = {wickets.get(0)} (expected 1.0)")
            ok = False
        if wickets.get(10) != 0.0:
            print(f"  [FAIL] {ease}[10] = {wickets.get(10)} (expected 0.0)")
            ok = False

        # Check monotonicity
        for wk in range(1, 11):
            if wickets.get(wk, 0) > wickets.get(wk - 1, 1):
                print(f"  [FAIL] {ease}: non-monotonic at wk={wk} "
                      f"({wickets[wk]} > {wickets[wk-1]})")
                ok = False

    # Check FR-002
    for ease in ease_keys:
        if ease not in T20_BASE_CHASE:
            continue
        for wk in range(4, 9):
            ipl_val = table[ease][wk]
            base_val = T20_BASE_CHASE[ease][wk]
            if ipl_val >= base_val:
                print(f"  [FAIL] FR-002 violation: {ease}[{wk}] "
                      f"IPL={ipl_val} >= T20_BASE={base_val}")
                ok = False

    return ok


def validate_inn1(table: Dict[str, Dict[str, Dict[int, float]]]) -> bool:
    """Validate 1st innings penalty table structure."""
    ok = True
    expected_phases = {"powerplay", "middle", "death", "final"}
    if set(table.keys()) != expected_phases:
        print(f"  [FAIL] Missing phase keys: {expected_phases - set(table.keys())}")
        ok = False

    for phase in table:
        for ease in table[phase]:
            wk_table = table[phase][ease]
            if wk_table.get(0) != 1.0:
                print(f"  [FAIL] {phase}/{ease}[0] = {wk_table.get(0)}")
                ok = False
            if wk_table.get(10) != 0.0:
                print(f"  [FAIL] {phase}/{ease}[10] = {wk_table.get(10)}")
                ok = False
            for wk in range(1, 11):
                if wk_table.get(wk, 0) > wk_table.get(wk - 1, 1):
                    print(f"  [FAIL] {phase}/{ease}: non-monotonic at wk={wk}")
                    ok = False
    return ok


def print_chase_table(table: Dict[str, Dict[int, float]]) -> None:
    """Pretty-print the chase penalty table."""
    ease_order = ["very_easy", "easy", "comfortable", "tough", "desperate"]
    header = f"{'Ease':<13s}" + "".join(f"{'W' + str(w):>6s}" for w in range(11))
    print(f"\n  {header}")
    print(f"  {'-' * len(header)}")
    for ease in ease_order:
        vals = "".join(f"{table[ease][w]:6.2f}" for w in range(11))
        print(f"  {ease:<13s}{vals}")


def print_inn1_table(table: Dict[str, Dict[str, Dict[int, float]]]) -> None:
    """Print a summary of the 1st innings penalty table."""
    phase_order = ["powerplay", "middle", "death", "final"]
    ease_order = ["well_ahead", "ahead", "par", "behind", "well_behind"]
    for phase in phase_order:
        print(f"\n  --- {phase.upper()} ---")
        header = f"  {'Ease':<14s}" + "".join(f"{'W' + str(w):>6s}" for w in range(11))
        print(header)
        print(f"  {'-' * len(header)}")
        for ease in ease_order:
            if ease in table.get(phase, {}):
                vals = "".join(f"{table[phase][ease][w]:6.2f}" for w in range(11))
                print(f"  {ease:<14s}{vals}")


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════


def main() -> None:
    print("=" * 60)
    print("IPL Wicket Penalty Derivation")
    print("=" * 60)

    # --- Load data ---
    if not INPUT_PATH.exists():
        print(f"[ERROR] Input file not found: {INPUT_PATH}")
        sys.exit(1)

    print(f"\nLoading {INPUT_PATH} ...")
    df = pd.read_parquet(INPUT_PATH)
    print(f"  Total rows: {len(df):,}")
    print(f"  Innings 1:  {len(df[df['innings'] == 1]):,}")
    print(f"  Innings 2:  {len(df[df['innings'] == 2]):,}")

    # --- Derive chase penalties ---
    df_inn2 = df[df["innings"] == 2].copy()
    chase_table, chase_counts = derive_chase_penalties(df_inn2)

    # FR-002 enforcement
    chase_table, n_adjusted = enforce_fr002(chase_table)
    # Re-enforce monotonicity after FR-002 adjustments
    chase_table = enforce_monotonicity(chase_table)
    print(f"\n  FR-002 adjustments: {n_adjusted} cells modified")

    print("\n  Chase penalty table (IPL):")
    print_chase_table(chase_table)

    print("\n  T20 base (reference):")
    print_chase_table(T20_BASE_CHASE)

    # --- Derive 1st innings penalties ---
    df_inn1 = df[df["innings"] == 1].copy()
    inn1_table, inn1_counts = derive_inn1_penalties(df_inn1)

    print("\n  1st Innings penalty table (IPL):")
    print_inn1_table(inn1_table)

    # --- Validate ---
    print("\n\n=== Validation ===")
    chase_ok = validate_chase(chase_table)
    inn1_ok = validate_inn1(inn1_table)

    if chase_ok:
        print("  [PASS] Chase penalties valid")
    else:
        print("  [WARN] Chase penalties have issues (see above)")

    if inn1_ok:
        print("  [PASS] 1st innings penalties valid")
    else:
        print("  [WARN] 1st innings penalties have issues (see above)")

    # --- Convert int keys to strings for JSON serialization ---
    def int_keys_to_str(d: Any) -> Any:
        if isinstance(d, dict):
            return {str(k): int_keys_to_str(v) for k, v in d.items()}
        return d

    output = {
        "chase_penalties": int_keys_to_str(chase_table),
        "first_innings_penalties": int_keys_to_str(inn1_table),
        "metadata": {
            "source": str(INPUT_PATH),
            "total_rows": len(df),
            "inn1_rows": int(len(df[df["innings"] == 1])),
            "inn2_rows": int(len(df[df["innings"] == 2])),
            "min_observations": MIN_OBS,
            "fr002_adjustments": n_adjusted,
        },
    }

    # --- Write output ---
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n  Output written to {OUTPUT_PATH}")

    # Final sanity check
    if not OUTPUT_PATH.exists():
        print("[ERROR] Output file was not created!")
        sys.exit(1)

    file_size = OUTPUT_PATH.stat().st_size
    print(f"  File size: {file_size:,} bytes")
    print("\nDone.")


if __name__ == "__main__":
    main()
