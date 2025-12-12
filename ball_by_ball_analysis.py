"""
Ball-by-ball win probability analysis for ILT20 DV vs GG match.
Compares our model predictions with calculator-based resource_win_prob.
"""
from bbl_pipeline.inference.predictor import Predictor
from bbl_pipeline.inference.schema import MatchState
from bbl_pipeline.features.calculator import ResourceFeatureCalculator

# Load model
pred = Predictor.load('models/ilt20_v3', 'data/ilt_feature_store_v2')
calc = ResourceFeatureCalculator()

# Target: 158 (Gulf Giants scored in first innings)
TARGET = 158

# Ball-by-ball data extracted from commentary
# Format: (over, ball, score, wickets, batsman1, batsman2, bowler, commentary)
ball_data = [
    # Over 1 - Thushara
    (0, 1, 3, 0, "Fakhar Zaman", "Max Holden", "Nuwan Thushara", "3 runs"),
    (0, 2, 4, 0, "Fakhar Zaman", "Max Holden", "Nuwan Thushara", "1 run"),
    (0, 3, 6, 0, "Fakhar Zaman", "Max Holden", "Nuwan Thushara", "2 runs"),
    (0, 4, 10, 0, "Fakhar Zaman", "Max Holden", "Nuwan Thushara", "FOUR"),
    (0, 5, 11, 0, "Fakhar Zaman", "Max Holden", "Nuwan Thushara", "1 run"),
    (0, 6, 16, 0, "Fakhar Zaman", "Max Holden", "Nuwan Thushara", "FOUR + wide"),
    
    # Over 2 - Wood
    (1, 1, 16, 0, "Fakhar Zaman", "Max Holden", "Chris Wood", "dot"),
    (1, 2, 18, 0, "Fakhar Zaman", "Max Holden", "Chris Wood", "2 runs"),
    (1, 3, 20, 0, "Fakhar Zaman", "Max Holden", "Chris Wood", "2 runs"),
    (1, 4, 20, 1, "Hasan Nawaz", "Max Holden", "Chris Wood", "WICKET - Fakhar bowled"),
    (1, 5, 20, 1, "Hasan Nawaz", "Max Holden", "Chris Wood", "dot"),
    (1, 6, 20, 1, "Hasan Nawaz", "Max Holden", "Chris Wood", "dot"),
    
    # Over 3 - Adair
    (2, 1, 21, 1, "Hasan Nawaz", "Max Holden", "Mark Adair", "1 run"),
    (2, 2, 22, 1, "Hasan Nawaz", "Max Holden", "Mark Adair", "dot"),  # leg bye
    (2, 3, 24, 1, "Hasan Nawaz", "Max Holden", "Mark Adair", "2 runs"),
    (2, 4, 25, 1, "Hasan Nawaz", "Max Holden", "Mark Adair", "1 run (lb)"),
    (2, 5, 28, 1, "Hasan Nawaz", "Max Holden", "Mark Adair", "2+1 (wide)"),
    (2, 6, 28, 1, "Hasan Nawaz", "Max Holden", "Mark Adair", "1 run"),
    
    # Over 4 - Wood
    (3, 1, 29, 1, "Hasan Nawaz", "Max Holden", "Chris Wood", "1 run"),
    (3, 2, 29, 1, "Hasan Nawaz", "Max Holden", "Chris Wood", "dot"),
    (3, 3, 33, 1, "Hasan Nawaz", "Max Holden", "Chris Wood", "FOUR"),
    (3, 4, 34, 1, "Hasan Nawaz", "Max Holden", "Chris Wood", "1 run"),
    (3, 5, 35, 1, "Hasan Nawaz", "Max Holden", "Chris Wood", "1 run"),
    (3, 6, 35, 2, "Sam Curran", "Max Holden", "Chris Wood", "RUN OUT - Nawaz"),
    
    # Over 5 - Thushara
    (4, 1, 39, 2, "Sam Curran", "Max Holden", "Nuwan Thushara", "FOUR"),
    (4, 2, 43, 2, "Sam Curran", "Max Holden", "Nuwan Thushara", "FOUR"),
    (4, 3, 44, 2, "Sam Curran", "Max Holden", "Nuwan Thushara", "1 run"),
    (4, 4, 45, 2, "Sam Curran", "Max Holden", "Nuwan Thushara", "1 run"),
    (4, 5, 47, 2, "Sam Curran", "Max Holden", "Nuwan Thushara", "2 runs"),
    (4, 6, 47, 2, "Sam Curran", "Max Holden", "Nuwan Thushara", "dot (credited 0)"),
    
    # Over 6 - Wood
    (5, 1, 47, 2, "Sam Curran", "Max Holden", "Chris Wood", "dot"),
    (5, 2, 48, 2, "Sam Curran", "Max Holden", "Chris Wood", "1 run"),
    (5, 3, 49, 2, "Sam Curran", "Max Holden", "Chris Wood", "1 run"),
    (5, 4, 53, 2, "Sam Curran", "Max Holden", "Chris Wood", "FOUR"),
    (5, 5, 53, 2, "Sam Curran", "Max Holden", "Chris Wood", "dot"),
    (5, 6, 53, 2, "Sam Curran", "Max Holden", "Chris Wood", "dot"),
    
    # Over 7 - Mayers
    (6, 1, 53, 2, "Sam Curran", "Max Holden", "Kyle Mayers", "dot"),
    (6, 2, 54, 2, "Sam Curran", "Max Holden", "Kyle Mayers", "1 run"),
    (6, 3, 55, 2, "Sam Curran", "Max Holden", "Kyle Mayers", "1 run"),
    (6, 4, 56, 2, "Sam Curran", "Max Holden", "Kyle Mayers", "1 run"),
    (6, 5, 56, 2, "Sam Curran", "Max Holden", "Kyle Mayers", "dot"),
    (6, 6, 57, 2, "Sam Curran", "Max Holden", "Kyle Mayers", "1 run"),
    
    # Over 8 - Adair
    (7, 1, 58, 2, "Sam Curran", "Max Holden", "Mark Adair", "1 run"),
    (7, 2, 58, 2, "Sam Curran", "Max Holden", "Mark Adair", "dot"),
    (7, 3, 62, 2, "Sam Curran", "Max Holden", "Mark Adair", "FOUR"),
    (7, 4, 64, 2, "Sam Curran", "Max Holden", "Mark Adair", "2 runs"),
    (7, 5, 65, 2, "Sam Curran", "Max Holden", "Mark Adair", "1 run"),
    (7, 6, 65, 2, "Sam Curran", "Max Holden", "Mark Adair", "dot"),
    
    # Over 9 - Erasmus
    (8, 1, 69, 2, "Sam Curran", "Max Holden", "Gerhard Erasmus", "FOUR"),
    (8, 2, 70, 2, "Sam Curran", "Max Holden", "Gerhard Erasmus", "1 run"),
    (8, 3, 71, 2, "Sam Curran", "Max Holden", "Gerhard Erasmus", "1 run"),
    (8, 4, 73, 2, "Sam Curran", "Max Holden", "Gerhard Erasmus", "2 runs"),
    (8, 5, 75, 2, "Sam Curran", "Max Holden", "Gerhard Erasmus", "2 runs"),
    (8, 6, 75, 2, "Sam Curran", "Max Holden", "Gerhard Erasmus", "1 run"),
]

