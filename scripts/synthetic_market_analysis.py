"""
Synthetic Market Feature Analysis

Can our features learn to approximate exchange market probabilities?
If yes, this "synthetic market" can be used as a feature for ALL historical data
(not just the 510 observations where we have actual market odds).

Approach:
  1. Join 2026 IPL training features with market observations (510 obs, 16 matches)
  2. Train XGB regression: features → market_prob (leave-one-match-out CV)
  3. Analyze: what does the market-approximator weight differently vs our win model?
  4. Test: does using synthetic_market_prob as a feature improve predictions?
  5. Generate synthetic market probs for ALL historical data

Key insight: The market sees pitch, dew, momentum, crowd. Our features CAN'T capture
these directly. But the market's RESPONSE to scoreboard states may be learnable —
e.g., "when CRR is 8.5 at over 10 in inn2, market usually gives 62% to batting team"
"""
import sys, os, warnings, json
warnings.filterwarnings('ignore')
sys.path.insert(0, 'src')

import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import LeaveOneGroupOut
from scipy.special import logit, expit

def brier(p, y):
    return np.mean((p - y)**2)

def logloss(p, y, eps=1e-15):
    p = np.clip(p, eps, 1 - eps)
    return -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))

TEAM_ALIASES = {
    'Royal Challengers Bangalore': 'Royal Challengers Bengaluru',
    'Delhi Daredevils': 'Delhi Capitals',
    'Kings XI Punjab': 'Punjab Kings',
    'Rising Pune Supergiant': 'Rising Pune Supergiants',
}


# ── STEP 1: Join features with market data ──
print("=" * 70)
print("  STEP 1: Join 2026 features with market observations")
print("=" * 70)

# Load raw data for metadata
raw = pd.read_parquet('data/ipl_raw/matches')
raw = raw.drop_duplicates(subset=['match_id', 'innings', 'over', 'ball'], keep='first')
raw = raw.sort_values(['match_id', 'innings', 'over', 'ball']).reset_index(drop=True)

# Load features
train_full = pd.read_parquet('data/ipl_features_v3/training.parquet')
assert len(raw) == len(train_full), f"Row mismatch: {len(raw)} vs {len(train_full)}"

# Attach metadata
train_full['season'] = raw['season'].values
train_full['match_id'] = raw['match_id'].values
train_full['raw_innings'] = raw['innings'].values
train_full['raw_over'] = raw['over'].values
train_full['raw_date'] = pd.to_datetime(raw['date']).dt.strftime('%Y-%m-%d').values
train_full['raw_batting_team'] = raw['batting_team'].map(lambda x: TEAM_ALIASES.get(x, x)).values
# bowling_team not in raw, derive from batting_team_id/bowling_team_id mapping
# Not strictly needed - we only need batting_team for matching

# Get per-over aggregates for 2026 (to match market data granularity)
mask_2026 = train_full['season'] == '2026'
df_2026 = train_full[mask_2026].copy()

# Market data uses over 1-20, training has raw_over 0-19
df_2026['over_for_join'] = df_2026['raw_over'] + 1

# Take LAST ball of each over (most representative state)
df_2026_per_over = df_2026.sort_values(['match_id', 'raw_innings', 'raw_over']).groupby(
    ['match_id', 'raw_innings', 'over_for_join']
).last().reset_index()

print(f"  2026 per-over rows: {len(df_2026_per_over)}")

# Load market data
mkt = pd.read_parquet('data/ipl_model_vs_market_v2.parquet')
print(f"  Market observations: {len(mkt)} ({mkt['event_id'].nunique()} matches)")

# Market has event_id, we need to match by date + team + innings + over
# First get match info from raw data for 2026
match_info = raw[raw['season'] == '2026'][['match_id', 'date', 'batting_team', 'innings']].drop_duplicates(['match_id', 'innings'])
match_info['batting_team'] = match_info['batting_team'].map(lambda x: TEAM_ALIASES.get(x, x))
match_info['date_str'] = pd.to_datetime(match_info['date']).dt.strftime('%Y-%m-%d')

# Build event_id → match_id mapping via the validate_oos approach
# We need to match market's team names with our team names
# Get team1 from market (team batting in inn1)
mkt_match_info = mkt.groupby('event_id').first().reset_index()

