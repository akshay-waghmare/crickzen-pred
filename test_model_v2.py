"""Test both innings with the new professional model v2."""
from bbl_pipeline.inference.predictor import Predictor
from bbl_pipeline.inference.schema import MatchState

pred = Predictor.load('models/ilt20_v3', 'data/ilt_feature_store_v2')

print('=' * 70)
print('PROFESSIONAL MODEL V2 - FIRST INNINGS VALIDATION')
print('=' * 70)

# Key first innings scenarios
first_inn_tests = [
    # Powerplay
    ('Powerplay: 30/0 (3 ov) - Good', 3, 0, 30, 0),
    ('Powerplay: 20/3 (3 ov) - Poor', 3, 0, 20, 3),
    ('Powerplay: 60/1 (6 ov) - Strong', 6, 0, 60, 1),
    # Middle overs
    ('Middle: 70/1 (10 ov) - Par', 10, 0, 70, 1),
    ('Middle: 90/2 (10 ov) - Ahead', 10, 0, 90, 2),
    ('Middle: 60/5 (10 ov) - Trouble', 10, 0, 60, 5),
    ('Middle: 130/3 (15 ov) - Strong', 15, 0, 130, 3),
    # Death overs
    ('Death: 140/3 (16 ov) - Par', 16, 0, 140, 3),
    ('Death: 160/4 (18 ov) - Good', 18, 0, 160, 4),
    ('Death: 180/3 (19 ov) - Great', 19, 0, 180, 3),
]

print(f"{'Scenario':<35} {'DV Win Prob':<12}")
print('-' * 50)
for desc, over, ball, score, wickets in first_inn_tests:
    state = MatchState(
        match_id='test',
        venue='Dubai International Cricket Stadium',
        batting_team='Desert Vipers',
        bowling_team='Gulf Giants',
        innings=1,
        over=over, ball=ball,
        current_score=score,
        wickets_lost=wickets,
        target_runs=None,
        batsman_1='Test', batsman_2='Test', bowler='Test'
    )
    prob = pred.predict(state)
    print(f'{desc:<35} {prob*100:.1f}%')

print()
print('=' * 70)
print('COMPARISON: 2ND INNINGS (Chase Scenarios)')
print('=' * 70)

second_inn_tests = [
    ('Chase 158: 20/1 (1.4 ov) - Early', 1, 4, 20, 1, 158),
    ('Chase 180: 50/1 (6 ov) - Good', 6, 0, 50, 1, 180),
    ('Chase 180: 90/3 (10 ov) - Par', 10, 0, 90, 3, 180),
    ('Chase 160: 100/2 (12 ov) - Ahead', 12, 0, 100, 2, 160),
    ('Chase 180: 140/5 (16 ov) - Tough', 16, 0, 140, 5, 180),
    ('Chase 170: 165/4 (19 ov) - Close', 19, 0, 165, 4, 170),
]

print(f"{'Scenario':<35} {'Chase Prob':<12}")
print('-' * 50)
for desc, over, ball, score, wickets, target in second_inn_tests:
    state = MatchState(
        match_id='test',
        venue='Dubai International Cricket Stadium',
        batting_team='Desert Vipers',
        bowling_team='Gulf Giants',
        innings=2,
        over=over, ball=ball,
        current_score=score,
        wickets_lost=wickets,
        target_runs=target,
        batsman_1='Test', batsman_2='Test', bowler='Test'
    )
    prob = pred.predict(state)
    print(f'{desc:<35} {prob*100:.1f}%')
