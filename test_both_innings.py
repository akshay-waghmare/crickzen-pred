"""
Test the data-calibrated calculator for both innings.
"""
from src.bbl_pipeline.features.calculator import ResourceFeatureCalculator

calc = ResourceFeatureCalculator()

print("=" * 70)
print("FIRST INNINGS - DATA-CALIBRATED CALCULATOR")
print("=" * 70)

# Test first innings scenarios
scenarios_1st = [
    (1, 5, 0, 50, 0, None, "Powerplay 50/0 (proj ~167)"),
    (1, 5, 0, 50, 2, None, "Powerplay 50/2 (proj ~167)"),
    (1, 5, 0, 30, 3, None, "Powerplay 30/3 (proj ~100)"),
    (1, 10, 0, 80, 2, None, "Middle 80/2 (proj ~160)"),
    (1, 10, 0, 100, 1, None, "Middle 100/1 (proj ~200)"),
    (1, 10, 0, 60, 5, None, "Middle 60/5 (proj ~120)"),
    (1, 15, 0, 140, 3, None, "Death 140/3 (proj ~187)"),
    (1, 15, 0, 120, 6, None, "Death 120/6 (proj ~160)"),
    (1, 18, 0, 170, 4, None, "Final 170/4 (proj ~189)"),
    (1, 18, 0, 130, 7, None, "Final 130/7 (proj ~144)"),
]

print(f"{'Scenario':<35} {'Proj Score':<12} {'Win Prob':<10}")
print("-" * 70)
for innings, over, ball, score, wickets, target, desc in scenarios_1st:
    features = calc.calculate_all_features(innings, over, ball, score, wickets, target)
    proj = features['expected_final_score']
    win_prob = features['resource_win_prob']
    print(f"{desc:<35} {proj:<12.0f} {win_prob*100:<10.1f}%")

print()
print("=" * 70)
print("SECOND INNINGS - DATA-CALIBRATED CALCULATOR (Chase)")
print("=" * 70)

scenarios_2nd = [
    (2, 5, 0, 48, 2, 158, "Powerplay 48/2 chasing 158"),
    (2, 10, 0, 80, 3, 158, "Middle 80/3 chasing 158"),
    (2, 15, 0, 120, 4, 158, "Death 120/4 chasing 158"),
    (2, 10, 0, 100, 2, 170, "Middle 100/2 chasing 170"),
]

print(f"{'Scenario':<35} {'RRR':<8} {'Win Prob':<10}")
print("-" * 70)
for innings, over, ball, score, wickets, target, desc in scenarios_2nd:
    features = calc.calculate_all_features(innings, over, ball, score, wickets, target)
    rrr = features['required_run_rate']
    win_prob = features['resource_win_prob']
    print(f"{desc:<35} {rrr:<8.2f} {win_prob*100:<10.1f}%")

print()
print("=" * 70)
print("COMPARISON WITH EDA DATA")
print("=" * 70)
print("First Innings EDA findings:")
print("  Proj <150: 17-24% win rate")
print("  Proj 160-170: 35% win rate")
print("  Proj 180-200: 58% win rate")
print("  0 wickets: 48%, 3 wickets: 34%, 6 wickets: 23%")
print()
print("Second Innings EDA findings:")
print("  RRR 7-8: 80% win rate")
print("  RRR 9-10: 44% win rate")
print("  Wicket penalty: 5 wkts = 31%, 6 wkts = 21%")
