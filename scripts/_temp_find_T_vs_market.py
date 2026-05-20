"""
Proper 3-way temporal split with market comparison:
  Train:     seasons <= 2024  (model weights)
  Calibrate: 2025             (per-over isotonic calibrators on unseen predictions)
  Test:      2026             (true holdout — compare vs Betfair market at various T)
"""
import pandas as pd
import numpy as np
import joblib, sys, time
sys.path.insert(0, 'src')
from sklearn.metrics import brier_score_loss, log_loss
from sklearn.isotonic import IsotonicRegression
from scipy.special import expit
from scipy.optimize import minimize_scalar
from bbl_pipeline.training.trainer import XGBLogRegEnsemble

# ── Load features ─────────────────────────────────────────────────────────────
df = pd.read_parquet('data/ipl_features_v7/training.parquet')
df['season_int'] = pd.to_numeric(df['season'].str.split('/').str[0], errors='coerce')

train_df = df[df['season_int'] <= 2024].copy()
cal_df   = df[df['season_int'] == 2025].copy()
test_df  = df[df['season_int'] == 2026].copy()

print(f"Train   : {len(train_df):>7,} rows | 2008–2024 | {train_df['match_id'].nunique()} matches")
print(f"Calibrate: {len(cal_df):>6,} rows | 2025      | {cal_df['match_id'].nunique()} matches")
print(f"Test    : {len(test_df):>7,} rows | 2026      | {test_df['match_id'].nunique()} matches")

# ── 1. Train model on ≤2024 ───────────────────────────────────────────────────
feats = [f for f in XGBLogRegEnsemble.TOP_FEATURES if f in train_df.columns]
print(f"\nFeatures: {len(feats)} — {feats}")

target = 'is_winner'
X_train = train_df[feats].fillna(0)
y_train = train_df[target].values

print("\nTraining model on ≤2024...")
t0 = time.time()
model = XGBLogRegEnsemble(xgb_weight=0.5, n_features=len(feats))
model.fit(X_train, y_train)
print(f"  Done in {time.time()-t0:.1f}s")

# ── 2. Calibrate on 2025 (per-over isotonic) ─────────────────────────────────
X_cal   = cal_df[feats].fillna(0)
y_cal   = cal_df[target].values
inn_cal = cal_df['innings'].values
ov_cal  = cal_df['over'].values

raw_cal = model.predict_proba(X_cal)[:, 1]

per_over_cals = {}
for inn_n in [1, 2]:
    for ov in range(0, 20):
        mask = (inn_cal == inn_n) & (ov_cal == ov)
        if mask.sum() >= 20:
            iso = IsotonicRegression(y_min=0.01, y_max=0.99, out_of_bounds='clip')
            iso.fit(raw_cal[mask], y_cal[mask])
            per_over_cals[f"inn{inn_n}_over{ov}"] = iso

iso_fb1 = IsotonicRegression(y_min=0.01, y_max=0.99, out_of_bounds='clip')
iso_fb2 = IsotonicRegression(y_min=0.01, y_max=0.99, out_of_bounds='clip')
iso_fb1.fit(raw_cal[inn_cal == 1], y_cal[inn_cal == 1])
iso_fb2.fit(raw_cal[inn_cal == 2], y_cal[inn_cal == 2])
print(f"  Fitted {len(per_over_cals)} per-over calibrators on 2025 data")

def apply_cals(raw, inn_arr, ov_arr):
    out = np.zeros_like(raw)
    for i in range(len(raw)):
        key = f"inn{int(inn_arr[i])}_over{int(ov_arr[i])}"
        if key in per_over_cals:
            out[i] = per_over_cals[key].predict([raw[i]])[0]
        elif int(inn_arr[i]) == 1:
            out[i] = iso_fb1.predict([raw[i]])[0]
        else:
            out[i] = iso_fb2.predict([raw[i]])[0]
    return out

def apply_temp(p, T):
    logits = np.log(p / (1 - p + 1e-9))
    return np.clip(expit(logits / T), 0.01, 0.99)

# ── 3. Predict on 2026 ────────────────────────────────────────────────────────
X_test   = test_df[feats].fillna(0)
inn_test = test_df['innings'].values
ov_test  = test_df['over'].values

raw_test = model.predict_proba(X_test)[:, 1]
cal_test = apply_cals(raw_test, inn_test, ov_test)

# ── 4. Aggregate to per-over (last ball of each over) for market comparison ───
test_df = test_df.copy()
test_df['raw_p']  = raw_test
test_df['cal_p']  = cal_test

# Group by match_id + innings + over → take last ball
per_over_test = (
    test_df.sort_values(['match_id', 'innings', 'over', 'ball'])
    .groupby(['match_id', 'innings', 'over'])
    .last()
    .reset_index()
)[['match_id', 'innings', 'over', 'raw_p', 'cal_p', 'is_winner', 'batting_team']]
per_over_test = per_over_test.rename(columns={'batting_team': 'batting_team_id'})

print(f"\n2026 per-over rows: {len(per_over_test)}")

# ── 5. Load market data and merge ─────────────────────────────────────────────
mkt = pd.read_parquet('data/ipl_market_vs_model_corrected_2026.parquet')
mkt['match_id'] = mkt['cs_match_id'].astype(str)

