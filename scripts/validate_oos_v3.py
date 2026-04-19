"""
True OOS Validation for IPL v3 Features (Config B: 28 features)

Validates that partnership + win rate features improve model vs market.
Directly comparable to scripts/validate_platt_oos.py results.

Approach:
  - Uses v3 training features (which contain partnership_runs, partnership_balls,
    batsman_win_rate) for model training and 2026 scoring
  - Matches 2026 training rows to market observations by (date, batting_team, innings, over)
  - This tests the FEATURE improvement, not inference-time approximation
"""
import sys, os, warnings, json, pickle
warnings.filterwarnings('ignore')
sys.path.insert(0, 'src')

import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.model_selection import StratifiedKFold
from sklearn.linear_model import LogisticRegression
from scipy.special import logit, expit

def brier(p, y):
    return np.mean((p - y)**2)

def logloss(p, y, eps=1e-15):
    p = np.clip(p, eps, 1 - eps)
    return -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))

def assign_phase(over, innings):
    if over < 6: return 'powerplay'
    elif over < 16: return 'middle'
    else: return 'death'

TEAM_ALIASES = {
    'Royal Challengers Bangalore': 'Royal Challengers Bengaluru',
    'Delhi Daredevils': 'Delhi Capitals',
    'Kings XI Punjab': 'Punjab Kings',
    'Rising Pune Supergiant': 'Rising Pune Supergiants',
}


# ── STEP 1: Load & split ──
print("=" * 70)
print("  STEP 1: Loading v3 features and creating temporal split")
print("=" * 70)

raw = pd.read_parquet('data/ipl_raw/matches')
raw = raw.drop_duplicates(subset=['match_id', 'innings', 'over', 'ball'], keep='first')
raw = raw.sort_values(['match_id', 'innings', 'over', 'ball']).reset_index(drop=True)

train_full = pd.read_parquet('data/ipl_features_v3/training.parquet')
assert len(raw) == len(train_full), f"Row count mismatch: {len(raw)} vs {len(train_full)}"

# Attach metadata from raw data
train_full['season'] = raw['season'].values
train_full['match_id'] = raw['match_id'].values
train_full['raw_innings'] = raw['innings'].values
train_full['raw_over'] = raw['over'].values
train_full['raw_date'] = pd.to_datetime(raw['date']).dt.strftime('%Y-%m-%d').values
train_full['raw_batting_team'] = raw['batting_team'].map(
    lambda x: TEAM_ALIASES.get(x, x)
).values

# Split
mask_pre2026 = train_full['season'] != '2026'
mask_recent = train_full['season'].isin(['2023', '2024', '2025'])

train_pre2026 = train_full[mask_pre2026].copy()
train_recent = train_full[mask_recent].copy()

# Feature columns = everything except metadata and target
meta_cols = ['is_winner', 'season', 'match_id', 'raw_innings', 'raw_over', 'raw_date', 'raw_batting_team']
feature_cols = [c for c in train_full.columns if c not in meta_cols]
print(f"  Full dataset:    {len(train_full):>8,} rows")
print(f"  Pre-2026 train:  {len(train_pre2026):>8,} rows  ({train_pre2026['match_id'].nunique()} matches)")
print(f"  2023-2025 (OOF): {len(train_recent):>8,} rows  ({train_recent['match_id'].nunique()} matches)")
print(f"  2026 (excluded): {(~mask_pre2026).sum():>8,} rows")
print(f"  Features: {len(feature_cols)}")

# Check new features
for col in ['partnership_runs', 'partnership_balls', 'batsman_win_rate']:
    if col in feature_cols:
        print(f"  + {col} (mean={train_full[col].mean():.4f})")
    else:
        print(f"  - {col} MISSING")


# ── STEP 2: Train holdout model with Config B ──
print("\n" + "=" * 70)
print("  STEP 2: Training holdout model with Config B (28 features)")
print("=" * 70)

from bbl_pipeline.training.trainer import XGBLogRegEnsemble

model = XGBLogRegEnsemble(config='B')
X_pre2026 = train_pre2026[feature_cols]
y_pre2026 = train_pre2026['is_winner']
model.fit(X_pre2026, y_pre2026)

preds_train = model.predict_proba(X_pre2026)[:, 1]
train_brier = brier(preds_train, y_pre2026)
print(f"  Selected features: {len(model.selected_features_)}")
print(f"  Features: {model.selected_features_}")
print(f"  In-sample Brier: {train_brier:.4f}")

