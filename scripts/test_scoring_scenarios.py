"""
Test multiple scenarios to verify the expected_final_score fix works correctly.
"""
from bbl_pipeline.inference.predictor import Predictor
from bbl_pipeline.inference.schema import MatchState

predictor = Predictor.load("models/ilt_champion_v2", "data/ilt_feature_store_v2")

def test_scenario(name, states):
    """Test a sequence of match states and verify probability increases when scoring."""
    print(f"\n{'='*70}")
    print(f"SCENARIO: {name}")
    print(f"{'='*70}")
    
    prev_prob = None
    for label, state in states:
        prob = predictor.predict(state)
        
        if prev_prob is not None:
            delta = prob - prev_prob
            symbol = "✅" if delta >= 0 else "🔴"
            print(f"  {label}: {prob*100:.2f}% ({delta*100:+.2f}%) {symbol}")
        else:
            print(f"  {label}: {prob*100:.2f}%")
        
        prev_prob = prob

# Helper to create states
def make_state(score, over, ball, wickets=0, target=158):
    return MatchState(
        match_id="test",
        venue="Dubai International Cricket Stadium",
        batting_team="Gulf Giants",
        bowling_team="Sharjah Warriorz",
        innings=2,
        over=over,
        ball=ball,
        current_score=score,
        wickets_lost=wickets,
        batsman_1="Unknown",
        batsman_2="Unknown", 
        bowler="Unknown",
        target_runs=target,
    )

# Test 1: Original bug scenario - six in early overs
test_scenario("Six in early overs (original bug)", [
    ("23/0 (2.0 ov)", make_state(23, 2, 0)),
    ("29/0 (2.1 ov) +6", make_state(29, 2, 1)),
])

# Test 2: Multiple consecutive boundaries
test_scenario("Multiple boundaries in powerplay", [
    ("10/0 (1.0 ov)", make_state(10, 1, 0)),
    ("14/0 (1.1 ov) +4", make_state(14, 1, 1)),
    ("20/0 (1.2 ov) +6", make_state(20, 1, 2)),
    ("24/0 (1.3 ov) +4", make_state(24, 1, 3)),
    ("26/0 (1.4 ov) +2", make_state(26, 1, 4)),
])

# Test 3: Wicket should decrease probability
test_scenario("Wicket should decrease probability", [
    ("50/0 (5.0 ov)", make_state(50, 5, 0, wickets=0)),
    ("50/1 (5.1 ov) W", make_state(50, 5, 1, wickets=1)),
    ("56/1 (5.3 ov) +6", make_state(56, 5, 3, wickets=1)),
])

# Test 4: Middle overs scenario
test_scenario("Middle overs scoring", [
    ("80/2 (10.0 ov)", make_state(80, 10, 0, wickets=2)),
    ("84/2 (10.1 ov) +4", make_state(84, 10, 1, wickets=2)),
    ("90/2 (10.2 ov) +6", make_state(90, 10, 2, wickets=2)),
])

# Test 5: Death overs - tight chase
test_scenario("Death overs tight chase", [
    ("130/4 (18.0 ov) need 28", make_state(130, 18, 0, wickets=4)),
    ("136/4 (18.1 ov) +6", make_state(136, 18, 1, wickets=4)),
    ("142/4 (18.2 ov) +6", make_state(142, 18, 2, wickets=4)),
])

# Test 6: Easy chase in death overs
test_scenario("Easy death overs (10 from 12)", [
    ("148/2 (18.0 ov) need 10", make_state(148, 18, 0, wickets=2)),
    ("152/2 (18.1 ov) +4", make_state(152, 18, 1, wickets=2)),
    ("158/2 (18.2 ov) WON", make_state(158, 18, 2, wickets=2)),
])

print("\n" + "="*70)
print("Summary: ✅ means probability increased after scoring (correct)")
print("         🔴 means probability decreased after scoring (BUG)")
print("="*70)
