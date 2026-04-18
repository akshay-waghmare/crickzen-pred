"""
Derive IPL-specific model improvements from training data.

Produces:
  1. IPL chase wicket penalties (WICKET_PENALTY_2D) - harsher at 4-8 wickets
  2. IPL first-innings wicket penalties (FIRST_INNINGS_WICKET_PENALTY_3D)
  3. Final-over empirical lookup table (runs_needed x wickets_in_hand -> win_prob)
  4. Optimal first_innings_score_midpoint for IPL

Usage:
    python scripts/derive_ipl_improvements.py

Output:
    scripts/ipl_derived_tables.py   - Python dict literals ready to paste
    data/ipl_final_over_lookup.csv  - Final over lookup as CSV
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "ipl_features_v1" / "training.parquet"
OUTPUT_PY = ROOT / "scripts" / "ipl_derived_tables.py"
OUTPUT_CSV = ROOT / "data" / "ipl_final_over_lookup.csv"


def load_data() -> pd.DataFrame:
    df = pd.read_parquet(DATA_PATH)
    df["over"] = 20 - df["overs_remaining"]
    df["balls_remaining"] = (df["overs_remaining"] * 6).round().astype(int)

    # Phase classification
    df["phase"] = "middle"
    df.loc[df["over"] <= 6, "phase"] = "powerplay"
    df.loc[df["over"] > 14, "phase"] = "death"
    df.loc[df["over"] > 18, "phase"] = "final"

    return df


# ── 1. Chase Wicket Penalties (2nd Innings) ─────────────────────────────────


def derive_chase_penalties(df: pd.DataFrame) -> dict:
    """Derive WICKET_PENALTY_2D from inn2 empirical win rates."""
    inn2 = df[df["innings"] == 2].copy()

    # chase_difficulty is RRR-based; we convert to CRR/RRR ratio
    # ease_ratio = CRR / RRR
    inn2["ease_ratio"] = np.where(
        inn2["required_run_rate"] > 0.1,
        inn2["current_run_rate"] / inn2["required_run_rate"],
        3.5,  # trivial chase
    )

    # Map to difficulty buckets (same thresholds as calculator.py)
    thresholds = {"very_easy": 3.0, "easy": 1.5, "comfortable": 1.0, "tough": 0.7, "desperate": 0.0}
    ordered_levels = ["desperate", "tough", "comfortable", "easy", "very_easy"]
    ordered_thresholds = [0.0, 0.7, 1.0, 1.5, 3.0]

    def classify_ease(ratio):
        for level, thresh in zip(reversed(ordered_levels), reversed(ordered_thresholds)):
            if ratio >= thresh:
                return level
        return "desperate"

    inn2["ease_level"] = inn2["ease_ratio"].apply(classify_ease)

    # Compute empirical win rate per (ease_level, wickets_lost)
    # Then normalize: penalty = win_rate(wk) / win_rate(0) for that ease level
    result = {}
    for level in ordered_levels:
        subset = inn2[inn2["ease_level"] == level]
        base_wr = subset[subset["wickets_lost"] == 0]["is_winner"].mean()
        if pd.isna(base_wr) or base_wr < 0.01:
            base_wr = 0.5

        penalties = {}
        for wk in range(11):
            wk_data = subset[subset["wickets_lost"] == wk]
            n = len(wk_data)
            if n >= 20:
                raw_wr = wk_data["is_winner"].mean()
                penalty = min(1.0, raw_wr / base_wr)
            elif n >= 5:
                # Shrinkage toward prior
                raw_wr = wk_data["is_winner"].mean()
                penalty = min(1.0, raw_wr / base_wr * 0.9 + 0.1)
            else:
                # Too sparse -- use monotonic fallback
                penalty = max(0.0, 1.0 - wk * 0.12) if level in ("very_easy", "easy") else max(0.0, 1.0 - wk * 0.15)

            penalties[wk] = round(max(0.00, min(1.00, penalty)), 2)

        # Enforce monotonicity: penalty should decrease as wickets increase
        for wk in range(1, 11):
            if penalties[wk] > penalties[wk - 1]:
                penalties[wk] = penalties[wk - 1]

        # Terminal: 10 wickets always 0
        penalties[10] = 0.00
        result[level] = penalties

    return result


# ── 2. First Innings Wicket Penalties ────────────────────────────────────────


def derive_first_innings_penalties(df: pd.DataFrame) -> dict:
    """Derive FIRST_INNINGS_WICKET_PENALTY_3D from inn1 empirical data."""
    inn1 = df[df["innings"] == 1].copy()

    # Ease classification using score_vs_par
    ease_thresholds = {
        "well_ahead": 1.15,
        "ahead": 1.05,
        "par": 0.95,
        "behind": 0.85,
        "well_behind": 0.0,
    }

    # Compute projected-to-par ratio
    # score_vs_par = projected_score - par, so ratio = projected_score / par
    # Use resource_win_prob as proxy for scoring position
    # Actually, let's use score_vs_par directly to classify ease
    inn1["par_ratio"] = np.where(
        inn1["expected_final_score"] > 0,
        inn1["expected_final_score"] / 173.45,  # IPL par
        1.0,
    )

    def classify_ease(ratio):
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

    inn1["ease_bucket"] = inn1["par_ratio"].apply(classify_ease)

    phases = ["powerplay", "middle", "death", "final"]
    ease_levels = ["well_ahead", "ahead", "par", "behind", "well_behind"]

    result = {}
    for phase in phases:
        result[phase] = {}
        phase_data = inn1[inn1["phase"] == phase]

        for ease in ease_levels:
            subset = phase_data[phase_data["ease_bucket"] == ease]
            base_wr = subset[subset["wickets_lost"] == 0]["is_winner"].mean()
            if pd.isna(base_wr) or base_wr < 0.05:
                base_wr = 0.5

            penalties = {}
            for wk in range(11):
                wk_data = subset[subset["wickets_lost"] == wk]
                n = len(wk_data)
                if n >= 15:
                    raw_wr = wk_data["is_winner"].mean()
                    penalty = min(1.0, raw_wr / base_wr)
                elif n >= 5:
                    raw_wr = wk_data["is_winner"].mean()
                    penalty = min(1.0, raw_wr / base_wr * 0.85 + 0.15)
                else:
                    # Sparse cell -- use harsher default for IPL
                    if phase in ("death", "final"):
                        penalty = max(0.01, 1.0 - wk * 0.08)
                    else:
                        penalty = max(0.01, 1.0 - wk * 0.12)

                penalties[wk] = round(max(0.01, min(1.00, penalty)), 2)

            # Enforce monotonicity
            for wk in range(1, 11):
                if penalties[wk] > penalties[wk - 1]:
                    penalties[wk] = penalties[wk - 1]

            penalties[10] = 0.01
            result[phase][ease] = penalties

    return result


# ── 3. Final-Over Lookup Table ───────────────────────────────────────────────


def derive_final_over_lookup(df: pd.DataFrame) -> dict:
    """Derive empirical win probability for final over by runs_needed x wickets_in_hand."""
    inn2 = df[df["innings"] == 2].copy()

    # Final over: balls_remaining <= 6
    final = inn2[inn2["balls_remaining"] <= 6].copy()

    # Compute runs_needed (we need target - current_score but we don't have target directly)
    # Use required_run_rate * overs_remaining * 6 / 6 to estimate runs_needed
    # Actually: runs_needed = required_run_rate * (balls_remaining / 6)
    final["runs_needed"] = (final["required_run_rate"] * final["overs_remaining"]).round().astype(int)
    final["wickets_in_hand"] = 10 - final["wickets_lost"]

    # Clamp
    final["runs_needed"] = final["runs_needed"].clip(0, 25)
    final["wickets_in_hand"] = final["wickets_in_hand"].clip(0, 10)

    # Compute empirical win rates
    lookup = {}
    rows = []
    for runs in range(0, 26):
        lookup[runs] = {}
        for wih in range(0, 11):
            subset = final[(final["runs_needed"] == runs) & (final["wickets_in_hand"] == wih)]
            n = len(subset)
            if n >= 10:
                wr = subset["is_winner"].mean()
            elif n >= 3:
                wr = subset["is_winner"].mean() * 0.8 + 0.1  # shrink toward 0.5
            else:
                wr = None  # fill later

            lookup[runs][wih] = wr
            rows.append({"runs_needed": runs, "wickets_in_hand": wih, "win_prob": wr, "n": n})

    # Fill sparse cells with monotonic interpolation
    for runs in range(0, 26):
        # runs=0 always wins
        if runs == 0:
            for wih in range(0, 11):
                lookup[runs][wih] = 1.0
            continue

        for wih in range(0, 11):
            if lookup[runs][wih] is None:
                # Interpolate from nearest known values
                # Heuristic: use sigmoid approximation as fallback
                if wih == 0:
                    lookup[runs][wih] = 0.0  # all out
                else:
                    rpb = runs / max(1, 6)  # assume 6 balls left
                    base = 1.0 / (1.0 + np.exp(4 * (rpb - 1.5)))
                    wih_factor = min(1.0, wih / 5.0)  # more wickets = higher prob
                    lookup[runs][wih] = round(base * wih_factor, 4)

    # Enforce monotonicity:
    # 1. As runs_needed increases, win_prob decreases (for fixed wickets)
    # 2. As wickets_in_hand increases, win_prob increases (for fixed runs)
    for wih in range(0, 11):
        for runs in range(1, 26):
            if lookup[runs][wih] > lookup[runs - 1][wih]:
                lookup[runs][wih] = lookup[runs - 1][wih]

    for runs in range(0, 26):
        for wih in range(1, 11):
            if lookup[runs][wih] < lookup[runs][wih - 1]:
                lookup[runs][wih] = lookup[runs][wih - 1]

    # Round all
    for runs in range(0, 26):
        for wih in range(0, 11):
            lookup[runs][wih] = round(lookup[runs][wih], 4)

    return lookup, rows


# ── 4. First Innings Score Midpoint ──────────────────────────────────────────


def derive_optimal_midpoint(df: pd.DataFrame) -> tuple:
    """Find the optimal first_innings_score_midpoint and beta for IPL."""
    inn1 = df[df["innings"] == 1].copy()

    # Only use end-of-innings states (overs_remaining near 0)
    eoi = inn1[inn1["overs_remaining"] <= 1.0].copy()

    # Get projected final score
    best_brier = 1.0
    best_mid = 165.0
    best_beta = 0.04

    for mid in np.arange(160, 185, 1.0):
        for beta in np.arange(0.02, 0.08, 0.005):
            prob = 1.0 / (1.0 + np.exp(-beta * (eoi["expected_final_score"] - mid)))
            brier = ((prob - eoi["is_winner"]) ** 2).mean()
            if brier < best_brier:
                best_brier = brier
                best_mid = mid
                best_beta = beta

    return best_mid, best_beta, best_brier


# ── Main ─────────────────────────────────────────────────────────────────────


def format_penalty_dict(d, indent=8):
    """Format a {int: float} dict as a Python literal."""
    items = [f"{k}: {v:.2f}" for k, v in sorted(d.items())]
    return "{" + ", ".join(items) + "}"


def main():
    print("Loading IPL training data...")
    df = load_data()
    print(f"  {len(df)} rows, {len(df.columns)} columns")
    print(f"  Inn1: {len(df[df['innings']==1])}, Inn2: {len(df[df['innings']==2])}")
    print()

    # 1. Chase wicket penalties
    print("=" * 60)
    print("1. DERIVING CHASE WICKET PENALTIES (2nd innings)")
    print("=" * 60)
    chase_penalties = derive_chase_penalties(df)
    for level, pens in chase_penalties.items():
        print(f"  {level:12s}: {pens}")
    print()

    # 2. First innings penalties
    print("=" * 60)
    print("2. DERIVING FIRST INNINGS WICKET PENALTIES")
    print("=" * 60)
    inn1_penalties = derive_first_innings_penalties(df)
    for phase in ["powerplay", "middle", "death", "final"]:
        print(f"  [{phase}]")
        for ease in ["well_ahead", "ahead", "par", "behind", "well_behind"]:
            print(f"    {ease:14s}: {inn1_penalties[phase][ease]}")
    print()

    # 3. Final over lookup
    print("=" * 60)
    print("3. DERIVING FINAL-OVER LOOKUP TABLE")
    print("=" * 60)
    lookup, rows_data = derive_final_over_lookup(df)
    print("  Runs needed (rows) x Wickets in hand (cols)")
    header = "     " + "".join(f"  wih={w:2d}" for w in range(0, 11))
    print(header)
    for runs in range(0, 21):
        row_str = f"  r={runs:2d}"
        for wih in range(0, 11):
            row_str += f"  {lookup[runs][wih]:6.3f}"
        print(row_str)
    print()

    # 4. Optimal midpoint
    print("=" * 60)
    print("4. DERIVING OPTIMAL FIRST INNINGS MIDPOINT")
    print("=" * 60)
    mid, beta, brier = derive_optimal_midpoint(df)
    print(f"  Optimal midpoint: {mid:.1f}")
    print(f"  Optimal beta: {beta:.3f}")
    print(f"  Brier at optimum: {brier:.4f}")
    print(f"  Current: midpoint=165.0, beta=0.04")
    print()

    # Write output Python file
    print("=" * 60)
    print("WRITING OUTPUT FILES")
    print("=" * 60)

    with open(OUTPUT_PY, "w") as f:
        f.write('"""IPL-derived penalty tables and lookup data.\n\n')
        f.write("Generated by scripts/derive_ipl_improvements.py\n")
        f.write(f"Source: {DATA_PATH.name} ({len(df)} rows)\n")
        f.write('"""\n\n')

        # Chase penalties
        f.write("# Chase wicket penalties (2nd innings)\n")
        f.write("# Derived from IPL empirical win rates by ease_level x wickets_lost\n")
        f.write("IPL_CHASE_WICKET_PENALTY_2D = {\n")
        for level in ["very_easy", "easy", "comfortable", "tough", "desperate"]:
            pens = chase_penalties[level]
            f.write(f'    "{level}": {format_penalty_dict(pens)},\n')
        f.write("}\n\n")

        # First innings penalties
        f.write("# First innings wicket penalties\n")
        f.write("# Derived from IPL empirical win rates by phase x ease x wickets\n")
        f.write("IPL_FIRST_INNINGS_WICKET_PENALTY_3D = {\n")
        for phase in ["powerplay", "middle", "death", "final"]:
            f.write(f'    "{phase}": {{\n')
            for ease in ["well_ahead", "ahead", "par", "behind", "well_behind"]:
                pens = inn1_penalties[phase][ease]
                f.write(f'        "{ease}": {format_penalty_dict(pens)},\n')
            f.write("    },\n")
        f.write("}\n\n")

        # Final over lookup
        f.write("# Final-over lookup: runs_needed -> {wickets_in_hand -> win_prob}\n")
        f.write("# Derived from IPL second-innings final-over data\n")
        f.write("IPL_FINAL_OVER_LOOKUP = {\n")
        for runs in range(0, 26):
            probs = lookup[runs]
            items = [f"{w}: {probs[w]:.4f}" for w in range(0, 11)]
            f.write(f"    {runs}: {{{', '.join(items)}}},\n")
        f.write("}\n\n")

        # Midpoint
        f.write(f"# Optimal first innings score midpoint for IPL\n")
        f.write(f"IPL_FIRST_INNINGS_SCORE_MIDPOINT = {mid:.1f}\n")
        f.write(f"IPL_FIRST_INNINGS_SCORE_BETA = {beta:.3f}\n")

    print(f"  Written: {OUTPUT_PY}")

    # Write CSV
    lookup_df = pd.DataFrame(rows_data)
    lookup_df.to_csv(OUTPUT_CSV, index=False)
    print(f"  Written: {OUTPUT_CSV}")

    print()
    print("Done! Review scripts/ipl_derived_tables.py and apply to format_config.py")


if __name__ == "__main__":
    main()
