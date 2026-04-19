"""
Config D: Add market-valued features + phase recalibration

The market-approximator found these features get significant weight:
  - score_adjusted_by_team (r=0.36, #5 overall)
  - resource_team_adjusted (r=0.42, #2 overall)  
  - run_rate_team_adj (r=0.17, #14 overall)

Strategy: Add these 3 to the model AND apply phase-specific bias correction.

Test pipeline:
  1. Train holdout model (pre-2026) with Config D features
  2. Score 2026 matches
  3. Apply phase bias correction (learned from market)
  4. Compare everything: raw, Config B, Config D, D+bias, market
"""
import sys, os, warnings, json
warnings.filterwarnings('ignore')
sys.path.insert(0, 'src')

import pandas as pd
import numpy as np
from pathlib import Path
from scipy.special import logit, expit
from scipy.optimize import minimize_scalar, minimize
from sklearn.model_selection import LeaveOneGroupOut

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


# ── STEP 1: Load data ──
print("=" * 70)
print("  STEP 1: Load data + define Config D features")
print("=" * 70)

raw = pd.read_parquet('data/ipl_raw/matches')
raw = raw.drop_duplicates(subset=['match_id', 'innings', 'over', 'ball'], keep='first')
raw = raw.sort_values(['match_id', 'innings', 'over', 'ball']).reset_index(drop=True)

train_full = pd.read_parquet('data/ipl_features_v3/training.parquet')
assert len(raw) == len(train_full), f"Row mismatch: {len(raw)} vs {len(train_full)}"

# Attach metadata
train_full['season'] = raw['season'].values
train_full['match_id'] = raw['match_id'].values
train_full['raw_innings'] = raw['innings'].values
train_full['raw_over'] = raw['over'].values
train_full['raw_date'] = pd.to_datetime(raw['date']).dt.strftime('%Y-%m-%d').values
train_full['raw_batting_team'] = raw['batting_team'].map(lambda x: TEAM_ALIASES.get(x, x)).values

meta_cols = ['is_winner', 'season', 'match_id', 'raw_innings', 'raw_over', 'raw_date', 'raw_batting_team']
all_feature_cols = [c for c in train_full.columns if c not in meta_cols]

# Config D: Original 25 + 3 market-valued features
CONFIG_D_FEATURES = [
    # Original 25
    'expected_final_score', 'resource_win_prob', 'score_vs_par',
    'dls_pressure_index', 'projected_vs_venue_avg', 'projected_score',
    'is_powerplay', 'score_per_wicket', 'run_rate_diff', 'required_run_rate',
    'chase_difficulty', 'wickets_times_balls', 'pressure_index',
    'team_strength_diff', 'rrr_times_wickets', 'overs_remaining',
    'batting_team_win_rate', 'bowling_team_win_rate', 'batting_team_situation_wr',
    'situation_advantage', 'boundary_pct_last_18', 'bowling_team_situation_wr',
    'runs_last_12', 'runs_last_18', 'wickets_last_12',
    # 3 NEW: market-valued features
    'score_adjusted_by_team',
    'resource_team_adjusted',
    'run_rate_team_adj',
]

# Config E: Swap 3 weakest for market-valued (keep at 25)
# Weakest by XGBoost gain in previous runs: boundary_pct_last_18, runs_last_12, wickets_last_12
CONFIG_E_FEATURES = [
    'expected_final_score', 'resource_win_prob', 'score_vs_par',
    'dls_pressure_index', 'projected_vs_venue_avg', 'projected_score',
    'is_powerplay', 'score_per_wicket', 'run_rate_diff', 'required_run_rate',
    'chase_difficulty', 'wickets_times_balls', 'pressure_index',
    'team_strength_diff', 'rrr_times_wickets', 'overs_remaining',
    'batting_team_win_rate', 'bowling_team_win_rate', 'batting_team_situation_wr',
    'situation_advantage', 'bowling_team_situation_wr', 'runs_last_18',
    # Swapped in
    'score_adjusted_by_team',
    'resource_team_adjusted',
    'run_rate_team_adj',
]

# Config F: All 55 features (let XGBoost decide)
CONFIG_F_FEATURES = all_feature_cols

# Verify all features exist
for name, feats in [('D', CONFIG_D_FEATURES), ('E', CONFIG_E_FEATURES)]:
    missing = [f for f in feats if f not in train_full.columns]
    if missing:
        print(f"  WARNING: Config {name} missing: {missing}")
    else:
        print(f"  Config {name}: {len(feats)} features - all present")

print(f"  Config F: {len(CONFIG_F_FEATURES)} features (all available)")

