"""
EDA to validate and calibrate first innings constants.
Following the professional model approach:
1. Historical batting first win rate
2. League/venue average scores
3. Score standard deviation by phase
4. Wicket impact on final scores (not probability)
5. SQI to win probability mapping
"""
import pandas as pd
import numpy as np

# Load data
df = pd.read_parquet('data/ilt_features_v2/training.parquet')

print("=" * 80)
print("ILT20 FIRST INNINGS CALIBRATION EDA")
print("=" * 80)

# Identify first innings rows
df_first = df[df['required_run_rate'] <= 0].copy()
print(f"\nTotal first innings rows: {len(df_first):,}")

# =========================================================================
# 1. HISTORICAL BATTING FIRST WIN RATE
# =========================================================================
print("\n" + "=" * 80)
print("1. HISTORICAL BATTING FIRST WIN RATE")
print("=" * 80)
bat_first_wr = df_first['is_winner'].mean()
print(f"Batting first win rate: {bat_first_wr:.1%}")
print(f"Current constant HISTORICAL_BAT_FIRST_WIN_RATE = 0.37")
print(f"Recommended: {bat_first_wr:.2f}")

# =========================================================================
# 2. LEAGUE AVERAGE SCORE
# =========================================================================
print("\n" + "=" * 80)
print("2. LEAGUE AVERAGE SCORE (First Innings Final Scores)")
print("=" * 80)

# Get end-of-innings rows (over 19, ball 6 or all out)
# We need to look at projected scores or actual final scores
# Using expected_final_score at end of innings as proxy
df_end = df_first[df_first['overs_remaining'] <= 1.0]
if len(df_end) > 0:
    avg_final_score = df_end['expected_final_score'].mean()
    median_final_score = df_end['expected_final_score'].median()
    std_final_score = df_end['expected_final_score'].std()
    print(f"Average final score (late overs proxy): {avg_final_score:.1f}")
    print(f"Median final score: {median_final_score:.1f}")
    print(f"Std dev of final scores: {std_final_score:.1f}")
else:
    print("No end-of-innings data found")
    avg_final_score = df_first['expected_final_score'].mean()
    print(f"Average expected score (all balls): {avg_final_score:.1f}")

print(f"\nCurrent constant LEAGUE_AVG_SCORE = 165.0")
print(f"Current constant PAR_SCORE_T20 = 160.0")

# =========================================================================
# 3. SCORE STANDARD DEVIATION BY PHASE
# =========================================================================
print("\n" + "=" * 80)
print("3. SCORE STANDARD DEVIATION BY PHASE")
print("=" * 80)

df_first['overs_bowled'] = 20 - df_first['overs_remaining']
df_first['phase'] = pd.cut(
    df_first['overs_bowled'],
    bins=[0, 6, 12, 16, 20],
    labels=['powerplay', 'middle_early', 'middle_late', 'death']
)

# For each phase, calculate std dev of expected_final_score
phase_std = df_first.groupby('phase', observed=True)['expected_final_score'].agg(['std', 'mean', 'count'])
print("\nExpected Final Score by Phase:")
print(phase_std)

# Also check actual variability in outcomes
print("\nVariability of expected_final_score:")
for phase in ['powerplay', 'middle_early', 'middle_late', 'death']:
    phase_data = df_first[df_first['phase'] == phase]['expected_final_score']
    if len(phase_data) > 0:
        print(f"  {phase}: std={phase_data.std():.1f}, range=[{phase_data.min():.0f}, {phase_data.max():.0f}]")

print(f"\nCurrent constants:")
print(f"  SCORE_STD_BASE = 35.0 (early overs)")
print(f"  SCORE_STD_MIN = 12.0 (death overs)")

# =========================================================================
# 4. WICKET IMPACT ON FINAL SCORES
# =========================================================================
print("\n" + "=" * 80)
print("4. WICKET IMPACT ON FINAL SCORES (NOT probability)")
print("=" * 80)

# For each wicket count, what's the average final score?
# Group by phase and wickets
wicket_impact = df_first.groupby(['phase', 'wickets_lost'], observed=True).agg({
    'expected_final_score': ['mean', 'std', 'count'],
    'is_winner': 'mean'
}).reset_index()
wicket_impact.columns = ['phase', 'wickets', 'avg_score', 'std_score', 'count', 'win_rate']

print("\nAverage Expected Final Score by Wickets (Middle Overs):")
middle_data = wicket_impact[wicket_impact['phase'].isin(['middle_early', 'middle_late'])]
for _, row in middle_data.iterrows():
    if row['count'] > 20:
        print(f"  {row['wickets']:.0f} wkts: avg_score={row['avg_score']:.1f}, win_rate={row['win_rate']:.1%} (n={row['count']:.0f})")