# Also train a v2 baseline (25 features, no config) for comparison
model_v2 = XGBLogRegEnsemble()
model_v2.fit(X_pre2026, y_pre2026)
print(f"  v2 baseline features: {len(model_v2.selected_features_)}")


# ── STEP 3: Generate OOF on 2023-2025 + Fit Platt ──
print("\n" + "=" * 70)
print("  STEP 3: OOF predictions (2023-2025) + phase-specific Platt")
print("=" * 70)

X_recent = train_recent[feature_cols]
y_recent = train_recent['is_winner']

# 5-fold match-level CV
unique_matches = train_recent[['match_id', 'is_winner']].drop_duplicates('match_id')
kf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

oof_probs_v3 = np.full(len(X_recent), np.nan)
oof_probs_v2 = np.full(len(X_recent), np.nan)
match_ids_recent = train_recent['match_id'].values

for fold, (train_idx, val_idx) in enumerate(kf.split(unique_matches['match_id'], unique_matches['is_winner'])):
    train_match_ids = unique_matches['match_id'].iloc[train_idx].values
    val_match_ids = unique_matches['match_id'].iloc[val_idx].values
    
    train_mask = np.isin(match_ids_recent, train_match_ids)
    val_mask = np.isin(match_ids_recent, val_match_ids)
    
    # v3 (Config B, 28 features)
    fold_v3 = XGBLogRegEnsemble(config='B')
    fold_v3.fit(X_recent.iloc[train_mask], y_recent.iloc[train_mask])
    oof_probs_v3[val_mask] = fold_v3.predict_proba(X_recent.iloc[val_mask])[:, 1]
    
    # v2 baseline (25 features)
    fold_v2 = XGBLogRegEnsemble()
    fold_v2.fit(X_recent.iloc[train_mask], y_recent.iloc[train_mask])
    oof_probs_v2[val_mask] = fold_v2.predict_proba(X_recent.iloc[val_mask])[:, 1]
    
    b3 = brier(oof_probs_v3[val_mask], y_recent.iloc[val_mask])
    b2 = brier(oof_probs_v2[val_mask], y_recent.iloc[val_mask])
    print(f"  Fold {fold+1}: v3={b3:.4f}, v2={b2:.4f} ({val_mask.sum()} obs)")

print(f"  OOF v3: {brier(oof_probs_v3, y_recent):.4f}")
print(f"  OOF v2: {brier(oof_probs_v2, y_recent):.4f}")

# Reconstruct overs from feature data
overs_remaining = train_recent['overs_remaining'].values
overs = (20 - overs_remaining).astype(int).clip(0, 19)

# Fit phase Platt calibrators for BOTH v3 and v2
def fit_platt_calibrators(oof_preds, y_vals, innings_arr, overs_arr):
    cals = {}
    for inn in [1, 2]:
        for phase in ['powerplay', 'middle', 'death']:
            key = f'inn{inn}_{phase}'
            phases = np.array([assign_phase(o, i) for o, i in zip(overs_arr, innings_arr)])
            mask = (innings_arr == inn) & (phases == phase)
            if mask.sum() < 50:
                continue
            p = oof_preds[mask]
            y = y_vals[mask]
            logits_arr = logit(np.clip(p, 1e-6, 1 - 1e-6)).reshape(-1, 1)
            lr = LogisticRegression(C=1.0, solver='lbfgs', max_iter=1000)
            lr.fit(logits_arr, y)
            cals[key] = lr
            b_before = brier(p, y)
            b_after = brier(lr.predict_proba(logits_arr)[:, 1], y)
            print(f"    {key}: {b_before:.4f} -> {b_after:.4f} ({mask.sum()} obs)")
    return cals

innings_recent = train_recent['raw_innings'].values
print("\n  v3 Platt calibrators:")
cals_v3 = fit_platt_calibrators(oof_probs_v3, y_recent.values, innings_recent, overs)
print(f"\n  v2 Platt calibrators:")
cals_v2 = fit_platt_calibrators(oof_probs_v2, y_recent.values, innings_recent, overs)


# ── STEP 4: Match 2026 training rows to market observations ──
print("\n" + "=" * 70)
print("  STEP 4: Scoring 2026 and matching to market observations")
print("=" * 70)