# For joining, we'll use the per-over features directly
# Add date and team info to per-over data
df_join = df_2026_per_over.copy()
df_join['date_str'] = df_join['raw_date']

# Create join key for both datasets
df_join['join_key'] = (
    df_join['date_str'] + '_' + 
    df_join['raw_batting_team'] + '_' + 
    df_join['raw_innings'].astype(str) + '_' + 
    df_join['over_for_join'].astype(str)
)

# For market data, we need to figure out batting team per row
# market_p_t1 = P(team1 wins), where team1 = team batting in innings 1
# In innings 1: batting_team = team1
# In innings 2: batting_team = team2 (bowling in inn1)

# Build mapping from the raw data
inn1_teams = raw[raw['season'] == '2026'].groupby('match_id').apply(
    lambda g: g[g['innings'] == 1]['batting_team'].iloc[0]
).reset_index()
inn1_teams.columns = ['match_id', 'team1']
inn1_teams['team1'] = inn1_teams['team1'].map(lambda x: TEAM_ALIASES.get(x, x))

inn2_teams = raw[raw['season'] == '2026'].groupby('match_id').apply(
    lambda g: g[g['innings'] == 2]['batting_team'].iloc[0] if (g['innings'] == 2).any() else None
).reset_index()
inn2_teams.columns = ['match_id', 'team2']
inn2_teams['team2'] = inn2_teams['team2'].map(lambda x: TEAM_ALIASES.get(x, x) if x else x)

match_teams = inn1_teams.merge(inn2_teams, on='match_id')
match_teams['date_str'] = raw[raw['season'] == '2026'].groupby('match_id')['date'].first().apply(
    lambda x: pd.Timestamp(x).strftime('%Y-%m-%d')
).values

# Now for each market event_id, we need to find the match_id
# Market observations don't have team names directly, but we matched them before
# Let's use the model predictions to match: find the event where model prob is closest
# Actually, let me just merge on what we have from validate_oos_v3 approach

# Better approach: use the fact that market data has unique (date, innings, over) combos
# if we can identify the date per event_id

# Let's try a simpler approach - join market directly with the per-over feature rows
# using the date+team matching from validate_oos_v3

# Load the previously-matched data if available
oos_result_path = Path('data/ipl_oos_validation_v3.json')
if oos_result_path.exists():
    with open(oos_result_path) as f:
        prev_results = json.load(f)
    print(f"  Previous OOS had {prev_results.get('n_matched', '?')} matched obs")

# Match approach: for each 2026 match_id, figure out which event_id it corresponds to
# by looking at batting team in inn2 (chasing team is distinctive)
print("\n  Building event_id → match_id mapping...")

# Get unique match_ids with dates and teams
match_lookup = match_teams[['match_id', 'team1', 'team2', 'date_str']].copy()
print(f"  2026 matches: {len(match_lookup)}")

# For each market event_id, we need to figure out team1 (batting in inn1)
# Market data has inn1 and inn2 data. In inn1, batting team = team1
# We can't directly know team1 from market data, but we can match by date

# Since market data has ~16 events and we have ~16 2026 matches, match by ordering
# Actually, let's try matching by the model predictions (ipl_v2_p_t1)
# OR just number them by date

# Group market by event_id and get the range of data
mkt_summary = mkt.groupby('event_id').agg(
    n_obs=('over', 'count'),
    innings=('innings', 'unique'),
).reset_index()
print(f"  Market events: {len(mkt_summary)}")

# Since we're working with per-over features that already have match_id,
# let's match differently: for each (match_id, innings, over) in features,
# find the corresponding market observation

# First, let's get the date per event_id from a known reference
# We previously computed this - let me try the brute force approach:
# iterate each training over, find matching market obs by checking model prob similarity

# Actually, the simplest approach: rebuild features → market_p mapping
# using the same approach as validate_oos_v3.py

# Let's aggregate training features to over-level and get model predictions
from bbl_pipeline.training.trainer import XGBLogRegEnsemble

meta_cols = ['is_winner', 'season', 'match_id', 'raw_innings', 'raw_over', 
             'raw_date', 'raw_batting_team', 'over_for_join', 'date_str', 'join_key']
