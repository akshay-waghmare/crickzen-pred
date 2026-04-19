"""
Enhanced Phase Bias Correction — Multiple Granularities

Tests increasingly granular bias correction approaches:
1. 6-segment (inn × phase) — current baseline
2. 12-segment (inn × phase, split middle into early/late)
3. Per-over (inn × over) — max granularity
4. Hierarchical: per-over with phase fallback for sparse overs
5. Scaled correction: multiply instead of add (handles asymmetry)
6. Logit-space bias: add bias in log-odds space (respects [0,1] bounds)
"""
import sys, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, 'src')

import pandas as pd
import numpy as np
from scipy.special import logit, expit
from sklearn.model_selection import LeaveOneGroupOut

def brier(p, y):
    return np.mean((p - y) ** 2)

def assign_phase(over):
    if over <= 6: return 'powerplay'
    elif over <= 15: return 'middle'
    else: return 'death'

def assign_phase_fine(over):
    if over <= 6: return 'powerplay'
    elif over <= 10: return 'early_middle'
    elif over <= 15: return 'late_middle'
    else: return 'death'

TEAM_ALIASES = {
    'Royal Challengers Bangalore': 'Royal Challengers Bengaluru',
    'Delhi Daredevils': 'Delhi Capitals',
    'Kings XI Punjab': 'Punjab Kings',
    'Rising Pune Supergiant': 'Rising Pune Supergiants',
}

# ── Load & prepare data (same as v2_bias_correction_oos.py) ──
print("Loading data...")
raw = pd.read_parquet('data/ipl_raw/matches')
raw = raw.drop_duplicates(subset=['match_id','innings','over','ball'], keep='first')
raw = raw.sort_values(['match_id','innings','over','ball']).reset_index(drop=True)

train_full = pd.read_parquet('data/ipl_features_v3/training.parquet')
train_full['season'] = raw['season'].values
train_full['match_id'] = raw['match_id'].values
train_full['raw_innings'] = raw['innings'].values
train_full['raw_over'] = raw['over'].values
train_full['raw_date'] = pd.to_datetime(raw['date']).dt.strftime('%Y-%m-%d').values
train_full['raw_batting_team'] = raw['batting_team'].map(lambda x: TEAM_ALIASES.get(x, x)).values

mask_pre2026 = train_full['season'] != '2026'
meta_cols = ['is_winner','season','match_id','raw_innings','raw_over','raw_date','raw_batting_team']
feature_cols = [c for c in train_full.columns if c not in meta_cols]

from bbl_pipeline.training.trainer import XGBLogRegEnsemble
print("Training v2 holdout model...")
model_v2 = XGBLogRegEnsemble()
model_v2.fit(train_full[mask_pre2026][feature_cols], train_full[mask_pre2026]['is_winner'])

test_2026 = train_full[~mask_pre2026].copy()
test_2026['v2_raw'] = model_v2.predict_proba(test_2026[feature_cols])[:, 1]

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
obs['match_key'] = obs['date'] + '_' + obs['batting_team'] + '_' + obs['innings'].astype(str) + '_' + obs['over'].astype(str)
merged = obs.merge(test_po[['match_key','v2_raw']], on='match_key', how='inner')
merged['bat_is_t1'] = merged['batting_team'] == merged['team1']
merged.loc[~merged['bat_is_t1'], 'v2_raw'] = 1.0 - merged.loc[~merged['bat_is_t1'], 'v2_raw']

actual = merged['actual_t1_wins'].values
market = merged['market_p_t1'].values
model_p = merged['v2_raw'].values
groups = merged['event_id'].values
merged['phase'] = merged['over'].apply(assign_phase)
merged['phase_fine'] = merged['over'].apply(assign_phase_fine)

n_obs = len(merged)
n_matches = merged['event_id'].nunique()
b_mkt = brier(market, actual)
b_raw = brier(model_p, actual)