# Calculate wicket capability decay
print("\nWicket capability decay (score reduction factor):")
# Baseline: 0 wickets
baseline_score = df_first[df_first['wickets_lost'] == 0]['expected_final_score'].mean()
print(f"Baseline (0 wkts): {baseline_score:.1f}")
for w in range(1, 8):
    w_score = df_first[df_first['wickets_lost'] == w]['expected_final_score'].mean()
    if not np.isnan(w_score):
        decay_factor = w_score / baseline_score
        implied_alpha = -np.log(decay_factor) / w if decay_factor > 0 else 0
        print(f"  {w} wkts: avg={w_score:.1f}, decay={decay_factor:.3f}, implied_alpha={implied_alpha:.3f}")

print(f"\nCurrent constant WICKET_DECAY_ALPHA = 0.08")

# =========================================================================
# 5. CONFIDENCE RAMP-UP (OVERS FOR FULL CONFIDENCE)
# =========================================================================
print("\n" + "=" * 80)
print("5. CONFIDENCE RAMP-UP ANALYSIS")
print("=" * 80)

# At what point does projected score become reliable?
# Compare projected score to actual win rate correlation
for overs_threshold in [4, 6, 8, 10, 12, 15]:
    phase_data = df_first[df_first['overs_bowled'] >= overs_threshold]
    if len(phase_data) > 100:
        # Bin by expected_final_score and check win rate
        phase_data = phase_data.copy()
        phase_data['score_bin'] = pd.cut(phase_data['expected_final_score'], bins=5)
        corr_data = phase_data.groupby('score_bin', observed=True)['is_winner'].mean()
        # Calculate correlation between score bin midpoint and win rate
        score_win_corr = phase_data['expected_final_score'].corr(phase_data['is_winner'])
        print(f"After {overs_threshold} overs: score-win correlation = {score_win_corr:.3f}")

print(f"\nCurrent constant CONFIDENCE_FULL_OVERS = 12.0")

# =========================================================================
# 6. SQI TO WIN PROBABILITY MAPPING
# =========================================================================
print("\n" + "=" * 80)
print("6. SQI TO WIN PROBABILITY MAPPING")
print("=" * 80)

# Calculate SQI for each ball
# SQI = (expected_score - contextual_par) / std_dev
# For now, use simple par = 165

par_score = 165.0
df_first['sqi'] = (df_first['expected_final_score'] - par_score) / 35.0

# Bin SQI and check win rate
sqi_bins = [-3, -2, -1, -0.5, 0, 0.5, 1, 2, 3]
df_first['sqi_bin'] = pd.cut(df_first['sqi'], bins=sqi_bins)
sqi_win_rate = df_first.groupby('sqi_bin', observed=True)['is_winner'].agg(['mean', 'count'])
print("\nWin Rate by Score Quality Index (SQI):")
print(sqi_win_rate)

# What beta gives the best fit?
print("\nTesting different SQI_BETA values:")
for beta in [0.4, 0.5, 0.6, 0.7, 0.8]:
    # Predict probability using sigmoid
    df_first['pred_prob'] = 1.0 / (1.0 + np.exp(-beta * df_first['sqi']))
    # Calculate MSE
    mse = ((df_first['pred_prob'] - df_first['is_winner']) ** 2).mean()
    print(f"  beta={beta}: MSE={mse:.4f}")

print(f"\nCurrent constant SQI_BETA = 0.6")

# =========================================================================
# 7. VENUE-SPECIFIC PAR SCORES
# =========================================================================
print("\n" + "=" * 80)
print("7. VENUE-SPECIFIC ANALYSIS (if available)")
print("=" * 80)

# Check if venue stats are being used
if 'venue_avg_score' in df.columns:
    print("Venue avg scores found in data")
    venue_scores = df_first.groupby('venue_avg_score').size().head(10)
    print(venue_scores)
else:
    print("No venue_avg_score column - venue data may be in feature store")

print("\n" + "=" * 80)
print("SUMMARY: RECOMMENDED CONSTANTS")
print("=" * 80)
print(f"""
Based on EDA:
  HISTORICAL_BAT_FIRST_WIN_RATE = {bat_first_wr:.2f}  (current: 0.37)
  LEAGUE_AVG_SCORE = {avg_final_score:.0f}  (current: 165.0)
  SCORE_STD_BASE = ~35 (matches current)
  SCORE_STD_MIN = ~15-20 (current: 12.0)
  WICKET_DECAY_ALPHA = (see analysis above)
  CONFIDENCE_FULL_OVERS = 10-12 (current: 12.0)
  SQI_BETA = (see MSE analysis above)
""")