feature_cols = [c for c in df_2026_per_over.columns if c not in meta_cols]
print(f"  Feature columns: {len(feature_cols)}")

# Train model on pre-2026 data
pre2026 = train_full[train_full['season'] != '2026'].copy()
pre2026_meta = ['is_winner', 'season', 'match_id', 'raw_innings', 'raw_over', 
                'raw_date', 'raw_batting_team']
pre2026_feat_cols = [c for c in pre2026.columns if c not in pre2026_meta]

model = XGBLogRegEnsemble(config='B')
model.fit(pre2026[pre2026_feat_cols], pre2026['is_winner'])

# Get predictions for 2026 per-over data
preds_2026 = model.predict_proba(df_2026_per_over[feature_cols])[:, 1]
df_2026_per_over['model_p_batting'] = preds_2026

# Convert to P(team1) for matching with market
# Inn1: batting_team = team1, so model_p = P(team1)
# Inn2: batting_team = team2, so model_p = P(team2) = 1 - P(team1)
df_2026_per_over = df_2026_per_over.merge(
    match_teams[['match_id', 'team1']], on='match_id', how='left'
)
df_2026_per_over['is_team1_batting'] = df_2026_per_over['raw_batting_team'] == df_2026_per_over['team1']
df_2026_per_over['model_p_t1'] = np.where(
    df_2026_per_over['is_team1_batting'],
    df_2026_per_over['model_p_batting'],
    1 - df_2026_per_over['model_p_batting']
)

# Now match with market by date + team1 + innings + over
# First, attach date to market events by matching with our data
# Try matching by brute force: for each event_id, find match_id where
# model predictions correlate most

event_to_match = {}
for eid in mkt['event_id'].unique():
    mkt_sub = mkt[mkt['event_id'] == eid].sort_values(['innings', 'over'])
    best_corr = -1
    best_mid = None
    for mid in df_2026_per_over['match_id'].unique():
        feat_sub = df_2026_per_over[df_2026_per_over['match_id'] == mid].sort_values(['raw_innings', 'over_for_join'])
        # Match on (innings, over) pairs
        merged = mkt_sub.merge(
            feat_sub[['raw_innings', 'over_for_join', 'model_p_t1']],
            left_on=['innings', 'over'],
            right_on=['raw_innings', 'over_for_join'],
            how='inner'
        )
        if len(merged) < 5:
            continue
        corr = merged['ipl_v2_p_t1'].corr(merged['model_p_t1'])
        if corr > best_corr:
            best_corr = corr
            best_mid = mid
    event_to_match[eid] = (best_mid, best_corr)

print("\n  Event → Match mapping (by model prediction correlation):")
for eid, (mid, corr) in sorted(event_to_match.items()):
    date = df_2026_per_over[df_2026_per_over['match_id'] == mid]['raw_date'].iloc[0] if mid else '?'
    print(f"    event {eid} → match {mid}  (corr={corr:.3f}, date={date})")

# Now do the actual join
matched_rows = []
for eid, (mid, corr) in event_to_match.items():
    if mid is None or corr < 0.5:
        continue
    mkt_sub = mkt[mkt['event_id'] == eid]
    feat_sub = df_2026_per_over[df_2026_per_over['match_id'] == mid]
    
    merged = mkt_sub.merge(
        feat_sub,
        left_on=['innings', 'over'],
        right_on=['raw_innings', 'over_for_join'],
        how='inner',
        suffixes=('_mkt', '_feat')
    )
    matched_rows.append(merged)

if matched_rows:
    matched = pd.concat(matched_rows, ignore_index=True)
    print(f"\n  Matched observations: {len(matched)} (from {len(event_to_match)} events)")
else:
    print("  ERROR: No matches found!")
    sys.exit(1)


# ── STEP 2: Can features predict market probabilities? ──
print("\n" + "=" * 70)
print("  STEP 2: Can our features predict market probabilities?")
print("=" * 70)

# Convert market_p_t1 to market_p_batting for the regression target
# (model predicts P(batting_team), market has P(team1))
matched['market_p_batting'] = np.where(
    matched['is_team1_batting'],
    matched['market_p_t1'],
    1 - matched['market_p_t1']
)

