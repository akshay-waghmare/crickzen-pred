"""
Test the new professional first innings v2 calculator.
Validates:
1. SQI-based probability mapping
2. Wicket capability decay (affects score, not probability directly)
3. Confidence blending with historical prior
4. Phase-dependent standard deviation
"""
from src.bbl_pipeline.features.calculator import ResourceFeatureCalculator

calc = ResourceFeatureCalculator()

print("=" * 80)
print("FIRST INNINGS V2 PROFESSIONAL MODEL TEST")
print("=" * 80)

# Test scenarios across phases
test_cases = [
    # Powerplay tests (overs 1-6)
    {"desc": "PP: 30/0 (3.0 ov) - Good start", "expected": 180, "balls_left": 102, "wickets": 0},
    {"desc": "PP: 20/3 (3.0 ov) - Poor start", "expected": 140, "balls_left": 102, "wickets": 3},
    {"desc": "PP: 50/1 (6.0 ov) - Strong PP", "expected": 190, "balls_left": 84, "wickets": 1},
    {"desc": "PP: 35/2 (6.0 ov) - Mediocre PP", "expected": 155, "balls_left": 84, "wickets": 2},
    
    # Middle overs tests (overs 7-15)
    {"desc": "MID: 70/1 (10.0 ov) - On track", "expected": 165, "balls_left": 60, "wickets": 1},
    {"desc": "MID: 90/2 (10.0 ov) - Ahead", "expected": 185, "balls_left": 60, "wickets": 2},
    {"desc": "MID: 60/4 (10.0 ov) - Struggling", "expected": 140, "balls_left": 60, "wickets": 4},
    {"desc": "MID: 110/2 (12.0 ov) - Dominant", "expected": 200, "balls_left": 48, "wickets": 2},
    {"desc": "MID: 80/5 (12.0 ov) - Crisis", "expected": 130, "balls_left": 48, "wickets": 5},
    
    # Death overs tests (overs 16-20)
    {"desc": "DTH: 130/3 (16.0 ov) - Par", "expected": 165, "balls_left": 24, "wickets": 3},
    {"desc": "DTH: 150/2 (16.0 ov) - Strong", "expected": 185, "balls_left": 24, "wickets": 2},
    {"desc": "DTH: 100/6 (16.0 ov) - Collapse", "expected": 130, "balls_left": 24, "wickets": 6},
    {"desc": "DTH: 160/4 (18.0 ov) - Final push", "expected": 175, "balls_left": 12, "wickets": 4},
    {"desc": "DTH: 180/3 (19.0 ov) - Excellent", "expected": 195, "balls_left": 6, "wickets": 3},
]

print(f"\n{'Scenario':<35} {'Exp Score':<10} {'Wickets':<8} {'Win Prob':<10}")
print("-" * 70)

for tc in test_cases:
    balls_remaining = tc["balls_left"]
    overs_bowled = 20 - balls_remaining / 6.0
    resource_pct = calc.calculate_resource_percentage(balls_remaining / 6.0, tc["wickets"])
    
    prob = calc.calculate_resource_win_probability(
        innings=1,
        expected_final_score=tc["expected"],
        target_runs=0,
        resource_pct=resource_pct,
        current_run_rate=0,
        required_run_rate=0,
        current_score=0,
        balls_remaining=balls_remaining,
        wickets_lost=tc["wickets"]
    )
    
    print(f"{tc['desc']:<35} {tc['expected']:<10} {tc['wickets']:<8} {prob*100:.1f}%")

# Show component breakdown for key scenarios
print("\n" + "=" * 80)
print("COMPONENT BREAKDOWN (Key Scenarios)")
print("=" * 80)

breakdown_cases = [
    {"desc": "Early: 30/0 (3 ov), proj 180", "expected": 180, "balls_left": 102, "wickets": 0},
    {"desc": "Mid: 80/5 (12 ov), proj 130", "expected": 130, "balls_left": 48, "wickets": 5},
    {"desc": "Late: 160/4 (18 ov), proj 175", "expected": 175, "balls_left": 12, "wickets": 4},
]

