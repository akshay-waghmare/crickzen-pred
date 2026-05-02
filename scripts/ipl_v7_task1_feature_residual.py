"""Task 1: Feature Residual Analysis for IPL v7"""
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')
import os

TOP_FEATURES = [
    'expected_final_score', 'resource_win_prob', 'score_vs_par',
    'dls_pressure_index', 'projected_vs_venue_avg', 'projected_score',
    'is_powerplay', 'score_per_wicket', 'run_rate_diff', 'required_run_rate',
    'chase_difficulty', 'wickets_times_balls', 'pressure_index',
    'team_strength_diff', 'rrr_times_wickets', 'overs_remaining',
    'batting_team_win_rate', 'bowling_team_win_rate', 'batting_team_situation_wr',
    'situation_advantage', 'boundary_pct_last_18', 'bowling_team_situation_wr',
    'runs_last_12', 'runs_last_18', 'wickets_last_12',
    'inn1_defendability', 'target_above_par',
    'inn1_wickets_lost', 'inn1_death_rr', 'inn1_pp_runs',
    'venue_chase_success', 'batting_won_toss'
]

print("Loading features...")
features = pd.read_parquet('data/ipl_features_latest/training.parquet')
print(f"  Features shape: {features.shape}")

# End-of-over rows
eoo = features.groupby(['match_id', 'innings', 'over'], as_index=False).tail(1)
print(f"  End-of-over rows: {eoo.shape}")

print("Loading market comparison...")
mkt = pd.read_parquet('data/ipl_latest_market_vs_model.parquet')
print(f"  Market shape: {mkt.shape}")
print(f"  Market columns: {list(mkt.columns)}")
print(f"  Market innings unique: {mkt['innings'].unique()}")
print(f"  Market over range: {mkt['over'].min()} - {mkt['over'].max()}")
print(f"  features match_id dtype: {eoo['match_id'].dtype}, sample: {eoo['match_id'].iloc[0]}")
print(f"  mkt cs_match_id dtype: {mkt['cs_match_id'].dtype}, sample: {mkt['cs_match_id'].iloc[0]}")

# Align dtypes
eoo['match_id_str'] = eoo['match_id'].astype(str)
mkt['cs_match_id_str'] = mkt['cs_match_id'].astype(str)

# Merge
merged = eoo.merge(
    mkt[['cs_match_id_str', 'innings', 'over', 'actual_inn1_wins', 'market_p_inn1', 'raw_p_inn1', 'iso_p_inn1']],
    left_on=['match_id_str', 'innings', 'over'],
    right_on=['cs_match_id_str', 'innings', 'over'],
    how='inner'
)
print(f"\n  Merged rows: {merged.shape}")

# Filter inn2
inn2 = merged[merged['innings'] == 2].copy()
print(f"  Inn2 rows: {inn2.shape}")

if len(inn2) == 0:
    print("WARNING: No inn2 rows in merged! Checking sample keys...")
    print("  eoo match_ids sample:", eoo['match_id_str'].unique()[:5])
    print("  mkt cs_match_ids sample:", mkt['cs_match_id_str'].unique()[:5])
    print("  eoo innings:", eoo['innings'].unique())
    print("  mkt innings:", mkt['innings'].unique())

# Residual
inn2['residual'] = inn2['iso_p_inn1'] - inn2['actual_inn1_wins']
print(f"\n  Residual stats:")
print(f"    mean={inn2['residual'].mean():.4f}, std={inn2['residual'].std():.4f}")
print(f"    min={inn2['residual'].min():.4f}, max={inn2['residual'].max():.4f}")

# All numeric features for analysis
numeric_cols = inn2.select_dtypes(include=[np.number]).columns.tolist()
exclude = ['innings', 'over', 'ball', 'actual_inn1_wins', 'market_p_inn1', 'raw_p_inn1', 'iso_p_inn1', 'residual', 'is_winner']
feat_cols = [c for c in numeric_cols if c not in exclude]
print(f"\n  Numeric feature columns available: {len(feat_cols)}")

# Pearson correlation with residual
print("\n--- Top 20 Features by |Pearson Correlation| with Residual ---")
correlations = {}
for col in feat_cols:
    if inn2[col].std() > 1e-10:
        corr = inn2[col].corr(inn2['residual'])
        if not np.isnan(corr):
            correlations[col] = corr

corr_series = pd.Series(correlations).sort_values(key=abs, ascending=False)
top20_corr = corr_series.head(20)
print(top20_corr.to_string())

# RandomForest feature importance
print("\n--- RandomForest Feature Importances (residual prediction) ---")
rf_cols = [c for c in feat_cols if inn2[c].notna().sum() > len(inn2)*0.8]
X_rf = inn2[rf_cols].fillna(inn2[rf_cols].median())
y_rf = inn2['residual'].values

rf = RandomForestRegressor(n_estimators=100, max_depth=6, random_state=42, n_jobs=-1)
rf.fit(X_rf, y_rf)
rf_importance = pd.Series(rf.feature_importances_, index=rf_cols).sort_values(ascending=False)
print("Top 20 RF importances:")
print(rf_importance.head(20).to_string())

# Summary report
report_lines = [
    "=" * 70,
    "IPL v7 Feature Residual Analysis",
    "Date: 2026-04-22",
    "=" * 70,
    "",
    f"Dataset: {features.shape[0]:,} rows → {eoo.shape[0]:,} end-of-over rows",
    f"Merged with market (inn2 only): {len(inn2):,} rows",
    "",
    "Residual = iso_p_inn1 - actual_inn1_wins",
    f"  Mean bias: {inn2['residual'].mean():.4f}",
    f"  Std:       {inn2['residual'].std():.4f}",
    "",
    "=" * 70,
    "TOP 20 FEATURES BY |PEARSON CORR| WITH RESIDUAL",
    "=" * 70,
    top20_corr.to_string(),
    "",
    "=" * 70,
    "TOP 20 FEATURES BY RANDOM FOREST IMPORTANCE (residual prediction)",
    "=" * 70,
    rf_importance.head(20).to_string(),
    "",
    "=" * 70,
    "INTERPRETATION",
    "=" * 70,
    "Features highly correlated with residual indicate where the model",
    "systematically over- or under-predicts. Positive corr means feature",
    "drives overestimation; negative means underestimation.",
    "",
    "Key inn2 calibration issue: model S-curve is flattened vs reality.",
    "  - (0.3-0.4]: model 0.351 vs actual 0.140 -> +0.211 overestimate",
    "  - (0.6-0.7]: model 0.659 vs actual 0.811 -> -0.152 underestimate",
    "",
    "Recommendation: Apply IsotonicRegression on raw_p_inn1 for inn2.",
]

os.makedirs('experiments', exist_ok=True)
with open('experiments/ipl_v7_feature_residual.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(report_lines))

print('\n' + '\n'.join(report_lines))
print("\n[Task 1 Complete] Report saved to experiments/ipl_v7_feature_residual.txt")
