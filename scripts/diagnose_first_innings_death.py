"""
Diagnose First Innings Death Over Win Probability Issues.

Issues reported:
1. High score + wickets fallen → probability too low
2. Low scoring matches → model is too optimistic

This script tests various first innings death over scenarios to identify calibration issues.
"""
from bbl_pipeline.features.calculator import ResourceFeatureCalculator
import numpy as np

calc = ResourceFeatureCalculator()


def test_scenario(desc: str, over: float, ball: int, score: int, wickets: int):
    """Test a first innings scenario and print diagnostics."""
    overs_bowled = over + ball / 6.0
    balls_remaining = int((20 - overs_bowled) * 6)
    
    # Calculate current run rate
    if overs_bowled > 0:
        crr = score / overs_bowled
    else:
        crr = 0
    
    features = calc.calculate_all_features(
        innings=1,
        over=int(over),
        ball=ball,
        current_score=score,
        wickets_lost=wickets,
        target_runs=None
    )
    
    # Get individual components for diagnosis
    phase = calc.get_first_innings_phase(overs_bowled)
    ease_bucket = calc.get_first_innings_ease_bucket(crr, phase)
    wicket_penalty = calc.get_first_innings_dynamic_penalty(wickets, overs_bowled, crr)
    
    expected_score = features['expected_final_score']
    resource_prob = features['resource_win_prob']
    
    # Calculate expected RR for this phase
    expected_rr = calc.FIRST_INNINGS_EXPECTED_RR.get(phase, 8.0)
    ease_ratio = crr / expected_rr if expected_rr > 0 else 1.0
    
    print(f"\n{desc}")
    print(f"  State: {score}/{wickets} at {overs_bowled:.1f} overs")
    print(f"  Phase: {phase}")
    print(f"  CRR: {crr:.2f} | Expected RR: {expected_rr:.1f} | Ease ratio: {ease_ratio:.2f}")
    print(f"  Ease bucket: {ease_bucket}")
    print(f"  Wicket penalty: {wicket_penalty:.3f}")
    print(f"  Projected score: {expected_score:.0f}")
    print(f"  Win probability: {resource_prob:.1%}")
    
    return features


print("=" * 80)
print("ISSUE 1: HIGH SCORE + WICKETS → PROBABILITY TOO LOW?")
print("=" * 80)

# Death overs - high scores with wickets fallen
test_scenario("HIGH: 180/4 at 18.0 overs (excellent position)", 18, 0, 180, 4)
test_scenario("HIGH: 170/5 at 17.0 overs (still great)", 17, 0, 170, 5)
test_scenario("HIGH: 160/6 at 16.0 overs (good despite wickets)", 16, 0, 160, 6)
test_scenario("HIGH: 150/7 at 15.0 overs (dangerous)", 15, 0, 150, 7)

print("\n" + "=" * 80)
print("ISSUE 2: LOW SCORING MATCHES → MODEL TOO OPTIMISTIC?")
print("=" * 80)

# Death overs - low scores
test_scenario("LOW: 110/3 at 15.0 overs (below par, few wkts)", 15, 0, 110, 3)
test_scenario("LOW: 100/4 at 15.0 overs (below par, some wkts)", 15, 0, 100, 4)
test_scenario("LOW: 90/5 at 15.0 overs (poor, middle order exposed)", 15, 0, 90, 5)
test_scenario("LOW: 80/6 at 15.0 overs (collapse)", 15, 0, 80, 6)

# Compare to par score scenario
test_scenario("PAR: 130/3 at 15.0 overs (on track)", 15, 0, 130, 3)

print("\n" + "=" * 80)
print("EXPECTED WIN RATES BY SCORE BUCKET (From Research)")
print("=" * 80)
print("""
Historical First Innings Win Rates (T20):
- Score < 140:  ~25-30% win rate
- Score 140-160: ~35-40% win rate  
- Score 160-180: ~45-55% win rate
- Score 180-200: ~60-70% win rate
- Score > 200:   ~75-85% win rate

BBL Averages: 164 mean score, 42% bat-first win rate
""")

print("\n" + "=" * 80)
print("DEATH OVER FINAL SCENARIOS (18-20 overs)")
print("=" * 80)

