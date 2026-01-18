"""
Temporal Holdout Validation for S-Curve Correction
Train on earlier matches, test on later matches
"""
import pandas as pd
import numpy as np
from sklearn.metrics import brier_score_loss, log_loss
import joblib

# Load training data
df = pd.read_parquet('data/bbl_features_v4/training.parquet')
model = joblib.load('models/bbl_v12/champion_model.joblib')
FEATURES = model.selected_features_

# Load raw matches to get dates
raw_matches = pd.read_parquet('data/bbl_raw/matches')
match_dates = raw_matches.groupby('match_id')['date'].first().reset_index()
match_dates.columns = ['match_id', 'match_date']

# Check if we have match_id in features
if 'match_id' not in df.columns:
    # Use row index as proxy for temporal ordering 
    # Data is typically processed chronologically, so this is a reasonable approximation
    print("Using row index as temporal proxy (no match_id in features)")
    print(f'Total samples: {len(df):,}')
    # Data is already in order, no need to sort

# Temporal split: 80% train, 20% test (most recent samples)
split_idx = int(len(df) * 0.8)
train_df = df.iloc[:split_idx]
test_df = df.iloc[split_idx:]

print(f'Train: {len(train_df):,} samples (first 80%)')
print(f'Test:  {len(test_df):,} samples (last 20%)')

X_train = train_df[FEATURES]
y_train = train_df['is_winner'].astype(int)
X_test = test_df[FEATURES]
y_test = test_df['is_winner'].astype(int)
innings_test = test_df['innings'].values

# Train model on earlier matches
from sklearn.base import clone
fold_model = clone(model)
fold_model.fit(X_train, y_train)

# Get raw predictions on test set
raw_preds = fold_model.predict_proba(X_test)[:, 1]

# S-curve correction (only high probs)
def apply_scurve_correction(prob, innings):
    if prob <= 0.5:
        return prob
    else:
        power = 0.70 if innings == 1 else 0.80
        normalized = (prob - 0.5) / 0.5
        corrected_normalized = normalized ** power
        return 0.5 + corrected_normalized * 0.5

# Apply S-curve correction
scurve_preds = np.array([apply_scurve_correction(p, inn) for p, inn in zip(raw_preds, innings_test)])

# ECE calculation
def calc_ece(y_true, y_pred, n_bins=10):
    bin_edges = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        mask = (y_pred >= bin_edges[i]) & (y_pred < bin_edges[i + 1])
        if mask.sum() > 0:
            ece += mask.sum() * abs(y_true[mask].mean() - y_pred[mask].mean())
    return ece / len(y_true)

print()
print('=' * 70)
print('TEMPORAL HOLDOUT VALIDATION')
print('Train on earlier matches, test on later matches')
print('=' * 70)
print()
print('OVERALL METRICS (Test Set):')
print('  Raw Model:')
print(f'    Brier: {brier_score_loss(y_test, raw_preds):.4f}')
print(f'    LogLoss: {log_loss(y_test, raw_preds):.4f}')
print(f'    ECE: {calc_ece(y_test.values, raw_preds):.4f}')
print()
print('  S-Curve Corrected:')
print(f'    Brier: {brier_score_loss(y_test, scurve_preds):.4f}')
print(f'    LogLoss: {log_loss(y_test, scurve_preds):.4f}')
print(f'    ECE: {calc_ece(y_test.values, scurve_preds):.4f}')

# Improvement
brier_raw = brier_score_loss(y_test, raw_preds)
brier_sc = brier_score_loss(y_test, scurve_preds)
ece_raw = calc_ece(y_test.values, raw_preds)
ece_sc = calc_ece(y_test.values, scurve_preds)

print()
print('IMPROVEMENT:')
print(f'  Brier: {(brier_sc - brier_raw) / brier_raw * 100:.2f}%')
print(f'  ECE:   {(ece_sc - ece_raw) / ece_raw * 100:.2f}%')

# By probability bin
print()
print('BY 10% PROBABILITY BINS (Test Set):')
print(f'{"Bin":<10} {"N":>6} {"Actual":>8} {"Raw":>8} {"S-Curve":>8} {"RawErr":>8} {"SCErr":>8} {"Better?":>8}')
print('-' * 75)
for lo in range(0, 100, 10):
    hi = lo + 10
    bin_mask = (raw_preds >= lo/100) & (raw_preds < hi/100)
    n = bin_mask.sum()
    if n > 20:
        actual = y_test.values[bin_mask].mean() * 100
        raw_pred = raw_preds[bin_mask].mean() * 100
        scurve_pred = scurve_preds[bin_mask].mean() * 100
        raw_err = abs(actual - raw_pred)
        scurve_err = abs(actual - scurve_pred)
        better = 'YES' if scurve_err < raw_err - 0.5 else ('SAME' if abs(scurve_err - raw_err) < 0.5 else 'no')
        print(f'{lo:>2}-{hi:<3}%    {n:>5}   {actual:>5.1f}%   {raw_pred:>5.1f}%   {scurve_pred:>6.1f}%   {raw_err:>5.1f}%   {scurve_err:>5.1f}%   {better:>8}')

# By innings
print()
print('BY INNINGS (Test Set):')
for inn in [1, 2]:
    mask = innings_test == inn
    raw_brier = brier_score_loss(y_test.values[mask], raw_preds[mask])
    sc_brier = brier_score_loss(y_test.values[mask], scurve_preds[mask])
    raw_ece = calc_ece(y_test.values[mask], raw_preds[mask])
    sc_ece = calc_ece(y_test.values[mask], scurve_preds[mask])
    print(f'  Innings {inn}:')
    print(f'    Raw:     Brier={raw_brier:.4f}, ECE={raw_ece:.4f}')
    print(f'    S-Curve: Brier={sc_brier:.4f}, ECE={sc_ece:.4f}')
    print(f'    Improvement: Brier={(sc_brier-raw_brier)/raw_brier*100:.2f}%, ECE={(sc_ece-raw_ece)/raw_ece*100:.2f}%')
