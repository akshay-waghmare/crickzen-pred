"""
Test script for first innings 3D dynamic wicket penalty.

Tests the problem scenarios:
- 202/2 at 18 overs → should have HIGH win probability
- 210/6 at 19 overs → should still have high probability (score banked)

The 3D penalty uses: PHASE × EASE × WICKETS lookup with smooth interpolation.
"""

import sys
sys.path.insert(0, 'src')

from bbl_pipeline.features.calculator import ResourceFeatureCalculator

def test_first_innings_scenarios():
    """Test first innings death over scenarios."""
    calc = ResourceFeatureCalculator()
    
    print("=" * 70)
    print("FIRST INNINGS 3D DYNAMIC WICKET PENALTY - TEST RESULTS")
    print("=" * 70)
    
    # Test scenarios: (score, wickets, overs, description)
    scenarios = [
        # Problem scenario 1: 202/2 at 18 overs
        (202, 2, 18.0, "Great position - 202/2 at 18 overs"),
        
        # Problem scenario 2: 210/6 at 19 overs (should NOT be worse than 202/2!)
        (210, 6, 19.0, "210/6 at 19 overs - score is banked"),
        
        # Comparative scenarios in death overs
        (180, 3, 17.0, "180/3 at 17 overs - solid"),
        (180, 6, 17.0, "180/6 at 17 overs - struggled but recovered"),
        (160, 6, 17.0, "160/6 at 17 overs - below par, many wickets"),
        
        # Early innings comparisons
        (60, 4, 8.0, "60/4 at 8 overs - struggling early"),
        (80, 1, 8.0, "80/1 at 8 overs - great start"),
        (45, 6, 10.0, "45/6 at 10 overs - collapsed"),
        
        # Final overs
        (190, 5, 19.0, "190/5 at 19 overs - good score"),
        (200, 7, 19.5, "200/7 at 19.5 overs - excellent score despite wickets"),
    ]
    
    print("\n" + "-" * 70)
    print("Testing penalty values by scenario:")
    print("-" * 70)
    
    for score, wickets, overs, desc in scenarios:
        current_rr = score / overs if overs > 0 else 0
        
        # Get phase and ease info
        phase = calc.get_first_innings_phase(overs)
        expected_rr = calc.FIRST_INNINGS_EXPECTED_RR.get(phase, 8.0)
        ease = current_rr / expected_rr if expected_rr > 0 else 1.0
        ease_bucket = calc.get_first_innings_ease_bucket(current_rr, phase)
        
        # Get the dynamic penalty
        penalty = calc.get_first_innings_dynamic_penalty(wickets, overs, current_rr)
        
        print(f"\n{desc}")
        print(f"  Score: {score}/{wickets} at {overs} overs")
        print(f"  CRR: {current_rr:.2f}, Expected RR: {expected_rr:.2f}")
        print(f"  Ease ratio: {ease:.3f} ({ease_bucket})")
        print(f"  Phase: {phase}")
        print(f"  Wicket Penalty: {penalty:.3f}")
    
    print("\n" + "=" * 70)
    print("Testing full win probability calculation:")
    print("=" * 70)
    
    # Test full probability calculation for key scenarios
    key_scenarios = [
        (202, 2, 18.0, 12, "202/2 at 18 overs (2 balls left in over)"),
        (210, 6, 19.0, 6, "210/6 at 19 overs (6 balls left)"),
        (190, 5, 19.0, 6, "190/5 at 19 overs"),
        (180, 6, 17.0, 18, "180/6 at 17 overs (3 overs left)"),
    ]
    
    for score, wickets, overs, balls_remaining, desc in key_scenarios:
        current_rr = score / overs if overs > 0 else 0
        
        # Estimate projected final score based on current rate
        balls_left = balls_remaining
        projected_additional = (current_rr / 6) * balls_left
        projected_final = score + projected_additional
        
        # Calculate resource percentage
        resource_pct = (balls_remaining / 120.0) * 100  # Simplified
        
        # Get win probability
        win_prob = calc.calculate_resource_win_probability(
            innings=1,
            expected_final_score=projected_final,
            target_runs=0,  # Not relevant for innings 1
            resource_pct=resource_pct,
            current_run_rate=current_rr,
            required_run_rate=0,  # Not relevant for innings 1
            current_score=score,
            balls_remaining=balls_remaining,
            wickets_lost=wickets
        )
        
        phase = calc.get_first_innings_phase(overs)
        penalty = calc.get_first_innings_dynamic_penalty(wickets, overs, current_rr)
        
        print(f"\n{desc}")
        print(f"  Score: {score}/{wickets}, Projected: {projected_final:.0f}")
        print(f"  Phase: {phase}, Penalty: {penalty:.3f}")
        print(f"  Win Probability: {win_prob:.1%}")
    
    print("\n" + "=" * 70)
    print("KEY VALIDATION:")
    print("=" * 70)
    
    # The key test: 202/2 should NOT have lower probability than 210/6!
    wp_202_2 = calc.calculate_resource_win_probability(
        innings=1, expected_final_score=220, target_runs=0, resource_pct=10,
        current_run_rate=202/18, required_run_rate=0,
        current_score=202, balls_remaining=12, wickets_lost=2
    )
    
    wp_210_6 = calc.calculate_resource_win_probability(
        innings=1, expected_final_score=220, target_runs=0, resource_pct=5,
        current_run_rate=210/19, required_run_rate=0,
        current_score=210, balls_remaining=6, wickets_lost=6
    )
    
    print(f"\n202/2 at 18 overs: {wp_202_2:.1%}")
    print(f"210/6 at 19 overs: {wp_210_6:.1%}")
    print(f"\nExpected: 210/6 should be >= 202/2 (higher score, later in innings)")
    
    if wp_210_6 >= wp_202_2 * 0.95:  # Allow 5% tolerance
        print("✅ PASS: 210/6 probability is appropriate relative to 202/2")
    else:
        print(f"⚠️  WARNING: 210/6 ({wp_210_6:.1%}) seems too low vs 202/2 ({wp_202_2:.1%})")
        print("    The extra 8 runs should offset the wicket loss in death overs")


if __name__ == '__main__':
    test_first_innings_scenarios()
