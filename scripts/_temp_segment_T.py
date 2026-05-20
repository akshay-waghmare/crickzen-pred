"""
Find optimal T per-segment (Inn1 PP, Inn2 Mid) on 2026 holdout.
Same train/calibrate/test split as _temp_find_T_vs_market.py
"""
import pandas as pd
import numpy as np
import sys, time
sys.path.insert(0, 'src')
from sklearn.metrics import brier_score_loss, log_loss
from sklearn.isotonic import IsotonicRegression
from scipy.special import expit, logit
from scipy.optimize import minimize_scalar
from bbl_pipeline.training.trainer import XGBLogRegEnsemble

# ── Load & split ──────────────────────────────────────────────────────────────
df = pd.read_parquet('data/ipl_features_v7/training.parquet')
df['season_int'] = pd.to_numeric(df['season'].str.split('/').str[0], errors='coerce')

train_df = df[df['season_int'] <= 2024].copy()
cal_df   = df[df['season_int'] == 2025].copy()
test_df  = df[df['season_int'] == 2026].copy()

feats = [f for f in XGBLogRegEnsemble.TOP_FEATURES if f in train_df.columns]
target = 'is_winner'

# ── Train ≤2024 ───────────────────────────────────────────────────────────────
print("Training on ≤2024...")
t0 = time.time()
model = XGBLogRegEnsemble(xgb_weight=0.5, n_features=len(feats))
model.fit(train_df[feats].fillna(0), train_df[target].values)
print(f"  Done in {time.time()-t0:.1f}s")

# ── Fit per-over calibrators on 2025 ─────────────────────────────────────────
raw_cal = model.predict_proba(cal_df[feats].fillna(0))[:, 1]
inn_cal = cal_df['innings'].values
ov_cal  = cal_df['over'].values
y_cal   = cal_df[target].values

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
    return np.clip(expit(logit(np.clip(p, 0.01, 0.99)) / T), 0.01, 0.99)

# ── Predict on 2026 ───────────────────────────────────────────────────────────
raw_test = model.predict_proba(test_df[feats].fillna(0))[:, 1]
cal_test = apply_cals(raw_test, test_df['innings'].values, test_df['over'].values)
test_df = test_df.copy()
test_df['raw_p']  = raw_test
test_df['cal_p']  = cal_test

per_over_test = (
    test_df.sort_values(['match_id', 'innings', 'over', 'ball'])
    .groupby(['match_id', 'innings', 'over'])
    .last()
    .reset_index()
)[['match_id', 'innings', 'over', 'raw_p', 'cal_p', 'is_winner', 'batting_team']]
per_over_test.rename(columns={'batting_team': 'batting_team_id'}, inplace=True)

# ── Merge with market ─────────────────────────────────────────────────────────
mkt = pd.read_parquet('data/ipl_market_vs_model_corrected_2026.parquet')
mkt['match_id'] = mkt['cs_match_id'].astype(str)

merged = per_over_test.merge(
    mkt[['match_id', 'innings', 'over', 'market_p_inn1', 'actual_inn1_wins', 'inn1_team']],
    on=['match_id', 'innings', 'over'], how='inner'
)
merged['is_inn1_batting'] = (merged['batting_team_id'] == merged['inn1_team']).astype(int)
merged['market_p']      = np.where(merged['is_inn1_batting']==1, merged['market_p_inn1'], 1-merged['market_p_inn1'])
merged['actual_outcome'] = np.where(merged['is_inn1_batting']==1, merged['actual_inn1_wins'], 1-merged['actual_inn1_wins'])

inn_m  = merged['innings'].values
ov_m   = merged['over'].values
y_mkt  = merged['actual_outcome'].values
mkt_p  = np.clip(merged['market_p'].values, 0.01, 0.99)
cal_p  = merged['cal_p'].values

# ── Segments of interest ──────────────────────────────────────────────────────
segments = {
    'Inn1 PP':    (inn_m == 1) & (ov_m <= 5),
    'Inn1 Mid':   (inn_m == 1) & (ov_m > 5) & (ov_m <= 14),
    'Inn1 Death': (inn_m == 1) & (ov_m > 14),
    'Inn2 PP':    (inn_m == 2) & (ov_m <= 5),
    'Inn2 Mid':   (inn_m == 2) & (ov_m > 5) & (ov_m <= 14),
    'Inn2 Death': (inn_m == 2) & (ov_m > 14),
    'Overall':    np.ones(len(y_mkt), bool),
}

