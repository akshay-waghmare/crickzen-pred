"""
V2 Baseline (25 features) + Phase Bias Correction — True OOS on 2026 IPL
Uses date+team matching (349 obs) from validate_oos_v3.py approach.
"""
import sys, os, warnings, json
warnings.filterwarnings('ignore')
sys.path.insert(0, 'src')

import pandas as pd
import numpy as np
from scipy.special import logit, expit
from sklearn.model_selection import LeaveOneGroupOut

def brier(p, y):
    return np.mean((p - y)**2)

def logloss(p, y, eps=1e-15):
    p = np.clip(p, eps, 1-eps)
    return -np.mean(y*np.log(p) + (1-y)*np.log(1-p))

def assign_phase(over):
    if over <= 6: return 'powerplay'
    elif over <= 15: return 'middle'
    else: return 'death'

TEAM_ALIASES = {
    'Royal Challengers Bangalore': 'Royal Challengers Bengaluru',
    'Delhi Daredevils': 'Delhi Capitals',
    'Kings XI Punjab': 'Punjab Kings',
    'Rising Pune Supergiant': 'Rising Pune Supergiants',
}

# ── Load data ──
print("Loading data...")
raw = pd.read_parquet('data/ipl_raw/matches')
raw = raw.drop_duplicates(subset=['match_id','innings','over','ball'], keep='first')
raw = raw.sort_values(['match_id','innings','over','ball']).reset_index(drop=True)

train_full = pd.read_parquet('data/ipl_features_v3/training.parquet')
assert len(raw) == len(train_full)

train_full['season'] = raw['season'].values
train_full['match_id'] = raw['match_id'].values
train_full['raw_innings'] = raw['innings'].values
train_full['raw_over'] = raw['over'].values
train_full['raw_date'] = pd.to_datetime(raw['date']).dt.strftime('%Y-%m-%d').values
train_full['raw_batting_team'] = raw['batting_team'].map(lambda x: TEAM_ALIASES.get(x, x)).values

mask_pre2026 = train_full['season'] != '2026'
meta_cols = ['is_winner','season','match_id','raw_innings','raw_over','raw_date','raw_batting_team']
feature_cols = [c for c in train_full.columns if c not in meta_cols]

# ── Train v2 baseline holdout ──
print("Training v2 holdout model (pre-2026)...")
from bbl_pipeline.training.trainer import XGBLogRegEnsemble

model_v2 = XGBLogRegEnsemble()
train_pre = train_full[mask_pre2026]
model_v2.fit(train_pre[feature_cols], train_pre['is_winner'])
print(f"  Trained with {len(model_v2.selected_features_)} features")

# ── Score 2026 ──
test_2026 = train_full[~mask_pre2026].copy()
test_2026['v2_raw'] = model_v2.predict_proba(test_2026[feature_cols])[:, 1]

# Per-over aggregation + matching
test_po = test_2026.groupby(['match_id','raw_innings','raw_over']).agg(
    v2_raw=('v2_raw','last'), is_winner=('is_winner','first'),
    date=('raw_date','first'), batting_team=('raw_batting_team','first'),
).reset_index()
test_po['match_key'] = (
    test_po['date'] + '_' + test_po['batting_team'] + '_' +
    test_po['raw_innings'].astype(str) + '_' +
    (test_po['raw_over'] + 1).astype(str)
)

obs = pd.read_parquet('data/ipl_model_vs_market.parquet')
obs['match_key'] = (
    obs['date'] + '_' + obs['batting_team'] + '_' +
    obs['innings'].astype(str) + '_' + obs['over'].astype(str)
)

merged = obs.merge(test_po[['match_key','v2_raw']], on='match_key', how='inner')

# Flip inn2
merged['bat_is_t1'] = merged['batting_team'] == merged['team1']
merged.loc[~merged['bat_is_t1'], 'v2_raw'] = 1.0 - merged.loc[~merged['bat_is_t1'], 'v2_raw']

actual = merged['actual_t1_wins'].values
market = merged['market_p_t1'].values
model_p = merged['v2_raw'].values
groups = merged['event_id'].values
merged['phase'] = merged['over'].apply(assign_phase)

n_obs = len(merged)
n_matches = merged['event_id'].nunique()

print("=" * 70)
print(f"  V2 BASELINE + PHASE BIAS CORRECTION (LOMO-CV)")
print(f"  {n_obs} obs, {n_matches} matches")
print("=" * 70)

b_mkt = brier(market, actual)
b_raw = brier(model_p, actual)
print(f"\n  Market:   {b_mkt:.4f}")
print(f"  v2 raw:   {b_raw:.4f}  (+{(b_raw/b_mkt-1)*100:.1f}%)")