# Also store actual outcome for batting team
matched['actual_batting_wins'] = np.where(
    matched['is_team1_batting'],
    matched['actual_t1_wins'],
    1 - matched['actual_t1_wins']
)

# Feature matrix for market prediction
# Use the same features our win model uses
feature_cols_clean = [c for c in feature_cols if c in matched.columns]
X_mkt = matched[feature_cols_clean].copy()
y_mkt = matched['market_p_batting'].values
y_actual = matched['actual_batting_wins'].values
match_ids_mkt = matched['match_id'].values

print(f"  Features: {len(feature_cols_clean)}")
print(f"  Observations: {len(X_mkt)}")
print(f"  Market prob range: [{y_mkt.min():.3f}, {y_mkt.max():.3f}]")
print(f"  Unique matches: {len(np.unique(match_ids_mkt))}")

# Leave-one-match-out CV for market approximation
from xgboost import XGBRegressor

logo = LeaveOneGroupOut()
synthetic_market_probs = np.full(len(X_mkt), np.nan)

# Also track per-match metrics
match_metrics = []

for fold_idx, (train_idx, test_idx) in enumerate(logo.split(X_mkt, y_mkt, match_ids_mkt)):
    X_tr, X_te = X_mkt.iloc[train_idx], X_mkt.iloc[test_idx]
    y_tr, y_te = y_mkt[train_idx], y_mkt[test_idx]
    
    # XGB regression to predict market prob
    xgb_mkt = XGBRegressor(
        n_estimators=200, max_depth=4, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        min_child_weight=5, reg_alpha=1.0, reg_lambda=3.0,
        random_state=42, verbosity=0
    )
    xgb_mkt.fit(X_tr, y_tr)
    
    preds = xgb_mkt.predict(X_te).clip(0.01, 0.99)
    synthetic_market_probs[test_idx] = preds
    
    mid = match_ids_mkt[test_idx][0]
    mse = mean_squared_error(y_te, preds)
    r2 = r2_score(y_te, preds) if len(y_te) > 1 else 0
    match_metrics.append({
        'match_id': mid, 'n_obs': len(y_te),
        'mse': mse, 'r2': r2,
        'actual_market_std': np.std(y_te),
    })

# Overall metrics
overall_mse = mean_squared_error(y_mkt, synthetic_market_probs)
overall_r2 = r2_score(y_mkt, synthetic_market_probs)
overall_mae = np.mean(np.abs(y_mkt - synthetic_market_probs))

print(f"\n  Market Approximation (Leave-One-Match-Out):")
print(f"    MSE:  {overall_mse:.6f}")
print(f"    MAE:  {overall_mae:.4f}")
print(f"    R²:   {overall_r2:.4f}")
print(f"    RMSE: {np.sqrt(overall_mse):.4f}")

# Compare: how good is our raw model at predicting market?
raw_model_mse = mean_squared_error(y_mkt, matched['model_p_batting'].values)
raw_model_r2 = r2_score(y_mkt, matched['model_p_batting'].values)
raw_model_mae = np.mean(np.abs(y_mkt - matched['model_p_batting'].values))

print(f"\n  Comparison (raw win model vs market):")
print(f"    MSE:  {raw_model_mse:.6f}")
print(f"    MAE:  {raw_model_mae:.4f}")
print(f"    R²:   {raw_model_r2:.4f}")
print(f"    RMSE: {np.sqrt(raw_model_mse):.4f}")

improvement = (raw_model_mse - overall_mse) / raw_model_mse * 100
print(f"\n  Synthetic market vs raw model: {improvement:+.1f}% MSE improvement in matching market")


# ── STEP 3: What features does the market-approximator weight? ──
print("\n" + "=" * 70)
print("  STEP 3: Feature importance (market-approximator vs win model)")
print("=" * 70)

# Train final market approximator on all data for feature importance
xgb_mkt_final = XGBRegressor(
    n_estimators=200, max_depth=4, learning_rate=0.05,
    subsample=0.8, colsample_bytree=0.8,
    min_child_weight=5, reg_alpha=1.0, reg_lambda=3.0,
    random_state=42, verbosity=0
)
xgb_mkt_final.fit(X_mkt, y_mkt)