# Get 2026 rows from training data
test_2026 = train_full[~mask_pre2026].copy()
X_test = test_2026[feature_cols]

# Score with both models
raw_probs_v3 = model.predict_proba(X_test)[:, 1]
raw_probs_v2 = model_v2.predict_proba(X_test)[:, 1]

# Apply Platt calibration
def apply_platt(raw_probs, calibrators, innings_arr, overs_arr):
    cal = raw_probs.copy()
    for i in range(len(raw_probs)):
        phase = assign_phase(int(overs_arr[i]), int(innings_arr[i]))
        key = f'inn{int(innings_arr[i])}_{phase}'
        if key in calibrators:
            lr = calibrators[key]
            l = logit(np.clip(raw_probs[i], 1e-6, 1 - 1e-6))
            cal[i] = lr.predict_proba(np.array([[l]]))[0, 1]
    return cal

cal_probs_v3 = apply_platt(raw_probs_v3, cals_v3, test_2026['raw_innings'].values, test_2026['raw_over'].values)
cal_probs_v2 = apply_platt(raw_probs_v2, cals_v2, test_2026['raw_innings'].values, test_2026['raw_over'].values)

test_2026['v3_raw'] = raw_probs_v3
test_2026['v3_platt'] = cal_probs_v3
test_2026['v2_raw'] = raw_probs_v2
test_2026['v2_platt'] = cal_probs_v2

# Full 2026 Brier (all 5451 rows)
print(f"  Full 2026 ({len(test_2026)} rows):")
print(f"    v3 Raw: {brier(raw_probs_v3, test_2026['is_winner'].values):.4f}")
print(f"    v3 Platt: {brier(cal_probs_v3, test_2026['is_winner'].values):.4f}")
print(f"    v2 Raw: {brier(raw_probs_v2, test_2026['is_winner'].values):.4f}")
print(f"    v2 Platt: {brier(cal_probs_v2, test_2026['is_winner'].values):.4f}")

# Now match to market observations
# Market uses per-over observations at end of over (last ball)
# Training data is per-ball. Take the LAST ball of each (match, innings, over)
obs = pd.read_parquet('data/ipl_model_vs_market.parquet')
print(f"\n  Market observations: {len(obs)} (from {obs['event_id'].nunique()} matches)")

# Create matching key: date + batting_team + innings + over
obs['match_key'] = obs['date'] + '_' + obs['batting_team'] + '_' + obs['innings'].astype(str) + '_' + obs['over'].astype(str)

# For training data, group by (match_id, raw_innings, raw_over), take last ball
test_per_over = test_2026.groupby(['match_id', 'raw_innings', 'raw_over']).agg(
    v3_raw=('v3_raw', 'last'),
    v3_platt=('v3_platt', 'last'),
    v2_raw=('v2_raw', 'last'),
    v2_platt=('v2_platt', 'last'),
    is_winner=('is_winner', 'first'),
    date=('raw_date', 'first'),
    batting_team=('raw_batting_team', 'first'),
).reset_index()

test_per_over['match_key'] = (
    test_per_over['date'] + '_' + 
    test_per_over['batting_team'] + '_' + 
    test_per_over['raw_innings'].astype(str) + '_' + 
    (test_per_over['raw_over'] + 1).astype(str)  # Training overs 0-19 → market overs 1-20
)

# Join
merged = obs.merge(
    test_per_over[['match_key', 'v3_raw', 'v3_platt', 'v2_raw', 'v2_platt']],
    on='match_key',
    how='inner'
)

print(f"  Matched: {len(merged)}/{len(obs)} market observations")
if len(merged) < len(obs):
    # Debug: check unmatched
    unmatched = obs[~obs['match_key'].isin(test_per_over['match_key'])]
    if len(unmatched) > 0:
        print(f"  Unmatched market keys (sample): {unmatched['match_key'].head(5).tolist()}")
        print(f"  Training keys (sample): {test_per_over['match_key'].head(5).tolist()}")
        # Check dates that differ
        mkt_dates = set(obs['date'].unique())
        train_dates = set(test_per_over['date'].unique())
        print(f"  Market dates: {sorted(mkt_dates)}")
        print(f"  Training dates: {sorted(train_dates)}")