print(f"\n{'='*75}")
print(f"  SEGMENT-SPECIFIC OPTIMAL T — searching 0.30 to 1.50")
print(f"{'='*75}")
print(f"  {'Segment':15s}  {'n':>5}  {'Mkt Brier':>10}  {'T=1 Brier':>10}  {'Opt T':>7}  {'Opt Brier':>10}  {'vs Mkt':>8}  dir")
print(f"  {'-'*73}")

optimal_Ts = {}
for seg_name, mask in segments.items():
    if mask.sum() < 15:
        continue
    ym   = y_mkt[mask]
    pm   = mkt_p[mask]
    pc   = cal_p[mask]

    res = minimize_scalar(
        lambda T: brier_score_loss(ym, apply_temp(pc, T)),
        bounds=(0.30, 1.50), method='bounded'
    )
    T_opt = res.x
    optimal_Ts[seg_name] = T_opt

    b_mkt   = brier_score_loss(ym, pm)
    b_t1    = brier_score_loss(ym, pc)                   # T=1.0
    b_opt   = brier_score_loss(ym, apply_temp(pc, T_opt))
    vs_mkt  = (b_opt - b_mkt) / b_mkt * 100
    direction = "sharper↑" if T_opt < 1.0 else "softer↓ "
    beat = "✅" if b_opt < b_mkt else "❌"
    print(f"  {seg_name:15s}  {mask.sum():>5}  {b_mkt:.4f}  {b_t1:.4f}  {T_opt:.3f}  {b_opt:.4f}  {vs_mkt:+.1f}%  {direction} {beat}")

# ── Detailed T sweep for all Inn2 segments ────────────────────────────────────
for seg_name in ['Inn2 PP', 'Inn2 Mid', 'Inn2 Death']:
    mask = segments[seg_name]
    ym   = y_mkt[mask]
    pm   = mkt_p[mask]
    pc   = cal_p[mask]

    print(f"\n  Detailed T sweep — {seg_name} (n={mask.sum()})")
    print(f"  {'T':>6}  {'Brier':>8}  {'vs Mkt':>8}  {'Std(p)':>8}")
    for T in [0.50, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.20, 1.30, 1.40, 1.50]:
        p_s = apply_temp(pc, T)
        b   = brier_score_loss(ym, p_s)
        vm  = (b - brier_score_loss(ym, pm)) / brier_score_loss(ym, pm) * 100
        marker = " ◄ current" if T == 1.00 else (f" ◄ optimal" if abs(T - optimal_Ts.get(seg_name, 99)) < 0.03 else "")
        print(f"  {T:.2f}  {b:.4f}  {vm:+.1f}%  {p_s.std():.4f}{marker}")

# ── What does combining segment Ts look like? ─────────────────────────────────
print(f"\n  {'='*65}")
print(f"  COMBINED: apply segment-specific T to each ball")
print(f"  {'='*65}")

p_combined = cal_p.copy()
seg_map = {
    'Inn1 PP':    (inn_m == 1) & (ov_m <= 5),
    'Inn1 Mid':   (inn_m == 1) & (ov_m > 5)  & (ov_m <= 14),
    'Inn1 Death': (inn_m == 1) & (ov_m > 14),
    'Inn2 PP':    (inn_m == 2) & (ov_m <= 5),
    'Inn2 Mid':   (inn_m == 2) & (ov_m > 5)  & (ov_m <= 14),
    'Inn2 Death': (inn_m == 2) & (ov_m > 14),
}
for seg_name, mask in seg_map.items():
    if seg_name in optimal_Ts and mask.sum() > 0:
        p_combined[mask] = apply_temp(cal_p[mask], optimal_Ts[seg_name])

b_combined = brier_score_loss(y_mkt, p_combined)
b_t1       = brier_score_loss(y_mkt, cal_p)
b_mkt_all  = brier_score_loss(y_mkt, mkt_p)

print(f"  Market T=1.0:          Brier = {b_mkt_all:.4f}")
print(f"  Model  T=1.0:          Brier = {b_t1:.4f}  ({(b_t1-b_mkt_all)/b_mkt_all*100:+.1f}% vs mkt)")
print(f"  Model  seg-T optimal:  Brier = {b_combined:.4f}  ({(b_combined-b_mkt_all)/b_mkt_all*100:+.1f}% vs mkt)")
print(f"  Improvement vs T=1.0: {(b_combined-b_t1)/b_t1*100:+.2f}%")
print()
print("  Optimal T values per segment:")
for seg, T in optimal_Ts.items():
    print(f"    {seg:15s}: T={T:.3f}")
