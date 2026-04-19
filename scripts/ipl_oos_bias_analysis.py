"""
IPL OOS Bias Analysis — Correct Version

Approach: Use Cricsheet features as ground truth for innings/over/batting_team.
Match betx21 odds by date + team overlap + timestamps.
Do proper OOS bias calibration (train first ~60%, test last ~40%).

Saves:
  - data/ipl_model_vs_market_v3.parquet (correctly mapped dataset)
  - OOS validation metrics
"""
import gzip, json, glob, os, sys
import pandas as pd, numpy as np, joblib, warnings
from scipy.special import logit, expit
from datetime import datetime

warnings.filterwarnings('ignore')
sys.path.insert(0, 'src')
from bbl_pipeline.inference.predictor import _restore_simple_imputer_compatibility

ODDS_DIR = r'C:\Users\ADMINS\Documents\projects\betx21.live\ipl_matches_download'
PROJ_DIR = r'C:\Users\ADMINS\Documents\projects\machine_learning_bbl_009-odi-mc-predictor'

IPL_TEAMS = {
    'Chennai Super Kings', 'Mumbai Indians', 'Royal Challengers Bengaluru',
    'Royal Challengers Bangalore', 'Kolkata Knight Riders', 'Delhi Capitals',
    'Punjab Kings', 'Rajasthan Royals', 'Sunrisers Hyderabad',
    'Gujarat Titans', 'Lucknow Super Giants',
}

# ============================================================
# STEP 1: Load Cricsheet features (ground truth)
# ============================================================
print("=" * 70)
print("STEP 1: Loading Cricsheet features + model")
print("=" * 70)

model = joblib.load(os.path.join(PROJ_DIR, 'models/t20_male_v2/champion_model.joblib'))
_restore_simple_imputer_compatibility(model)
cal = joblib.load(os.path.join(PROJ_DIR, 'models/t20_male_v2/isotonic_calibrator.pkl'))

raw = pd.read_parquet(os.path.join(PROJ_DIR, 'data/ipl_raw/matches'))
raw = raw.drop_duplicates(subset=['match_id','innings','over','ball'], keep='first')
raw = raw.sort_values(['match_id','innings','over','ball']).reset_index(drop=True)

feat = pd.read_parquet(os.path.join(PROJ_DIR, 'data/ipl_features_v2/training.parquet'))
feat['innings'] = raw['innings'].values
feat['over'] = raw['over'].values
feat['season'] = raw['season'].values
feat['match_id'] = raw['match_id'].values
feat['batting_team'] = raw['batting_team'].values
feat['date'] = pd.to_datetime(raw['date'])
feat['winner'] = raw['winner'].values

f26 = feat[feat['season'] == '2026'].copy()
f26['over_1idx'] = f26['over'] + 1
f26['date_str'] = f26['date'].dt.strftime('%Y-%m-%d')

# Last ball per over (for matching with odds)
f26_last = f26.groupby(['match_id', 'innings', 'over']).tail(1).copy()
print(f"2026 features: {len(f26)} rows, {f26['match_id'].nunique()} matches, {len(f26_last)} overs")

# ============================================================
# STEP 2: Parse betx21 IPL odds and scores
# ============================================================
print("\n" + "=" * 70)
print("STEP 2: Parsing betx21 IPL odds + scores")
print("=" * 70)

# Find IPL matches from scores files
ipl_events = {}
for gz in sorted(glob.glob(os.path.join(ODDS_DIR, '**', '*_scores.jsonl.gz'), recursive=True)):
    eid = os.path.basename(gz).replace('_scores.jsonl.gz', '')
    date = os.path.basename(os.path.dirname(gz))
    try:
        with gzip.open(gz, 'rt', encoding='utf-8', errors='replace') as f:
            first = json.loads(f.readline())
        t1 = first.get('t1', '')
        t2 = first.get('t2', '')
        if t1 in IPL_TEAMS or t2 in IPL_TEAMS:
            ipl_events[eid] = {'date': date, 't1': t1, 't2': t2, 'teams': frozenset([t1, t2])}
    except:
        pass

print(f"Found {len(ipl_events)} IPL events in betx21 data")

