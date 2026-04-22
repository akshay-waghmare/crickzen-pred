"""
Derive PSL-specific model improvements from training data.

Produces:
  1. PSL chase wicket penalties (WICKET_PENALTY_2D)
  2. PSL first-innings wicket penalties (FIRST_INNINGS_WICKET_PENALTY_3D)
  3. Final-over empirical lookup table (runs_needed x wickets_in_hand -> win_prob)
  4. Optimal first_innings_score_midpoint for PSL
  5. Key scoring constants (par_score, league_avg_score, bat_first_win_rate, run rates)

Usage:
    python scripts/derive_psl_improvements.py

Output:
    scripts/psl_derived_tables.py   - Python dict literals ready to paste
    data/psl_final_over_lookup.csv  - Final over lookup as CSV
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "psl_features_v1" / "training.parquet"
OUTPUT_PY = ROOT / "scripts" / "psl_derived_tables.py"
OUTPUT_CSV = ROOT / "data" / "psl_final_over_lookup.csv"


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


# ── 0. Basic Scoring Constants ──────────────────────────────────────────────


def derive_scoring_constants(df: pd.DataFrame) -> dict:
    """Derive par_score, league_avg_score, bat_first_win_rate, run rates from PSL data."""
    inn1 = df[df["innings"] == 1]
    inn2 = df[df["innings"] == 2]

    # Average final score from end-of-innings rows
    eoi1 = inn1[inn1["overs_remaining"] <= 0.5]
    par_score = eoi1["expected_final_score"].mean() if len(eoi1) > 100 else inn1["expected_final_score"].max()

    # League average first-innings score
    league_avg_score = inn1["expected_final_score"].mean()

    # Bat-first win rate: use end-of-innings rows for inn1 as a proxy
    eoi1_wr = eoi1["is_winner"].mean() if len(eoi1) > 50 else 0.50
    bat_first_win_rate = round(float(eoi1_wr), 4)

    # Per-phase run rates from inn1
    run_rates = {}
    for phase in ["powerplay", "middle", "death", "final"]:
        phase_data = inn1[inn1["phase"] == phase]
        if len(phase_data) > 100 and "current_run_rate" in phase_data.columns:
            run_rates[phase] = round(phase_data["current_run_rate"].median(), 2)
        else:
            # Fallback T20 defaults
            defaults = {"powerplay": 7.0, "middle": 7.0, "death": 8.5, "final": 10.0}
            run_rates[phase] = defaults[phase]

    return {
        "par_score": round(par_score, 2),
        "league_avg_score": round(league_avg_score, 2),
        "bat_first_win_rate": round(bat_first_win_rate, 4),
        "run_rates": run_rates,
    }


# ── 1. Chase Wicket Penalties (2nd Innings) ─────────────────────────────────


def derive_chase_penalties(df: pd.DataFrame) -> dict:
    """Derive WICKET_PENALTY_2D from inn2 empirical win rates."""
    inn2 = df[df["innings"] == 2].copy()

    inn2["ease_ratio"] = np.where(
        inn2["required_run_rate"] > 0.1,
        inn2["current_run_rate"] / inn2["required_run_rate"],
        3.5,
    )

    thresholds = {"very_easy": 3.0, "easy": 1.5, "comfortable": 1.0, "tough": 0.7, "desperate": 0.0}
    ordered_levels = ["desperate", "tough", "comfortable", "easy", "very_easy"]
    ordered_thresholds = [0.0, 0.7, 1.0, 1.5, 3.0]

    def classify_ease(ratio):
        for level, thresh in zip(reversed(ordered_levels), reversed(ordered_thresholds)):
            if ratio >= thresh:
                return level
        return "desperate"

    inn2["ease_level"] = inn2["ease_ratio"].apply(classify_ease)

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
                raw_wr = wk_data["is_winner"].mean()
                penalty = min(1.0, raw_wr / base_wr * 0.9 + 0.1)
            else:
                penalty = max(0.0, 1.0 - wk * 0.12) if level in ("very_easy", "easy") else max(0.0, 1.0 - wk * 0.15)

            penalties[wk] = round(max(0.00, min(1.00, penalty)), 2)

        for wk in range(1, 11):
            if penalties[wk] > penalties[wk - 1]:
                penalties[wk] = penalties[wk - 1]

        penalties[10] = 0.00
        result[level] = penalties

    return result


# ── 2. First Innings Wicket Penalties ────────────────────────────────────────


def derive_first_innings_penalties(df: pd.DataFrame, par_score: float) -> dict:
    """Derive FIRST_INNINGS_WICKET_PENALTY_3D from inn1 empirical data."""
    inn1 = df[df["innings"] == 1].copy()

    inn1["par_ratio"] = np.where(
        inn1["expected_final_score"] > 0,
        inn1["expected_final_score"] / par_score,
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
                    if phase in ("death", "final"):
                        penalty = max(0.01, 1.0 - wk * 0.08)
                    else:
                        penalty = max(0.01, 1.0 - wk * 0.12)

                penalties[wk] = round(max(0.01, min(1.00, penalty)), 2)

            for wk in range(1, 11):
                if penalties[wk] > penalties[wk - 1]:
                    penalties[wk] = penalties[wk - 1]

            penalties[10] = 0.01
            result[phase][ease] = penalties

    return result


# ── 3. Final-Over Lookup Table ───────────────────────────────────────────────


def derive_final_over_lookup(df: pd.DataFrame) -> tuple:
    """Derive empirical win probability for final over by runs_needed x wickets_in_hand."""
    inn2 = df[df["innings"] == 2].copy()

    final = inn2[inn2["balls_remaining"] <= 6].copy()

    final["runs_needed"] = (final["required_run_rate"] * final["overs_remaining"]).round().astype(int)
    final["wickets_in_hand"] = 10 - final["wickets_lost"]

    final["runs_needed"] = final["runs_needed"].clip(0, 25)
    final["wickets_in_hand"] = final["wickets_in_hand"].clip(0, 10)

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
                wr = subset["is_winner"].mean() * 0.8 + 0.1
            else:
                wr = None

            lookup[runs][wih] = wr
            rows.append({"runs_needed": runs, "wickets_in_hand": wih, "win_prob": wr, "n": n})

    for runs in range(0, 26):
        if runs == 0:
            for wih in range(0, 11):
                lookup[runs][wih] = 1.0
            continue

        for wih in range(0, 11):
            if lookup[runs][wih] is None:
                if wih == 0:
                    lookup[runs][wih] = 0.0
                else:
                    rpb = runs / max(1, 6)
                    base = 1.0 / (1.0 + np.exp(4 * (rpb - 1.5)))
                    wih_factor = min(1.0, wih / 5.0)
                    lookup[runs][wih] = round(base * wih_factor, 4)

    for wih in range(0, 11):
        for runs in range(1, 26):
            if lookup[runs][wih] > lookup[runs - 1][wih]:
                lookup[runs][wih] = lookup[runs - 1][wih]

    for runs in range(0, 26):
        for wih in range(1, 11):
            if lookup[runs][wih] < lookup[runs][wih - 1]:
                lookup[runs][wih] = lookup[runs][wih - 1]

    for runs in range(0, 26):
        for wih in range(0, 11):
            lookup[runs][wih] = round(lookup[runs][wih], 4)

    return lookup, rows


# ── 4. First Innings Score Midpoint ──────────────────────────────────────────


def derive_optimal_midpoint(df: pd.DataFrame) -> tuple:
    """Find the optimal first_innings_score_midpoint and beta for PSL."""
    inn1 = df[df["innings"] == 1].copy()

    eoi = inn1[inn1["overs_remaining"] <= 1.0].copy()

    best_brier = 1.0
    best_mid = 160.0
    best_beta = 0.04

    for mid in np.arange(150, 180, 1.0):
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
    print("Loading PSL training data...")
    df = load_data()
    print(f"  {len(df)} rows, {len(df.columns)} columns")
    print(f"  Inn1: {len(df[df['innings']==1])}, Inn2: {len(df[df['innings']==2])}")
    print()

    # 0. Scoring constants
    print("=" * 60)
    print("0. DERIVING PSL SCORING CONSTANTS")
    print("=" * 60)
    constants = derive_scoring_constants(df)
    print(f"  par_score:          {constants['par_score']}")
    print(f"  league_avg_score:   {constants['league_avg_score']}")
    print(f"  bat_first_win_rate: {constants['bat_first_win_rate']}")
    print(f"  run_rates:          {constants['run_rates']}")
    par_score = constants["par_score"]
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
    inn1_penalties = derive_first_innings_penalties(df, par_score)
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
    print("  Sample (runs 0-10):")
    header = "     " + "".join(f"  wih={w:2d}" for w in range(0, 11))
    print(header)
    for runs in range(0, 11):
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
    print()

    # Write output Python file
    print("=" * 60)
    print("WRITING OUTPUT FILES")
    print("=" * 60)

    with open(OUTPUT_PY, "w") as f:
        f.write('"""PSL-derived penalty tables and scoring constants.\n\n')
        f.write("Generated by scripts/derive_psl_improvements.py\n")
        f.write(f"Source: {DATA_PATH.name} ({len(df)} rows)\n")
        f.write('"""\n\n')

        f.write("# PSL scoring environment constants\n")
        f.write(f"PSL_PAR_SCORE = {constants['par_score']}\n")
        f.write(f"PSL_LEAGUE_AVG_SCORE = {constants['league_avg_score']}\n")
        f.write(f"PSL_BAT_FIRST_WIN_RATE = {constants['bat_first_win_rate']}\n")
        f.write(f"PSL_FIRST_INNINGS_SCORE_MIDPOINT = {mid:.1f}\n")
        f.write(f"PSL_FIRST_INNINGS_SCORE_BETA = {beta:.3f}\n")
        f.write(f"PSL_EXPECTED_RUN_RATES = {{\n")
        for phase, rr in constants["run_rates"].items():
            f.write(f'    "{phase}": {rr},\n')
        f.write("}\n\n")

        f.write("# Chase wicket penalties (2nd innings)\n")
        f.write("PSL_CHASE_WICKET_PENALTY_2D = {\n")
        for level in ["very_easy", "easy", "comfortable", "tough", "desperate"]:
            pens = chase_penalties[level]
            f.write(f'    "{level}": {format_penalty_dict(pens)},\n')
        f.write("}\n\n")

        f.write("# First innings wicket penalties\n")
        f.write("PSL_FIRST_INNINGS_WICKET_PENALTY_3D = {\n")
        for phase in ["powerplay", "middle", "death", "final"]:
            f.write(f'    "{phase}": {{\n')
            for ease in ["well_ahead", "ahead", "par", "behind", "well_behind"]:
                pens = inn1_penalties[phase][ease]
                f.write(f'        "{ease}": {format_penalty_dict(pens)},\n')
            f.write("    },\n")
        f.write("}\n\n")

        f.write("# Final-over lookup: runs_needed -> {wickets_in_hand -> win_prob}\n")
        f.write("PSL_FINAL_OVER_LOOKUP = {\n")
        for runs in range(0, 26):
            probs = lookup[runs]
            items = [f"{w}: {probs[w]:.4f}" for w in range(0, 11)]
            f.write(f"    {runs}: {{{', '.join(items)}}},\n")
        f.write("}\n")

    print(f"  Written: {OUTPUT_PY}")

    lookup_df = pd.DataFrame(rows_data)
    lookup_df.to_csv(OUTPUT_CSV, index=False)
    print(f"  Written: {OUTPUT_CSV}")

    print()
    print("Done! Review scripts/psl_derived_tables.py and apply to format_config.py")


if __name__ == "__main__":
    main()
