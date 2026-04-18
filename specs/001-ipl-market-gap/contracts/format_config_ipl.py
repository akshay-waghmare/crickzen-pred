"""
Contract: IPL FormatConfig Override

Defines the expected interface for FormatConfig.ipl() after the IPL market gap
improvement. This contract specifies which fields MUST be overridden and their
expected value ranges.

This is a design contract, not executable code. Implementation modifies
src/bbl_pipeline/features/format_config.py.
"""

from typing import Dict


# --- Contract: FormatConfig.ipl() must override these fields from t20() base ---

IPL_CONFIG_OVERRIDES = {
    # Existing overrides (unchanged)
    "par_score": 173.45,
    "league_avg_score": 167.28,
    "bat_first_win_rate": 0.4581,
    "expected_run_rates": {
        "powerplay": 7.53,
        "middle": 7.51,
        "death": 9.02,
        "final": 10.68,
    },

    # NEW overrides for this feature
    "first_innings_score_midpoint": 173.0,  # FR-007: was 165.0 (inherited)
    # Range: 170.0 <= midpoint <= 176.0 (within ±3 of 173.45)

    "chase_wicket_penalty_2d": "IPL-SPECIFIC",
    # FR-001/FR-002: Derived from training data
    # Contract: For wickets 4-8, every value MUST be < T20 base value

    "first_innings_wicket_penalty_3d": "IPL-SPECIFIC",
    # FR-001: Derived from training data
    # Contract: For wickets 4-8, every value MUST be < T20 base value
}


# --- Contract: Chase wicket penalty structure ---

CHASE_PENALTY_CONTRACT = {
    "dimensions": ["ease_level", "wickets_lost"],
    "ease_levels": ["very_easy", "easy", "comfortable", "tough", "desperate"],
    "wickets_range": range(0, 11),  # 0-10 inclusive
    "value_range": (0.0, 1.0),
    "constraints": [
        "penalty[ease][w] <= penalty[ease][w-1] for w > 0 (monotonic decrease with wickets)",
        "penalty[harder_ease][w] <= penalty[easier_ease][w] (harder chase = harsher penalty)",
        "penalty[any][10] == 0.0 (all out = zero probability)",
        "penalty[any][0] == 1.0 (no wickets lost = no penalty)",
        "For w in 4..8: IPL penalty < T20 base penalty (FR-002 strict requirement)",
    ],
}


# --- Contract: First innings penalty structure ---

FIRST_INNINGS_PENALTY_CONTRACT = {
    "dimensions": ["phase", "ease_bucket", "wickets_lost"],
    "phases": ["powerplay", "middle", "death", "final"],
    "ease_buckets": ["well_ahead", "ahead", "par", "behind", "well_behind"],
    "wickets_range": range(0, 11),
    "value_range": (0.0, 1.0),
    "constraints": [
        "Same monotonicity rules as chase penalties",
        "For w in 4..8: IPL penalty < T20 base penalty (FR-002)",
    ],
}
