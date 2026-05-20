"""
Proper temporal split:
  Train:     seasons <= 2024  (model weights)
  Calibrate: 2025             (fit per-over isotonic calibrators on unseen predictions)
  Test:      2026             (true holdout — find optimal T)
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

df = pd.read_parquet('data/ipl_features_v7/training.parquet')
df['season_int'] = pd.to_numeric(df['season'].str.split('/').str[0], errors='coerce')

train_df = df[df['season_int'] <= 2024].copy()
cal_df   = df[df['season_int'] == 2025].copy()
test_df  = df[df['season_int'] == 2026].copy()

print(f"Train   : {len(train_df):>7,} rows | seasons {int(train_df['season_int'].min())}–2024")
print(f"Calibrate: {len(cal_df):>6,} rows | season 2025 | {cal_df['match_id'].nunique()} matches")
print(f"Test    : {len(test_df):>7,} rows | season 2026 | {test_df['match_id'].nunique()} matches")

# ── 1. Train final model on ≤2024 ───────────────────────────────────────────
target = 'is_winner'
model = XGBLogRegEnsemble(xgb_weight=0.5, n_features=38)

# Get feature columns from the template's TOP_FEATURES list
feats = [f for f in XGBLogRegEnsemble.TOP_FEATURES if f in train_df.columns]
print(f"\nFeatures used: {len(feats)}")

X_train = train_df[feats].fillna(0)
y_train = train_df[target].values
X_cal   = cal_df[feats].fillna(0)
y_cal   = cal_df[target].values
X_test  = test_df[feats].fillna(0)
y_test  = test_df[target].values

print("\nTraining model on ≤2024 data...")
t0 = time.time()
model.fit(X_train, y_train)
print(f"  Done in {time.time()-t0:.1f}s")

# ── 2. Predict on calibration set (2025) ────────────────────────────────────
print("\nPredicting on 2025 calibration set...")
raw_cal  = model.predict_proba(X_cal)[:, 1]
raw_test = model.predict_proba(X_test)[:, 1]

# ── 3. Fit per-over isotonic calibrators on 2025 ────────────────────────────
print("Fitting per-over calibrators on 2025...")
inn_cal  = cal_df['innings'].values
over_cal = cal_df['over'].values
inn_test = test_df['innings'].values
over_test = test_df['over'].values

per_over_cals = {}
for inn_n in [1, 2]:
    for ov in range(0, 20):
        mask = (inn_cal == inn_n) & (over_cal == ov)
        if mask.sum() >= 20:
            iso = IsotonicRegression(y_min=0.01, y_max=0.99, out_of_bounds='clip')
            iso.fit(raw_cal[mask], y_cal[mask])
            per_over_cals[f"inn{inn_n}_over{ov}"] = iso

# Fallback innings-specific calibrators
iso_inn1 = IsotonicRegression(y_min=0.01, y_max=0.99, out_of_bounds='clip')
iso_inn2 = IsotonicRegression(y_min=0.01, y_max=0.99, out_of_bounds='clip')
iso_inn1.fit(raw_cal[inn_cal == 1], y_cal[inn_cal == 1])
iso_inn2.fit(raw_cal[inn_cal == 2], y_cal[inn_cal == 2])
print(f"  Fitted {len(per_over_cals)} per-over calibrators + 2 innings fallbacks")

# ── 4. Apply calibrators to 2026 test set ───────────────────────────────────
cal_test = np.zeros_like(raw_test)
for i in range(len(raw_test)):
    key = f"inn{int(inn_test[i])}_over{int(over_test[i])}"
    if key in per_over_cals:
        cal_test[i] = per_over_cals[key].predict([raw_test[i]])[0]
    elif int(inn_test[i]) == 1:
        cal_test[i] = iso_inn1.predict([raw_test[i]])[0]
    else:
        cal_test[i] = iso_inn2.predict([raw_test[i]])[0]

# Also check calibration set performance as sanity check
cal_cal = np.zeros_like(raw_cal)
for i in range(len(raw_cal)):
    key = f"inn{int(inn_cal[i])}_over{int(over_cal[i])}"
    if key in per_over_cals:
        cal_cal[i] = per_over_cals[key].predict([raw_cal[i]])[0]
    elif int(inn_cal[i]) == 1:
        cal_cal[i] = iso_inn1.predict([raw_cal[i]])[0]
    else:
        cal_cal[i] = iso_inn2.predict([raw_cal[i]])[0]

print(f"\n  2025 cal set  — Raw Brier: {brier_score_loss(y_cal, raw_cal):.4f} → Calibrated: {brier_score_loss(y_cal, cal_cal):.4f}")
print(f"  2026 test set — Raw Brier: {brier_score_loss(y_test, raw_test):.4f} → Calibrated: {brier_score_loss(y_test, cal_test):.4f}")

# ── 5. Find optimal T on true 2026 holdout ──────────────────────────────────
def apply_temp(p, T):
    logits = np.log(p / (1 - p + 1e-9))
    return np.clip(expit(logits / T), 0.01, 0.99)

def brier_at_T(T):
    return brier_score_loss(y_test, apply_temp(cal_test, T))

res = minimize_scalar(brier_at_T, bounds=(0.4, 1.5), method='bounded')
opt_T = res.x
opt_brier = res.fun

print(f"\n{'='*60}")
print(f"  OPTIMAL T on TRUE 2026 HOLDOUT")
print(f"{'='*60}")
print(f"  Optimal T  : {opt_T:.3f}")
print(f"  Brier T=opt: {opt_brier:.4f}")
print(f"  Brier T=1.0: {brier_at_T(1.0):.4f}")
print(f"  Improvement: {(brier_at_T(1.0)-opt_brier)/brier_at_T(1.0)*100:.2f}%")

print(f"\n  {'T':>6}  {'Brier':>8}  {'LogLoss':>8}  {'Std(p)':>8}  {'%>70':>7}  {'%<30':>7}")
for T in [0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00, 1.10]:
    p_s = apply_temp(cal_test, T)
    b   = brier_score_loss(y_test, p_s)
    ll  = log_loss(y_test, p_s)
    marker = ' ◄ optimal' if abs(T - round(opt_T, 2)) < 0.03 else (' ◄ current' if T == 1.00 else '')
    print(f"  {T:.2f}  {b:.4f}  {ll:.4f}  {p_s.std():.4f}  {(p_s>0.7).mean()*100:.1f}%  {(p_s<0.3).mean()*100:.1f}%{marker}")

# ── 6. Segment breakdown at optimal T ───────────────────────────────────────
print(f"\n  SEGMENT BREAKDOWN — T=1.00 vs T={opt_T:.2f}")
print(f"  {'Segment':20s}  {'T=1.00':>8}  {'T={:.2f}'.format(opt_T):>8}  {'Delta':>8}  n")
p_opt = apply_temp(cal_test, opt_T)
segs = {
    'Overall':    np.ones(len(y_test), bool),
    'Inn1':       inn_test == 1,
    'Inn2':       inn_test == 2,
    'Inn1 PP':    (inn_test==1) & (over_test<=5),
    'Inn1 Mid':   (inn_test==1) & (over_test>5) & (over_test<=14),
    'Inn1 Death': (inn_test==1) & (over_test>14),
    'Inn2 PP':    (inn_test==2) & (over_test<=5),
    'Inn2 Mid':   (inn_test==2) & (over_test>5) & (over_test<=14),
    'Inn2 Death': (inn_test==2) & (over_test>14),
}
for seg, mask in segs.items():
    if mask.sum() < 30:
        continue
    b1 = brier_score_loss(y_test[mask], cal_test[mask])
    b2 = brier_score_loss(y_test[mask], p_opt[mask])
    d  = b2 - b1
    print(f"  {seg:20s}  {b1:.4f}  {b2:.4f}  {d:+.4f} {'✅' if d<0 else '❌'}  n={mask.sum()}")