# Split
mask_pre2026 = train_full['season'] != '2026'
train_pre = train_full[mask_pre2026].copy()
train_2026 = train_full[~mask_pre2026].copy()

print(f"  Pre-2026: {len(train_pre):,} rows ({train_pre['match_id'].nunique()} matches)")
print(f"  2026:     {len(train_2026):,} rows ({train_2026['match_id'].nunique()} matches)")


# ── STEP 2: Train models ──
print("\n" + "=" * 70)
print("  STEP 2: Train holdout models (pre-2026)")
print("=" * 70)

from bbl_pipeline.training.trainer import XGBLogRegEnsemble

configs = {
    'v2_baseline': {
        'model': XGBLogRegEnsemble(),  # default 25 features
        'features': None,  # uses TOP_FEATURES[:25]
    },
    'B_partnership': {
        'model': XGBLogRegEnsemble(config='B'),
        'features': None,
    },
    'D_mkt_expand28': {
        'model': XGBLogRegEnsemble(n_features=28),
        'features': CONFIG_D_FEATURES,
    },
    'E_mkt_swap25': {
        'model': XGBLogRegEnsemble(n_features=25),
        'features': CONFIG_E_FEATURES,
    },
    'F_all_features': {
        'model': XGBLogRegEnsemble(n_features=55),
        'features': CONFIG_F_FEATURES,
    },
}

X_pre = train_pre[all_feature_cols]
y_pre = train_pre['is_winner']

for cname, cinfo in configs.items():
    model = cinfo['model']
    
    if cinfo['features'] is not None:
        # Override TOP_FEATURES for custom configs
        model.TOP_FEATURES = cinfo['features']
    
    model.fit(X_pre, y_pre)
    cinfo['trained_model'] = model
    
    n_sel = len(model.selected_features_)
    in_brier = brier(model.predict_proba(X_pre)[:, 1], y_pre)
    print(f"  {cname:20s}: {n_sel} features, in-sample Brier={in_brier:.4f}")
    
    # Show XGBoost feature importance (top 10)
    try:
        xgb_imp = model.xgb_model_.feature_importances_
        feat_imp = sorted(zip(model.selected_features_, xgb_imp), key=lambda x: -x[1])
        top5 = ', '.join([f"{f}({i:.3f})" for f, i in feat_imp[:5]])
        print(f"    Top 5: {top5}")
    except:
        pass


# ── STEP 3: Score 2026 + match with market ──
print("\n" + "=" * 70)
print("  STEP 3: Score 2026 + match with market data")
print("=" * 70)

# Get per-over aggregates for 2026
train_2026['over_for_join'] = train_2026['raw_over'] + 1
df_2026_po = train_2026.sort_values(['match_id', 'raw_innings', 'raw_over']).groupby(
    ['match_id', 'raw_innings', 'over_for_join']
).last().reset_index()

# Get team1 mapping
inn1_teams = raw[raw['season'] == '2026'].groupby('match_id').apply(
    lambda g: g[g['innings'] == 1]['batting_team'].iloc[0]
).reset_index()
inn1_teams.columns = ['match_id', 'team1']
inn1_teams['team1'] = inn1_teams['team1'].map(lambda x: TEAM_ALIASES.get(x, x))

df_2026_po = df_2026_po.merge(inn1_teams, on='match_id', how='left')
df_2026_po['is_team1_batting'] = df_2026_po['raw_batting_team'] == df_2026_po['team1']

# Score all configs
for cname, cinfo in configs.items():
    model = cinfo['trained_model']
    preds = model.predict_proba(df_2026_po[all_feature_cols])[:, 1]
    # Convert to P(team1)
    df_2026_po[f'{cname}_p_t1'] = np.where(
        df_2026_po['is_team1_batting'], preds, 1 - preds
    )
    df_2026_po[f'{cname}_p_bat'] = preds

# Match with market using correlation-based mapping
mkt = pd.read_parquet('data/ipl_model_vs_market_v2.parquet')

event_to_match = {}
for eid in mkt['event_id'].unique():
    mkt_sub = mkt[mkt['event_id'] == eid].sort_values(['innings', 'over'])
    best_corr = -1
    best_mid = None
    for mid in df_2026_po['match_id'].unique():
        feat_sub = df_2026_po[df_2026_po['match_id'] == mid].sort_values(['raw_innings', 'over_for_join'])
        merged = mkt_sub.merge(
            feat_sub[['raw_innings', 'over_for_join', 'v2_baseline_p_t1']],
            left_on=['innings', 'over'],
            right_on=['raw_innings', 'over_for_join'],
            how='inner'
        )
        if len(merged) < 5:
            continue
        corr = merged['ipl_v2_p_t1'].corr(merged['v2_baseline_p_t1'])
        if corr > best_corr:
            best_corr = corr
            best_mid = mid
    event_to_match[eid] = (best_mid, best_corr)

