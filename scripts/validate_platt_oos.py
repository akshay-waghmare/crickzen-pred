"""
True Out-of-Sample Validation: Train Platt on Historical IPL, Test on 2026

Methodology:
  1. Train a holdout model on IPL 2007-2025 (excludes ALL 2026 data)
  2. Generate 5-fold OOF predictions on 2023-2025 data
  3. Fit phase-specific Platt calibrators on 2023-2025 OOF predictions
  4. Score 2026 live observations (510 obs, 16 matches) with holdout model + Platt
  5. Compare against exchange market odds — TRUE out-of-sample test

Usage:
  python scripts/validate_platt_oos.py
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

# ── Helpers ──────────────────────────────────────────────────────────────
def brier(p, y):
    return np.mean((p - y)**2)

def log_loss(p, y, eps=1e-15):
    p = np.clip(p, eps, 1 - eps)
    return -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))

def assign_phase(over, innings):
    if over < 6:
        return 'powerplay'
    elif over < 16:
        return 'middle'
    else:
        return 'death'

TEAM_ALIASES = {
    'Chennai Super Kings': 'Chennai Super Kings',
    'Mumbai Indians': 'Mumbai Indians',
    'Royal Challengers Bengaluru': 'Royal Challengers Bengaluru',
    'Royal Challengers Bangalore': 'Royal Challengers Bengaluru',
    'Kolkata Knight Riders': 'Kolkata Knight Riders',
    'Rajasthan Royals': 'Rajasthan Royals',
    'Sunrisers Hyderabad': 'Sunrisers Hyderabad',
    'Delhi Capitals': 'Delhi Capitals',
    'Delhi Daredevils': 'Delhi Capitals',
    'Punjab Kings': 'Punjab Kings',
    'Kings XI Punjab': 'Punjab Kings',
    'Gujarat Titans': 'Gujarat Titans',
    'Lucknow Super Giants': 'Lucknow Super Giants',
}


# ═══════════════════════════════════════════════════════════════════════
#  STEP 1: Load data and create pre-2026 / 2023-2025 splits
# ═══════════════════════════════════════════════════════════════════════
print("=" * 70)
print("  STEP 1: Preparing data splits")
print("=" * 70)

# Load raw data to get season mapping
raw = pd.read_parquet('data/ipl_raw/matches')
raw = raw.drop_duplicates(subset=['match_id', 'innings', 'over', 'ball'], keep='first')
raw = raw.sort_values(['match_id', 'innings', 'over', 'ball']).reset_index(drop=True)

# Load training features (perfectly aligned with raw)
train_full = pd.read_parquet('data/ipl_features_v2/training.parquet')
assert len(raw) == len(train_full), f"Row count mismatch: {len(raw)} vs {len(train_full)}"

# Attach season and match_id
train_full['season'] = raw['season'].values
train_full['match_id'] = raw['match_id'].values

# Split
mask_pre2026 = train_full['season'] != '2026'
mask_recent = train_full['season'].isin(['2023', '2024', '2025'])

train_pre2026 = train_full[mask_pre2026].copy()
train_recent = train_full[mask_recent].copy()

feature_cols = [c for c in train_full.columns if c not in ['is_winner', 'season', 'match_id']]
X_pre2026 = train_pre2026[feature_cols]
y_pre2026 = train_pre2026['is_winner']

print(f"  Full dataset:    {len(train_full):>8,} rows")
print(f"  Pre-2026 train:  {len(train_pre2026):>8,} rows  ({train_pre2026['match_id'].nunique()} matches)")
print(f"  2023-2025 (OOF): {len(train_recent):>8,} rows  ({train_recent['match_id'].nunique()} matches)")
print(f"  2026 (excluded): {(~mask_pre2026).sum():>8,} rows")
print(f"  Features: {len(feature_cols)}")


# ═══════════════════════════════════════════════════════════════════════
#  STEP 2: Train holdout model on pre-2026 data
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  STEP 2: Training holdout model (2007-2025)")
print("=" * 70)

from bbl_pipeline.training.trainer import XGBLogRegEnsemble

model = XGBLogRegEnsemble()
model.fit(X_pre2026, y_pre2026)

# Quick sanity check
preds_train = model.predict_proba(X_pre2026)[:, 1]
train_brier = brier(preds_train, y_pre2026)
print(f"  In-sample Brier: {train_brier:.4f}")
print(f"  Model trained on {len(X_pre2026):,} rows")

# Save holdout model
holdout_dir = Path('models/ipl_holdout_pre2026')
holdout_dir.mkdir(parents=True, exist_ok=True)
import joblib
joblib.dump(model, holdout_dir / 'champion_model.joblib')
print(f"  Saved to {holdout_dir}")


# ═══════════════════════════════════════════════════════════════════════
#  STEP 3: Generate OOF predictions on 2023-2025 for Platt fitting
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  STEP 3: 5-fold OOF on 2023-2025 for Platt calibrator fitting")
print("=" * 70)

X_recent = train_recent[feature_cols]
y_recent = train_recent['is_winner']
match_ids_recent = train_recent['match_id'].values

# Stratified k-fold at MATCH level (prevent data leakage within a match)
unique_matches = train_recent[['match_id', 'is_winner']].drop_duplicates('match_id')
kf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

oof_preds = np.full(len(X_recent), np.nan)
for fold, (train_idx, val_idx) in enumerate(kf.split(unique_matches['match_id'], unique_matches['is_winner'])):
    train_match_ids = unique_matches['match_id'].iloc[train_idx].values
    val_match_ids = unique_matches['match_id'].iloc[val_idx].values
    
    # Map match-level splits to ball-level rows
    train_mask = np.isin(match_ids_recent, train_match_ids)
    val_mask = np.isin(match_ids_recent, val_match_ids)
    
    fold_model = XGBLogRegEnsemble()
    fold_model.fit(X_recent.iloc[train_mask], y_recent.iloc[train_mask])
    oof_preds[val_mask] = fold_model.predict_proba(X_recent.iloc[val_mask])[:, 1]
    
    fold_brier = brier(oof_preds[val_mask], y_recent.iloc[val_mask])
    print(f"  Fold {fold+1}: Brier={fold_brier:.4f} (train={train_mask.sum():,}, val={val_mask.sum():,})")

oof_brier = brier(oof_preds, y_recent)
print(f"  Overall OOF Brier (2023-2025): {oof_brier:.4f}")


# ═══════════════════════════════════════════════════════════════════════
#  STEP 4: Fit phase-specific Platt calibrators on 2023-2025 OOF
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  STEP 4: Fitting phase-specific Platt calibrators on OOF predictions")
print("=" * 70)

# Compute phase for each row
innings_recent = train_recent['innings'].values
# Reconstruct over from overs_remaining
overs_remaining = train_recent['overs_remaining'].values
overs = (20 - overs_remaining).astype(int).clip(0, 19)
phases = [assign_phase(o, i) for o, i in zip(overs, innings_recent)]

train_recent_oof = pd.DataFrame({
    'pred': oof_preds,
    'actual': y_recent.values,
    'innings': innings_recent,
    'phase': phases,
})

calibrators = {}
for inn in [1, 2]:
    for phase in ['powerplay', 'middle', 'death']:
        key = f'inn{inn}_{phase}'
        mask = (train_recent_oof['innings'] == inn) & (train_recent_oof['phase'] == phase)
        subset = train_recent_oof[mask]
        
        if len(subset) < 30:
            print(f"  {key}: SKIP (only {len(subset)} samples)")
            continue
        
        # Platt scaling: logistic regression on logit of predictions
        logits = logit(np.clip(subset['pred'].values, 1e-6, 1-1e-6)).reshape(-1, 1)
        lr = LogisticRegression(C=1.0, solver='lbfgs', max_iter=1000)
        lr.fit(logits, subset['actual'].values)
        
        cal_preds = lr.predict_proba(logits)[:, 1]
        raw_brier = brier(subset['pred'], subset['actual'])
        cal_brier = brier(cal_preds, subset['actual'])
        
        calibrators[key] = lr
        delta_pct = (cal_brier - raw_brier) / raw_brier * 100
        print(f"  {key}: n={len(subset):>5,}, Raw={raw_brier:.4f}, Platt={cal_brier:.4f} ({delta_pct:+.1f}%)")

# Also fit an overall calibrator per innings
for inn in [1, 2]:
    key = f'inn{inn}_overall'
    mask = train_recent_oof['innings'] == inn
    subset = train_recent_oof[mask]
    logits = logit(np.clip(subset['pred'].values, 1e-6, 1-1e-6)).reshape(-1, 1)
    lr = LogisticRegression(C=1.0, solver='lbfgs', max_iter=1000)
    lr.fit(logits, subset['actual'].values)
    calibrators[key] = lr
    print(f"  {key}: n={len(subset):>5,}")

# Save calibrators
cal_path = holdout_dir / 'oos_platt_calibrators.pkl'
with open(cal_path, 'wb') as f:
    pickle.dump(calibrators, f)
print(f"\n  Saved {len(calibrators)} calibrators to {cal_path}")


# ═══════════════════════════════════════════════════════════════════════
#  STEP 5: Score 2026 live observations with holdout model + Platt
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  STEP 5: Scoring 2026 live observations (TRUE out-of-sample)")
print("=" * 70)

from bbl_pipeline.inference.predictor import Predictor
from bbl_pipeline.inference.schema import MatchState

# Load the original live-state data (has batting_team, runs, wickets, etc.)
live = pd.read_parquet('data/ipl_model_vs_market.parquet')
print(f"  Loaded {len(live)} live observations from {live['event_id'].nunique()} matches")

# Load the holdout model as a Predictor (re-create with feature store)
pred_holdout = Predictor.load(
    model_dir=str(holdout_dir),
    feature_store_dir='data/ipl_feature_store_v2'
)

results = []
errors = 0
for idx, row in live.iterrows():
    bat_team = TEAM_ALIASES.get(row['batting_team'], row['batting_team'])
    t1 = TEAM_ALIASES.get(row['team1'], row['team1'])
    t2 = TEAM_ALIASES.get(row['team2'], row['team2'])
    bowl_team = t2 if bat_team == t1 else t1
    
    state = MatchState(
        match_id=str(row['event_id']),
        venue='Unknown',
        batting_team=bat_team,
        bowling_team=bowl_team,
        innings=int(row['innings']),
        over=int(row['over']),
        ball=0,
        current_score=int(row['runs']),
        wickets_lost=int(row['wickets']),
        batsman_1='Unknown',
        batsman_2='Unknown',
        bowler='Unknown',
        target_runs=int(row['target']) if pd.notna(row.get('target')) else None,
        first_innings_score=int(row['target'])-1 if pd.notna(row.get('target')) else None,
    )
    
    try:
        p_raw = pred_holdout.predict(state)
        p_t1_raw = p_raw if bat_team == t1 else 1.0 - p_raw
    except Exception as e:
        p_t1_raw = np.nan
        errors += 1
        if errors <= 3:
            print(f"    Error at row {idx}: {e}")
    
    # Apply phase-specific Platt calibration
    phase = assign_phase(int(row['over']), int(row['innings']))
    platt_key = f"inn{int(row['innings'])}_{phase}"
    
    if platt_key in calibrators and not np.isnan(p_t1_raw):
        logit_val = logit(np.clip(p_t1_raw, 1e-6, 1-1e-6))
        p_t1_platt = calibrators[platt_key].predict_proba(np.array([[logit_val]]))[0, 1]
    else:
        p_t1_platt = p_t1_raw
    
    results.append({
        'event_id': row['event_id'],
        'innings': row['innings'],
        'over': row['over'],
        'phase': phase,
        'actual_t1_wins': row['actual_t1_wins'],
        'market_p_t1': row['market_p_t1'],
        'holdout_raw_p_t1': p_t1_raw,
        'holdout_platt_p_t1': p_t1_platt,
        'old_model_p_t1': row.get('model_p_t1', np.nan),
    })
    
    if idx % 100 == 0:
        print(f"  Processed {idx}/{len(live)}...")

res = pd.DataFrame(results)
valid = res.dropna(subset=['holdout_raw_p_t1', 'holdout_platt_p_t1'])
print(f"\n  Valid: {len(valid)}/{len(res)}, errors: {errors}")


# ═══════════════════════════════════════════════════════════════════════
#  STEP 6: RESULTS — True Out-of-Sample Comparison
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  RESULTS: TRUE OUT-OF-SAMPLE VALIDATION")
print("  Model trained on 2007-2025, Platt fitted on 2023-2025 OOF")
print("  Test set: 2026 IPL live observations with exchange market odds")
print("=" * 70)

# Overall
b_mkt = brier(valid['market_p_t1'], valid['actual_t1_wins'])
b_raw = brier(valid['holdout_raw_p_t1'], valid['actual_t1_wins'])
b_platt = brier(valid['holdout_platt_p_t1'], valid['actual_t1_wins'])
ll_mkt = log_loss(valid['market_p_t1'], valid['actual_t1_wins'])
ll_raw = log_loss(valid['holdout_raw_p_t1'], valid['actual_t1_wins'])
ll_platt = log_loss(valid['holdout_platt_p_t1'], valid['actual_t1_wins'])

print(f"\n  {'Source':<35} {'Brier':>8} {'vs Mkt':>8} {'LogLoss':>8} {'vs Mkt':>8}  n={len(valid)}")
print("  " + "-" * 75)
print(f"  {'Market (exchange mid-price)':<35} {b_mkt:.4f} {'':>8} {ll_mkt:.4f}")
print(f"  {'Holdout Model (raw)':<35} {b_raw:.4f} {(b_raw-b_mkt)/b_mkt*100:+.1f}%    {ll_raw:.4f} {(ll_raw-ll_mkt)/ll_mkt*100:+.1f}%")
print(f"  {'Holdout + Historical Platt':<35} {b_platt:.4f} {(b_platt-b_mkt)/b_mkt*100:+.1f}%    {ll_platt:.4f} {(ll_platt-ll_mkt)/ll_mkt*100:+.1f}%")

winner = "MODEL BEATS MARKET" if b_platt < b_mkt else "MARKET WINS"
print(f"\n  >>> VERDICT: {winner} <<<")

# Per-phase breakdown
print(f"\n  {'Phase':<20} {'n':>4} {'Market':>8} {'Raw':>8} {'Platt':>8} {'Platt vs Mkt':>12}")
print("  " + "-" * 65)
for inn in [1, 2]:
    for phase in ['powerplay', 'middle', 'death']:
        sub = valid[(valid['phase'] == phase) & (valid['innings'] == inn)]
        if len(sub) < 5:
            continue
        b_m = brier(sub['market_p_t1'], sub['actual_t1_wins'])
        b_r = brier(sub['holdout_raw_p_t1'], sub['actual_t1_wins'])
        b_p = brier(sub['holdout_platt_p_t1'], sub['actual_t1_wins'])
        delta = (b_p - b_m) / b_m * 100
        marker = ' *' if delta < -2 else ''
        print(f"  inn{inn} {phase:<14} {len(sub):4d}  {b_m:.4f}  {b_r:.4f}  {b_p:.4f}  {delta:+.1f}%{marker}")
    # Innings subtotal
    sub = valid[valid['innings'] == inn]
    b_m = brier(sub['market_p_t1'], sub['actual_t1_wins'])
    b_r = brier(sub['holdout_raw_p_t1'], sub['actual_t1_wins'])
    b_p = brier(sub['holdout_platt_p_t1'], sub['actual_t1_wins'])
    delta = (b_p - b_m) / b_m * 100
    print(f"  inn{inn} {'TOTAL':<14} {len(sub):4d}  {b_m:.4f}  {b_r:.4f}  {b_p:.4f}  {delta:+.1f}%")
    print()

# Per-phase LogLoss
print(f"\n  {'Phase (LogLoss)':<20} {'n':>4} {'Market':>8} {'Raw':>8} {'Platt':>8} {'Platt vs Mkt':>12}")
print("  " + "-" * 65)
for inn in [1, 2]:
    for phase in ['powerplay', 'middle', 'death']:
        sub = valid[(valid['phase'] == phase) & (valid['innings'] == inn)]
        if len(sub) < 5:
            continue
        ll_m = log_loss(sub['market_p_t1'], sub['actual_t1_wins'])
        ll_r = log_loss(sub['holdout_raw_p_t1'], sub['actual_t1_wins'])
        ll_p = log_loss(sub['holdout_platt_p_t1'], sub['actual_t1_wins'])
        delta = (ll_p - ll_m) / ll_m * 100
        print(f"  inn{inn} {phase:<14} {len(sub):4d}  {ll_m:.4f}  {ll_r:.4f}  {ll_p:.4f}  {delta:+.1f}%")

# Ensemble analysis — what if we blend holdout+Platt with market?
print(f"\n\n  ENSEMBLE: alpha * holdout_platt + (1-alpha) * market")
print("  " + "-" * 65)
from scipy.optimize import minimize_scalar
print(f"  {'Phase':<20} {'n':>4} {'Market':>8} {'Blend':>8} {'Alpha':>6} {'Improv':>8}")
print("  " + "-" * 55)
for inn in [1, 2]:
    for phase in ['powerplay', 'middle', 'death']:
        sub = valid[(valid['phase'] == phase) & (valid['innings'] == inn)]
        if len(sub) < 10:
            continue
        def obj(alpha):
            blend = alpha * sub['holdout_platt_p_t1'].values + (1-alpha) * sub['market_p_t1'].values
            return brier(blend, sub['actual_t1_wins'].values)
        res_opt = minimize_scalar(obj, bounds=(0, 1), method='bounded')
        b_m = brier(sub['market_p_t1'], sub['actual_t1_wins'])
        if res_opt.fun < b_m:
            print(f"  inn{inn} {phase:<14} {len(sub):4d}  {b_m:.4f}  {res_opt.fun:.4f}  {res_opt.x:.3f}  {(res_opt.fun-b_m)/b_m*100:+.1f}%")

# Overall ensemble
def obj_overall(alpha):
    blend = alpha * valid['holdout_platt_p_t1'].values + (1-alpha) * valid['market_p_t1'].values
    return brier(blend, valid['actual_t1_wins'].values)
res_opt = minimize_scalar(obj_overall, bounds=(0, 1), method='bounded')
b_m = brier(valid['market_p_t1'], valid['actual_t1_wins'])
print(f"\n  {'OVERALL':<20} {len(valid):4d}  {b_m:.4f}  {res_opt.fun:.4f}  {res_opt.x:.3f}  {(res_opt.fun-b_m)/b_m*100:+.1f}%")


# Save results
out_path = 'data/ipl_oos_validation_2026.parquet'
res.to_parquet(out_path)
print(f"\n  Saved detailed results to {out_path}")

# Save summary JSON
summary = {
    'methodology': 'True out-of-sample: model trained 2007-2025, Platt on 2023-2025 OOF, tested on 2026',
    'test_observations': int(len(valid)),
    'test_matches': int(valid['event_id'].nunique()),
    'overall': {
        'market_brier': float(b_mkt),
        'holdout_raw_brier': float(b_raw),
        'holdout_platt_brier': float(b_platt),
        'market_logloss': float(ll_mkt),
        'holdout_raw_logloss': float(ll_raw),
        'holdout_platt_logloss': float(ll_platt),
        'ensemble_alpha': float(res_opt.x),
        'ensemble_brier': float(res_opt.fun),
    }
}
with open('data/ipl_oos_validation_summary.json', 'w') as f:
    json.dump(summary, f, indent=2)
print(f"  Saved summary to data/ipl_oos_validation_summary.json")

print("\n" + "=" * 70)
print("  VALIDATION COMPLETE")
print("=" * 70)
