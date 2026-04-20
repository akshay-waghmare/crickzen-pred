"""
IPL 2026 Market vs Model — CORRECTED ANALYSIS
Fixes r1→team mapping per match using cross-validation with validated old dataset.
"""
import pandas as pd, numpy as np, sys, warnings, joblib
from pathlib import Path
warnings.filterwarnings('ignore')

sys.path.insert(0, 'src')
from bbl_pipeline.inference.predictor import _restore_simple_imputer_compatibility

# ═══ Load data ═══
old = pd.read_parquet('data/ipl_model_vs_market_v3.parquet')
merged = pd.read_parquet('data/ipl_betx21_merged_2026.parquet')
raw = pd.read_parquet('data/ipl_raw/matches')
raw = raw.drop_duplicates(subset=['match_id','innings','over','ball'], keep='first')
raw = raw.sort_values(['match_id','innings','over','ball']).reset_index(drop=True)
raw26 = raw[raw.season=='2026']
feat = pd.read_parquet('data/ipl_features_v3/training.parquet')

# Align features with raw
n = len(feat)
for c in ['innings','over','ball','season','match_id','batting_team','winner','date','venue_id']:
    if c in raw.columns:
        feat[c] = raw[c].values[:n]
f26 = feat[feat.season=='2026'].copy()

# ═══ Load model and calibrators ═══
ipl_model = joblib.load('models/ipl_v3/champion_model.joblib')
_restore_simple_imputer_compatibility(ipl_model)
ipl_cal = joblib.load('models/ipl_v3/isotonic_calibrator.pkl')
ipl_league = joblib.load('models/ipl_v3/league_calibrators/ipl/league_calibrator.pkl')
ipl_bias = ipl_league.get('calibrators', {})
ipl_temp = ipl_league.get('temperature_scalers', {})
po = ipl_cal.get('per_over_calibrators', {})
ph = ipl_cal.get('phase_calibrators', {})

def apply_iso(p, inn, over_0):
    key = f'inn{inn}_over{over_0+1}'
    if key in po:
        try: return float(po[key].predict([p])[0])
        except: pass
    phase = 'powerplay' if over_0 < 6 else ('middle' if over_0 < 16 else 'death')
    pkey = f'inn{inn}_{phase}'
    if pkey in ph:
        try: return float(ph[pkey].predict([p])[0])
        except: pass
    return p

def temp_scale(p, T):
    p = np.clip(p, 1e-6, 1-1e-6)
    return float(1 / (1 + np.exp(-np.log(p/(1-p)) / T)))

def apply_phase_temp(p, inn, over_0):
    phase = 'powerplay' if over_0 < 6 else ('middle' if over_0 < 16 else 'death')
    T = ipl_temp.get(f'inn{inn}_{phase}')
    if T is None or T == 1.0: return p
    return temp_scale(p, T)

def apply_bias(p, inn, over_0):
    phase = 'powerplay' if over_0 < 6 else ('middle' if over_0 < 16 else 'death')
    key = f'inn{inn}_{phase}'
    scaler = ipl_bias.get(key, ipl_bias.get(f'innings_{inn}'))
    if scaler is None: return p
    return float(np.asarray(scaler.predict(np.array([[p]]))).flat[0])

# Score model
feats_i = ipl_model.selected_features_
f26['raw_prob'] = ipl_model.predict_proba(f26[feats_i])[:, 1]
f26['iso_prob'] = [apply_iso(p,i,o) for p,i,o in zip(f26.raw_prob, f26.innings, f26['over'])]
f26['temp_prob'] = [apply_phase_temp(p,i,o) for p,i,o in zip(f26.iso_prob, f26.innings, f26['over'])]
f26['bias_prob'] = [apply_bias(p,i,o) for p,i,o in zip(f26.temp_prob, f26.innings, f26['over'])]
f26['over_1idx'] = f26['over'] + 1

