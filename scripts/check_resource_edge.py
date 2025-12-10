# Quick check: what does resource_win_prob say for these edge cases?
from bbl_pipeline.features.calculator import ResourceFeatureCalculator

calc = ResourceFeatureCalculator()

# Won the match: 158/2 (18.2 ov) chasing 158
f = calc.calculate_all_features(innings=2, over=18, ball=2, current_score=158, wickets_lost=2, target_runs=158)
print(f"Won match (158/2, chase 158): resource_win_prob = {f['resource_win_prob']:.4f}")

# About to win: 152/2 (18.1 ov) need 6
f = calc.calculate_all_features(innings=2, over=18, ball=1, current_score=152, wickets_lost=2, target_runs=158)
print(f"Need 6 from 11: resource_win_prob = {f['resource_win_prob']:.4f}")

# Need 10 from 12
f = calc.calculate_all_features(innings=2, over=18, ball=0, current_score=148, wickets_lost=2, target_runs=158)
print(f"Need 10 from 12: resource_win_prob = {f['resource_win_prob']:.4f}")
