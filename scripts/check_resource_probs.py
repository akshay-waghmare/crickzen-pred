import pandas as pd
from bbl_pipeline.inference.predictor import Predictor
from bbl_pipeline.inference.schema import MatchState

def check_resource_probs():
    print("Loading Predictor...")
    predictor = Predictor.load('models/ilt_champion_v2', 'data/ilt_feature_store_v2')
    
    TARGET = 151
    
    scenarios = [
        (145, 6, 18, 1, "18.1 (Two): Need 6 off 11"),
        (148, 6, 18, 4, "18.4 (Two): Need 3 off 8"),
        (149, 6, 18, 5, "18.5 (One): Need 2 off 7"),
    ]
    
    print("\n" + "="*80)
    print(f"{'Scenario':<40} | {'Resource Prob':<15} | {'Model Prob':<10}")
    print("="*80)
    
    for score, wkts, over, ball, desc in scenarios:
        state = MatchState(
            match_id='test',
            venue='Dubai International Cricket Stadium',
            batting_team='Desert Vipers', 
            bowling_team='Dubai Capitals',
            innings=2, 
            over=over, 
            ball=ball,
            current_score=score, 
            wickets_lost=wkts,
            batsman_1='Unknown', 
            batsman_2='Unknown', 
            bowler='Unknown',
            target_runs=TARGET,
        )
        
        # Generate features to get resource_win_prob
        scraped_data = {
            'innings_num': state.innings,
            'over_number': state.over,
            'ball_number': state.ball,
            'total_score': state.current_score,
            'total_wickets': state.wickets_lost,
            'current_batsman': state.batsman_1,
            'non_striker': state.batsman_2,
            'current_bowler': state.bowler,
            'batting_team': state.batting_team,
            'bowling_team': state.bowling_team,
            'venue': state.venue,
            'target_score': state.target_runs,
            'runs_needed': (state.target_runs - state.current_score)
        }
        
        X = predictor.feature_mapper.create_feature_dataframe(scraped_data)
        resource_prob = X['resource_win_prob'].iloc[0]
        
        # Get actual prediction (with current guardrails)
        model_prob = predictor.predict(state)
        
        print(f"{desc:<40} | {resource_prob:.6f}        | {model_prob:.4f}")

if __name__ == "__main__":
    check_resource_probs()