# CRITICAL: Model predicts P(batting_team wins) but market has P(team1 wins)
# In inn1, batting_team IS team1 (team that batted first)
# In inn2, batting_team IS team2 (chasing team)
# So for inn2 observations, we need to flip: P(team1) = 1 - P(batting_team)
# The market obs have team1 and batting_team columns to determine this

# For training data, we need to know which team is team1
# The raw data has batting_team. In inn1, batting_team=team1. In inn2, batting_team=team2.
# is_winner in training means batting_team won.
# actual_t1_wins in market means team1 won.
# For inn1: batting_team=team1, so P(t1)=P(batting) and actual_t1_wins matches is_winner
# For inn2: batting_team=team2, so P(t1)=1-P(batting) and actual_t1_wins=1-is_winner

# Apply conversion after merging: flip probabilities for inn2 (where batting team != team1)
# The market data has both team1 and batting_team, so we can check
merged['bat_is_t1'] = merged['batting_team'] == merged['team1']
n_flip = (~merged['bat_is_t1']).sum()
print(f"\n  Need to flip {n_flip}/{len(merged)} obs (inn2 where batting_team != team1)")

for col in ['v3_raw', 'v3_platt', 'v2_raw', 'v2_platt']:
    merged.loc[~merged['bat_is_t1'], col] = 1.0 - merged.loc[~merged['bat_is_t1'], col]


# ── STEP 5: Compare vs market ──
print("\n" + "=" * 70)
print("  STEP 5: RESULTS — TRUE OUT-OF-SAMPLE COMPARISON")
print("  Train: 2007-2025 | Platt: 2023-2025 OOF | Test: 2026")
print("=" * 70)

if len(merged) == 0:
    print("\n  ERROR: No matches between training data and market observations!")
    print("  Falling back to full 2026 comparison (no market)")
    valid = test_per_over.rename(columns={'raw_innings': 'innings', 'raw_over': 'over'})
    valid['market_p_t1'] = np.nan
    valid['actual_t1_wins'] = valid['is_winner']
else:
    valid = merged

actual = valid['actual_t1_wins'].values
market = valid['market_p_t1'].values

n = len(valid)
b_mkt = brier(market, actual)
b_v3_raw = brier(valid['v3_raw'], actual)
b_v3_platt = brier(valid['v3_platt'], actual)
b_v2_raw = brier(valid['v2_raw'], actual)
b_v2_platt = brier(valid['v2_platt'], actual)

ll_mkt = logloss(market, actual)
ll_v3_platt = logloss(valid['v3_platt'].values, actual)
ll_v2_platt = logloss(valid['v2_platt'].values, actual)

print(f"\n  {'Source':<40} {'Brier':>8} {'vs Mkt':>8} {'LogLoss':>8}  n={n}")
print("  " + "-" * 70)
print(f"  {'Market (exchange mid-price)':<40} {b_mkt:.4f} {'':>8} {ll_mkt:.4f}")
print(f"  {'v2 Holdout (25 feat, raw)':<40} {b_v2_raw:.4f} {(b_v2_raw-b_mkt)/b_mkt*100:+.1f}%    {logloss(valid['v2_raw'].values, actual):.4f}")
print(f"  {'v2 Holdout + Platt':<40} {b_v2_platt:.4f} {(b_v2_platt-b_mkt)/b_mkt*100:+.1f}%    {ll_v2_platt:.4f}")
print(f"  {'v3 Holdout (28 feat, raw)':<40} {b_v3_raw:.4f} {(b_v3_raw-b_mkt)/b_mkt*100:+.1f}%    {logloss(valid['v3_raw'].values, actual):.4f}")
print(f"  {'v3 Holdout + Platt':<40} {b_v3_platt:.4f} {(b_v3_platt-b_mkt)/b_mkt*100:+.1f}%    {ll_v3_platt:.4f}")

improvement = b_v2_platt - b_v3_platt
print(f"\n  v3 vs v2 improvement: {improvement:+.4f} Brier ({improvement/b_v2_platt*100:+.1f}%)")
print(f"  v3 vs Market gap:     {(b_v3_platt-b_mkt)/b_mkt*100:+.1f}%")
print(f"  v2 vs Market gap:     {(b_v2_platt-b_mkt)/b_mkt*100:+.1f}%")

winner = "v3 BEATS MARKET" if b_v3_platt < b_mkt else "MARKET WINS"
v3_vs_v2 = "v3 BEATS v2" if b_v3_platt < b_v2_platt else "v2 BEATS v3"
print(f"\n  >>> Model vs Market: {winner} <<<")
print(f"  >>> v3 vs v2: {v3_vs_v2} <<<")

