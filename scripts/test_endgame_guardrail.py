"""Test endgame scenarios with improved guardrail."""
from bbl_pipeline.inference.predictor import Predictor
from bbl_pipeline.inference.schema import MatchState

predictor = Predictor.load('models/ilt_champion_v2', 'data/ilt_feature_store_v2')

scenarios = [
    # (score, wickets, over, ball, target, description)
    (155, 3, 19, 1, 158, 'Need 3 from 5'),
    (155, 4, 19, 2, 158, 'Need 3 from 4'),
    (156, 4, 19, 3, 158, 'Need 2 from 3'),
    (157, 4, 19, 4, 158, 'Need 1 from 2'),
    (158, 4, 19, 5, 158, 'WON'),
    (130, 4, 18, 0, 158, 'Need 28 from 12'),
    (145, 2, 18, 0, 158, 'Need 13 from 12'),
    (100, 6, 16, 0, 158, 'Need 58 from 24'),
]

print('ENDGAME SCENARIOS (with improved guardrail):')
print('='*75)
print(f"{'Situation':<25} {'Model':>10} {'Resource':>10} {'Final':>10}")
print('-'*75)

for score, wkts, over, ball, target, desc in scenarios:
    state = MatchState(
        match_id='test',
        venue='Dubai International Cricket Stadium',
        batting_team='GG', bowling_team='SW',
        innings=2, over=over, ball=ball,
        current_score=score, wickets_lost=wkts,
        batsman_1='Unknown', batsman_2='Unknown', bowler='Unknown',
        target_runs=target,
    )
    
    # Get model prob without guardrail (directly)
    scraped = {
        'innings_num': 2, 'over_number': over, 'ball_number': ball,
        'total_score': score, 'total_wickets': wkts,
        'current_batsman': 'Unknown', 'non_striker': 'Unknown', 'current_bowler': 'Unknown',
        'batting_team': 'GG', 'bowling_team': 'SW',
        'venue': 'Dubai International Cricket Stadium',
        'target_score': target, 'runs_needed': target - score,
    }
    X = predictor.feature_mapper.create_feature_dataframe(scraped)
    model_prob = predictor.model.predict_proba(X)[0, 1]
    resource_prob = X['resource_win_prob'].iloc[0]
    
    # Get final prob with guardrail
    final_prob = predictor.predict(state)
    
    label = f"{score}/{wkts} ({over}.{ball}) {desc}"
    print(f"{label:<25} {model_prob*100:>9.1f}% {resource_prob*100:>9.1f}% {final_prob*100:>9.1f}%")

print('='*75)
print("Final should be closer to Resource in death overs (over >= 16)")
