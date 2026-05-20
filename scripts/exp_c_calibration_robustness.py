"""
Experiment C — Calibration Robustness Comparison
Test 6 calibration methods on MID phase predictions.
Train base MID model on pre-2024; compare calibrators on test 2025+2026.
Goal: find which method preserves raw std best while minimising Brier.

Methods:
  1. Isotonic (current, trained on 2024 val — small n)
  2. Isotonic + min-bins (n_samples >= 50 per bin)
  3. Platt scaling (logistic on logit(raw))
  4. Temperature scaling (single param, logit / T)
  5. OOF Isotonic (5-fold on pre-2024 train data — most data)
  6. Rolling-year isotonic (2023 as val, applied to 2024+)
"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, json
from scipy.special import expit, logit
from scipy.optimize import minimize_scalar
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import log_loss, brier_score_loss
from bbl_pipeline.training.blend_model import XGBLRBlend

print("Loading data…")
df = pd.read_parquet("data/ipl_inn2_features_v1/training.parquet")
df["phase_label"] = df["over"].apply(
    lambda o: "PP" if 1<=o<=6 else ("MID" if 7<=o<=15 else "DEATH"))
mid = df[df["phase_label"] == "MID"].copy()

with open("models/ipl_inn2_v1/phase_features.json") as f:
    FEATS = json.load(f)["mid"]

TRAIN_SEASONS  = {s for s in mid["season"].unique() if s < "2024"}
TRAIN23_SEASONS = {s for s in mid["season"].unique() if "2022" <= s < "2024"}  # rolling-year val
VAL_SEASONS    = {"2024"}
TEST_SEASONS   = {"2025", "2026"}

train  = mid[mid["season"].isin(TRAIN_SEASONS)]
train23 = mid[mid["season"].isin(TRAIN23_SEASONS)]
val    = mid[mid["season"].isin(VAL_SEASONS)]
test   = mid[mid["season"].isin(TEST_SEASONS)]
print(f"  Train: {len(train):,}  Train23(rolling-val): {len(train23):,}  Val2024: {len(val):,}  Test: {len(test):,}")

def safe_feats(df_s, feats):
    return df_s[[f for f in feats if f in df_s.columns]].fillna(0)

Xtr   = safe_feats(train,   FEATS).values;  ytr  = train["is_winner"].values
Xtr23 = safe_feats(train23, FEATS).values;  ytr23 = train23["is_winner"].values
Xva   = safe_feats(val,     FEATS).values;  yva  = val["is_winner"].values
Xte   = safe_feats(test,    FEATS).values;  yte  = test["is_winner"].values

# ── train base model ──────────────────────────────────────────────────────────
print("Training base MID model…")
m = XGBLRBlend()
m.fit(Xtr, ytr)

raw_train = m.predict_proba(Xtr)[:, 1]
raw_val   = m.predict_proba(Xva)[:, 1]
raw_test  = m.predict_proba(Xte)[:, 1]
print(f"  Raw test Brier: {np.mean((raw_test - yte)**2):.5f}  std: {raw_test.std():.4f}")

# ── calibrators ───────────────────────────────────────────────────────────────

# 1. Isotonic on 2024 val
def fit_isotonic(raw, y, out_raw=None):
    iso = IsotonicRegression(out_of_bounds="clip")
    iso.fit(raw, y)
    return iso.transform(out_raw if out_raw is not None else raw)

cal1 = fit_isotonic(raw_val, yva, raw_test)

# 2. Isotonic with min-bin size (50 samples per bucket before fitting)
#    Implementation: create monotone intervals with minimum 50 samples
def fit_isotonic_min_bins(raw, y, out_raw, min_bin=50):
    order = np.argsort(raw)
    raw_s, y_s = raw[order], y[order]
    n = len(raw_s)
    # coarsen: bucket every `min_bin` samples, use mean label
    buckets = []
    for i in range(0, n, min_bin):
        chunk_raw = raw_s[i:i+min_bin]
        chunk_y   = y_s[i:i+min_bin]
        buckets.append((chunk_raw.mean(), chunk_y.mean()))
    # apply pool adjacent violators
    from sklearn.isotonic import IsotonicRegression
    bx = np.array([b[0] for b in buckets])
    by = np.array([b[1] for b in buckets])
    iso2 = IsotonicRegression(out_of_bounds="clip")
    iso2.fit(bx, by)
    return iso2.transform(out_raw)

cal2 = fit_isotonic_min_bins(raw_val, yva, raw_test, min_bin=50)

# 3. Platt scaling (logistic regression on logit of raw)
def fit_platt(raw_tr, y_tr, raw_te):
    eps = 1e-6
    X_logit = logit(np.clip(raw_tr, eps, 1-eps)).reshape(-1, 1)
    lr = LogisticRegression(C=1.0)
    lr.fit(X_logit, y_tr)
    X_te_logit = logit(np.clip(raw_te, eps, 1-eps)).reshape(-1, 1)
    return lr.predict_proba(X_te_logit)[:, 1]

cal3 = fit_platt(raw_val, yva, raw_test)

# 4. Temperature scaling (single parameter T: p_cal = sigmoid(logit(p) / T))
def fit_temperature(raw_tr, y_tr, raw_te):
    eps = 1e-6
    log_tr = logit(np.clip(raw_tr, eps, 1-eps))
    def neg_ll(T):
        T = max(T, 0.1)
        p_cal = expit(log_tr / T)
        return log_loss(y_tr, np.clip(p_cal, eps, 1-eps))
    res = minimize_scalar(neg_ll, bounds=(0.5, 3.0), method="bounded")
    T_opt = res.x
    log_te = logit(np.clip(raw_te, eps, 1-eps))
    cal = expit(log_te / T_opt)
    print(f"    Temperature T={T_opt:.4f}")
    return cal

cal4 = fit_temperature(raw_val, yva, raw_test)

# 5. OOF isotonic: 5-fold on ALL pre-2024 training data
#    Build OOF predictions on train, then fit one global isotonic → apply to test
def fit_oof_isotonic(X_tr, y_tr, X_te, n_splits=5):
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    oof_raw = np.zeros(len(X_tr))
    for fold_i, (tr_idx, va_idx) in enumerate(skf.split(X_tr, y_tr)):
        fold_m = XGBLRBlend()
        fold_m.fit(X_tr[tr_idx], y_tr[tr_idx])
        oof_raw[va_idx] = fold_m.predict_proba(X_tr[va_idx])[:, 1]
        print(f"    OOF fold {fold_i+1}/{n_splits} done")
    iso = IsotonicRegression(out_of_bounds="clip")
    iso.fit(oof_raw, y_tr)
    # apply to test with the original model
    return iso.transform(raw_test)

print("Fitting OOF isotonic (3-fold)…")
cal5 = fit_oof_isotonic(Xtr, ytr, Xte, n_splits=3)

# 6. Rolling-year isotonic: train model on pre-2022, val on 2022-2023, test on 2024+
def fit_rolling_year(X_tr23, y_tr23, X_te):
    # fit model on earlier seasons (already fit in m above — we re-use raw_test)
    # Use 2022-2023 as val for calibrator
    m2 = XGBLRBlend()
    # train on everything before 2022
    pre22_mask = mid["season"].isin({s for s in TRAIN_SEASONS if s < "2022"})
    tr22 = safe_feats(mid[pre22_mask], FEATS).values
    y22  = mid[pre22_mask]["is_winner"].values
    m2.fit(tr22, y22)
    # val: 2022-2023
    val22_raw = m2.predict_proba(X_tr23)[:, 1]
    iso6 = IsotonicRegression(out_of_bounds="clip")
    iso6.fit(val22_raw, y_tr23)
    # now we need raw predictions from m2 on test
    raw_te2 = m2.predict_proba(X_te)[:, 1]
    cal = iso6.transform(raw_te2)
    return cal

print("Fitting rolling-year calibrator…")
cal6 = fit_rolling_year(Xtr23, ytr23, Xte)

# ── evaluate ──────────────────────────────────────────────────────────────────
def metrics(p, y):
    p = np.clip(p, 1e-7, 1-1e-7)
    return {
        "brier":   round(float(np.mean((p-y)**2)), 5),
        "logloss": round(float(log_loss(y, p)), 5),
        "std":     round(float(p.std()), 4),
        "mean":    round(float(p.mean()), 4),
        "unc%":    round(float(((p>=0.45)&(p<=0.55)).mean()*100), 1),
        "conf%":   round(float(((p<0.30)|(p>0.70)).mean()*100), 1),
    }

results = {
    "Raw (no calibration)":                 metrics(raw_test, yte),
    "1. Isotonic (val 2024, small n)":       metrics(cal1, yte),
    "2. Isotonic + min-bins 50":             metrics(cal2, yte),
    "3. Platt scaling":                      metrics(cal3, yte),
    "4. Temperature scaling":                metrics(cal4, yte),
    "5. OOF Isotonic (5-fold pre-2024)":     metrics(cal5, yte),
    "6. Rolling-year Isotonic (2022-23 val)":metrics(cal6, yte),
}

print("\n")
print("=" * 110)
print("EXPERIMENT C: CALIBRATION ROBUSTNESS  |  MID Phase  |  Test: 2025+2026")
print("=" * 110)
print(f"\n{'Method':<45} {'Brier':>8} {'LogLoss':>9} {'std':>7} {'mean':>7} {'unc%':>7} {'conf%':>7}")
print("-" * 100)
for name, m_ in results.items():
    print(f"  {name:<43} {m_['brier']:>8.5f} {m_['logloss']:>9.5f} {m_['std']:>7.4f} {m_['mean']:>7.4f} {m_['unc%']:>6.1f}% {m_['conf%']:>6.1f}%")

# what is raw vs best calibrated std?
raw_std = results["Raw (no calibration)"]["std"]
best_brier_method = min(results, key=lambda k: results[k]["brier"])
print(f"\n  Raw std: {raw_std:.4f}  |  Best Brier: '{best_brier_method}' = {results[best_brier_method]['brier']:.5f}")

# Market reference (if available)
try:
    mkt = pd.read_parquet("data/ipl_model_vs_market_v3.parquet")
    mkt_inn2 = mkt[mkt.get("innings_label","").isin(["inn2"]) if "innings_label" in mkt.columns else mkt.index == mkt.index]
    mkt_mid = mkt_inn2[mkt_inn2.get("phase","").isin(["mid","MID"]) if "phase" in mkt_inn2.columns else mkt_inn2.index == mkt_inn2.index]
    if len(mkt_mid) > 0 and "market_prob" in mkt_mid.columns and "is_winner" in mkt_mid.columns:
        mkt_stats = metrics(mkt_mid["market_prob"].values, mkt_mid["is_winner"].values)
        print(f"\n  Market MID reference (n={len(mkt_mid)}): Brier={mkt_stats['brier']:.5f} std={mkt_stats['std']:.4f} unc%={mkt_stats['unc%']}% conf%={mkt_stats['conf%']}%")
except Exception as ex:
    print(f"  (Market data unavailable: {ex})")

import json as js
with open("data/exp_c_calibration_results.json", "w") as f:
    js.dump(results, f, default=str)
print("\nSaved: data/exp_c_calibration_results.json")
