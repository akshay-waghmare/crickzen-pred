"""
Validate innings transition smoothing against market data.

Replays OOS Cricsheet features through the production model + calibrators,
then applies transition blending and measures Brier, LogLoss, ECE improvement
by innings×phase. Uses the same data pipeline as ipl_oos_bias_analysis.py.

Usage:
    python scripts/validate_transition_smoothing.py
"""
import os, sys, warnings
import pandas as pd
import numpy as np
import joblib

warnings.filterwarnings('ignore')
sys.path.insert(0, 'src')
from bbl_pipeline.inference.predictor import _restore_simple_imputer_compatibility
from bbl_pipeline.training.league_calibrator import LogitBiasScaler

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── Metrics ──────────────────────────────────────────────────
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

# ── STEP 1: Load model + calibrators ────────────────────────
print("=" * 70)
print("Loading model + calibrators + features")
print("=" * 70)

model = joblib.load(os.path.join(PROJ, 'models/t20_male_v2/champion_model.joblib'))
_restore_simple_imputer_compatibility(model)
cal = joblib.load(os.path.join(PROJ, 'models/t20_male_v2/isotonic_calibrator.pkl'))

league_cal = joblib.load(
    os.path.join(PROJ, 'models/t20_male_v2/league_calibrators/ipl/league_calibrator.pkl')
)
bias_calibrators = league_cal.get('calibrators', {})

# ── STEP 2: Load features + identify 2026 matches ───────────
raw = pd.read_parquet(os.path.join(PROJ, 'data/ipl_raw/matches'))
raw = raw.drop_duplicates(subset=['match_id', 'innings', 'over', 'ball'], keep='first')
raw = raw.sort_values(['match_id', 'innings', 'over', 'ball']).reset_index(drop=True)

feat = pd.read_parquet(os.path.join(PROJ, 'data/ipl_features_v2/training.parquet'))
feat['innings']      = raw['innings'].values
feat['over']         = raw['over'].values
feat['ball']         = raw['ball'].values
feat['season']       = raw['season'].values
feat['match_id']     = raw['match_id'].values
feat['batting_team'] = raw['batting_team'].values
feat['date']         = pd.to_datetime(raw['date'])
feat['winner']       = raw['winner'].values

f26 = feat[feat['season'] == '2026'].copy()
f26['over_1idx'] = f26['over'] + 1
f26['date_str']  = f26['date'].dt.strftime('%Y-%m-%d')
print(f"2026 features: {len(f26)} balls, {f26['match_id'].nunique()} matches")

# ── STEP 3: Model predictions with calibration chain ────────
print("\nScoring with production model + calibration chain...")

po  = cal.get('per_over_calibrators', {})
ph  = cal.get('phase_calibrators', {})
inn_cal = {
    'innings_1': cal.get('calibrator_innings1'),
    'innings_2': cal.get('calibrator_innings2'),
}

def apply_isotonic(p, inn, over_0):
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

def apply_bias(p, inn, over_0):
    phase = 'powerplay' if over_0 < 6 else ('middle' if over_0 < 16 else 'death')
    key = 'inn%d_%s' % (inn, phase)
    scaler = bias_calibrators.get(key, bias_calibrators.get('innings_%d' % inn))
    if scaler is None:
        return p
    result = scaler.predict(np.array([[p]]))
    return float(np.asarray(result).flat[0])

feats = model.selected_features_
f26['ml_raw'] = model.predict_proba(f26[feats])[:, 1]
f26['ml_iso'] = [apply_isotonic(p, i, o) for p, i, o in zip(f26['ml_raw'], f26['innings'], f26['over'])]
f26['ml_bias'] = [apply_bias(p, i, o) for p, i, o in zip(f26['ml_iso'], f26['innings'], f26['over'])]

# ── STEP 4: Apply transition blending (simulate per match) ──
print("Applying transition blending...")