print(f"\n{'='*70}")
print(f"  ENHANCED BIAS CORRECTION COMPARISON")
print(f"  {n_obs} obs, {n_matches} matches")
print(f"  Market: {b_mkt:.4f}  |  v2 raw: {b_raw:.4f} (+{(b_raw/b_mkt-1)*100:.1f}%)")
print(f"{'='*70}")


def lomo_bias_correct(model_p, market, actual, groups, seg_labels, min_obs=5):
    """Apply additive bias correction with LOMO-CV per segment."""
    cal = np.copy(model_p)
    logo = LeaveOneGroupOut()
    for seg in np.unique(seg_labels):
        mask = seg_labels == seg
        if mask.sum() < min_obs:
            continue
        seg_g = groups[mask]
        seg_m = model_p[mask]
        seg_mkt = market[mask]
        seg_a = actual[mask]
        seg_cal = np.full(mask.sum(), np.nan)
        unique_g = np.unique(seg_g)
        if len(unique_g) < 3:
            seg_cal = seg_m.copy()
        else:
            for tr, te in logo.split(seg_m.reshape(-1,1), seg_a, seg_g):
                bias = np.mean(seg_mkt[tr] - seg_m[tr])
                seg_cal[te] = np.clip(seg_m[te] + bias, 0.01, 0.99)
        cal[mask] = seg_cal
    return cal


def lomo_logit_bias(model_p, market, actual, groups, seg_labels, min_obs=5):
    """Apply additive bias correction in logit space with LOMO-CV."""
    cal = np.copy(model_p)
    logo = LeaveOneGroupOut()
    for seg in np.unique(seg_labels):
        mask = seg_labels == seg
        if mask.sum() < min_obs:
            continue
        seg_g = groups[mask]
        seg_m_logit = logit(np.clip(model_p[mask], 0.01, 0.99))
        seg_mkt_logit = logit(np.clip(market[mask], 0.01, 0.99))
        seg_a = actual[mask]
        seg_cal = np.full(mask.sum(), np.nan)
        unique_g = np.unique(seg_g)
        if len(unique_g) < 3:
            seg_cal = model_p[mask].copy()
        else:
            for tr, te in logo.split(seg_m_logit.reshape(-1,1), seg_a, seg_g):
                bias = np.mean(seg_mkt_logit[tr] - seg_m_logit[tr])
                seg_cal[te] = expit(seg_m_logit[te] + bias)
        cal[mask] = np.clip(seg_cal, 0.01, 0.99)
    return cal


def lomo_scale_correct(model_p, market, actual, groups, seg_labels, min_obs=5):
    """Multiplicative scaling: p_cal = p_model * (mean_market / mean_model) per segment."""
    cal = np.copy(model_p)
    logo = LeaveOneGroupOut()
    for seg in np.unique(seg_labels):
        mask = seg_labels == seg
        if mask.sum() < min_obs:
            continue
        seg_g = groups[mask]
        seg_m = model_p[mask]
        seg_mkt = market[mask]
        seg_a = actual[mask]
        seg_cal = np.full(mask.sum(), np.nan)
        unique_g = np.unique(seg_g)
        if len(unique_g) < 3:
            seg_cal = seg_m.copy()
        else:
            for tr, te in logo.split(seg_m.reshape(-1,1), seg_a, seg_g):
                mean_mkt = np.mean(seg_mkt[tr])
                mean_m = np.mean(seg_m[tr])
                if mean_m > 0.01:
                    scale = mean_mkt / mean_m
                    seg_cal[te] = np.clip(seg_m[te] * scale, 0.01, 0.99)
                else:
                    seg_cal[te] = seg_m[te]
        cal[mask] = seg_cal
    return cal