# ── Phase bias correction with LOMO-CV ──
segments = {}
for inn in [1, 2]:
    for ph in ['powerplay', 'middle', 'death']:
        mask = (merged['innings'] == inn) & (merged['phase'] == ph)
        if mask.sum() > 5:
            segments[f'inn{inn}_{ph}'] = mask.values

cal_bias = np.copy(model_p)
logo = LeaveOneGroupOut()

print(f"\n  Phase bias correction (leave-one-match-out):")
for seg_name, mask in segments.items():
    seg_groups = groups[mask]
    seg_model = model_p[mask]
    seg_market = market[mask]
    seg_actual = actual[mask]
    seg_cal = np.full(mask.sum(), np.nan)

    unique_g = np.unique(seg_groups)
    if len(unique_g) < 3:
        print(f"    {seg_name:15s} SKIP (only {len(unique_g)} matches)")
        seg_cal = seg_model.copy()
    else:
        for tr, te in logo.split(seg_model.reshape(-1, 1), seg_actual, seg_groups):
            bias = np.mean(seg_market[tr] - seg_model[tr])
            seg_cal[te] = np.clip(seg_model[te] + bias, 0.01, 0.99)

    cal_bias[mask] = seg_cal
    avg_bias = np.mean(seg_market - seg_model)
    b_seg_raw = brier(seg_model, seg_actual)
    b_seg_cal = brier(seg_cal, seg_actual)
    b_seg_mkt = brier(market[mask], seg_actual)
    gap_pct = (b_seg_cal / b_seg_mkt - 1) * 100
    print(f"    {seg_name:15s} n={mask.sum():3d}  bias={avg_bias:+.4f}  "
          f"mkt={b_seg_mkt:.4f}  raw={b_seg_raw:.4f}  cal={b_seg_cal:.4f}  vs_mkt={gap_pct:+.1f}%")

b_bias = brier(cal_bias, actual)
gap_closed = (1 - (b_bias - b_mkt) / (b_raw - b_mkt)) * 100

print(f"\n  OVERALL:")
print(f"    Market:           {b_mkt:.4f}")
print(f"    v2 raw:           {b_raw:.4f}  (+{(b_raw/b_mkt-1)*100:.1f}%)")
print(f"    v2 + bias corr:   {b_bias:.4f}  (+{(b_bias/b_mkt-1)*100:.1f}%)  Gap closed: {gap_closed:.1f}%")
print(f"    LogLoss: mkt={logloss(market, actual):.4f}  "
      f"raw={logloss(model_p, actual):.4f}  cal={logloss(cal_bias, actual):.4f}")

# ── Best blend with market ──
print(f"\n  Blend: alpha*bias_corrected + (1-alpha)*market")
best_a, best_b = 0, 999
for a in np.arange(0, 1.01, 0.05):
    blend = a * cal_bias + (1 - a) * market
    b = brier(blend, actual)
    if b < best_b:
        best_a, best_b = a, b
print(f"    Best alpha={best_a:.2f}  Brier={best_b:.4f}  (pure market={b_mkt:.4f})")

# ── Inn2 middle detail ──
inn2_mid = ((merged['innings'] == 2) & (merged['phase'] == 'middle')).values
if inn2_mid.sum() > 0:
    print(f"\n  INN2 MIDDLE (our sweet spot, n={inn2_mid.sum()}):")
    print(f"    Market:     {brier(market[inn2_mid], actual[inn2_mid]):.4f}")
    print(f"    v2 raw:     {brier(model_p[inn2_mid], actual[inn2_mid]):.4f}")
    print(f"    v2 + bias:  {brier(cal_bias[inn2_mid], actual[inn2_mid]):.4f}")
    blend_mid = best_a * cal_bias[inn2_mid] + (1 - best_a) * market[inn2_mid]
    print(f"    Blend({best_a:.0%}/{1-best_a:.0%}): {brier(blend_mid, actual[inn2_mid]):.4f}")

# ── Inn2 per-over detail ──
print(f"\n  INN2 PER-OVER BREAKDOWN:")
print(f"    {'Over':>6s}  {'n':>4s}  {'Market':>8s}  {'Raw':>8s}  {'Bias':>8s}  {'vs_Mkt':>8s}")
print(f"    {'-'*50}")
inn2 = merged['innings'] == 2
for ov in sorted(merged.loc[inn2, 'over'].unique()):
    m = (inn2 & (merged['over'] == ov)).values
    if m.sum() < 3:
        continue
    b_m = brier(market[m], actual[m])
    b_r = brier(model_p[m], actual[m])
    b_c = brier(cal_bias[m], actual[m])
    vs = (b_c / b_m - 1) * 100
    winner = "MODEL" if b_c < b_m else ""
    print(f"    {ov:6d}  {m.sum():4d}  {b_m:8.4f}  {b_r:8.4f}  {b_c:8.4f}  {vs:+7.1f}%  {winner}")

print("\nDone.")
