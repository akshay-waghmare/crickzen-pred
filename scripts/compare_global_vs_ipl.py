"""
Compare Global T20 model vs IPL v3 standalone — Full Pipeline Analysis

Compares 4 pipelines on 2026 IPL OOS data (12 matches, 432 obs) vs Betfair exchange:
  A) Global FULL = t20_male_v2 + global_iso + global_LogitBias + blend(6)
  B) IPL v3 +iso = ipl_v3 + ipl_iso only (no bias, no blend)
  C) IPL v3 FULL = ipl_v3 + ipl_iso + ipl_LogitBias + blend(6)
  D) IPL v3 FULL+T = ipl_v3 + ipl_iso + phase-T + ipl_LogitBias + blend(6)  [RECOMMENDED]

Usage:
    python scripts/compare_global_vs_ipl.py
"""
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


def make_apply_iso(cal_dict):
    """Create isotonic calibration function from calibrator dict."""
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
    """Apply logit-bias correction from league calibrator."""
    phase = 'powerplay' if over_0 < 6 else ('middle' if over_0 < 16 else 'death')
    key = 'inn%d_%s' % (inn, phase)
    scaler = bias_cals.get(key, bias_cals.get('innings_%d' % inn))
    if scaler is None:
        return p
    result = scaler.predict(np.array([[p]]))
    return float(np.asarray(result).flat[0])


def temp_scale(p, T):
    """Apply temperature scaling to probability. T<1 sharpens, T>1 softens."""
    p = np.clip(p, 1e-6, 1 - 1e-6)
    logit = np.log(p / (1 - p))
    return float(1 / (1 + np.exp(-logit / T)))


def apply_phase_temp(p, inn, over_0, temp_scalers):
    """Apply phase-specific temperature scaling."""
    phase = 'powerplay' if over_0 < 6 else ('middle' if over_0 < 16 else 'death')
    key = 'inn%d_%s' % (inn, phase)
    T = temp_scalers.get(key)
    if T is None or T == 1.0:
        return p
    return temp_scale(p, T)


def apply_transition(df, prob_col, transition_overs=6):
    """Apply innings transition smoothing using inn1 final prob as prior."""
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


print('Loading models and data...')

# Global T20 model + calibrators
global_model = joblib.load('models/t20_male_v2/champion_model.joblib')
_restore_simple_imputer_compatibility(global_model)
global_cal = joblib.load('models/t20_male_v2/isotonic_calibrator.pkl')
global_league = joblib.load('models/t20_male_v2/league_calibrators/ipl/league_calibrator.pkl')
global_bias = global_league.get('calibrators', {})

# IPL v3 standalone model + calibrators
ipl_model = joblib.load('models/ipl_v3/champion_model.joblib')
_restore_simple_imputer_compatibility(ipl_model)
ipl_cal = joblib.load('models/ipl_v3/isotonic_calibrator.pkl')
ipl_league = joblib.load('models/ipl_v3/league_calibrators/ipl/league_calibrator.pkl')
ipl_bias = ipl_league.get('calibrators', {})

# Load raw data for metadata
raw = pd.read_parquet('data/ipl_raw/matches')
raw = raw.drop_duplicates(subset=['match_id', 'innings', 'over', 'ball'], keep='first')
raw = raw.sort_values(['match_id', 'innings', 'over', 'ball']).reset_index(drop=True)

feat_v2 = pd.read_parquet('data/ipl_features_v2/training.parquet')
feat_v3 = pd.read_parquet('data/ipl_features_v3/training.parquet')

for feat in [feat_v2, feat_v3]:
    n = len(feat)
    for c in ['innings', 'over', 'ball', 'season', 'match_id', 'batting_team', 'winner']:
        feat[c] = raw[c].values[:n]

f26_v2 = feat_v2[feat_v2['season'] == '2026'].copy()
f26_v3 = feat_v3[feat_v3['season'] == '2026'].copy()
f26_v2['over_1idx'] = f26_v2['over'] + 1
f26_v3['over_1idx'] = f26_v3['over'] + 1

n2 = f26_v2['match_id'].nunique()
n3 = f26_v3['match_id'].nunique()
print(f'2026 v2 features: {len(f26_v2)} balls, {n2} matches')
print(f'2026 v3 features: {len(f26_v3)} balls, {n3} matches')

# ── Pipeline A: Global FULL (current production) ──
global_iso = make_apply_iso(global_cal)
feats_g = global_model.selected_features_
f26_v2['g_raw'] = global_model.predict_proba(f26_v2[feats_g])[:, 1]
f26_v2['g_iso'] = [global_iso(p, i, o) for p, i, o
                   in zip(f26_v2['g_raw'], f26_v2['innings'], f26_v2['over'])]
f26_v2['g_bias'] = [apply_bias(p, i, o, global_bias) for p, i, o
                    in zip(f26_v2['g_iso'], f26_v2['innings'], f26_v2['over'])]
f26_v2['g_blend6'] = apply_transition(f26_v2, 'g_bias', 6)
print('Pipeline A (Global FULL) scored')

# ── Pipeline B: IPL v3 + iso only ──
ipl_iso_fn = make_apply_iso(ipl_cal)
feats_i = ipl_model.selected_features_
f26_v3['i_raw'] = ipl_model.predict_proba(f26_v3[feats_i])[:, 1]
f26_v3['i_iso'] = [ipl_iso_fn(p, i, o) for p, i, o
                   in zip(f26_v3['i_raw'], f26_v3['innings'], f26_v3['over'])]
print('Pipeline B (IPL v3 +iso) scored')

