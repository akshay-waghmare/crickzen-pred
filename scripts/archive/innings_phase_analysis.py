"""Analyze Brier score by innings and match phase."""
import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss
from sklearn.model_selection import TimeSeriesSplit
import warnings
warnings.filterwarnings('ignore')

# Load data
df = pd.read_parquet('data/training_sampled.parquet')
X = df.drop('is_winner', axis=1)
y = df['is_winner']

print("=" * 70)
print("BRIER SCORE ANALYSIS BY INNINGS AND PHASE")
print("=" * 70)
print(f"Total samples: {len(df)}")

# Use same data - already has all features
full_df = df.copy()

# Best model config
model_config = {
    'n_estimators': 700,
    'max_depth': 2,
    'learning_rate': 0.010,
    'subsample': 0.5,
    'colsample_bytree': 0.5,
    'min_child_weight': 30,
    'reg_alpha': 3.0,
    'reg_lambda': 4.0,
    'random_state': 42
}

# Train on 85% of data, test on 15%
train_size = int(len(X) * 0.85)
X_train, X_test = X.iloc[:train_size], X.iloc[train_size:]
y_train, y_test = y.iloc[:train_size], y.iloc[train_size:]

# Split train into train + calibration
calib_size = int(len(X_train) * 0.15)
X_train_actual = X_train.iloc[:-calib_size]
y_train_actual = y_train.iloc[:-calib_size]
X_calib = X_train.iloc[-calib_size:]
y_calib = y_train.iloc[-calib_size:]

print(f"\nTrain: {len(X_train_actual)}, Calib: {len(X_calib)}, Test: {len(X_test)}")

# Train model
model = XGBClassifier(**model_config)
model.fit(X_train_actual, y_train_actual)

# Calibrate
calibrator = CalibratedClassifierCV(model, method='sigmoid', cv='prefit')
calibrator.fit(X_calib, y_calib)

# Predict on test
y_prob = calibrator.predict_proba(X_test)[:, 1]

# Overall Brier
overall_brier = brier_score_loss(y_test, y_prob)
print(f"\nOverall Test Brier Score: {overall_brier:.4f}")

# Get test data with predictions
test_df = full_df.iloc[train_size:].copy()
test_df['predicted_prob'] = y_prob
test_df['actual'] = y_test.values

# Check what columns we have for innings/phase
print("\n" + "-" * 70)
print("Available columns for analysis:")
if 'innings' in test_df.columns:
    print("  - innings: YES")
else:
    print("  - innings: NO (will derive from features)")

# Derive innings from required_run_rate (0 for innings 1, >0 for innings 2)
if 'innings' not in test_df.columns:
    # In innings 2, required_run_rate > 0
    test_df['innings'] = np.where(test_df['required_run_rate'] > 0, 2, 1)

# Derive phase from resources_remaining
# Powerplay: resources > 0.7 (balls_remaining > 84)
# Middle: 0.3 < resources <= 0.7 (balls 36-84)
# Death: resources <= 0.3 (balls < 36)
test_df['phase'] = pd.cut(
    test_df['resources_remaining'],
    bins=[-0.01, 0.25, 0.55, 1.01],
    labels=['Death (16-20)', 'Middle (7-15)', 'Powerplay (1-6)']
)

# === INNINGS-WISE ANALYSIS ===
print("\n" + "=" * 70)
print("INNINGS-WISE BRIER SCORE")
print("=" * 70)

for innings in [1, 2]:
    mask = test_df['innings'] == innings
    if mask.sum() > 0:
        innings_brier = brier_score_loss(
            test_df.loc[mask, 'actual'],
            test_df.loc[mask, 'predicted_prob']
        )
        print(f"  Innings {innings}: Brier = {innings_brier:.4f} (n={mask.sum()})")

# === PHASE-WISE ANALYSIS ===
print("\n" + "=" * 70)
print("PHASE-WISE BRIER SCORE")
print("=" * 70)