# Parse all scores to get over-level timestamps
print("Parsing scores for timestamps...")
event_scores = {}
for eid in ipl_events:
    scores_file = glob.glob(os.path.join(ODDS_DIR, '**', f'{eid}_scores.jsonl.gz'), recursive=True)
    if not scores_file:
        continue
    records = []
    try:
        with gzip.open(scores_file[0], 'rt', encoding='utf-8', errors='replace') as f:
            for line in f:
                try:
                    records.append(json.loads(line))
                except:
                    pass
    except EOFError:
        pass
    event_scores[eid] = records

# Parse all matchOdds ticks
print("Parsing odds ticks...")
event_odds = {}
for eid in ipl_events:
    odds_file = glob.glob(os.path.join(ODDS_DIR, '**', f'{eid}_odds.jsonl.gz'), recursive=True)
    if not odds_file:
        continue
    ticks = []
    try:
        with gzip.open(odds_file[0], 'rt', encoding='utf-8', errors='replace') as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    if rec.get('mt') != 'matchOdds' or rec.get('ms') == 'closed':
                        continue
                    runners = rec.get('r', [])
                    if len(runners) < 2:
                        continue
                    b0 = runners[0].get('b', [])
                    l0 = runners[0].get('l', [])
                    b1 = runners[1].get('b', [])
                    l1 = runners[1].get('l', [])
                    
                    p0_back = b0[0][0] if b0 else None
                    p0_lay = l0[0][0] if l0 else None
                    p1_back = b1[0][0] if b1 else None
                    p1_lay = l1[0][0] if l1 else None
                    
                    price0 = ((p0_back or p0_lay) + (p0_lay or p0_back)) / 2 if (p0_back or p0_lay) else None
                    price1 = ((p1_back or p1_lay) + (p1_lay or p1_back)) / 2 if (p1_back or p1_lay) else None
                    
                    if not price0 or not price1 or price0 <= 1 or price1 <= 1:
                        continue
                    
                    imp0 = 1.0 / price0
                    imp1 = 1.0 / price1
                    total = imp0 + imp1
                    
                    ticks.append({
                        'ts': pd.to_datetime(rec.get('t', ''), errors='coerce'),
                        'p_r0': imp0 / total,
                        'r0_id': runners[0].get('id', ''),
                    })
                except:
                    pass
    except EOFError:
        pass
    
    if ticks:
        odds_df = pd.DataFrame(ticks).dropna(subset=['ts']).sort_values('ts')
        event_odds[eid] = odds_df
        
print(f"Parsed odds for {len(event_odds)} events")

# ============================================================
# STEP 3: Match betx21 events to Cricsheet matches
# ============================================================
print("\n" + "=" * 70)
print("STEP 3: Matching betx21 events to Cricsheet matches")
print("=" * 70)

# Build Cricsheet match lookup: date -> {teams} -> match_id
cric_lookup = {}
for mid in f26['match_id'].unique():
    sub = f26[f26['match_id'] == mid]
    d = sub['date_str'].iloc[0]
    teams = frozenset(sub['batting_team'].unique())
    cric_lookup[(d, teams)] = mid

# Match events
event_to_match = {}
for eid, info in ipl_events.items():
    key = (info['date'], info['teams'])
    if key in cric_lookup:
        event_to_match[eid] = cric_lookup[key]

print(f"Matched {len(event_to_match)} betx21 events to Cricsheet matches")
for eid, mid in sorted(event_to_match.items(), key=lambda x: ipl_events[x[0]]['date']):
    info = ipl_events[eid]
    has_odds = eid in event_odds
    n_ticks = len(event_odds[eid]) if has_odds else 0
    print(f"  {info['date']}  {eid} -> {mid}  {info['t1'][:20]:20s} vs {info['t2'][:20]:20s}  {n_ticks} ticks")

# ============================================================
# STEP 4: Build per-over market probabilities using correct innings mapping
# ============================================================
print("\n" + "=" * 70)
print("STEP 4: Building per-over market data with correct innings mapping")
print("=" * 70)

# For each matched event, we need to determine which odds runner = which team
# Approach: find timestamps per innings transition in scores, then map runner prices