# Transition blend
def apply_transition(df, prob_col, n_overs=6):
    bl = df[prob_col].copy()
    for mid in df.match_id.unique():
        match = df[df.match_id==mid]
        inn1 = match[match.innings==1]
        inn2 = match[match.innings==2]
        if len(inn1)==0 or len(inn2)==0: continue
        inn1_final = inn1.iloc[-1][prob_col]
        inn1_bat = inn1.iloc[-1]['batting_team']
        for idx, row in inn2.iterrows():
            ob = row['over'] + row['ball']/6.0
            if ob >= n_overs: continue
            prior = inn1_final if row['batting_team']==inn1_bat else 1.0-inn1_final
            alpha = max(0.0, 1.0 - ob/n_overs)
            bl.loc[idx] = alpha * prior + (1-alpha) * row[prob_col]
    return bl

f26['blend_prob'] = apply_transition(f26, 'bias_prob', 6)
print(f"Model scored: {len(f26)} balls, {f26.match_id.nunique()} matches")

# ═══ Determine r1→team flip per match ═══
name_map = {'RC Bengaluru': 'Royal Challengers Bengaluru'}
def norm(t): return name_map.get(t, t)

flip_matches = set()
betx21_mids = merged.match_id.unique()

for bmid in betx21_mids:
    bdata = merged[merged.match_id==bmid]
    t1, t2 = bdata.iloc[0]['t1'], bdata.iloc[0]['t2']
    
    # Find cricsheet match
    cs_mid = None
    for cid in raw26.match_id.unique():
        teams = set(raw26[raw26.match_id==cid]['batting_team'].unique())
        if norm(t1) in teams and norm(t2) in teams:
            cs_mid = cid
            break
    if not cs_mid: continue
    
    # Check against old dataset
    old_m = old[old.match_id==cs_mid]
    if len(old_m) < 5: continue
    
    inn1_team = raw26[(raw26.match_id==cs_mid)&(raw26.innings==1)]['batting_team'].iloc[0]
    t1_is_inn1 = norm(t1) == inn1_team
    
    new_by_over = bdata.groupby(['innings','over']).agg(r1_p=('r1_prob','last')).reset_index()
    new_by_over['over'] = new_by_over['over'].astype(int)
    
    # betx21 over_int matches old dataset over directly (both effectively 1-indexed for complete overs)
    m = old_m.merge(new_by_over, on=['innings','over'])
    if len(m) < 3: continue
    
    new_p_inn1 = m['r1_p'] if t1_is_inn1 else 1-m['r1_p']
    corr = m['market_p_inn1'].corr(new_p_inn1)
    
    if corr < 0:
        flip_matches.add(bmid)

print(f"Matches needing flip: {flip_matches}")

# ═══ Build corrected per-over dataset ═══
print("Building corrected per-over dataset...")