# market_p_inn1 is probability for inn1 team — convert to perspective of batting team
# In the features test_df, is_winner=1 means batting team wins
# Per-over: check if batting team is inn1 team
merged = per_over_test.merge(
    mkt[['match_id', 'innings', 'over', 'market_p_inn1', 'actual_inn1_wins', 'inn1_team']],
    on=['match_id', 'innings', 'over'],
    how='inner'
)

# Align market prob to batting team perspective
# If batting team == inn1 team: market_p_batting = market_p_inn1
# If batting team == inn2 team: market_p_batting = 1 - market_p_inn1
merged['is_inn1_batting'] = (merged['batting_team_id'] == merged['inn1_team']).astype(int)
merged['market_p'] = np.where(
    merged['is_inn1_batting'] == 1,
    merged['market_p_inn1'],
    1 - merged['market_p_inn1']
)
merged['actual_outcome'] = np.where(
    merged['is_inn1_batting'] == 1,
    merged['actual_inn1_wins'],
    1 - merged['actual_inn1_wins']
)

print(f"Merged rows: {len(merged)} | matches: {merged['match_id'].nunique()}")
y_mkt = merged['actual_outcome'].values
market_p = np.clip(merged['market_p'].values, 0.01, 0.99)
cal_p_mkt = merged['cal_p'].values

# ── 6. Optimal T vs actual outcomes ──────────────────────────────────────────
res = minimize_scalar(
    lambda T: brier_score_loss(y_mkt, apply_temp(cal_p_mkt, T)),
    bounds=(0.4, 1.5), method='bounded'
)
opt_T = res.x

print(f"\n{'='*65}")
print(f"  RESULTS: Model (≤2024 train, 2025 calibrate) vs Market on 2026")
print(f"{'='*65}")
print(f"  Optimal T (minimize Brier vs actual): {opt_T:.3f}")
print(f"\n  {'Source':20s}  {'Brier':>8}  {'LogLoss':>8}  {'Std(p)':>8}  note")
print(f"  {'-'*60}")

mkt_brier = brier_score_loss(y_mkt, market_p)
mkt_ll    = log_loss(y_mkt, market_p)
print(f"  {'Betfair market':20s}  {mkt_brier:.4f}  {mkt_ll:.4f}  {market_p.std():.4f}  baseline")

for T in [0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00]:
    p_s = apply_temp(cal_p_mkt, T)
    b   = brier_score_loss(y_mkt, p_s)
    ll  = log_loss(y_mkt, p_s)
    vs_mkt = (b - mkt_brier) / mkt_brier * 100
    opt_mark = ' ◄ optimal' if abs(T - round(opt_T, 2)) < 0.03 else (' ◄ current' if T == 1.00 else '')
    vs_str = f'{vs_mkt:+.1f}% vs mkt'
    print(f"  Model T={T:.2f}             {b:.4f}  {ll:.4f}  {p_s.std():.4f}  {vs_str}{opt_mark}")

# ── 7. Segment breakdown at optimal T ─────────────────────────────────────────
p_opt = apply_temp(cal_p_mkt, opt_T)
p_cur = cal_p_mkt

print(f"\n  SEGMENT BREAKDOWN — T={opt_T:.2f} vs T=1.00 vs Market")
print(f"  {'Segment':20s}  {'Market':>8}  {'T=1.00':>8}  {'T={:.2f}'.format(opt_T):>8}  {'Delta':>8}  n")
inn_m  = merged['innings'].values
ov_m   = merged['over'].values

segs = {
    'Overall':    np.ones(len(y_mkt), bool),
    'Inn1':       inn_m == 1,
    'Inn2':       inn_m == 2,
    'Inn1 PP':    (inn_m==1) & (ov_m<=5),
    'Inn1 Mid':   (inn_m==1) & (ov_m>5) & (ov_m<=14),
    'Inn1 Death': (inn_m==1) & (ov_m>14),
    'Inn2 PP':    (inn_m==2) & (ov_m<=5),
    'Inn2 Mid':   (inn_m==2) & (ov_m>5) & (ov_m<=14),
    'Inn2 Death': (inn_m==2) & (ov_m>14),
}
for seg, mask in segs.items():
    if mask.sum() < 10: continue
    b_mkt  = brier_score_loss(y_mkt[mask], market_p[mask])
    b_cur  = brier_score_loss(y_mkt[mask], p_cur[mask])
    b_opt  = brier_score_loss(y_mkt[mask], p_opt[mask])
    d = b_opt - b_cur
    vs_m = '✅' if b_opt < b_mkt else '❌'
    print(f"  {seg:20s}  {b_mkt:.4f}  {b_cur:.4f}  {b_opt:.4f}  {d:+.4f}  {vs_m} vs mkt  n={mask.sum()}")

# ── 8. Match-level summary ────────────────────────────────────────────────────
print(f"\n  PER-MATCH BRIER (T={opt_T:.2f} vs Market)")
print(f"  {'Match':12s}  {'Market':>8}  {'Model':>8}  {'Diff':>8}")
for mid, grp in merged.groupby('match_id'):
    ym = grp['actual_outcome'].values
    pm = np.clip(grp['market_p'].values, 0.01, 0.99)
    po = apply_temp(grp['cal_p'].values, opt_T)
    bm = brier_score_loss(ym, pm)
    bo = brier_score_loss(ym, po)
    mark = '✅' if bo < bm else '❌'
    print(f"  {mid:12s}  {bm:.4f}  {bo:.4f}  {bo-bm:+.4f} {mark}")