# Phase breakdown
print(f"\n  {'Phase':<20} {'n':>4} {'Market':>8} {'v2+P':>8} {'v3+P':>8} {'v3 vs Mkt':>10} {'v3 vs v2':>10}")
print("  " + "-" * 75)
from scipy.optimize import minimize_scalar

for inn in [1, 2]:
    for phase in ['powerplay', 'middle', 'death']:
        mask = (valid['innings'] == inn) & (valid['phase'] == phase)
        if mask.sum() < 5:
            continue
        n_p = mask.sum()
        b_m = brier(market[mask], actual[mask])
        b_v2 = brier(valid['v2_platt'].values[mask], actual[mask])
        b_v3 = brier(valid['v3_platt'].values[mask], actual[mask])
        g_mkt = (b_v3 - b_m) / b_m * 100
        g_v2 = (b_v3 - b_v2) / b_v2 * 100
        marker = ' *' if g_mkt < -2 else ''
        print(f"  inn{inn} {phase:<14} {n_p:4d}  {b_m:.4f}  {b_v2:.4f}  {b_v3:.4f}  {g_mkt:+.1f}%{marker}    {g_v2:+.1f}%")
    # Innings subtotal
    mask = valid['innings'] == inn
    n_p = mask.sum()
    b_m = brier(market[mask], actual[mask])
    b_v2 = brier(valid['v2_platt'].values[mask], actual[mask])
    b_v3 = brier(valid['v3_platt'].values[mask], actual[mask])
    g_mkt = (b_v3 - b_m) / b_m * 100
    g_v2 = (b_v3 - b_v2) / b_v2 * 100
    print(f"  inn{inn} {'TOTAL':<14} {n_p:4d}  {b_m:.4f}  {b_v2:.4f}  {b_v3:.4f}  {g_mkt:+.1f}%    {g_v2:+.1f}%")
    print()

# Ensemble analysis
print(f"\n  ENSEMBLE: alpha * model + (1-alpha) * market")
print("  " + "-" * 60)
print(f"  {'Source':<20} {'n':>4} {'Market':>8} {'Blend':>8} {'Alpha':>6} {'Improv':>8}")
print("  " + "-" * 55)
for model_name, col in [('v2+Platt', 'v2_platt'), ('v3+Platt', 'v3_platt')]:
    def obj(alpha, col=col):
        blend = alpha * valid[col].values + (1-alpha) * market
        return brier(blend, actual)
    res_opt = minimize_scalar(obj, bounds=(0, 1), method='bounded')
    print(f"  {model_name:<20} {n:4d}  {b_mkt:.4f}  {res_opt.fun:.4f}  {res_opt.x:.3f}  {(res_opt.fun-b_mkt)/b_mkt*100:+.1f}%")

# Save results
results = {
    'methodology': 'True OOS: v3 Config B (28 features) vs v2 (25 features), trained 2007-2025, Platt on 2023-2025 OOF, tested 2026',
    'test_observations': int(n),
    'test_matches': int(valid['event_id'].nunique()) if 'event_id' in valid.columns else 16,
    'new_features': ['partnership_runs', 'partnership_balls', 'batsman_win_rate'],
    'overall': {
        'market_brier': float(b_mkt),
        'v2_raw_brier': float(b_v2_raw),
        'v2_platt_brier': float(b_v2_platt),
        'v3_raw_brier': float(b_v3_raw),
        'v3_platt_brier': float(b_v3_platt),
        'v3_vs_v2_improvement': float(improvement),
        'v3_vs_market_gap_pct': float((b_v3_platt-b_mkt)/b_mkt*100),
        'v2_vs_market_gap_pct': float((b_v2_platt-b_mkt)/b_mkt*100),
    },
    'previous_v2_baseline': {
        'holdout_platt_brier': 0.1878,
        'market_brier': 0.1546,
        'gap_pct': 21.5,
        'description': 'v2 features from validate_platt_oos.py'
    }
}

with open('data/ipl_oos_validation_v3.json', 'w') as f:
    json.dump(results, f, indent=2)

print(f"\n  Results saved to data/ipl_oos_validation_v3.json")
print("\n" + "=" * 70)
print("  VALIDATION COMPLETE")
print("=" * 70)