rows = []
for bmid in betx21_mids:
    bdata = merged[merged.match_id==bmid]
    t1, t2 = bdata.iloc[0]['t1'], bdata.iloc[0]['t2']
    
    cs_mid = None
    for cid in raw26.match_id.unique():
        teams = set(raw26[raw26.match_id==cid]['batting_team'].unique())
        if norm(t1) in teams and norm(t2) in teams:
            cs_mid = cid
            break
    if not cs_mid: continue
    
    inn1_team = raw26[(raw26.match_id==cs_mid)&(raw26.innings==1)]['batting_team'].iloc[0]
    t1_is_inn1 = norm(t1) == inn1_team
    winner = raw26[raw26.match_id==cs_mid]['winner'].iloc[0]
    actual_inn1_wins = 1.0 if inn1_team == winner else 0.0
    need_flip = bmid in flip_matches
    
    # Market: aggregate to per-over, correct flip
    bdata_c = bdata.copy()
    bdata_c['over_int'] = bdata_c['over'].astype(int)
    mkt_by_over = bdata_c.groupby(['innings','over_int']).agg(r1_p=('r1_prob','last')).reset_index()
    
    # Model: last ball per over from cricsheet
    cs_data = f26[f26.match_id==cs_mid].copy()
    mdl_by_over = cs_data.groupby(['innings','over']).tail(1)[
        ['innings','over','over_1idx','batting_team','raw_prob','iso_prob',
         'temp_prob','bias_prob','blend_prob']].copy()
    
    # Convert model P(bat) to P(inn1)
    for col in ['raw_prob','iso_prob','temp_prob','bias_prob','blend_prob']:
        mdl_by_over[f'{col}_inn1'] = mdl_by_over.apply(
            lambda r: r[col] if r['batting_team']==inn1_team else 1-r[col], axis=1)
    
    for _, mrow in mkt_by_over.iterrows():
        inn, ov = int(mrow['innings']), int(mrow['over_int'])
        
        model_row = mdl_by_over[(mdl_by_over.innings==inn)&(mdl_by_over.over_1idx==ov)]
        if len(model_row)==0: continue
        model_row = model_row.iloc[0]
        
        # Market P(inn1): convert r1_prob accounting for flip and t1→inn1 mapping
        r1_p = mrow['r1_p']
        if need_flip: r1_p = 1.0 - r1_p  # fix runner order
        market_p_inn1 = r1_p if t1_is_inn1 else 1.0 - r1_p
        
        phase = 'powerplay' if ov<=6 else ('middle' if ov<=15 else 'death')
        rows.append({
            'betx21_id': bmid, 'cs_match_id': cs_mid,
            'innings': inn, 'over': ov, 'phase': phase,
            'inn1_team': inn1_team, 'inn2_team': norm(t2) if t1_is_inn1 else norm(t1),
            'winner': winner, 'actual_inn1_wins': actual_inn1_wins,
            'market_p_inn1': market_p_inn1,
            'raw_p_inn1': model_row['raw_prob_inn1'],
            'iso_p_inn1': model_row['iso_prob_inn1'],
            'temp_p_inn1': model_row['temp_prob_inn1'],
            'bias_p_inn1': model_row['bias_prob_inn1'],
            'full_p_inn1': model_row['blend_prob_inn1'],
        })

result = pd.DataFrame(rows)
print(f"Corrected dataset: {len(result)} rows, {result.cs_match_id.nunique()} matches")

# ═══ Cross-validate: compare with old dataset ═══
m = old.merge(result, left_on=['match_id','innings','over'],
              right_on=['cs_match_id','innings','over'], how='inner')
print(f"\nCross-validation with old dataset: {len(m)} matched rows")
corr = m['market_p_inn1_x'].corr(m['market_p_inn1_y'])
mad = (m['market_p_inn1_x'] - m['market_p_inn1_y']).abs().mean()
print(f"  Correlation: {corr:.4f}")
print(f"  Mean abs diff: {mad:.4f}")

# Save
result.to_parquet('data/ipl_market_vs_model_corrected_2026.parquet', index=False)

# ═══ ANALYSIS ═══
y = result['actual_inn1_wins'].values.astype(float)

def brier(y, p): return np.mean((y-p)**2)
def logloss(y, p):
    p = np.clip(p, 1e-7, 1-1e-7)
    return -np.mean(y*np.log(p) + (1-y)*np.log(1-p))
def ece(y, p, bins=10):
    edges = np.linspace(0,1,bins+1); total=0
    for i in range(bins):
        mask=(p>=edges[i])&(p<edges[i+1])
        if mask.sum()==0: continue
        total += mask.sum()*abs(p[mask].mean()-y[mask].mean())
    return total/len(y)

n_m = result.cs_match_id.nunique()
print()
print('='*100)
print(f'IPL 2026 CORRECTED ANALYSIS — {n_m} matches, {len(result)} per-over obs')
print(f'Pipeline: IPL v3 + iso + phase-T + LogitBias + blend(6)')
print('='*100)