# Join
matched_rows = []
for eid, (mid, corr) in event_to_match.items():
    if mid is None or corr < 0.5:
        continue
    mkt_sub = mkt[mkt['event_id'] == eid]
    feat_sub = df_2026_po[df_2026_po['match_id'] == mid]
    merged = mkt_sub.merge(
        feat_sub, left_on=['innings', 'over'],
        right_on=['raw_innings', 'over_for_join'],
        how='inner', suffixes=('_mkt', '_feat')
    )
    matched_rows.append(merged)

matched = pd.concat(matched_rows, ignore_index=True)
print(f"  Matched: {len(matched)} observations, {matched['match_id'].nunique()} matches")

# Convert market to P(batting_team)
matched['market_p_bat'] = np.where(
    matched['is_team1_batting'], matched['market_p_t1'], 1 - matched['market_p_t1']
)
matched['actual_bat_wins'] = np.where(
    matched['is_team1_batting'], matched['actual_t1_wins'], 1 - matched['actual_t1_wins']
)

# Phase labels
matched['phase'] = matched.apply(
    lambda r: 'powerplay' if r['over_for_join'] <= 6
    else 'death' if r['over_for_join'] >= 16
    else 'middle', axis=1
)


# ── STEP 4: Raw comparison ──
print("\n" + "=" * 70)
print("  STEP 4: Raw model comparison (no recalibration)")
print("=" * 70)

print(f"\n  {'Config':20s} {'Brier':>8s} {'vs Mkt':>8s} {'LogLoss':>8s}")
print(f"  {'-'*20} {'-'*8} {'-'*8} {'-'*8}")

b_mkt = brier(matched['market_p_bat'], matched['actual_bat_wins'])
ll_mkt = logloss(matched['market_p_bat'], matched['actual_bat_wins'])
print(f"  {'Market':20s} {b_mkt:8.4f} {'---':>8s} {ll_mkt:8.4f}")

for cname in configs:
    col = f'{cname}_p_bat'
    b = brier(matched[col], matched['actual_bat_wins'])
    ll = logloss(matched[col], matched['actual_bat_wins'])
    vs = (b / b_mkt - 1) * 100
    print(f"  {cname:20s} {b:8.4f} {vs:+7.1f}% {ll:8.4f}")


# ── STEP 5: Apply phase bias correction to each config ──
print("\n" + "=" * 70)
print("  STEP 5: Phase bias correction (LOMO-CV) for each config")
print("=" * 70)

segments = {}
for inn in [1, 2]:
    for ph in ['powerplay', 'middle', 'death']:
        mask = (matched['raw_innings'] == inn) & (matched['phase'] == ph)
        if mask.sum() > 10:
            segments[f'inn{inn}_{ph}'] = mask

groups = matched['match_id'].values

for cname in configs:
    col_bat = f'{cname}_p_bat'
    col_cal = f'{cname}_bias_cal'
    matched[col_cal] = matched[col_bat].values.copy()
    
    for seg_name, mask in segments.items():
        logo = LeaveOneGroupOut()
        seg_groups = groups[mask]
        seg_model = matched.loc[mask, col_bat].values
        seg_market = matched.loc[mask, 'market_p_bat'].values
        seg_actual = matched.loc[mask, 'actual_bat_wins'].values
        seg_cal = np.full(mask.sum(), np.nan)
        
        for tr, te in logo.split(seg_model.reshape(-1, 1), seg_actual, seg_groups):
            bias = np.mean(seg_market[tr] - seg_model[tr])
            seg_cal[te] = np.clip(seg_model[te] + bias, 0.01, 0.99)
        
        matched.loc[mask, col_cal] = seg_cal

print(f"\n  {'Config':20s} {'Raw':>8s} {'+Bias':>8s} {'Market':>8s} {'Gap Closed':>12s}")
print(f"  {'-'*20} {'-'*8} {'-'*8} {'-'*8} {'-'*12}")

for cname in configs:
    b_raw = brier(matched[f'{cname}_p_bat'], matched['actual_bat_wins'])
    b_cal = brier(matched[f'{cname}_bias_cal'], matched['actual_bat_wins'])
    gap_closed = (1 - (b_cal - b_mkt) / (b_raw - b_mkt)) * 100 if b_raw > b_mkt else 0
    print(f"  {cname:20s} {b_raw:8.4f} {b_cal:8.4f} {b_mkt:8.4f} {gap_closed:>11.1f}%")


# ── STEP 6: Segment breakdown for best config ──
print("\n" + "=" * 70)
print("  STEP 6: Segment breakdown (best config + bias correction)")
print("=" * 70)