print("=" * 100)
print("BALL-BY-BALL WIN PROBABILITY: Desert Vipers vs Gulf Giants (Target: 158)")
print("=" * 100)
print()
print(f"{'Ball':<8} {'Score':<10} {'RRR':<8} {'Calculator':<12} {'Model':<12} {'Diff':<10} Commentary")
print("-" * 100)

for over, ball, score, wickets, bat1, bat2, bowler, commentary in ball_data:
    # Calculate overs bowled
    overs_bowled = over + ball / 6.0
    balls_remaining = 120 - (over * 6 + ball)
    runs_required = TARGET - score
    overs_remaining = balls_remaining / 6.0
    
    if overs_remaining > 0:
        rrr = runs_required / overs_remaining
    else:
        rrr = 0
    
    # Get calculator resource_win_prob
    calc_features = calc.calculate_all_features(
        innings=2,
        over=over,
        ball=ball,
        current_score=score,
        wickets_lost=wickets,
        target_runs=TARGET
    )
    calc_prob = calc_features['resource_win_prob']
    
    # Get model prediction
    state = MatchState(
        match_id='test',
        venue='Dubai International Cricket Stadium',
        batting_team='Desert Vipers',
        bowling_team='Gulf Giants',
        innings=2,
        over=over, ball=ball,
        current_score=score,
        wickets_lost=wickets,
        target_runs=TARGET,
        batsman_1=bat1, batsman_2=bat2, bowler=bowler
    )
    model_prob = pred.predict(state)
    
    # Difference
    diff = model_prob - calc_prob
    
    ball_str = f"{over}.{ball}"
    score_str = f"{score}/{wickets}"
    
    print(f"{ball_str:<8} {score_str:<10} {rrr:<8.2f} {calc_prob*100:<12.1f}% {model_prob*100:<12.1f}% {diff*100:+.1f}%    {commentary}")

print()
print("=" * 100)
print("SUMMARY:")
print(f"  Calculator: Uses RRR-based logistic (beta=0.7, mu=9.5) + wicket penalty")
print(f"  Model: XGBLogRegEnsemble trained on ILT20 data with resource_win_prob as feature")
print("=" * 100)