for phase in ['Powerplay (1-6)', 'Middle (7-15)', 'Death (16-20)']:
    mask = test_df['phase'] == phase
    if mask.sum() > 0:
        phase_brier = brier_score_loss(
            test_df.loc[mask, 'actual'],
            test_df.loc[mask, 'predicted_prob']
        )
        print(f"  {phase}: Brier = {phase_brier:.4f} (n={mask.sum()})")

# === INNINGS + PHASE COMBINED ===
print("\n" + "=" * 70)
print("INNINGS x PHASE BRIER SCORE (DETAILED)")
print("=" * 70)

print(f"\n{'Innings':<10} {'Phase':<20} {'Brier':<10} {'Samples':<10} {'Win Rate':<10}")
print("-" * 60)

for innings in [1, 2]:
    for phase in ['Powerplay (1-6)', 'Middle (7-15)', 'Death (16-20)']:
        mask = (test_df['innings'] == innings) & (test_df['phase'] == phase)
        if mask.sum() > 10:  # At least 10 samples
            segment_brier = brier_score_loss(
                test_df.loc[mask, 'actual'],
                test_df.loc[mask, 'predicted_prob']
            )
            win_rate = test_df.loc[mask, 'actual'].mean()
            print(f"{innings:<10} {phase:<20} {segment_brier:.4f}     {mask.sum():<10} {win_rate:.2%}")

# === CALIBRATION CHECK ===
print("\n" + "=" * 70)
print("CALIBRATION CHECK (Predicted vs Actual by Probability Bucket)")
print("=" * 70)

test_df['prob_bucket'] = pd.cut(
    test_df['predicted_prob'],
    bins=[0, 0.2, 0.4, 0.5, 0.6, 0.8, 1.0],
    labels=['0-20%', '20-40%', '40-50%', '50-60%', '60-80%', '80-100%']
)

print(f"\n{'Bucket':<12} {'Predicted':<12} {'Actual':<12} {'Diff':<10} {'Count':<10}")
print("-" * 56)

for bucket in ['0-20%', '20-40%', '40-50%', '50-60%', '60-80%', '80-100%']:
    mask = test_df['prob_bucket'] == bucket
    if mask.sum() > 0:
        pred_mean = test_df.loc[mask, 'predicted_prob'].mean()
        actual_mean = test_df.loc[mask, 'actual'].mean()
        diff = pred_mean - actual_mean
        print(f"{bucket:<12} {pred_mean:.2%}        {actual_mean:.2%}        {diff:+.2%}     {mask.sum()}")

# === ADDITIONAL INSIGHTS ===
print("\n" + "=" * 70)
print("ADDITIONAL INSIGHTS")
print("=" * 70)

# Brier by wickets lost
print("\nBrier by Wickets Lost:")
for wickets in range(0, 8):
    mask = (test_df['wickets_lost'] >= wickets) & (test_df['wickets_lost'] < wickets + 2)
    if mask.sum() > 50:
        wicket_brier = brier_score_loss(
            test_df.loc[mask, 'actual'],
            test_df.loc[mask, 'predicted_prob']
        )
        print(f"  {wickets}-{wickets+1} wickets: Brier = {wicket_brier:.4f} (n={mask.sum()})")

# Brier by required run rate (innings 2 only)
print("\nBrier by Required Run Rate (Innings 2):")
innings2 = test_df[test_df['innings'] == 2]
for rrr_low, rrr_high, label in [(0, 6, 'Easy (<6)'), (6, 10, 'Moderate (6-10)'), (10, 15, 'Hard (10-15)'), (15, 50, 'Very Hard (>15)')]:
    mask = (innings2['required_run_rate'] >= rrr_low) & (innings2['required_run_rate'] < rrr_high)
    if mask.sum() > 30:
        rrr_brier = brier_score_loss(
            innings2.loc[mask, 'actual'],
            innings2.loc[mask, 'predicted_prob']
        )
        print(f"  {label}: Brier = {rrr_brier:.4f} (n={mask.sum()})")

print("\n" + "=" * 70)
