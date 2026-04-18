"""
Contract: Final-Over Lookup Table

Defines the interface for the empirical final-over win probability lookup that
replaces the sigmoid formula at calculator.py:883-898.

This is a design contract, not executable code. Implementation modifies
src/bbl_pipeline/features/calculator.py and win_prob_lookup_tables.py.
"""

from typing import Dict, Optional


# --- Contract: Lookup table structure ---

class FinalOverLookupContract:
    """
    Contract for the final-over empirical lookup table.

    Replaces: calculator.py L887:
        endgame_prob = 1.0 / (1.0 + np.exp(4 * (runs_per_ball_needed - 1.5)))

    With: Direct empirical lookup from IPL historical data.

    Structure:
        FINAL_OVER_WIN_PROB[runs_needed][wickets_in_hand] -> float (0.0-1.0)
    """

    # Table dimensions
    MAX_RUNS_NEEDED: int = 25       # rows 0-25
    MAX_WICKETS_IN_HAND: int = 10   # columns 0-10

    # Type signature
    table_type = Dict[int, Dict[int, float]]  # runs_needed -> wickets_in_hand -> prob

    # Boundary conditions (MUST be enforced)
    BOUNDARY_CONDITIONS = {
        "runs_needed_0": "Always 1.0 (already won) for any wickets > 0",
        "wickets_0": "Always 0.0 (all out) for any runs > 0",
        "runs_gt_20_wickets_le_2": "Default 0.0 (near-impossible)",
        "runs_needed_0_wickets_0": "Not applicable (match already decided)",
    }

    # Monotonicity constraints
    MONOTONICITY = {
        "runs_axis": "For fixed wickets: prob(r) >= prob(r+1)",
        "wickets_axis": "For fixed runs: prob(w) <= prob(w+1)",
    }

    # Integration point in calculator.py
    TRIGGER_CONDITION = "balls_remaining <= 6"  # Over 20 = final over only
    # Note: Current endgame uses endgame_balls=12 (2 overs). The lookup
    # replaces ONLY the final over (6 balls). Overs 18-19 continue to use
    # the sigmoid.


# --- Contract: Lookup function signature ---

def get_final_over_win_prob(
    runs_needed: int,
    wickets_in_hand: int,
    lookup_table: Dict[int, Dict[int, float]],
) -> float:
    """
    Look up empirical win probability for final-over scenarios.

    Args:
        runs_needed: Runs required to win (0+)
        wickets_in_hand: Wickets remaining (0-10)
        lookup_table: Pre-computed empirical table

    Returns:
        Win probability in [0.0, 1.0]

    Behavior:
        1. If runs_needed <= 0: return 1.0
        2. If wickets_in_hand <= 0: return 0.0
        3. If (runs_needed, wickets_in_hand) in table: return table value
        4. If runs_needed > MAX_RUNS: return 0.01 (near-impossible)
        5. Otherwise: interpolate from nearest cells maintaining monotonicity
    """
    ...


# --- Contract: Data derivation requirements ---

DERIVATION_CONTRACT = {
    "source": "Cricsheet IPL JSON files (ipl_male_json/)",
    "filter": "Second innings, final over (over == 20 in T20)",
    "group_by": ["runs_needed_at_start_of_over", "wickets_in_hand_at_start_of_over"],
    "metric": "win_rate = chasing_team_wins / total_observations",
    "min_samples_per_cell": 5,
    "sparse_fill_strategy": "Monotonic interpolation from populated neighbors",
    "output": "Python dict literal in win_prob_lookup_tables.py",
}
