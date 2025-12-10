"""
Debug: Test why model outputs lower probability after scoring a six.

Scenario:
- Team chasing 158 in ILT20
- Before: 23/0 off 2.0 overs -> 78.0% win prob
- After:  29/0 off 2.1 overs -> 74.7% win prob (after a SIX!)

This is clearly wrong. Let's find the bug.
"""
import pandas as pd
import numpy as np

# Load the model
from bbl_pipeline.inference.predictor import Predictor
from bbl_pipeline.inference.schema import MatchState

# Load the ILT20 model
predictor = Predictor.load("models/ilt_champion", "data/ilt_feature_store")

# Test scenario: chasing 158 at Dubai
# State BEFORE the six: 23/0 off 2.0 overs
state_before = MatchState(
    match_id="test_debug",
    venue="Dubai International Cricket Stadium",
    batting_team="Gulf Giants",
    bowling_team="Sharjah Warriorz",
    innings=2,
    over=2,
    ball=0,  # 2.0 overs
    current_score=23,
    wickets_lost=0,
    batsman_1="Unknown",
    batsman_2="Unknown",
    bowler="Unknown",
    target_runs=158,
)

# State AFTER the six: 29/0 off 2.1 overs
state_after = MatchState(
    match_id="test_debug",
    venue="Dubai International Cricket Stadium",
    batting_team="Gulf Giants",
    bowling_team="Sharjah Warriorz",
    innings=2,
    over=2,
    ball=1,  # 2.1 overs
    current_score=29,
    wickets_lost=0,
    batsman_1="Unknown",
    batsman_2="Unknown",
    bowler="Unknown",
    target_runs=158,
)

print("="*80)
print("DEBUG: Model prediction after scoring a SIX")
print("="*80)

print("\n--- BEFORE SIX: 23/0 (2.0 overs) ---")
prob_before = predictor.predict(state_before, debug=True)
print(f"\n>>> Model prediction: {prob_before*100:.2f}%")

print("\n--- AFTER SIX: 29/0 (2.1 overs) ---")
prob_after = predictor.predict(state_after, debug=True)
print(f"\n>>> Model prediction: {prob_after*100:.2f}%")

print("\n" + "="*80)
print("COMPARISON")
print("="*80)
print(f"Before six: {prob_before*100:.2f}%")
print(f"After six:  {prob_after*100:.2f}%")
print(f"Change:     {(prob_after - prob_before)*100:+.2f}%")

if prob_after < prob_before:
    print("\n🔴 BUG CONFIRMED: Probability DECREASED after scoring a six!")
else:
    print("\n🟢 OK: Probability increased correctly")
