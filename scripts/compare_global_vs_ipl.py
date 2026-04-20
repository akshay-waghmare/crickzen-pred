import os, sys, warnings
import pandas as pd
import numpy as np
import joblib

warnings.filterwarnings('ignore')
sys.path.insert(0, 'src')
from bbl_pipeline.inference.predictor import _restore_simple_imputer_compatibility
from bbl_pipeline.training.league_calibrator import LogitBiasScaler

def brier(y, p):   return np.mean((y - p) ** 2)
def logloss(y, p):
    p = np.clip(p, 1e-7, 1-1e-7)
    return -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))
def ece(y, p, bins=10):
    edges = np.linspace(0, 1, bins + 1)
    total = 0
    for i in range(bins):
        mask = (p >= edges[i]) & (p < edges[i + 1])
        if mask.sum() == 0: continue
        total += mask.sum() * abs(p[mask].mean() - y[mask].mean())
    return total / len(y)

print('Loading models and data...')

# Global T20 model
global_model = joblib.load('models/t20_male_v2/champion_model.joblib')
_restore_simple_imputer_compatibility(global_model)
global_cal = joblib.load('models/t20_male_v2/isotonic_calibrator.pkl')
league_cal = joblib.load('models/t20_male_v2/league_calibrators/ipl/league_calibrator.pkl')
bias_calibrators = league_cal.get('calibrators', {})

# IPL v3 standalone model
ipl_model = joblib.load('models/ipl_v3/champion_model.joblib')
_restore_simple_imputer_compatibility(ipl_model)
ipl_cal = joblib.load('models/ipl_v3/isotonic_calibrator.pkl')

# Load raw data
raw = pd.read_parquet('data/ipl_raw/matches')
raw = raw.drop_duplicates(subset=['match_id', 'innings', 'over', 'ball'], keep='first')
raw = raw.sort_values(['match_id', 'innings', 'over', 'ball']).reset_index(drop=True)

feat_v2 = pd.read_parquet('data/ipl_features_v2/training.parquet')
feat_v3 = pd.read_parquet('data/ipl_features_v3/training.parquet')

# Align with raw
for feat in [feat_v2, feat_v3]:
    n = len(feat)
    feat['innings'] = raw['innings'].values[:n]
    feat['over'] = raw['over'].values[:n]
    feat['ball'] = raw['ball'].values[:n]
    feat['season'] = raw['season'].values[:n]
    feat['match_id'] = raw['match_id'].values[:n]
    feat['batting_team'] = raw['batting_team'].values[:n]
    feat['date'] = pd.to_datetime(raw['date'].values[:n])
    feat['winner'] = raw['winner'].values[:n]

f26_v2 = feat_v2[feat_v2['season'] == '2026'].copy()
f26_v3 = feat_v3[feat_v3['season'] == '2026'].copy()
f26_v2['over_1idx'] = f26_v2['over'] + 1
f26_v3['over_1idx'] = f26_v3['over'] + 1

n2 = f26_v2['match_id'].nunique()
n3 = f26_v3['match_id'].nunique()
print(f'2026 v2 features: {len(f26_v2)} balls, {n2} matches')
print(f'2026 v3 features: {len(f26_v3)} balls, {n3} matches')

# Isotonic calibration helper
def make_apply_iso(cal_dict):
    po = cal_dict.get('per_over_calibrators', {})
    ph = cal_dict.get('phase_calibrators', {})
    inn_cal = {
        'innings_1': cal_dict.get('calibrator_innings1'),
        'innings_2': cal_dict.get('calibrator_innings2'),
    }
    def apply_iso(p, inn, over_0):
        key = 'inn%d_over%d' % (inn, over_0 + 1)
        if key in po:
            try: return float(po[key].predict([p])[0])
            except: pass
        phase = 'powerplay' if over_0 < 6 else ('middle' if over_0 < 16 else 'death')
        pkey = 'inn%d_%s' % (inn, phase)
        if pkey in ph:
            try: return float(ph[pkey].predict([p])[0])
            except: pass
        ikey = 'innings_%d' % inn
        if ikey in inn_cal and inn_cal[ikey] is not None:
            try: return float(inn_cal[ikey].predict([p])[0])
            except: pass
        return p
    return apply_iso

