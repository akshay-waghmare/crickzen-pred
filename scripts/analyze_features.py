"""
Display all feature values for a given match state and verify they are correct.
"""
import pandas as pd
from bbl_pipeline.inference.predictor import Predictor
from bbl_pipeline.inference.schema import MatchState

# Load the v2 model
predictor = Predictor.load("models/ilt_champion_v2", "data/ilt_feature_store_v2")

def analyze_match_state(score, wickets, over, ball, target, batting_team="GG", bowling_team="SW"):
    """Analyze a match state and print all features with validation."""
    
    state = MatchState(
        match_id="test",
        venue="Dubai International Cricket Stadium",
        batting_team=batting_team,
        bowling_team=bowling_team,
        innings=2,
        over=over,
        ball=ball,
        current_score=score,
        wickets_lost=wickets,
        batsman_1="Unknown",
        batsman_2="Unknown",
        bowler="Unknown",
        target_runs=target,
    )
    
    # Build features using the feature mapper
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
        'runs_needed': (state.target_runs - state.current_score),
    }
    
    # Get features
    features_df = predictor.feature_mapper.create_feature_dataframe(scraped_data)
    
    # Get prediction
    prob = predictor.predict(state)
    
    # Calculate expected values for validation
    overs_bowled = over + ball/6
    balls_remaining = 120 - (over * 6 + ball)
    runs_needed = target - score
    crr = score / overs_bowled if overs_bowled > 0 else 0
    rrr = runs_needed / (20 - overs_bowled) if overs_bowled < 20 else 99
    
    print("=" * 80)
    print(f"MATCH STATE: {score}/{wickets} ({over}.{ball} ov) chasing {target}")
    print("=" * 80)
    print(f"Win Probability: {prob*100:.2f}%")
    print()
    
    print("KEY FEATURES (with validation):")
    print("-" * 80)
    
    # Group features for easier reading
    feature_groups = {
        "Core Match State": [
            ("innings", 2, "Should be 2 for chase"),
            ("over", over, "Current over"),
            ("ball", ball, "Ball in over"),
            ("current_score", score, "Runs scored"),
            ("wickets_lost", wickets, "Wickets fallen"),
        ],
        "Run Rates": [
            ("current_run_rate", crr, f"Expected ~{crr:.2f}"),
            ("required_run_rate", rrr, f"Expected ~{rrr:.2f}"),
            ("run_rate_diff", crr - rrr, f"CRR - RRR = {crr:.2f} - {rrr:.2f} = {crr-rrr:.2f} (positive = ahead)"),
        ],
        "Chase Status": [
            ("runs_required", runs_needed, f"Target - Score = {target} - {score}"),
            ("balls_remaining", balls_remaining, f"120 - {over*6+ball}"),
            ("overs_remaining", 20 - overs_bowled, f"20 - {overs_bowled:.2f}"),
            ("chase_difficulty", rrr / (crr + 0.1), f"RRR/CRR ratio"),
        ],
        "Resource-Based": [
            ("resource_pct", None, "DLS resources remaining (0-100)"),
            ("resource_win_prob", None, "Pure DLS-based win probability"),
            ("dls_pressure_index", None, "Pressure from required rate"),
            ("pressure_index", None, "Overall pressure index"),
        ],
        "Score Projections": [
            ("expected_final_score", None, "Regressed projected score (should be ~160-200)"),
            ("projected_score", None, "Same as expected_final_score"),
            ("score_vs_par", None, f"Score - par at this point (positive = ahead)"),
            ("projected_vs_venue_avg", None, "Projected - venue avg"),
        ],
        "Derived Features": [
            ("score_per_wicket", score / (wickets + 1), f"{score}/{wickets+1} = {score/(wickets+1):.2f}"),
            ("wickets_times_balls", wickets * (120 - balls_remaining), f"{wickets} × {120-balls_remaining}"),
            ("rrr_times_wickets", rrr * wickets, f"{rrr:.2f} × {wickets}"),
        ],
    }
    
    for group_name, features in feature_groups.items():
        print(f"\n{group_name}:")
        for feature_name, expected, note in features:
            actual = features_df[feature_name].iloc[0] if feature_name in features_df.columns else "N/A"
            if expected is not None:
                match = "✓" if abs(float(actual) - expected) < 0.1 else "✗"
                print(f"  {feature_name:<25} = {actual:>12.4f}  {match} {note}")
            else:
                print(f"  {feature_name:<25} = {actual:>12.4f}     {note}")
    
    print("\n" + "=" * 80)
    return prob


# Test current match state from live predictor
print("\n" + "=" * 80)
print("CURRENT LIVE MATCH: GG vs SW, ILT20")  
print("=" * 80)

# Test the current state
analyze_match_state(score=107, wickets=1, over=12, ball=0, target=158)

# Test what happens after a boundary
print("\n\n>>> AFTER A FOUR (+4 runs):")
analyze_match_state(score=111, wickets=1, over=12, ball=1, target=158)

print("\n\n>>> AFTER A SIX (+6 runs):")
analyze_match_state(score=117, wickets=1, over=12, ball=2, target=158)

print("\n\n>>> AFTER A WICKET:")
analyze_match_state(score=117, wickets=2, over=12, ball=3, target=158)
