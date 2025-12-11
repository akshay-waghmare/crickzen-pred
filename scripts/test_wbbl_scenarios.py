"""
Test WBBL Model with scenarios
"""
from bbl_pipeline.inference.predictor import Predictor
from bbl_pipeline.inference.schema import MatchState

def test_wbbl_scenarios():
    print("Loading WBBL Champion Model (v1)...")
    predictor = Predictor.load('models/wbbl_champion_v1', 'data/wbbl_feature_store_v2')
    
    # Test scenarios
    scenarios = [
        # (score, wickets, over, ball, target, description)
        (0, 0, 0, 0, None, "Start of Match (1st Innings)"),
        (50, 1, 6, 0, None, "End of Powerplay (1st Innings)"),
        (100, 3, 12, 0, None, "Middle Overs (1st Innings)"),
        (140, 5, 20, 0, None, "End of 1st Innings"),
        
        # 2nd Innings Scenarios
        (0, 0, 0, 0, 141, "Start of Chase"),
        (50, 1, 6, 0, 141, "End of Powerplay (Chase)"),
        (80, 2, 12, 0, 141, "Need 61 off 48"),
        (120, 3, 17, 0, 141, "Need 21 off 18"),
        (135, 4, 19, 0, 141, "Need 6 off 6"),
        (140, 4, 19, 5, 141, "Need 1 off 1"),
    ]
    
    print("\n" + "="*80)
    print(f"{'Scenario':<40} | {'Win Prob':<10} | {'Equation'}")
    print("="*80)
    
    for score, wkts, over, ball, target, desc in scenarios:
        innings = 1 if target is None else 2
        
        state = MatchState(
            match_id='test_wbbl',
            venue='Sydney Showground Stadium',
            batting_team='Sydney Sixers',
            bowling_team='Brisbane Heat',
            innings=innings,
            over=over,
            ball=ball,
            current_score=score,
            wickets_lost=wkts,
            batsman_1='Unknown',
            batsman_2='Unknown',
            bowler='Unknown',
            target_runs=target,
        )
        
        prob = predictor.predict(state)
        
        if target:
            runs_needed = target - score
            balls_left = (20 - over) * 6 - ball
            equation = f"{runs_needed} off {balls_left}"
        else:
            equation = f"Score: {score}/{wkts}"
        
        print(f"{desc:<40} | {prob*100:.1f}%      | {equation}")

if __name__ == "__main__":
    test_wbbl_scenarios()