# Get feature importances
mkt_importance = pd.Series(
    xgb_mkt_final.feature_importances_, index=feature_cols_clean
).sort_values(ascending=False)

# Compare with win model importance
win_importance = pd.Series(
    dict(zip(model.selected_features_, 
             [1.0] * len(model.selected_features_)))  # placeholder
)

# Get XGBoost gain from win model
try:
    xgb_gain = model.xgb_model_.get_booster().get_score(importance_type='gain')
    # Map feature names
    win_gain = {}
    for fname in model.selected_features_:
        idx = list(model.xgb_model_.get_booster().feature_names).index(fname)
        fkey = f'f{idx}'
        if fkey in xgb_gain:
            win_gain[fname] = xgb_gain[fkey]
        elif fname in xgb_gain:
            win_gain[fname] = xgb_gain[fname]
except:
    win_gain = {}

print(f"\n  Top 15 features for MARKET approximation:")
print(f"  {'Feature':35s} {'Mkt Imp':>10s} {'Win Gain':>10s} {'Diff':>10s}")
print(f"  {'-'*35} {'-'*10} {'-'*10} {'-'*10}")
for feat, imp in mkt_importance.head(15).items():
    wg = win_gain.get(feat, 0)
    diff = 'NEW' if wg == 0 else f'{imp/max(mkt_importance)*100 - wg/max(win_gain.values())*100:+.1f}%' if win_gain else ''
    print(f"  {feat:35s} {imp:10.4f} {wg:10.1f} {diff:>10s}")


# ── STEP 4: Does synthetic market improve win predictions? ──
print("\n" + "=" * 70)
print("  STEP 4: Does synthetic market prob improve win predictions?")
print("=" * 70)

# Compare Brier scores:
# a) Our raw model prob → actual outcome
# b) Market prob → actual outcome  
# c) Synthetic market prob → actual outcome
# d) Blend (model + synthetic) → actual outcome

model_p = matched['model_p_batting'].values
synth_p = synthetic_market_probs

brier_model = brier(model_p, y_actual)
brier_market = brier(y_mkt, y_actual)
brier_synth = brier(synth_p, y_actual)

print(f"  Predicting actual outcome (Brier, lower=better):")
print(f"    Market (actual):      {brier_market:.4f}  (gold standard)")
print(f"    Our model:            {brier_model:.4f}  (+{(brier_model/brier_market-1)*100:.1f}%)")
print(f"    Synthetic market:     {brier_synth:.4f}  (+{(brier_synth/brier_market-1)*100:.1f}%)")

# Try blends
print(f"\n  Blend search (α × model + (1-α) × synthetic):")
best_alpha = 0.0
best_brier = 999
for alpha in np.arange(0, 1.01, 0.05):
    blend_p = alpha * model_p + (1 - alpha) * synth_p
    b = brier(blend_p, y_actual)
    if b < best_brier:
        best_brier = b
        best_alpha = alpha
    if alpha in [0.0, 0.25, 0.5, 0.75, 1.0]:
        print(f"    α={alpha:.2f}: Brier={b:.4f}")

print(f"    Best: α={best_alpha:.2f}, Brier={best_brier:.4f}")

# Also try: use synthetic as a FEATURE in logistic regression
from sklearn.linear_model import LogisticRegression
from scipy.special import logit as safe_logit

# Feature set: model_logit + synthetic_logit
X_blend = np.column_stack([
    logit(np.clip(model_p, 0.01, 0.99)),
    logit(np.clip(synth_p, 0.01, 0.99)),
])

# Leave-one-match-out for stacking
stacked_probs = np.full(len(y_actual), np.nan)
for fold_idx, (train_idx, test_idx) in enumerate(logo.split(X_blend, y_actual, match_ids_mkt)):
    lr = LogisticRegression(C=1.0, max_iter=1000)
    lr.fit(X_blend[train_idx], y_actual[train_idx])
    stacked_probs[test_idx] = lr.predict_proba(X_blend[test_idx])[:, 1]

brier_stacked = brier(stacked_probs, y_actual)
print(f"\n  Stacked (LR on model + synthetic logits): Brier={brier_stacked:.4f}")