def apply_bias(p, inn, over_0, bias_cals):
    phase = 'powerplay' if over_0 < 6 else ('middle' if over_0 < 16 else 'death')
    key = 'inn%d_%s' % (inn, phase)
    scaler = bias_cals.get(key, bias_cals.get('innings_%d' % inn))
    if scaler is None:
        return p
    result = scaler.predict(np.array([[p]]))
    return float(np.asarray(result).flat[0])

def apply_transition(df, prob_col, transition_overs=6):
    blended = df[prob_col].copy()
    for mid in df['match_id'].unique():
        match = df[df['match_id'] == mid]
        inn1 = match[match['innings'] == 1]
        inn2 = match[match['innings'] == 2]
        if len(inn1) == 0 or len(inn2) == 0:
            continue
        inn1_final_p_bat = inn1.iloc[-1][prob_col]
        inn1_batting_team = inn1.iloc[-1]['batting_team']
        for idx, row in inn2.iterrows():
            overs_bowled = row['over'] + row['ball'] / 6.0
            if overs_bowled >= transition_overs:
                continue
            if row['batting_team'] == inn1_batting_team:
                inn1_prior = inn1_final_p_bat
            else:
                inn1_prior = 1.0 - inn1_final_p_bat
            alpha = max(0.0, 1.0 - overs_bowled / transition_overs)
            blended.loc[idx] = alpha * inn1_prior + (1.0 - alpha) * row[prob_col]
    return blended

# Score Global model (v2 features)
global_iso = make_apply_iso(global_cal)
feats_g = global_model.selected_features_
f26_v2['g_raw'] = global_model.predict_proba(f26_v2[feats_g])[:, 1]
f26_v2['g_iso'] = [global_iso(p, i, o) for p, i, o in zip(f26_v2['g_raw'], f26_v2['innings'], f26_v2['over'])]
f26_v2['g_bias'] = [apply_bias(p, i, o, bias_calibrators) for p, i, o in zip(f26_v2['g_iso'], f26_v2['innings'], f26_v2['over'])]
f26_v2['g_blend6'] = apply_transition(f26_v2, 'g_bias', 6)
print('Global model scored')

# Score IPL v3 model (v3 features)
ipl_iso_fn = make_apply_iso(ipl_cal)
feats_i = ipl_model.selected_features_
f26_v3['i_raw'] = ipl_model.predict_proba(f26_v3[feats_i])[:, 1]
f26_v3['i_iso'] = [ipl_iso_fn(p, i, o) for p, i, o in zip(f26_v3['i_raw'], f26_v3['innings'], f26_v3['over'])]
print('IPL v3 model scored')

# Merge with market
market = pd.read_parquet('data/ipl_model_vs_market_v3.parquet')

f26_v2_last = f26_v2.groupby(['match_id', 'innings', 'over']).tail(1).copy()
mg = f26_v2_last.merge(market, left_on=['match_id', 'innings', 'over_1idx'],
                        right_on=['match_id', 'innings', 'over'],
                        how='inner', suffixes=('', '_mkt'))

f26_v3_last = f26_v3.groupby(['match_id', 'innings', 'over']).tail(1).copy()
mi = f26_v3_last.merge(market, left_on=['match_id', 'innings', 'over_1idx'],
                        right_on=['match_id', 'innings', 'over'],
                        how='inner', suffixes=('', '_mkt'))

nm_g = mg['match_id'].nunique()
nm_i = mi['match_id'].nunique()
print(f'Global merged: {len(mg)} obs, {nm_g} matches')
print(f'IPL v3 merged: {len(mi)} obs, {nm_i} matches')

# Convert to P(inn1) space
for col in ['g_raw', 'g_iso', 'g_bias', 'g_blend6']:
    mg[col + '_pi1'] = np.where(mg['innings'] == 1, mg[col], 1 - mg[col])
for col in ['i_raw', 'i_iso']:
    mi[col + '_pi1'] = np.where(mi['innings'] == 1, mi[col], 1 - mi[col])

# Merge IPL v3 predictions into global df
mg = mg.merge(mi[['match_id', 'innings', 'over_1idx', 'i_raw_pi1', 'i_iso_pi1']],
              on=['match_id', 'innings', 'over_1idx'], how='left')

y = mg['actual_inn1_wins'].values.astype(float)
mkt = mg['market_p_inn1'].values.astype(float)

def phase_of(over_1idx):
    if over_1idx <= 6:  return 'PP'
    if over_1idx <= 15: return 'Mid'
    return 'Death'
mg['phase'] = mg['over_1idx'].apply(phase_of)