# ── Pipeline C: IPL v3 FULL (iso + bias + blend) ──
f26_v3['i_bias'] = [apply_bias(p, i, o, ipl_bias) for p, i, o
                    in zip(f26_v3['i_iso'], f26_v3['innings'], f26_v3['over'])]
f26_v3['i_blend6'] = apply_transition(f26_v3, 'i_bias', 6)
print('Pipeline C (IPL v3 FULL) scored')

# ── Pipeline D: IPL v3 FULL+T (iso + temp + bias + blend) ──
ipl_temp_scalers = ipl_league.get('temperature_scalers', {})
f26_v3['i_temped'] = [apply_phase_temp(p, i, o, ipl_temp_scalers) for p, i, o
                      in zip(f26_v3['i_iso'], f26_v3['innings'], f26_v3['over'])]
f26_v3['i_temped_bias'] = [apply_bias(p, i, o, ipl_bias) for p, i, o
                           in zip(f26_v3['i_temped'], f26_v3['innings'], f26_v3['over'])]
f26_v3['i_temped_blend6'] = apply_transition(f26_v3, 'i_temped_bias', 6)
print('Pipeline D (IPL v3 FULL+T) scored')

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

# Convert to P(inn1) space
for col in ['g_raw', 'g_iso', 'g_bias', 'g_blend6']:
    mg[col + '_pi1'] = np.where(mg['innings'] == 1, mg[col], 1 - mg[col])
for col in ['i_raw', 'i_iso', 'i_bias', 'i_blend6', 'i_temped_bias', 'i_temped_blend6']:
    mi[col + '_pi1'] = np.where(mi['innings'] == 1, mi[col], 1 - mi[col])

# Merge IPL v3 predictions into global df
mg = mg.merge(mi[['match_id', 'innings', 'over_1idx',
                   'i_iso_pi1', 'i_blend6_pi1', 'i_temped_blend6_pi1']],
              on=['match_id', 'innings', 'over_1idx'], how='left')

y = mg['actual_inn1_wins'].values.astype(float)
mkt = mg['market_p_inn1'].values.astype(float)

def phase_of(over_1idx):
    if over_1idx <= 6:  return 'PP'
    if over_1idx <= 15: return 'Mid'
    return 'Death'
mg['phase'] = mg['over_1idx'].apply(phase_of)

n_matches = mg['match_id'].nunique()
print(f'Merged: {len(mg)} obs, {n_matches} matches')

# ── RESULTS ──
print()
print('=' * 100)
print(f'COMPREHENSIVE MODEL COMPARISON — IPL 2026 OOS ({n_matches} matches, vs Betfair exchange)')
print('  A) Global FULL  = t20_male_v2 + global_iso + global_bias + blend(6)')
print('  B) IPL v3 +iso  = ipl_v3 + ipl_iso (standalone, no bias/blend)')
print('  C) IPL v3 FULL  = ipl_v3 + ipl_iso + ipl_bias + blend(6)')
print('  D) IPL v3 FULL+T = ipl_v3 + ipl_iso + phase_T + ipl_bias + blend(6)  [RECOMMENDED]')
print('=' * 100)

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

pipelines = {
    'A) G FULL':    mg['g_blend6_pi1'].values,
    'B) IPL+iso':   mg['i_iso_pi1'].values,
    'C) IPL FULL':  mg['i_blend6_pi1'].values,
    'D) IPL FULL+T':mg['i_temped_blend6_pi1'].values,
}

for metric_name, metric_fn in [('BRIER SCORE', brier), ('LOG LOSS', logloss), ('ECE (10-bin)', ece)]:
    print()
    print(f'── {metric_name} ' + '─' * 80)
    header = '  %-12s %4s %8s' % ('Segment', 'N', 'Market')
    for name in pipelines:
        header += ' %16s' % name
    header += '  WINNER'
    print(header)
    print('  ' + '-' * (28 + 17 * len(pipelines) + 18))

    for seg_name, idx in segments:
        if len(idx) < 3: continue
        yi = y[idx]
        m_val = metric_fn(yi, mkt[idx])
        line = '  %-12s %4d %8.4f' % (seg_name, len(idx), m_val)
        best_val, best_name = 999, ''
        for name, preds in pipelines.items():
            pi = preds[idx]
            if np.any(np.isnan(pi)):
                line += ' %16s' % 'N/A'
                continue
            val = metric_fn(yi, pi)
            pct = (val / m_val - 1) * 100 if m_val > 0 else 0
            marker = '✅' if pct < -1 else '⬜' if abs(pct) <= 1 else '❌'
            line += '  %7.4f%+5.1f%%%s' % (val, pct, marker)
            if val < best_val:
                best_val = val
                best_name = name
        line += '  ← %s' % best_name
        print(line)

# ── IPL bias details ──
print()
print('── IPL v3 LogitBias Calibrator Details ──')
for k, v in sorted(ipl_bias.items()):
    print('  %s: bias=%+.4f' % (k, v.bias))
print('  (inn2_death, inn2_middle removed — overfitting on small samples)')

print()
print('── IPL v3 Phase Temperature Scalers ──')
for k, v in sorted(ipl_temp_scalers.items()):
    effect = 'sharpens' if v < 1 else ('softens' if v > 1 else 'no change')
    print('  %s: T=%.2f (%s)' % (k, v, effect))

print()
print('── Global LogitBias Calibrator Details ──')
for k, v in sorted(global_bias.items()):
    print('  %s: bias=%+.4f' % (k, v.bias))

print()
print('Key: ✅ = beats market (>1%), ⬜ = close to market (±1%), ❌ = worse than market (>1%)')
print()