# Compare to using market as a feature directly
if True:
    X_with_mkt = np.column_stack([
        logit(np.clip(model_p, 0.01, 0.99)),
        logit(np.clip(y_mkt, 0.01, 0.99)),  # actual market
    ])
    gold_probs = np.full(len(y_actual), np.nan)
    for fold_idx, (train_idx, test_idx) in enumerate(logo.split(X_with_mkt, y_actual, match_ids_mkt)):
        lr = LogisticRegression(C=1.0, max_iter=1000)
        lr.fit(X_with_mkt[train_idx], y_actual[train_idx])
        gold_probs[test_idx] = lr.predict_proba(X_with_mkt[test_idx])[:, 1]
    
    brier_gold = brier(gold_probs, y_actual)
    print(f"  Stacked (LR on model + REAL market logits): Brier={brier_gold:.4f}")


# ── STEP 5: Segment analysis ──
print("\n" + "=" * 70)
print("  STEP 5: Segment analysis (where does synthetic market help?)")
print("=" * 70)

matched['synth_p'] = synth_p
matched['stacked_p'] = stacked_probs
matched['phase'] = matched.apply(
    lambda r: 'powerplay' if r['over_for_join'] <= 6 
    else 'death' if r['over_for_join'] >= 16 
    else 'middle', axis=1
)

print(f"\n  {'Segment':25s} {'N':>5s} {'Market':>8s} {'Model':>8s} {'Synth':>8s} {'Stacked':>8s}")
print(f"  {'-'*25} {'-'*5} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")

for name, mask in [
    ('Overall', np.ones(len(matched), dtype=bool)),
    ('Inn1', matched['raw_innings'] == 1),
    ('Inn2', matched['raw_innings'] == 2),
    ('Inn1 PP', (matched['raw_innings'] == 1) & (matched['phase'] == 'powerplay')),
    ('Inn1 Middle', (matched['raw_innings'] == 1) & (matched['phase'] == 'middle')),
    ('Inn1 Death', (matched['raw_innings'] == 1) & (matched['phase'] == 'death')),
    ('Inn2 PP', (matched['raw_innings'] == 2) & (matched['phase'] == 'powerplay')),
    ('Inn2 Middle', (matched['raw_innings'] == 2) & (matched['phase'] == 'middle')),
    ('Inn2 Death', (matched['raw_innings'] == 2) & (matched['phase'] == 'death')),
]:
    if mask.sum() < 5:
        continue
    sub = matched[mask]
    b_mkt = brier(sub['market_p_batting'], sub['actual_batting_wins'])
    b_mod = brier(sub['model_p_batting'], sub['actual_batting_wins'])
    b_syn = brier(sub['synth_p'], sub['actual_batting_wins'])
    b_stk = brier(sub['stacked_p'], sub['actual_batting_wins'])
    print(f"  {name:25s} {len(sub):5d} {b_mkt:8.4f} {b_mod:8.4f} {b_syn:8.4f} {b_stk:8.4f}")


# ── STEP 6: Can we generate synthetic market for ALL historical data? ──
print("\n" + "=" * 70)
print("  STEP 6: Feasibility of synthetic market for historical data")
print("=" * 70)

# The key question: if we train on 16 matches of (features → market_prob),
# can we generalize to ALL historical IPL data?
# Answer: PROBABLY NOT - 16 matches is too thin
# But let's check the model's behavior

# Check if the synthetic market just learned resource_win_prob
corr_synth_vs_model = np.corrcoef(synth_p, model_p)[0, 1]
corr_synth_vs_market = np.corrcoef(synth_p, y_mkt)[0, 1]
corr_model_vs_market = np.corrcoef(model_p, y_mkt)[0, 1]

print(f"  Correlations:")
print(f"    Synthetic vs Market:  {corr_synth_vs_market:.4f}")
print(f"    Model vs Market:      {corr_model_vs_market:.4f}")
print(f"    Synthetic vs Model:   {corr_synth_vs_model:.4f}")
print(f"\n  If synth ≈ model (r > 0.95), the approximator learned nothing new")
print(f"  If synth ≈ market (r > 0.90), the approximator captures market behavior")