def apply_transition(df, transition_overs=6):
    """Simulate transition blending per match on ball-level data."""
    blended = df['ml_bias'].copy()
    
    for mid in df['match_id'].unique():
        match = df[df['match_id'] == mid]
        inn1 = match[match['innings'] == 1]
        inn2 = match[match['innings'] == 2]
        if len(inn1) == 0 or len(inn2) == 0:
            continue
        
        # Last inn1 ball: P(inn1 batting team wins) after full calibration
        inn1_final_p_bat = inn1.iloc[-1]['ml_bias']
        inn1_batting_team = inn1.iloc[-1]['batting_team']
        
        for idx, row in inn2.iterrows():
            overs_bowled = row['over'] + row['ball'] / 6.0
            if overs_bowled >= transition_overs:
                continue
            
            # Inn2 batting team ≠ inn1 batting team in normal matches
            if row['batting_team'] == inn1_batting_team:
                inn1_prior = inn1_final_p_bat
            else:
                inn1_prior = 1.0 - inn1_final_p_bat
            
            alpha = max(0.0, 1.0 - overs_bowled / transition_overs)
            blended.loc[idx] = alpha * inn1_prior + (1.0 - alpha) * row['ml_bias']
    
    return blended

f26['ml_blend_6'] = apply_transition(f26, transition_overs=6)
f26['ml_blend_4'] = apply_transition(f26, transition_overs=4)
f26['ml_blend_8'] = apply_transition(f26, transition_overs=8)
f26['ml_blend_3'] = apply_transition(f26, transition_overs=3)

# ── STEP 5: Merge with market data (one row per over) ───────
print("Merging with market data...")

market = pd.read_parquet(os.path.join(PROJ, 'data/ipl_model_vs_market_v3.parquet'))
# v3 has: match_id, innings, over (1-indexed), market_p_inn1, actual_inn1_wins

# Take last ball per over for merge
f26_last = f26.groupby(['match_id', 'innings', 'over']).tail(1).copy()

merged = f26_last.merge(
    market,
    left_on=['match_id', 'innings', 'over_1idx'],
    right_on=['match_id', 'innings', 'over'],
    how='inner', suffixes=('', '_mkt')
)

print(f"Merged: {len(merged)} obs, {merged['match_id'].nunique()} matches")

# Convert to P(inn1_team) space for consistent comparison with market
for col in ['ml_raw', 'ml_iso', 'ml_bias', 'ml_blend_6', 'ml_blend_4', 'ml_blend_8', 'ml_blend_3']:
    merged[col + '_pi1'] = np.where(merged['innings'] == 1, merged[col], 1 - merged[col])

y = merged['actual_inn1_wins'].values.astype(float)
mkt = merged['market_p_inn1'].values.astype(float)

# ── STEP 6: Results ─────────────────────────────────────────
print("\n" + "=" * 90)
print("INNINGS TRANSITION SMOOTHING VALIDATION")
print(f"  {len(merged)} obs, {merged['match_id'].nunique()} matches")
print("=" * 90)

models = [
    ('Market',          mkt),
    ('ML raw',          merged['ml_raw_pi1'].values),
    ('ML +iso',         merged['ml_iso_pi1'].values),
    ('ML +iso+bias',    merged['ml_bias_pi1'].values),
    ('ML +blend(3)',    merged['ml_blend_3_pi1'].values),
    ('ML +blend(4)',    merged['ml_blend_4_pi1'].values),
    ('ML +blend(6)',    merged['ml_blend_6_pi1'].values),
    ('ML +blend(8)',    merged['ml_blend_8_pi1'].values),
]

def phase_of(over_1idx):
    if over_1idx <= 6:  return 'powerplay'
    if over_1idx <= 15: return 'middle'
    return 'death'

merged['phase'] = merged['over_1idx'].apply(phase_of)

segments = [
    ('OVERALL',          merged.index),
    ('Inn1',             merged[merged['innings'] == 1].index),
    ('Inn2',             merged[merged['innings'] == 2].index),
    ('Inn1 PP',          merged[(merged['innings'] == 1) & (merged['phase'] == 'powerplay')].index),
    ('Inn1 Mid',         merged[(merged['innings'] == 1) & (merged['phase'] == 'middle')].index),
    ('Inn1 Death',       merged[(merged['innings'] == 1) & (merged['phase'] == 'death')].index),
    ('Inn2 PP',          merged[(merged['innings'] == 2) & (merged['phase'] == 'powerplay')].index),
    ('Inn2 Mid',         merged[(merged['innings'] == 2) & (merged['phase'] == 'middle')].index),
    ('Inn2 Death',       merged[(merged['innings'] == 2) & (merged['phase'] == 'death')].index),
]

