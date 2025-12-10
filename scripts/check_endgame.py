"""Check why 155/4 needing 3 from 4 balls shows only 85.9%"""
from bbl_pipeline.inference.predictor import Predictor
from bbl_pipeline.inference.schema import MatchState
from bbl_pipeline.features.calculator import ResourceFeatureCalculator

predictor = Predictor.load('models/ilt_champion_v2', 'data/ilt_feature_store_v2')

# Current state: 155/4 (19.2) need 3 from 4 balls
state = MatchState(
    match_id='test',
    venue='Dubai International Cricket Stadium',
    batting_team='GG',
    bowling_team='SW',
    innings=2,
    over=19,
    ball=2,
    current_score=155,
    wickets_lost=4,
    batsman_1='Unknown',
    batsman_2='Unknown',
    bowler='Unknown',
    target_runs=158,
)

prob = predictor.predict(state, debug=True)
print(f'\nModel Win Prob: {prob*100:.2f}%')

# What should it be?
print()
print('REALITY CHECK:')
print('  Need 3 runs from 4 balls with 6 wickets in hand')
print('  Even a dot-dot-dot-six wins it')
print('  This should be ~98%+ not 85.9%!')

# Check resource_win_prob
calc = ResourceFeatureCalculator()
f = calc.calculate_all_features(innings=2, over=19, ball=2, current_score=155, wickets_lost=4, target_runs=158)
print(f'\n  resource_win_prob (DLS-based): {f["resource_win_prob"]*100:.2f}%')
print(f'  pressure_index: {f["pressure_index"]:.4f}')