all_market_rows = []
for eid, mid in sorted(event_to_match.items(), key=lambda x: ipl_events[x[0]]['date']):
    info = ipl_events[eid]
    
    if eid not in event_odds or len(event_odds[eid]) < 10:
        print(f"  SKIP {eid} - insufficient odds ({len(event_odds.get(eid, []))} ticks)")
        continue
    
    scores = event_scores.get(eid, [])
    if not scores:
        print(f"  SKIP {eid} - no scores")
        continue
    
    odds_df = event_odds[eid]
    
    # Get Cricsheet match info
    match_feat = f26_last[f26_last['match_id'] == mid]
    winner = match_feat['winner'].iloc[0] if 'winner' in match_feat.columns else None
    inn1_team = match_feat[match_feat['innings'] == 1]['batting_team'].iloc[0]
    inn2_team = match_feat[match_feat['innings'] == 2]['batting_team'].iloc[0] if 2 in match_feat['innings'].values else None
    
    # Determine runner -> team mapping using end-of-match odds
    # The winning team's runner should have p close to 1.0 at match end
    late_ticks = odds_df.tail(max(1, len(odds_df) // 10))
    last_tick = late_ticks.iloc[-1]
    p_r0_end = last_tick['p_r0']
    
    # Runner 0 is the winner if p_r0 > 0.5 at end
    if p_r0_end > 0.7:
        r0_team = winner
    elif p_r0_end < 0.3:
        r0_team = inn1_team if winner == inn2_team else inn2_team
    else:
        # Ambiguous - skip
        print(f"  SKIP {eid} - ambiguous runner mapping (p_r0_end={p_r0_end:.2f})")
        continue
    
    r0_is_inn1_team = (r0_team == inn1_team)
    
    # Get per-innings-over timestamps from scores
    # Parse scores to find over boundaries
    over_timestamps = {}
    for s in scores:
        ts = pd.to_datetime(s.get('t', ''), errors='coerce')
        if pd.isna(ts):
            continue
        
        s1 = s.get('s1', '')
        s2 = s.get('s2', '')
        
        def parse_score(sc):
            if not sc or '/' not in sc:
                return None, None
            try:
                parts = sc.split('(')
                overs = float(parts[1].replace(')', '').strip()) if len(parts) > 1 else 0
                return int(overs), overs
            except:
                return None, None
        
        o1_int, o1_raw = parse_score(s1)
        o2_int, o2_raw = parse_score(s2)
        
        # s1 belongs to t1 in betx21, s2 to t2
        # We need to map to Cricsheet innings
        scores_t1 = info['t1']
        scores_t2 = info['t2']
        
        if scores_t1 == inn1_team:
            # t1 batted first (inn1 = s1, inn2 = s2)
            if o1_int and o1_int > 0:
                over_timestamps[(1, o1_int)] = ts
            if o2_int and o2_int > 0:
                over_timestamps[(2, o2_int)] = ts
        elif scores_t2 == inn1_team:
            # t2 batted first (inn1 = s2, inn2 = s1)
            if o2_int and o2_int > 0:
                over_timestamps[(1, o2_int)] = ts
            if o1_int and o1_int > 0:
                over_timestamps[(2, o1_int)] = ts
        else:
            # Can't determine mapping
            continue
    
    if not over_timestamps:
        print(f"  SKIP {eid} - no over timestamps")
        continue
    
    # For each Cricsheet over, find closest odds tick
    rows_added = 0
    for _, frow in match_feat.iterrows():
        inn = frow['innings']
        ov_1idx = frow['over_1idx']
        
        key = (inn, ov_1idx)
        if key not in over_timestamps:
            continue
        
        ts = over_timestamps[key]
        time_diff = (odds_df['ts'] - ts).abs()
        closest_idx = time_diff.idxmin()
        
        if time_diff[closest_idx].total_seconds() > 300:
            continue
        
        p_r0 = odds_df.loc[closest_idx, 'p_r0']
        
        # Convert p_r0 to P(inn1_team wins)
        p_inn1_team = p_r0 if r0_is_inn1_team else (1 - p_r0)
        
        batting = frow['batting_team']
        phase = 'powerplay' if ov_1idx <= 6 else ('middle' if ov_1idx <= 15 else 'death')
        actual_inn1_wins = 1 if winner == inn1_team else 0
        
        all_market_rows.append({
            'event_id': eid,
            'match_id': mid,
            'date': info['date'],
            'inn1_team': inn1_team,
            'inn2_team': inn2_team or '',
            'innings': inn,
            'over': ov_1idx,
            'phase': phase,
            'batting_team': batting,
            'market_p_inn1': p_inn1_team,
            'actual_inn1_wins': actual_inn1_wins,
            'winner': winner,
        })
        rows_added += 1
    
    print(f"  {info['date']}  {eid}  {inn1_team[:20]:20s} bat first  {rows_added} obs  r0={r0_team[:15]}")

market_df = pd.DataFrame(all_market_rows)
print(f"\nTotal: {len(market_df)} obs, {market_df['event_id'].nunique()} matches")

# Save
market_df.to_parquet(os.path.join(PROJ_DIR, 'data/ipl_model_vs_market_v3.parquet'), index=False)
print("Saved: data/ipl_model_vs_market_v3.parquet")

# ============================================================
# STEP 5: Score with production model + isotonic chain
# ============================================================
print("\n" + "=" * 70)
print("STEP 5: Scoring with production model")
print("=" * 70)

def get_phase(over_0idx):
    if over_0idx < 6: return 'powerplay'
    elif over_0idx < 16: return 'middle'
    else: return 'death'

po = cal.get('per_over_calibrators', {})
ph = cal.get('phase_calibrators', {})
inn_cal = {'innings_1': cal.get('calibrator_innings1'), 'innings_2': cal.get('calibrator_innings2')}

def apply_isotonic(p, inn, over_0):
    key = 'inn%d_over%d' % (inn, over_0 + 1)
    if key in po:
        try: return float(po[key].predict([p])[0])
        except: pass
    phase = get_phase(over_0)
    pkey = 'inn%d_%s' % (inn, phase)
    if pkey in ph:
        try: return float(ph[pkey].predict([p])[0])
        except: pass
    ikey = 'innings_%d' % inn
    if ikey in inn_cal and inn_cal[ikey] is not None:
        try: return float(inn_cal[ikey].predict([p])[0])
        except: pass
    return p

# Predict on 2026 features
feats = model.selected_features_
f26['ml_raw'] = model.predict_proba(f26[feats])[:, 1]
f26['ml_iso'] = [apply_isotonic(p, i, o) for p, i, o in zip(f26['ml_raw'], f26['innings'], f26['over'])]

# Take last ball per over for merge
f26_last2 = f26.groupby(['match_id', 'innings', 'over']).tail(1).copy()

# Merge with market data
merged = f26_last2.merge(
    market_df,
    left_on=['match_id', 'innings', 'over_1idx'],
    right_on=['match_id', 'innings', 'over'],
    how='inner', suffixes=('', '_mkt')
)

print(f"Merged: {len(merged)} obs, {merged['match_id'].nunique()} matches")

# Convert model probs to P(inn1_team) space for comparison
# Model outputs P(batting_team wins). For inn1, batting_team=inn1_team so P(bat)=P(inn1)
# For inn2, batting_team=inn2_team so P(bat)=P(inn2)=1-P(inn1)
merged['ml_raw_pinn1'] = np.where(merged['innings'] == 1, merged['ml_raw'], 1 - merged['ml_raw'])
merged['ml_iso_pinn1'] = np.where(merged['innings'] == 1, merged['ml_iso'], 1 - merged['ml_iso'])

# Sort by date for OOS split
merged = merged.sort_values(['date_str', 'match_id', 'innings', 'over_1idx']).reset_index(drop=True)
match_dates = merged.groupby('match_id')['date_str'].first().sort_values()
match_order = list(match_dates.index)
n_matches = len(match_order)
n_train = max(2, n_matches * 2 // 3)
train_matches = set(match_order[:n_train])
test_matches = set(match_order[n_train:])

print(f"\nOOS Split: {n_train} train ({len(merged[merged['match_id'].isin(train_matches)])} obs), "
      f"{n_matches - n_train} test ({len(merged[merged['match_id'].isin(test_matches)])} obs)")

# ============================================================
# STEP 6: Train OOS bias on TRAIN, evaluate on TEST
# ============================================================
print("\n" + "=" * 70)
print("STEP 6: OOS Bias Calibration")
print("=" * 70)

from bbl_pipeline.training.league_calibrator import LogitBiasScaler

train_data = merged[merged['match_id'].isin(train_matches)].copy()
test_data = merged[merged['match_id'].isin(test_matches)].copy()

# Train bias on TRAIN set
biases_oos = {}
for inn in [1, 2]:
    for phase in ['powerplay', 'middle', 'death']:
        sub = train_data[(train_data['innings'] == inn)]
        sub = sub[sub['over_1idx'].apply(lambda o: 'powerplay' if o <= 6 else ('middle' if o <= 15 else 'death')) == phase]
        if len(sub) < 5:
            print(f"  inn{inn}_{phase}: SKIP (N={len(sub)})")
            continue
        
        model_p_bat = sub['ml_iso'].values
        market_p_bat = np.where(sub['innings'] == 1, sub['market_p_inn1'], 1 - sub['market_p_inn1']).astype(float)
        
        scaler = LogitBiasScaler()
        scaler.fit(model_p_bat, market_p_bat)
        biases_oos['inn%d_%s' % (inn, phase)] = scaler
        print(f"  inn{inn}_{phase}: bias={scaler.bias:+.4f} (N={len(sub)})")

for inn in [1, 2]:
    sub = train_data[train_data['innings'] == inn]
    model_p_bat = sub['ml_iso'].values
    market_p_bat = np.where(sub['innings'] == 1, sub['market_p_inn1'], 1 - sub['market_p_inn1']).astype(float)
    scaler = LogitBiasScaler()
    scaler.fit(model_p_bat, market_p_bat)
    biases_oos['innings_%d' % inn] = scaler
    print(f"  innings_{inn}: bias={scaler.bias:+.4f} (N={len(sub)})")

# Apply OOS bias
def apply_bias(p, inn, over_1idx, bias_dict):
    phase = 'powerplay' if over_1idx <= 6 else ('middle' if over_1idx <= 15 else 'death')
    key = 'inn%d_%s' % (inn, phase)
    scaler = bias_dict.get(key, bias_dict.get('innings_%d' % inn))
    if scaler is None: return p
    return float(scaler.predict(np.array([p]))[0])

merged['ml_bias_oos'] = [apply_bias(p, i, o, biases_oos) for p, i, o in zip(merged['ml_iso'], merged['innings'], merged['over_1idx'])]
merged['ml_bias_oos_pinn1'] = np.where(merged['innings'] == 1, merged['ml_bias_oos'], 1 - merged['ml_bias_oos'])

# Also apply existing bias if available
try:
    existing_bias = joblib.load(os.path.join(PROJ_DIR, 'models/t20_male_v2/league_calibrators/ipl/league_calibrator.pkl'))['calibrators']
    merged['ml_bias_exist'] = [apply_bias(p, i, o, existing_bias) for p, i, o in zip(merged['ml_iso'], merged['innings'], merged['over_1idx'])]
    merged['ml_bias_exist_pinn1'] = np.where(merged['innings'] == 1, merged['ml_bias_exist'], 1 - merged['ml_bias_exist'])
    has_existing = True
except:
    has_existing = False

# ============================================================
# STEP 7: Results
# ============================================================
print("\n" + "=" * 70)
print("STEP 7: Results")
print("=" * 70)

def brier(p, y): return np.mean((p - y) ** 2)
def logloss(p, y):
    p = np.clip(p, 1e-7, 1-1e-7)
    return -np.mean(y * np.log(p) + (1-y) * np.log(1-p))
def ece(p, y, bins=10):
    edges = np.linspace(0, 1, bins+1)
    total = 0
    for i in range(bins):
        mask = (p >= edges[i]) & (p < edges[i+1])
        if mask.sum() == 0: continue
        total += mask.sum() * abs(p[mask].mean() - y[mask].mean())
    return total / len(p)

models_list = [
    ('Market', 'market_p_inn1'),
    ('ML raw', 'ml_raw_pinn1'),
    ('ML +isotonic', 'ml_iso_pinn1'),
]
if has_existing:
    models_list.append(('ML +iso +bias(existing)', 'ml_bias_exist_pinn1'))
models_list.append(('ML +iso +bias(OOS)', 'ml_bias_oos_pinn1'))

for label, subset in [('ALL DATA', merged), 
                       ('TRAIN SET (in-sample)', merged[merged['match_id'].isin(train_matches)]), 
                       ('TEST SET (OOS)', merged[merged['match_id'].isin(test_matches)])]:
    s = subset
    y = s['actual_inn1_wins'].values.astype(float)
    n = len(s)
    nm = s['match_id'].nunique()
    
    print(f"\n{'='*80}")
    print(f"  {label} ({n} obs, {nm} matches)")
    print(f"{'='*80}")
    print(f"  {'Model':<28} {'Brier':>8} {'LogLoss':>8} {'ECE':>8} {'vs Mkt':>8}")
    print(f"  {'-'*65}")
    mkt_b = brier(s['market_p_inn1'].values.astype(float), y)
    for name, col in models_list:
        if col not in s.columns:
            continue
        p = s[col].values.astype(float)
        b = brier(p, y)
        ll = logloss(p, y)
        e = ece(p, y)
        gap = (b / mkt_b - 1) * 100 if mkt_b > 0 else 0
        print(f"  {name:<28} {b:>8.4f} {ll:>8.4f} {e:>8.4f} {gap:>+7.1f}%")

# Phase breakdown on TEST SET
if len(test_data) > 0:
    print(f"\n{'='*80}")
    print(f"  TEST SET BY INNINGS+PHASE (OOS)")
    print(f"{'='*80}")
    test_m = merged[merged['match_id'].isin(test_matches)].copy()
    test_m['computed_phase'] = test_m['over_1idx'].apply(lambda o: 'powerplay' if o <= 6 else ('middle' if o <= 15 else 'death'))
    
    header = f"  {'Segment':<20} {'N':>4} {'Market':>8} {'ML+Iso':>8} "
    if has_existing:
        header += f"{'Bias(ex)':>10} "
    header += f"{'Bias(OOS)':>10} {'Best gap':>10}"
    print(header)
    print(f"  {'-'*80}")
    
    for inn in [1, 2]:
        for ph in ['powerplay', 'middle', 'death']:
            sub = test_m[(test_m['innings'] == inn) & (test_m['computed_phase'] == ph)]
            if len(sub) < 3: continue
            y = sub['actual_inn1_wins'].values.astype(float)
            m_b = brier(sub['market_p_inn1'].values.astype(float), y)
            iso_b = brier(sub['ml_iso_pinn1'].values.astype(float), y)
            oos_b = brier(sub['ml_bias_oos_pinn1'].values.astype(float), y)
            
            label = 'inn%d_%s' % (inn, ph)
            line = f"  {label:<20} {len(sub):>4} {m_b:>8.4f} {iso_b:>8.4f} "
            if has_existing:
                ex_b = brier(sub['ml_bias_exist_pinn1'].values.astype(float), y)
                line += f"{ex_b:>10.4f} "
                best = min(iso_b, ex_b, oos_b)
            else:
                best = min(iso_b, oos_b)
            line += f"{oos_b:>10.4f} {(best/m_b-1)*100:>+9.1f}%"
            print(line)

# Bias comparison
if has_existing:
    print(f"\n{'='*80}")
    print(f"  BIAS COMPARISON: Existing vs OOS-trained")
    print(f"{'='*80}")
    print(f"  {'Segment':<20} {'Existing':>10} {'OOS':>10} {'Diff':>10} {'Train N':>8}")
    print(f"  {'-'*60}")
    for key in ['inn1_powerplay', 'inn1_middle', 'inn1_death', 'inn2_powerplay', 'inn2_middle', 'inn2_death']:
        e_bias = existing_bias[key].bias if key in existing_bias else 0
        o_bias = biases_oos[key].bias if key in biases_oos else 0
        inn_n = int(key[3])
        ph_n = key.split('_', 1)[1]
        sub = train_data[(train_data['innings'] == inn_n)]
        sub = sub[sub['over_1idx'].apply(lambda o: 'powerplay' if o <= 6 else ('middle' if o <= 15 else 'death')) == ph_n]
        print(f"  {key:<20} {e_bias:>+10.4f} {o_bias:>+10.4f} {o_bias-e_bias:>+10.4f} {len(sub):>8}")

print(f"\n  Total matched: {len(merged)} obs, {n_matches} matches")
print(f"  OOS split: {n_train} train, {n_matches - n_train} test")
print(f"\nDone! data/ipl_model_vs_market_v3.parquet saved.")
