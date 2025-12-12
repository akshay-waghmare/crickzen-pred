"""
EDA to validate the 4 improvements made to first innings calculator:
1. Phase-aware wicket decay (0.8 early → 1.4 late)
2. Contextual par with venue (60% venue + 40% league)
3. SQI sigmoid shift (-0.35 to encode bat-first disadvantage)
4. Dynamic clamp range (0.95 → 0.98 late)
"""
import pandas as pd
import numpy as np

# Load data
df = pd.read_parquet('data/ilt_features_v2/training.parquet')

# Identify first innings rows
df_first = df[df['required_run_rate'] <= 0].copy()
print("=" * 80)
print("ILT20 FIRST INNINGS - VALIDATING IMPROVEMENTS")
print("=" * 80)
print(f"Total first innings rows: {len(df_first):,}")

df_first['overs_bowled'] = 20 - df_first['overs_remaining']
df_first['overs_progress'] = df_first['overs_bowled'] / 20.0

# =========================================================================
# 1. VALIDATE PHASE-AWARE WICKET DECAY
# =========================================================================
print("\n" + "=" * 80)
print("1. PHASE-AWARE WICKET DECAY")
print("   Hypothesis: Late wickets hurt more than early wickets")
print("=" * 80)

# Create phase bins
df_first['phase'] = pd.cut(
    df_first['overs_bowled'],
    bins=[0, 6, 12, 20],
    labels=['early (1-6)', 'middle (7-12)', 'late (13-20)']
)

# Win rate by wickets and phase
print("\nWin Rate by Wickets Lost and Phase:")
print("-" * 60)
pivot = df_first.groupby(['phase', 'wickets_lost'], observed=True)['is_winner'].agg(['mean', 'count'])
pivot.columns = ['win_rate', 'count']
pivot = pivot[pivot['count'] >= 20]  # Filter for significance

for phase in ['early (1-6)', 'middle (7-12)', 'late (13-20)']:
    print(f"\n{phase}:")
    phase_data = pivot.loc[phase] if phase in pivot.index.get_level_values(0) else pd.DataFrame()
    if len(phase_data) > 0:
        for wickets in range(0, 8):
            if wickets in phase_data.index:
                row = phase_data.loc[wickets]
                print(f"  {wickets} wkts: {row['win_rate']:.1%} (n={row['count']:.0f})")

# Calculate implied wicket impact by phase
print("\nImplied Wicket Impact (win rate drop per wicket):")
for phase in ['early (1-6)', 'middle (7-12)', 'late (13-20)']:
    phase_df = df_first[df_first['phase'] == phase]
    if len(phase_df) > 100:
        wr_0_2 = phase_df[phase_df['wickets_lost'] <= 2]['is_winner'].mean()
        wr_4_6 = phase_df[(phase_df['wickets_lost'] >= 4) & (phase_df['wickets_lost'] <= 6)]['is_winner'].mean()
        drop = wr_0_2 - wr_4_6
        print(f"  {phase}: {wr_0_2:.1%} (0-2 wkts) → {wr_4_6:.1%} (4-6 wkts) = {drop:.1%} drop")

# =========================================================================
# 2. VALIDATE VENUE-BASED PAR (if venue data available)
# =========================================================================
print("\n" + "=" * 80)
print("2. VENUE-BASED PAR SCORE")
print("   Hypothesis: Different venues have different par scores")
print("=" * 80)

# Check venue stats in data
if 'venue_avg_first_innings_score' in df.columns:
    venue_scores = df_first.groupby('venue_avg_first_innings_score')['is_winner'].mean()
    print("Venue avg scores found")
    print(venue_scores)
else:
    # Calculate venue stats from data
    # Get end-of-innings scores per match
    df_end = df_first[df_first['overs_remaining'] <= 1.0]
    
    # Use venue from original data if available
    if 'venue' in df.columns:
        venue_stats = df.groupby('venue').agg({
            'expected_final_score': 'mean',
            'is_winner': 'mean',
            'match_id': 'nunique'
        }).sort_values('match_id', ascending=False)
        venue_stats.columns = ['avg_score', 'bat_first_wr', 'matches']
        print("\nVenue Statistics (where available):")
        print(venue_stats.head(10))
    else:
        print("No venue column found - using league average")
        print(f"League average score: 165.0")

# =========================================================================
# 3. VALIDATE SQI SIGMOID SHIFT (-0.35)
# =========================================================================
print("\n" + "=" * 80)
print("3. SQI SIGMOID SHIFT (-0.35)")
print("   Hypothesis: SQI=0 should give <50% (bat-first disadvantage)")
print("=" * 80)

# Calculate SQI for each ball (using current formula)
LEAGUE_AVG = 165.0
SCORE_STD_EARLY = 15.0
SCORE_STD_LATE = 26.0

df_first['phase_std'] = SCORE_STD_EARLY + df_first['overs_progress'] * (SCORE_STD_LATE - SCORE_STD_EARLY)
df_first['sqi'] = (df_first['expected_final_score'] - LEAGUE_AVG) / df_first['phase_std']

# What win rate do we see at different SQI levels?
sqi_bins = [-3, -2, -1, -0.5, 0, 0.5, 1, 2, 3]
df_first['sqi_bin'] = pd.cut(df_first['sqi'], bins=sqi_bins)

sqi_analysis = df_first.groupby('sqi_bin', observed=True)['is_winner'].agg(['mean', 'count'])
print("\nActual Win Rate by SQI:")
print(sqi_analysis)