for tc in breakdown_cases:
    balls_remaining = tc["balls_left"]
    overs_bowled = 20 - balls_remaining / 6.0
    overs_progress = overs_bowled / 20.0
    expected = tc["expected"]
    wickets = tc["wickets"]
    
    import numpy as np
    
    # Step 1: Wicket capability
    wicket_cap = np.exp(-calc.WICKET_DECAY_ALPHA * wickets)
    adjusted_score = expected * wicket_cap
    
    # Step 2: Phase std and SQI
    phase_std = calc.SCORE_STD_EARLY + overs_progress * (calc.SCORE_STD_LATE - calc.SCORE_STD_EARLY)
    sqi = (adjusted_score - calc.LEAGUE_AVG_SCORE) / phase_std
    
    # Step 3: SQI to prob
    sqi_prob = 1.0 / (1.0 + np.exp(-calc.SQI_BETA * sqi))
    
    # Step 4: Confidence blend
    confidence = min(1.0, overs_bowled / calc.CONFIDENCE_FULL_OVERS)
    final_prob = (1 - confidence) * calc.HISTORICAL_BAT_FIRST_WIN_RATE + confidence * sqi_prob
    
    print(f"\n{tc['desc']}")
    print(f"  Overs: {overs_bowled:.1f}, Progress: {overs_progress:.1%}")
    print(f"  Wicket Capability: {wicket_cap:.3f} (5 wkts would be {np.exp(-calc.WICKET_DECAY_ALPHA * 5):.3f})")
    print(f"  Adjusted Expected Score: {adjusted_score:.1f} (raw: {expected})")
    print(f"  Phase Std Dev: {phase_std:.1f}")
    print(f"  SQI: {sqi:+.2f} ({adjusted_score:.1f} vs par {calc.LEAGUE_AVG_SCORE})")
    print(f"  SQI-based prob: {sqi_prob:.1%}")
    print(f"  Confidence: {confidence:.1%}")
    print(f"  Historical prior: {calc.HISTORICAL_BAT_FIRST_WIN_RATE:.1%}")
    print(f"  FINAL WIN PROB: {final_prob:.1%}")

# Edge cases
print("\n" + "=" * 80)
print("EDGE CASE VALIDATION")
print("=" * 80)

edge_cases = [
    {"desc": "All out early (10 wkts)", "expected": 80, "balls_left": 60, "wickets": 10},
    {"desc": "Massive projected (250)", "expected": 250, "balls_left": 48, "wickets": 2},
    {"desc": "Very low projected (100)", "expected": 100, "balls_left": 48, "wickets": 6},
]

for tc in edge_cases:
    balls_remaining = tc["balls_left"]
    resource_pct = calc.calculate_resource_percentage(balls_remaining / 6.0, tc["wickets"])
    
    prob = calc.calculate_resource_win_probability(
        innings=1,
        expected_final_score=tc["expected"],
        target_runs=0,
        resource_pct=resource_pct,
        current_run_rate=0,
        required_run_rate=0,
        current_score=0,
        balls_remaining=balls_remaining,
        wickets_lost=tc["wickets"]
    )
    
    print(f"{tc['desc']}: {prob*100:.1f}%")

print("\n" + "=" * 80)
print("Constants Used (EDA-Validated)")
print("=" * 80)
print(f"  HISTORICAL_BAT_FIRST_WIN_RATE: {calc.HISTORICAL_BAT_FIRST_WIN_RATE}")
print(f"  LEAGUE_AVG_SCORE: {calc.LEAGUE_AVG_SCORE}")
print(f"  WICKET_DECAY_ALPHA: {calc.WICKET_DECAY_ALPHA}")
print(f"  SCORE_STD_EARLY: {calc.SCORE_STD_EARLY}")
print(f"  SCORE_STD_LATE: {calc.SCORE_STD_LATE}")
print(f"  CONFIDENCE_FULL_OVERS: {calc.CONFIDENCE_FULL_OVERS}")
print(f"  SQI_BETA: {calc.SQI_BETA}")