def hierarchical_bias(model_p, market, actual, groups, over_labels, phase_labels, min_over_obs=15):
    """Per-over correction where enough data, phase fallback otherwise."""
    # First compute phase-level biases
    phase_cal = lomo_bias_correct(model_p, market, actual, groups, phase_labels)

    # Then try per-over, falling back to phase where sparse
    cal = np.copy(model_p)
    logo = LeaveOneGroupOut()
    for ov in np.unique(over_labels):
        mask = over_labels == ov
        if mask.sum() < min_over_obs:
            cal[mask] = phase_cal[mask]
            continue
        seg_g = groups[mask]
        seg_m = model_p[mask]
        seg_mkt = market[mask]
        seg_a = actual[mask]
        seg_cal = np.full(mask.sum(), np.nan)
        unique_g = np.unique(seg_g)
        if len(unique_g) < 3:
            cal[mask] = phase_cal[mask]
            continue
        for tr, te in logo.split(seg_m.reshape(-1,1), seg_a, seg_g):
            bias = np.mean(seg_mkt[tr] - seg_m[tr])
            seg_cal[te] = np.clip(seg_m[te] + bias, 0.01, 0.99)
        cal[mask] = seg_cal
    return cal


# ── Build segment labels ──
seg_phase = np.array([f"inn{i}_{p}" for i, p in zip(merged['innings'], merged['phase'])])
seg_fine = np.array([f"inn{i}_{p}" for i, p in zip(merged['innings'], merged['phase_fine'])])
seg_over = np.array([f"inn{i}_ov{o}" for i, o in zip(merged['innings'], merged['over'])])
phase_for_hier = seg_phase  # fallback
over_for_hier = seg_over

# ── Run all methods ──
results = {}

# 1. Phase (6 segments)
cal_phase = lomo_bias_correct(model_p, market, actual, groups, seg_phase)
results['1_phase_6seg'] = brier(cal_phase, actual)

# 2. Fine phase (8 segments)
cal_fine = lomo_bias_correct(model_p, market, actual, groups, seg_fine)
results['2_fine_phase_8seg'] = brier(cal_fine, actual)

# 3. Per-over (up to 40 segments)
cal_over = lomo_bias_correct(model_p, market, actual, groups, seg_over)
results['3_per_over_40seg'] = brier(cal_over, actual)

# 4. Hierarchical (per-over + phase fallback)
cal_hier = hierarchical_bias(model_p, market, actual, groups, seg_over, seg_phase, min_over_obs=12)
results['4_hierarchical'] = brier(cal_hier, actual)

# 5. Logit-space bias (6 segments)
cal_logit = lomo_logit_bias(model_p, market, actual, groups, seg_phase)
results['5_logit_phase'] = brier(cal_logit, actual)

# 6. Logit-space per-over
cal_logit_ov = lomo_logit_bias(model_p, market, actual, groups, seg_over)
results['6_logit_per_over'] = brier(cal_logit_ov, actual)

# 7. Scale correction (6 segments)
cal_scale = lomo_scale_correct(model_p, market, actual, groups, seg_phase)
results['7_scale_phase'] = brier(cal_scale, actual)

# 8. Scale per-over
cal_scale_ov = lomo_scale_correct(model_p, market, actual, groups, seg_over)
results['8_scale_per_over'] = brier(cal_scale_ov, actual)

# 9. Logit-space fine phase (8 segments)
cal_logit_fine = lomo_logit_bias(model_p, market, actual, groups, seg_fine)
results['9_logit_fine_8seg'] = brier(cal_logit_fine, actual)

print(f"\n  {'Method':<30s} {'Brier':>8s} {'vs Mkt':>8s} {'Gap Closed':>12s}")
print(f"  {'-'*62}")
print(f"  {'Market':<30s} {b_mkt:8.4f} {'':>8s} {'':>12s}")
print(f"  {'v2 raw':<30s} {b_raw:8.4f} {(b_raw/b_mkt-1)*100:+7.1f}% {'':>12s}")
for name, b in sorted(results.items(), key=lambda x: x[1]):
    gap = (1 - (b - b_mkt) / (b_raw - b_mkt)) * 100
    print(f"  {name:<30s} {b:8.4f} {(b/b_mkt-1)*100:+7.1f}% {gap:+11.1f}%")