test_scenario("FINAL: 195/4 at 19.0 overs (on for 210)", 19, 0, 195, 4)
test_scenario("FINAL: 175/4 at 19.0 overs (on for 185)", 19, 0, 175, 4)
test_scenario("FINAL: 155/4 at 19.0 overs (on for 165)", 19, 0, 155, 4)
test_scenario("FINAL: 135/4 at 19.0 overs (on for 145)", 19, 0, 135, 4)
test_scenario("FINAL: 115/4 at 19.0 overs (on for 125)", 19, 0, 115, 4)

# Very low vs very high
test_scenario("EXTREME LOW: 100/8 at 18.0 overs (collapsed)", 18, 0, 100, 8)
test_scenario("EXTREME HIGH: 200/3 at 18.0 overs (dominant)", 18, 0, 200, 3)

print("\n" + "=" * 80)
print("DIAGNOSIS: WICKET PENALTY TABLE VALUES")
print("=" * 80)

# Print the 3D wicket penalty table for death phase
print("\nDeath phase wicket penalties by ease × wickets:")
print("-" * 80)
print(f"{'Ease':<15} | " + " | ".join([f"{w}W" for w in range(0, 10, 2)]))
print("-" * 80)

for ease in ['well_ahead', 'ahead', 'par', 'behind', 'well_behind']:
    penalties = calc.FIRST_INNINGS_WICKET_PENALTY_3D['death'][ease]
    row = f"{ease:<15} | "
    row += " | ".join([f"{penalties.get(w, 0):.2f}" for w in range(0, 10, 2)])
    print(row)

print("\n" + "=" * 80)
print("PROPOSED FIXES")
print("=" * 80)
print("""
OBSERVATIONS:
1. If high scores with wickets show LOW probability:
   → Death/final phase wicket penalties may be too harsh
   → The model may not be trusting the "banked runs" enough

2. If low scores show HIGH probability (too optimistic):
   → The SQI_BETA (sigmoid steepness) may be too gentle
   → The HISTORICAL_BAT_FIRST_WIN_RATE blend may be dominating
   → Low score scenarios may need steeper penalties

POTENTIAL ADJUSTMENTS:
- For high score issue: Increase wicket penalties in death phase toward 1.0
- For low score issue: Decrease SQI_BETA or adjust contextual_par
- Consider: Separate calibration for different score brackets
""")

# Final check: What's the probability range across all realistic scenarios?
print("\n" + "=" * 80)
print("PROBABILITY DISTRIBUTION CHECK")
print("=" * 80)

probs = []
for score in range(80, 220, 10):
    for wickets in range(0, 9):
        features = calc.calculate_all_features(
            innings=1, over=18, ball=0,
            current_score=score, wickets_lost=wickets, target_runs=None
        )
        probs.append((score, wickets, features['resource_win_prob']))

print(f"\nAt 18 overs (death phase):")
print(f"  Min prob: {min(p[2] for p in probs):.1%} (score={min(p[:2] for p in probs if p[2] == min(p[2] for p in probs))[0]}, wkts={min(p[:2] for p in probs if p[2] == min(p[2] for p in probs))[1]})")
print(f"  Max prob: {max(p[2] for p in probs):.1%} (score={max(p[:2] for p in probs if p[2] == max(p[2] for p in probs))[0]}, wkts={max(p[:2] for p in probs if p[2] == max(p[2] for p in probs))[1]})")

# Check low score probabilities
print("\nLow score probabilities at 18 overs:")
for score in [80, 90, 100, 110]:
    for wkts in [4, 6, 8]:
        features = calc.calculate_all_features(
            innings=1, over=18, ball=0,
            current_score=score, wickets_lost=wkts, target_runs=None
        )
        print(f"  {score}/{wkts}: {features['resource_win_prob']:.1%}")

print("\nHigh score probabilities at 18 overs:")
for score in [180, 190, 200, 210]:
    for wkts in [3, 5, 7]:
        features = calc.calculate_all_features(
            innings=1, over=18, ball=0,
            current_score=score, wickets_lost=wkts, target_runs=None
        )
        print(f"  {score}/{wkts}: {features['resource_win_prob']:.1%}")