for metric_name, metric_fn in [('BRIER', brier), ('LOGLOSS', logloss), ('ECE', ece)]:
    print(f"\n── {metric_name} {'─'*75}")
    header = f"  {'Segment':<16} {'N':>4}"
    for name, _ in models:
        header += f" {name:>13}"
    print(header)
    print("  " + "-" * (20 + 14 * len(models)))
    
    for seg_name, idx in segments:
        if len(idx) < 3:
            continue
        yi = y[idx]
        line = f"  {seg_name:<16} {len(idx):>4}"
        mkt_val = metric_fn(yi, mkt[idx])
        for name, preds in models:
            val = metric_fn(yi, preds[idx])
            if name == 'Market':
                line += f" {val:>13.4f}"
            else:
                pct = (val / mkt_val - 1) * 100 if mkt_val > 0 else 0
                line += f" {val:.4f}{pct:>+5.1f}%"
        print(line)

# ── STEP 7: Per-over breakdown for inn2 ─────────────────────
print(f"\n{'='*90}")
print("INN2 PER-OVER BRIER BREAKDOWN")
print(f"{'='*90}")
inn2 = merged[merged['innings'] == 2]
print(f"\n  {'Over':<8} {'N':>4} | {'Market':>8} | {'ML+bias':>10} | {'blend(6)':>10} | {'Δ':>7} | {'blend(4)':>10} | {'blend(3)':>10}")
print("  " + "-" * 85)
for over_1 in sorted(inn2['over_1idx'].unique()):
    idx = inn2[inn2['over_1idx'] == over_1].index
    if len(idx) < 3:
        continue
    yi = y[idx]
    m = brier(yi, mkt[idx])
    b = brier(yi, merged.loc[idx, 'ml_bias_pi1'].values)
    bl6 = brier(yi, merged.loc[idx, 'ml_blend_6_pi1'].values)
    bl4 = brier(yi, merged.loc[idx, 'ml_blend_4_pi1'].values)
    bl3 = brier(yi, merged.loc[idx, 'ml_blend_3_pi1'].values)
    delta = bl6 - b
    icon = '✅' if delta < -0.002 else '⬜' if abs(delta) < 0.002 else '❌'
    print(f"  Over {over_1:<4} {len(idx):>4} | {m:>8.4f} | {b:>10.4f} | {bl6:>10.4f} | {delta:>+7.4f} {icon} | {bl4:>10.4f} | {bl3:>10.4f}")

# ── STEP 8: Show specific transition examples ───────────────
print(f"\n{'='*90}")
print("TRANSITION EXAMPLES (last inn1 ball -> first inn2 ball)")
print(f"{'='*90}")
for mid in sorted(merged['match_id'].unique()):
    m = merged[merged['match_id'] == mid]
    inn1 = m[m['innings'] == 1]
    inn2 = m[m['innings'] == 2]
    if len(inn1) == 0 or len(inn2) == 0:
        continue
    last1 = inn1.iloc[-1]
    first2 = inn2.iloc[0]
    gap = abs(last1['ml_bias_pi1'] - first2['ml_bias_pi1'])
    gap_bl = abs(last1['ml_bias_pi1'] - first2['ml_blend_6_pi1'])
    teams = f"{last1['batting_team'][:15]} vs {first2['batting_team'][:15]}"
    print(f"  {mid}: {teams}")
    print(f"    Inn1 last: P(inn1)={last1['ml_bias_pi1']:.1%}  Market={last1['market_p_inn1']:.1%}")
    print(f"    Inn2 1st:  P(inn1)={first2['ml_bias_pi1']:.1%}  Blended={first2['ml_blend_6_pi1']:.1%}  Market={first2['market_p_inn1']:.1%}")
    print(f"    Gap: {gap:.1%} -> {gap_bl:.1%} (reduced {(1-gap_bl/gap)*100:.0f}%)" if gap > 0.01 else f"    Gap: minimal")

print("\nDone!")

