import pandas as pd, numpy as np, sys, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, 'src')

from bbl_pipeline.inference.predictor import Predictor
from bbl_pipeline.inference.schema import MatchState
from scipy.optimize import minimize_scalar

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

def brier(p, y):
    return np.mean((p - y)**2)

df = pd.read_parquet('data/ipl_model_vs_market.parquet')
print(f'Loaded {len(df)} observations from {df["event_id"].nunique()} matches')

# Load models
print('Loading IPL v2 model...')
pred_ipl = Predictor.load(model_dir='models/ipl_v2', feature_store_dir='data/ipl_feature_store_v2')
print('Loading Global T20 model with IPL calibration...')
pred_global = Predictor.load(model_dir='models/t20_male_v2', feature_store_dir='data/ipl_feature_store_v2', league='ipl')

# Re-score ALL observations
results = []
errors = 0
for idx, row in df.iterrows():
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
        target_runs=int(row['target']) if pd.notna(row['target']) else None,
        first_innings_score=int(row['target'])-1 if pd.notna(row['target']) else None,
    )
    
    try:
        p_ipl = pred_ipl.predict(state)
        p_ipl_t1 = p_ipl if bat_team == t1 else 1.0 - p_ipl
    except Exception as e:
        p_ipl_t1 = np.nan
        errors += 1
    
    try:
        p_global = pred_global.predict(state)
        p_global_t1 = p_global if bat_team == t1 else 1.0 - p_global
    except Exception as e:
        p_global_t1 = np.nan
    
    results.append({
        'event_id': row['event_id'],
        'innings': row['innings'],
        'over': row['over'],
        'phase': row['phase'],
        'actual_t1_wins': row['actual_t1_wins'],
        'market_p_t1': row['market_p_t1'],
        'old_model_p_t1': row['model_p_t1'],
        'ipl_v2_p_t1': p_ipl_t1,
        'global_v2_p_t1': p_global_t1,
    })
    
    if idx % 100 == 0:
        print(f'  Processed {idx}/{len(df)}...')

res = pd.DataFrame(results)
valid = res.dropna(subset=['ipl_v2_p_t1'])
print(f'Valid: {len(valid)}/{len(res)}, errors: {errors}')

# === OVERALL COMPARISON ===
print('\n' + '='*70)
print('  MODEL COMPARISON ON LIVE IPL OBSERVATIONS')
print('='*70)
b_mkt = brier(valid['market_p_t1'], valid['actual_t1_wins'])
b_old = brier(valid['old_model_p_t1'], valid['actual_t1_wins'])
b_ipl = brier(valid['ipl_v2_p_t1'], valid['actual_t1_wins'])
b_glb = brier(valid['global_v2_p_t1'], valid['actual_t1_wins'])
print(f'{"Source":<30} {"Brier":>8} {"vs Market":>10}')
print('-'*55)
print(f'{"Market (betx21 exchange)":<30} {b_mkt:.4f}')
print(f'{"Old Global Model":<30} {b_old:.4f}   {(b_old-b_mkt)/b_mkt*100:+.1f}%')
print(f'{"IPL v2 (dedicated model)":<30} {b_ipl:.4f}   {(b_ipl-b_mkt)/b_mkt*100:+.1f}%')
print(f'{"Global + IPL Phase Platt":<30} {b_glb:.4f}   {(b_glb-b_mkt)/b_mkt*100:+.1f}%')

# === PER-PHASE COMPARISON ===
print('\n' + '='*70)
print('  PER-PHASE BRIER SCORE COMPARISON')
print('='*70)
print(f'{"Phase":<18} {"n":>4} {"Market":>8} {"IPL v2":>8} {"Global":>8} {"BestModel":>10} {"Gap":>8}')
print('-'*70)
for inn in [1,2]:
    for phase in ['powerplay','middle','death']:
        sub = valid[(valid['phase']==phase) & (valid['innings']==inn)]
        if len(sub) < 5:
            continue
        b_m = brier(sub['market_p_t1'], sub['actual_t1_wins'])
        b_i = brier(sub['ipl_v2_p_t1'], sub['actual_t1_wins'])
        b_g = brier(sub['global_v2_p_t1'], sub['actual_t1_wins'])
        best = min(b_i, b_g)
        best_name = 'IPL_v2' if b_i <= b_g else 'Global'
        gap = best - b_m
        marker = ' BEATS!' if gap < -0.001 else ' ~match' if abs(gap) < 0.002 else ''
        print(f'  inn{inn} {phase:<12} {len(sub):4d}  {b_m:.4f}  {b_i:.4f}  {b_g:.4f}  {best_name:>8} {gap:+.4f}{marker}')

# === ENSEMBLE ANALYSIS ===
print('\n' + '='*70)
print('  OPTIMAL ENSEMBLE (alpha*model + (1-alpha)*market)')
print('='*70)
print(f'{"Phase":<18} {"Model":>5} {"n":>4} {"Market":>8} {"Blend":>8} {"Alpha":>6} {"Improv":>8}')
print('-'*70)
found_beat = False
for inn in [1,2]:
    for phase in ['powerplay','middle','death']:
        sub = valid[(valid['phase']==phase) & (valid['innings']==inn)]
        if len(sub) < 5:
            continue
        for model_col, mname in [('ipl_v2_p_t1','IPL'), ('global_v2_p_t1','GLB')]:
            def obj(alpha, mc=model_col):
                blend = alpha * sub[mc].values + (1-alpha) * sub['market_p_t1'].values
                return brier(blend, sub['actual_t1_wins'].values)
            res_opt = minimize_scalar(obj, bounds=(0,1), method='bounded')
            b_m = brier(sub['market_p_t1'], sub['actual_t1_wins'])
            if res_opt.fun < b_m - 0.0001:
                found_beat = True
                print(f'  inn{inn} {phase:<8} {mname:>5} {len(sub):4d}  {b_m:.4f}  {res_opt.fun:.4f}  {res_opt.x:.3f}  {res_opt.fun-b_m:+.4f}')

if not found_beat:
    print('  No phase found where blending helps.')

# Save
res.to_parquet('data/ipl_model_vs_market_v2.parquet')
print(f'\nSaved results to data/ipl_model_vs_market_v2.parquet')