# The RESIDUAL: what does market know that we don't?
residual = y_mkt - model_p  # market - model
print(f"\n  Market-Model Residual Stats:")
print(f"    Mean:   {residual.mean():+.4f}")
print(f"    Std:    {residual.std():.4f}")
print(f"    Range:  [{residual.min():+.4f}, {residual.max():+.4f}]")

# Can features predict the residual?
from xgboost import XGBRegressor as XGBReg
residual_probs = np.full(len(residual), np.nan)
for fold_idx, (train_idx, test_idx) in enumerate(logo.split(X_mkt, residual, match_ids_mkt)):
    xgb_res = XGBReg(
        n_estimators=100, max_depth=3, learning_rate=0.05,
        min_child_weight=10, reg_alpha=2.0, reg_lambda=5.0,
        random_state=42, verbosity=0
    )
    xgb_res.fit(X_mkt.iloc[train_idx], residual[train_idx])
    residual_probs[test_idx] = xgb_res.predict(X_mkt.iloc[test_idx])

residual_r2 = r2_score(residual, residual_probs)
print(f"\n  Residual predictability (features → market-model gap):")
print(f"    R² = {residual_r2:.4f}")
print(f"    {'YES - features explain market gap' if residual_r2 > 0.1 else 'NO - gap is due to unobservable info'}")

# Corrected predictions: model + predicted_residual
corrected_p = np.clip(model_p + residual_probs, 0.01, 0.99)
brier_corrected = brier(corrected_p, y_actual)
print(f"\n  Corrected model (model + predicted residual):")
print(f"    Brier: {brier_corrected:.4f}  (market={brier_market:.4f}, raw model={brier_model:.4f})")


# ── SUMMARY ──
print("\n" + "=" * 70)
print("  SUMMARY")
print("=" * 70)

print(f"""
  Can our features approximate market odds?
    Market approximation R²:  {overall_r2:.4f}  ({'Good' if overall_r2 > 0.8 else 'Moderate' if overall_r2 > 0.5 else 'Poor'})
    Synth-Market correlation:  {corr_synth_vs_market:.4f}
    Synth-Model correlation:   {corr_synth_vs_model:.4f}

  Does the synthetic market improve predictions?
    Market Brier:     {brier_market:.4f}  (gold standard)
    Model Brier:      {brier_model:.4f}  (+{(brier_model/brier_market-1)*100:.1f}%)
    Synthetic Brier:  {brier_synth:.4f}  (+{(brier_synth/brier_market-1)*100:.1f}%)
    Stacked Brier:    {brier_stacked:.4f}  (+{(brier_stacked/brier_market-1)*100:.1f}%)
    
  Is the market-model gap predictable from features?
    Residual R²: {residual_r2:.4f}  ({'Partially' if residual_r2 > 0.1 else 'No'} - {'some gap is from feature interactions' if residual_r2 > 0.1 else 'gap is from unobservable context'})
    
  Verdict:
""")

if residual_r2 > 0.1 and brier_synth < brier_model:
    print("    ✅ Synthetic market HELPS - the market captures feature interactions")
    print("       our win model misses. Worth generating for all historical data.")
elif brier_synth < brier_model and overall_r2 > 0.7:
    print("    ⚠️ Synthetic market is PROMISING but thin (16 matches).")
    print("       Need more recorded market data to build a robust approximator.")
else:
    print("    ❌ Synthetic market doesn't help significantly.")
    print("       The market-model gap is mostly from UNOBSERVABLE context")
    print("       (pitch, dew, momentum) that no historical feature can capture.")
    print("       Focus on Track B (live features) instead.")

print()

# Save results
results = {
    'n_matched': len(matched),
    'n_matches': len(np.unique(match_ids_mkt)),
    'market_approx_r2': float(overall_r2),
    'market_approx_mse': float(overall_mse),
    'synth_market_corr': float(corr_synth_vs_market),
    'synth_model_corr': float(corr_synth_vs_model),
    'brier_market': float(brier_market),
    'brier_model': float(brier_model),
    'brier_synthetic': float(brier_synth),
    'brier_stacked': float(brier_stacked),
    'brier_corrected': float(brier_corrected),
    'residual_r2': float(residual_r2),
}
with open('data/synthetic_market_analysis.json', 'w') as f:
    json.dump(results, f, indent=2)
print("  Results saved to data/synthetic_market_analysis.json")
