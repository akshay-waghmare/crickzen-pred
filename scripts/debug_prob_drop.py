"""Debug why probability dropped after a six."""

from bbl_pipeline.features.calculator import ResourceFeatureCalculator

calc = ResourceFeatureCalculator()

# Chasing 158
target = 158

# Before six: 23/0 (2.0 ov)
print("=== BEFORE SIX: 23/0 (2.0 ov) ===")
features1 = calc.calculate_all_features(
    innings=2,
    over=2,
    ball=0,
    current_score=23,
    wickets_lost=0,
    target_runs=target
)
for k, v in sorted(features1.items()):
    if isinstance(v, float):
        print(f"  {k}: {v:.4f}")
    else:
        print(f"  {k}: {v}")

# After six: 29/0 (2.1 ov)
print("\n=== AFTER SIX: 29/0 (2.1 ov) ===")
features2 = calc.calculate_all_features(
    innings=2,
    over=2,
    ball=1,
    current_score=29,
    wickets_lost=0,
    target_runs=target
)
for k, v in sorted(features2.items()):
    if isinstance(v, float):
        print(f"  {k}: {v:.4f}")
    else:
        print(f"  {k}: {v}")

# Key differences
print("\n=== CHANGES ===")
for k in sorted(features1.keys()):
    v1, v2 = features1[k], features2[k]
    if isinstance(v1, float) and isinstance(v2, float):
        delta = v2 - v1
        if abs(delta) > 0.0001:
            print(f"  {k}: {v1:.4f} -> {v2:.4f} ({delta:+.4f})")

# Deltas
print("\n=== CHANGES ===")
print(f"Resource pct: {features1['resource_pct']:.4f} -> {features2['resource_pct']:.4f} ({features2['resource_pct'] - features1['resource_pct']:+.4f})")
print(f"Win prob: {features1['resource_win_prob']:.4f} -> {features2['resource_win_prob']:.4f} ({features2['resource_win_prob'] - features1['resource_win_prob']:+.4f})")
print(f"Pressure: {features1['pressure_index']:.4f} -> {features2['pressure_index']:.4f} ({features2['pressure_index'] - features1['pressure_index']:+.4f})")

# Key insight: runs_needed and resources_remaining
runs_needed1 = target - 23
runs_needed2 = target - 29

# Calculate resources
balls_remaining1 = 120 - (2 * 6 + 0)  # 108
balls_remaining2 = 120 - (2 * 6 + 1)  # 107

resources_remaining1 = calc.calculate_resources_remaining(balls_remaining1, 0)
resources_remaining2 = calc.calculate_resources_remaining(balls_remaining2, 0)

print(f"\nRuns needed: {runs_needed1} -> {runs_needed2} ({runs_needed2 - runs_needed1:+d})")
print(f"Resources remaining: {resources_remaining1:.4f} -> {resources_remaining2:.4f} ({resources_remaining2 - resources_remaining1:+.4f})")

# Runs per resource
rpr1 = runs_needed1 / resources_remaining1 if resources_remaining1 > 0 else 0
rpr2 = runs_needed2 / resources_remaining2 if resources_remaining2 > 0 else 0
print(f"Runs/resource needed: {rpr1:.4f} -> {rpr2:.4f} ({rpr2 - rpr1:+.4f})")

# So 6 runs scored, resources dropped by ~0.0092
# 6 runs / 0.0092 resources = 652 runs/resource "scored"
resource_used = resources_remaining1 - resources_remaining2
runs_per_resource_scored = 6 / resource_used if resource_used > 0 else 0
print(f"\nRuns scored: 6 on {resource_used:.4f} resources = {runs_per_resource_scored:.2f} runs/resource")
print(f"Average to par: ~160 runs / 1.0 resource = 160 runs/resource")
print(f"Conclusion: 6 off 1 ball = {runs_per_resource_scored:.0f} runs/resource >> 160 runs/resource par!")
print("\nThis is MUCH better than par - win prob should INCREASE!")
