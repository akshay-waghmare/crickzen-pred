import pandas as pd
import numpy as np

# Load the full dataframe (not the training one, as we need match_id and ball info which might be dropped)
# Actually, processor.py saves 'training.parquet' with only feature_cols.
# But I need match_id to check transitions.
# Wait, processor.py saves 'training.parquet' with ONLY feature_cols.
# And feature_cols does NOT include match_id or ball number.
# This makes it hard to debug the transition.

# However, I can check the 'resource_win_prob' distribution.

# Let's try to load the raw parquet files and re-run the calculation for a single match to verify.
# Or I can modify processor.py to include match_id in the output for debugging.

# Better yet, I can use the 'training_sampled.parquet' which might have more info?
# No, it uses the same feature_cols.

# I will create a script that imports the processor logic and runs it on a small subset, printing the transition values.

from bbl_pipeline.features.calculator import ResourceFeatureCalculator

def test_transition():
    calc = ResourceFeatureCalculator()
    
    # Simulate end of innings 1
    # Score 160/5 in 20 overs.
    inn1_end = calc.calculate_all_features(
        innings=1,
        over=19,
        ball=6,
        current_score=160,
        wickets_lost=5,
        target_runs=None
    )
    print(f"Innings 1 End Prob: {inn1_end['resource_win_prob']:.4f}")
    
    # Simulate start of innings 2
    # Target 161. Score 0/0 in 0.0 overs.
    # We MUST pass innings1_end_prob to see the effect.
    
    inn2_start_with_fix = calc.calculate_all_features(
        innings=2,
        over=0,
        ball=1,
        current_score=0,
        wickets_lost=0,
        target_runs=161,
        innings1_end_prob=inn1_end['resource_win_prob']
    )
    print(f"Innings 2 Start Prob (WITH fix): {inn2_start_with_fix['resource_win_prob']:.4f}")
    
    inn2_start_no_fix = calc.calculate_all_features(
        innings=2,
        over=0,
        ball=1,
        current_score=0,
        wickets_lost=0,
        target_runs=161,
        innings1_end_prob=0.5 # Default
    )
    print(f"Innings 2 Start Prob (NO fix): {inn2_start_no_fix['resource_win_prob']:.4f}")

if __name__ == "__main__":
    test_transition()
