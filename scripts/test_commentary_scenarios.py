import pandas as pd
from bbl_pipeline.inference.predictor import Predictor
from bbl_pipeline.inference.schema import MatchState

def test_commentary_scenarios():
    print("Loading ILT20 Champion Model (v3)...")
    predictor = Predictor.load('models/ilt_champion_v2', 'data/ilt_feature_store_v2')
    
    # Target inferred from "132/5 in 16 overs and need 19 runs" -> 132+19 = 151
    TARGET = 151
    
    scenarios = [
        # Previous context
        (132, 5, 16, 0, "Start of Over 17: Need 19 off 24"),
        (133, 6, 16, 5, "16.5 (Wicket - Nawaz): Need 18 off 19"),
        
        # New context (Over 17 end)
        (137, 6, 17, 0, "End of Over 17: Need 14 off 18"),
        
        # Over 18
        (138, 6, 17, 3, "17.3 (Dot): Need 13 off 15"),
        (143, 6, 18, 0, "End of Over 18: Need 8 off 12"),
        
        # Over 19
        (145, 6, 18, 1, "18.1 (Two): Need 6 off 11"),
        (146, 6, 18, 3, "18.3 (Dot): Need 5 off 9"),
        (148, 6, 18, 4, "18.4 (Two): Need 3 off 8"),
        (149, 6, 18, 5, "18.5 (One): Need 2 off 7"),
    ]
    
    print("\n" + "="*80)
    print(f"{'Scenario':<55} | {'Win Prob':<10} | {'Equation'}")
    print("="*80)
    
    for score, wkts, over, ball, desc in scenarios:
        state = MatchState(
            match_id='commentary_test',
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
        
        prob = predictor.predict(state)
        
        runs_needed = TARGET - score
        balls_left = (20 - over) * 6 - ball
        equation = f"{runs_needed} off {balls_left}"
        
        print(f"{desc:<55} | {prob*100:.1f}%      | {equation}")

if __name__ == "__main__":
    test_commentary_scenarios()