# ── Best method segment breakdown ──
best_name = min(results, key=results.get)
best_brier = results[best_name]
print(f"\n  BEST: {best_name} (Brier={best_brier:.4f}, gap closed={((1-(best_brier-b_mkt)/(b_raw-b_mkt))*100):.1f}%)")

# Map best method to its calibrated array
cal_map = {
    '1_phase_6seg': cal_phase,
    '2_fine_phase_8seg': cal_fine,
    '3_per_over_40seg': cal_over,
    '4_hierarchical': cal_hier,
    '5_logit_phase': cal_logit,
    '6_logit_per_over': cal_logit_ov,
    '7_scale_phase': cal_scale,
    '8_scale_per_over': cal_scale_ov,
    '9_logit_fine_8seg': cal_logit_fine,
}
best_cal = cal_map[best_name]

# Segment breakdown for best
print(f"\n  Segment breakdown (best = {best_name}):")
print(f"    {'Segment':<20s} {'n':>4s} {'Market':>8s} {'Raw':>8s} {'Corrected':>10s} {'vs_Mkt':>8s}")
print(f"    {'-'*56}")
for inn in [1, 2]:
    for ph in ['powerplay', 'middle', 'death']:
        mask = (merged['innings'] == inn).values & (merged['phase'] == ph).values
        if mask.sum() < 3:
            continue
        seg = f"inn{inn}_{ph}"
        b_m = brier(market[mask], actual[mask])
        b_r = brier(model_p[mask], actual[mask])
        b_c = brier(best_cal[mask], actual[mask])
        vs = (b_c / b_m - 1) * 100
        win = " <-- BEATS" if b_c < b_m else ""
        print(f"    {seg:<20s} {mask.sum():4d} {b_m:8.4f} {b_r:8.4f} {b_c:10.4f} {vs:+7.1f}%{win}")
    if inn == 1:
        mask_inn = (merged['innings'] == 1).values
        b_m = brier(market[mask_inn], actual[mask_inn])
        b_c = brier(best_cal[mask_inn], actual[mask_inn])
        print(f"    {'INN1 TOTAL':<20s} {mask_inn.sum():4d} {b_m:8.4f} {'':>8s} {b_c:10.4f} {(b_c/b_m-1)*100:+7.1f}%")
mask_inn2 = (merged['innings'] == 2).values
b_m2 = brier(market[mask_inn2], actual[mask_inn2])
b_c2 = brier(best_cal[mask_inn2], actual[mask_inn2])
print(f"    {'INN2 TOTAL':<20s} {mask_inn2.sum():4d} {b_m2:8.4f} {'':>8s} {b_c2:10.4f} {(b_c2/b_m2-1)*100:+7.1f}%")

# ── Blend with market for best ──
print(f"\n  Blend: alpha*best_corrected + (1-alpha)*market")
best_a, best_blend_b = 0, 999
for a in np.arange(0, 1.01, 0.01):
    blend = a * best_cal + (1 - a) * market
    b = brier(blend, actual)
    if b < best_blend_b:
        best_a, best_blend_b = a, b
print(f"    Best alpha={best_a:.2f}  Brier={best_blend_b:.4f}  (pure market={b_mkt:.4f})")

# ── Also blend top 3 methods ──
print(f"\n  Blend top methods with market:")
top3 = sorted(results.items(), key=lambda x: x[1])[:3]
for name, b in top3:
    c = cal_map[name]
    ba, bb = 0, 999
    for a in np.arange(0, 1.01, 0.01):
        bl = a * c + (1 - a) * market
        bv = brier(bl, actual)
        if bv < bb:
            ba, bb = a, bv
    print(f"    {name:<30s} alpha={ba:.2f}  blend={bb:.4f}  (alone={b:.4f})")

print("\nDone.")
