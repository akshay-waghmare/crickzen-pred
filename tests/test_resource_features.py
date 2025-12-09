"""
Test script for ResourceFeatureCalculator.
Validates the hybrid resource-based features for BBL pipeline.
"""
import sys
sys.path.insert(0, r'c:\Users\ADMINS\Documents\projects\machine_learning\src')

from bbl_pipeline.features.calculator import ResourceFeatureCalculator


def test_resource_calculator():
    """Test the ResourceFeatureCalculator with various match scenarios."""
    calc = ResourceFeatureCalculator()
    
    print("=" * 60)
    print("Testing ResourceFeatureCalculator")
    print("=" * 60)
    
    # Test 1: First innings, powerplay
    print("\n--- Test 1: First Innings, Powerplay (Over 3, 40/1) ---")
    features = calc.calculate_all_features(
        innings=1, over=3, ball=2, 
        current_score=40, wickets_lost=1, 
        target_runs=None
    )
    print_features(features)
    
    # Test 2: First innings, death overs
    print("\n--- Test 2: First Innings, Death Overs (Over 17, 140/4) ---")
    features = calc.calculate_all_features(
        innings=1, over=17, ball=3, 
        current_score=140, wickets_lost=4, 
        target_runs=None
    )
    print_features(features)
    
    # Test 3: Second innings, comfortable chase
    print("\n--- Test 3: Second Innings, Comfortable Chase (Over 12, 100/2, Target 160) ---")
    features = calc.calculate_all_features(
        innings=2, over=12, ball=0, 
        current_score=100, wickets_lost=2, 
        target_runs=160
    )
    print_features(features)
    
    # Test 4: Second innings, tight chase
    print("\n--- Test 4: Second Innings, Tight Chase (Over 18, 145/5, Target 175) ---")
    features = calc.calculate_all_features(
        innings=2, over=18, ball=0, 
        current_score=145, wickets_lost=5, 
        target_runs=175
    )
    print_features(features)
    
    # Test 5: Second innings, almost lost (high pressure)
    print("\n--- Test 5: Second Innings, High Pressure (Over 19, 140/8, Target 185) ---")
    features = calc.calculate_all_features(
        innings=2, over=19, ball=0, 
        current_score=140, wickets_lost=8, 
        target_runs=185
    )
    print_features(features)
    
    # Test 6: Edge case - early wickets
    print("\n--- Test 6: First Innings, Early Collapse (Over 5, 25/4) ---")
    features = calc.calculate_all_features(
        innings=1, over=5, ball=0, 
        current_score=25, wickets_lost=4, 
        target_runs=None
    )
    print_features(features)
    
    # Test 7: DLS Resource calculation
    print("\n--- Test 7: DLS Resource Percentages ---")
    test_cases = [
        (20, 0), (15, 0), (10, 0), (5, 0),
        (10, 3), (10, 5), (10, 7),
        (5, 5), (5, 8),
    ]
    print(f"{'Overs Left':<12} {'Wickets Lost':<14} {'Resource %':<12}")
    print("-" * 40)
    for overs, wickets in test_cases:
        resource = calc.calculate_resource_percentage(overs, wickets)
        print(f"{overs:<12} {wickets:<14} {resource:.1f}%")
    
    print("\n" + "=" * 60)
    print("All tests completed successfully!")
    print("=" * 60)


def print_features(features):
    """Pretty print feature dictionary."""
    print(f"  Overs Remaining: {features['overs_remaining']:.2f}")
    print(f"  Balls Remaining: {features['balls_remaining']}")
    print(f"  Wickets Remaining: {features['wickets_remaining']}")
    print(f"  Resource %: {features['resource_pct']:.1f}%")
    print(f"  Current Run Rate: {features['current_run_rate']:.2f}")
    print(f"  Required Run Rate: {features['required_run_rate']:.2f}")
    print(f"  Run Rate Differential: {features['run_rate_differential']:.2f}")
    print(f"  Expected Final Score: {features['expected_final_score']:.1f}")
    print(f"  Runs Required: {features['runs_required']}")
    print(f"  Phase: PP={features['is_powerplay']} MID={features['is_middle_overs']} DEATH={features['is_death_overs']}")
    print(f"  Pressure Index: {features['pressure_index']:.3f}")
    print(f"  Resource Win Prob: {features['resource_win_prob']:.3f}")


if __name__ == "__main__":
    test_resource_calculator()