# Find best after bias correction
best_cname = min(configs.keys(), key=lambda c: brier(matched[f'{c}_bias_cal'], matched['actual_bat_wins']))
print(f"  Best config: {best_cname}")

print(f"\n  {'Segment':20s} {'N':>5s} {'Market':>8s} {'Raw':>8s} {'Bias-Cal':>8s} {'vs Mkt':>8s}")
print(f"  {'-'*20} {'-'*5} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")

for seg_name, mask in segments.items():
    sub = matched[mask]
    b_m = brier(sub['market_p_bat'], sub['actual_bat_wins'])
    b_r = brier(sub[f'{best_cname}_p_bat'], sub['actual_bat_wins'])
    b_c = brier(sub[f'{best_cname}_bias_cal'], sub['actual_bat_wins'])
    vs = (b_c / b_m - 1) * 100
    print(f"  {seg_name:20s} {mask.sum():5d} {b_m:8.4f} {b_r:8.4f} {b_c:8.4f} {vs:+7.1f}%")

# Also show overall inn1 vs inn2
for inn_name, inn_val in [('Inn1 total', 1), ('Inn2 total', 2)]:
    mask = matched['raw_innings'] == inn_val
    if mask.sum() > 0:
        sub = matched[mask]
        b_m = brier(sub['market_p_bat'], sub['actual_bat_wins'])
        b_r = brier(sub[f'{best_cname}_p_bat'], sub['actual_bat_wins'])
        b_c = brier(sub[f'{best_cname}_bias_cal'], sub['actual_bat_wins'])
        vs = (b_c / b_m - 1) * 100
        print(f"  {inn_name:20s} {mask.sum():5d} {b_m:8.4f} {b_r:8.4f} {b_c:8.4f} {vs:+7.1f}%")


# ── STEP 7: Feature importance comparison ──
print("\n" + "=" * 70)
print("  STEP 7: Feature importance (XGBoost gain) comparison")
print("=" * 70)

for cname in ['v2_baseline', best_cname]:
    model = configs[cname]['trained_model']
    try:
        imp = model.xgb_model_.feature_importances_
        feat_imp = sorted(zip(model.selected_features_, imp), key=lambda x: -x[1])
        print(f"\n  {cname} (top 15):")
        for i, (f, v) in enumerate(feat_imp[:15]):
            marker = ' NEW' if f in ['score_adjusted_by_team', 'resource_team_adjusted', 'run_rate_team_adj'] else ''
            print(f"    {i+1:2d}. {f:35s} {v:.4f}{marker}")
    except Exception as e:
        print(f"  {cname}: Error getting importance: {e}")


# ── SUMMARY ──
print("\n" + "=" * 70)
print("  SUMMARY")
print("=" * 70)

print(f"\n  Observations: {len(matched)} | Matches: {matched['match_id'].nunique()}")
print(f"\n  {'':30s} {'Brier':>8s} {'vs Mkt':>8s} {'Gap Closed':>12s}")
print(f"  {'-'*30} {'-'*8} {'-'*8} {'-'*12}")
print(f"  {'Market':30s} {b_mkt:8.4f}     ---          ---")

for cname in configs:
    b_raw = brier(matched[f'{cname}_p_bat'], matched['actual_bat_wins'])
    b_cal = brier(matched[f'{cname}_bias_cal'], matched['actual_bat_wins'])
    gc_raw = 0
    gc_cal = (1 - (b_cal - b_mkt) / (brier(matched['v2_baseline_p_bat'], matched['actual_bat_wins']) - b_mkt)) * 100
    vs_raw = (b_raw / b_mkt - 1) * 100
    vs_cal = (b_cal / b_mkt - 1) * 100
    print(f"  {cname + ' (raw)':30s} {b_raw:8.4f} {vs_raw:+7.1f}%")
    print(f"  {cname + ' + bias':30s} {b_cal:8.4f} {vs_cal:+7.1f}% {gc_cal:>11.1f}%")

# Save results
results = {
    'n_matched': len(matched),
    'n_matches': int(matched['match_id'].nunique()),
    'market_brier': float(b_mkt),
}
for cname in configs:
    results[f'{cname}_raw_brier'] = float(brier(matched[f'{cname}_p_bat'], matched['actual_bat_wins']))
    results[f'{cname}_biascal_brier'] = float(brier(matched[f'{cname}_bias_cal'], matched['actual_bat_wins']))

with open('data/config_d_analysis.json', 'w') as f:
    json.dump(results, f, indent=2)

print(f"\n  Results saved to data/config_d_analysis.json")
print("\nDone.")