# ── RESULTS ──
print()
print('=' * 115)
print('COMPREHENSIVE MODEL COMPARISON — IPL 2026 OOS (12 matches, vs Betfair exchange)')
print('  Global FULL = t20_male_v2 + per-over isotonic + LogitBias + transition blend(6)')
print('  IPL v3      = ipl_v3 standalone + per-over isotonic (IPL-only training data)')
print('=' * 115)

segments = [
    ('OVERALL',   mg.index),
    ('Inn1',      mg[mg['innings'] == 1].index),
    ('Inn2',      mg[mg['innings'] == 2].index),
    ('Inn1 PP',   mg[(mg['innings'] == 1) & (mg['phase'] == 'PP')].index),
    ('Inn1 Mid',  mg[(mg['innings'] == 1) & (mg['phase'] == 'Mid')].index),
    ('Inn1 Death',mg[(mg['innings'] == 1) & (mg['phase'] == 'Death')].index),
    ('Inn2 PP',   mg[(mg['innings'] == 2) & (mg['phase'] == 'PP')].index),
    ('Inn2 Mid',  mg[(mg['innings'] == 2) & (mg['phase'] == 'Mid')].index),
    ('Inn2 Death',mg[(mg['innings'] == 2) & (mg['phase'] == 'Death')].index),
]

models_dict = {
    'Market':       mkt,
    'G raw':        mg['g_raw_pi1'].values,
    'G +iso':       mg['g_iso_pi1'].values,
    'G +bias':      mg['g_bias_pi1'].values,
    'G FULL':       mg['g_blend6_pi1'].values,
    'IPL raw':      mg['i_raw_pi1'].values,
    'IPL +iso':     mg['i_iso_pi1'].values,
}
model_names = list(models_dict.keys())

for metric_name, metric_fn in [('BRIER SCORE', brier), ('LOG LOSS', logloss), ('ECE (10-bin)', ece)]:
    print()
    print(f'── {metric_name} ' + '─' * 95)
    header = '  %-12s %4s' % ('Segment', 'N')
    for name in model_names:
        header += ' %14s' % name
    print(header)
    print('  ' + '-' * (18 + 15 * len(model_names)))
    
    for seg_name, idx in segments:
        if len(idx) < 3: continue
        yi = y[idx]
        line = '  %-12s %4d' % (seg_name, len(idx))
        mkt_val = metric_fn(yi, mkt[idx])
        for name in model_names:
            pi = models_dict[name][idx]
            if np.any(np.isnan(pi)):
                line += ' %14s' % 'N/A'
                continue
            val = metric_fn(yi, pi)
            if name == 'Market':
                line += ' %14.4f' % val
            else:
                pct = (val / mkt_val - 1) * 100 if mkt_val > 0 else 0
                marker = ' ✅' if pct < -1 else ' ⬜' if abs(pct) <= 1 else ' ❌'
                line += ' %s' % ('%7.4f%+5.1f%%%s' % (val, pct, marker))
        print(line)

# Summary: head-to-head Global FULL vs IPL v3+iso
print()
print('=' * 90)
print('HEAD-TO-HEAD: Global FULL vs IPL v3+iso (Brier Score)')
print('=' * 90)
header = '  %-12s %4s %10s %12s %8s %12s %8s %10s' % (
    'Segment', 'N', 'Market', 'Global FULL', 'vs Mkt', 'IPL v3+iso', 'vs Mkt', 'Winner')
print(header)
print('  ' + '-' * 80)
for seg_name, idx in segments:
    if len(idx) < 3: continue
    yi = y[idx]
    m = brier(yi, mkt[idx])
    g = brier(yi, mg.loc[idx, 'g_blend6_pi1'].values)
    i_pi = mg.loc[idx, 'i_iso_pi1'].values
    if np.any(np.isnan(i_pi)):
        continue
    i_val = brier(yi, i_pi)
    g_pct = (g/m - 1)*100
    i_pct = (i_val/m - 1)*100
    winner = 'Global' if g < i_val else 'IPL v3' if i_val < g else 'Tie'
    print('  %-12s %4d %10.4f %12.4f %+7.1f%% %12.4f %+7.1f%% %10s' % (
        seg_name, len(idx), m, g, g_pct, i_val, i_pct, winner))

print()
print('Key: ✅ = beats market (>1%), ⬜ = close to market (±1%), ❌ = worse than market (>1%)')
print()