segments = [
    ('OVERALL', result.index),
    ('Inn1', result[result.innings==1].index),
    ('Inn2', result[result.innings==2].index),
    ('Inn1 PP', result[(result.innings==1)&(result.phase=='powerplay')].index),
    ('Inn1 Mid', result[(result.innings==1)&(result.phase=='middle')].index),
    ('Inn1 Dth', result[(result.innings==1)&(result.phase=='death')].index),
    ('Inn2 PP', result[(result.innings==2)&(result.phase=='powerplay')].index),
    ('Inn2 Mid', result[(result.innings==2)&(result.phase=='middle')].index),
    ('Inn2 Dth', result[(result.innings==2)&(result.phase=='death')].index),
]

pipelines = {'Market':'market_p_inn1', 'Raw':'raw_p_inn1', 'Iso':'iso_p_inn1',
             'Iso+T':'temp_p_inn1', 'Iso+T+Bias':'bias_p_inn1', 'FULL':'full_p_inn1'}

print()
print('── BRIER SCORE ──')
hdr = f"  {'Segment':<12s} {'N':>4s}"
for pn in pipelines: hdr += f" {pn:>12s}"
print(hdr)
print('  ' + '-'*(20+13*len(pipelines)))

for seg_name, idx in segments:
    if len(idx)<3: continue
    yi = y[idx]
    line = f"  {seg_name:<12s} {len(idx):>4d}"
    mkt = brier(yi, result.loc[idx,'market_p_inn1'].values)
    for pn, col in pipelines.items():
        val = brier(yi, result.loc[idx,col].values)
        if pn=='Market': line += f" {val:>12.4f}"
        else:
            d = (val/mkt-1)*100
            m = 'v' if d<-1 else ('^' if d>1 else '=')
            line += f" {d:>+8.1f}% {m}"
    print(line)

print()
print('── LOG LOSS ──')
hdr = f"  {'Segment':<12s} {'N':>4s}"
for pn in pipelines: hdr += f" {pn:>12s}"
print(hdr)
print('  ' + '-'*(20+13*len(pipelines)))

for seg_name, idx in segments:
    if len(idx)<3: continue
    yi = y[idx]
    line = f"  {seg_name:<12s} {len(idx):>4d}"
    mkt = logloss(yi, result.loc[idx,'market_p_inn1'].values)
    for pn, col in pipelines.items():
        val = logloss(yi, result.loc[idx,col].values)
        if pn=='Market': line += f" {val:>12.4f}"
        else:
            d = (val/mkt-1)*100
            m = 'v' if d<-1 else ('^' if d>1 else '=')
            line += f" {d:>+8.1f}% {m}"
    print(line)

# ═══ Per-over inn2 deep dive ═══
print()
print('='*100)
print('INN2 PER-OVER DETAIL')
print('='*100)
inn2 = result[result.innings==2]
for ov in range(1,21):
    od = inn2[inn2.over==ov]
    if len(od)<3: continue
    yi = od.actual_inn1_wins.values.astype(float)
    b_m = brier(yi, od.market_p_inn1.values)
    b_f = brier(yi, od.full_p_inn1.values)
    d = (b_f/b_m-1)*100
    mstd = od.market_p_inn1.std()
    fstd = od.full_p_inn1.std()
    sr = fstd/mstd if mstd>0 else 0
    mb = od.market_p_inn1.mean()-yi.mean()
    fb = od.full_p_inn1.mean()-yi.mean()
    print(f"  Over {ov:>2d}: N={len(od):>3d} | Mkt={b_m:.4f} FULL={b_f:.4f} ({d:>+6.1f}%) | "
          f"Spread: mkt={mstd:.3f} mdl={fstd:.3f} ratio={sr:.2f} | "
          f"Bias: mkt={mb:+.3f} mdl={fb:+.3f}")