# Key insight: What SQI gives 50% win rate?
print("\nFinding SQI where win_rate = 50%:")
for sqi_low in np.arange(-1, 1, 0.1):
    sqi_high = sqi_low + 0.2
    mask = (df_first['sqi'] >= sqi_low) & (df_first['sqi'] < sqi_high)
    if mask.sum() > 50:
        wr = df_first[mask]['is_winner'].mean()
        if 0.45 <= wr <= 0.55:
            print(f"  SQI [{sqi_low:.1f}, {sqi_high:.1f}): {wr:.1%} (n={mask.sum()})")

# Validate: At SQI=0, what's the actual win rate?
mask_sqi_0 = (df_first['sqi'] >= -0.25) & (df_first['sqi'] < 0.25)
wr_at_sqi_0 = df_first[mask_sqi_0]['is_winner'].mean()
print(f"\nActual win rate at SQI ≈ 0: {wr_at_sqi_0:.1%}")
print(f"Current shift: -0.35 (so SQI=0.35 → 50%)")

# What shift would make SQI=0 → actual baseline?
# If actual at SQI=0 is X%, we need shift such that sigmoid(0) = X%
# That means the shift should be where actual win rate = 50%
print("\nRecommendation: If SQI=0 gives 40-45% win rate, shift of -0.35 is appropriate")

# =========================================================================
# 4. VALIDATE DYNAMIC CLAMP RANGE
# =========================================================================
print("\n" + "=" * 80)
print("4. DYNAMIC CLAMP RANGE (0.95 → 0.98 late)")
print("   Hypothesis: Late innings with high scores should reach 97-98%")
print("=" * 80)

# Look at late innings (16+ overs) with high scores
late_high = df_first[(df_first['overs_bowled'] >= 16) & (df_first['expected_final_score'] >= 200)]
if len(late_high) > 10:
    print(f"\nLate innings (16+ ov) with projected 200+:")
    print(f"  Count: {len(late_high)}")
    print(f"  Actual win rate: {late_high['is_winner'].mean():.1%}")
    
# Very high scores
very_high = df_first[(df_first['overs_bowled'] >= 18) & (df_first['expected_final_score'] >= 210)]
if len(very_high) > 5:
    print(f"\nVery late (18+ ov) with projected 210+:")
    print(f"  Count: {len(very_high)}")
    print(f"  Actual win rate: {very_high['is_winner'].mean():.1%}")

# Look at low scores too
late_low = df_first[(df_first['overs_bowled'] >= 16) & (df_first['expected_final_score'] <= 120)]
if len(late_low) > 10:
    print(f"\nLate innings (16+ ov) with projected 120 or less:")
    print(f"  Count: {len(late_low)}")
    print(f"  Actual win rate: {late_low['is_winner'].mean():.1%}")

# =========================================================================
# 5. OVERALL VALIDATION: Compare model predictions to actual outcomes
# =========================================================================
print("\n" + "=" * 80)
print("5. OVERALL CALIBRATION CHECK")
print("=" * 80)

# Apply current model logic to calculate predicted probabilities
HISTORICAL_BAT_FIRST_WIN_RATE = 0.37
WICKET_DECAY_ALPHA = 0.025
SQI_BETA = 0.75
CONFIDENCE_FULL_OVERS = 12.0

# Phase-aware wicket decay
df_first['phase_mult'] = 0.8 + 0.6 * df_first['overs_progress']
df_first['wicket_cap'] = np.exp(-WICKET_DECAY_ALPHA * df_first['phase_mult'] * df_first['wickets_lost'])
df_first['adj_score'] = df_first['expected_final_score'] * df_first['wicket_cap']

# SQI with shift
df_first['sqi_adj'] = (df_first['adj_score'] - LEAGUE_AVG) / df_first['phase_std']
df_first['sqi_shifted'] = df_first['sqi_adj'] - 0.35
df_first['sqi_prob'] = 1.0 / (1.0 + np.exp(-SQI_BETA * df_first['sqi_shifted']))

# Confidence blend
df_first['confidence'] = np.minimum(1.0, df_first['overs_bowled'] / CONFIDENCE_FULL_OVERS)
df_first['pred_prob'] = (1 - df_first['confidence']) * HISTORICAL_BAT_FIRST_WIN_RATE + df_first['confidence'] * df_first['sqi_prob']

# Calibration: bin predictions and compare to actual
pred_bins = [0, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0]
df_first['pred_bin'] = pd.cut(df_first['pred_prob'], bins=pred_bins)

calibration = df_first.groupby('pred_bin', observed=True).agg({
    'is_winner': ['mean', 'count'],
    'pred_prob': 'mean'
})
calibration.columns = ['actual_wr', 'count', 'pred_mean']
print("\nCalibration Check (Predicted vs Actual):")
print("-" * 60)
print(f"{'Pred Bin':<15} {'Pred Mean':<12} {'Actual WR':<12} {'Count':<10} {'Gap':<10}")
print("-" * 60)
for idx, row in calibration.iterrows():
    gap = row['actual_wr'] - row['pred_mean']
    print(f"{str(idx):<15} {row['pred_mean']:.1%}        {row['actual_wr']:.1%}        {row['count']:.0f}        {gap:+.1%}")

# Brier score
brier = ((df_first['pred_prob'] - df_first['is_winner']) ** 2).mean()
print(f"\nBrier Score (lower is better): {brier:.4f}")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
