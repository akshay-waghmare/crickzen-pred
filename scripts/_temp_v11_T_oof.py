"""
v11 T-Scaling Analysis — Proper Season OOF
==========================================
Runs proper 5-fold season OOF on each phase, saves per-row predictions,
fits T on 2025+2026 folds, outputs full comparison table.

v7 cal | v11 no-T | v11+prodT | v11+shadowT
"""
import sys, json, pickle, warnings
sys.path.insert(0, 'src')
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import joblib
from sklearn.metrics import brier_score_loss
from sklearn.isotonic import IsotonicRegression
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from xgboost import XGBClassifier
from scipy.optimize import minimize_scalar, minimize
from scipy.special import expit

from bbl_pipeline.training.trainer import XGBLogRegEnsemble
from bbl_pipeline.training.blend_model import XGBLRBlend  # noqa: F401

EPS = 1e-9

def logit(p):
    p = np.clip(p, EPS, 1 - EPS)
    return np.log(p / (1 - p))

def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -50, 50)))

def apply_T(p, T, b=0.0):
    return np.clip(sigmoid(logit(p) / T + b), 0.01, 0.99)

def fit_T_simple(p, y):
    res = minimize_scalar(lambda T: brier_score_loss(y, apply_T(p, T)),
                          bounds=(0.3, 2.0), method='bounded')
    return res.x, res.fun

def fit_T_platt(p, y):
    res = minimize(lambda x: brier_score_loss(y, apply_T(p, x[0], x[1])),
                   x0=[1.0, 0.0], method='Nelder-Mead',
                   options={'xatol': 1e-6, 'fatol': 1e-8, 'maxiter': 5000})
    return res.x[0], res.x[1], res.fun


class XGBLRBlendLocal:
    """Local copy to avoid import issues"""
    XGB_PARAMS = dict(
        n_estimators=400, max_depth=5, learning_rate=0.02,
        subsample=0.8, colsample_bytree=0.9, min_child_weight=10,
        reg_alpha=0.5, reg_lambda=1.5, tree_method="hist",
        eval_metric="logloss", n_jobs=-1, verbosity=0, random_state=42,
    )
    def __init__(self):
        self.xgb = XGBClassifier(**self.XGB_PARAMS)
        self.lr = Pipeline([
            ("imp", SimpleImputer(strategy="mean")),
            ("sc",  StandardScaler()),
            ("clf", LogisticRegression(C=0.01, max_iter=1000, random_state=42)),
        ])
    def fit(self, X, y):
        self.xgb.fit(X, y)
        self.lr.fit(X, y)
        return self
    def predict_proba(self, X):
        return 0.5 * self.xgb.predict_proba(X)[:, 1] + 0.5 * self.lr.predict_proba(X)[:, 1]


# ── Load data ─────────────────────────────────────────────────────────────────
print("Loading data...")
df_inn2 = pd.read_parquet("data/ipl_inn2_features_v1/training.parquet")
df_inn2 = df_inn2.sort_values(["match_id", "over", "ball"]).reset_index(drop=True)
df_v7   = pd.read_parquet("data/ipl_features_v7/training.parquet")
df_v7   = df_v7.sort_values(["match_id", "innings", "over", "ball"]).reset_index(drop=True)
print(f"  inn2: {df_inn2.shape}, v7: {df_v7.shape}")

# Load phase features
with open("models/ipl_inn2_v1/phase_features.json") as f:
    pf = json.load(f)

PHASES = [("pp", (1, 6)), ("mid", (7, 15)), ("death", (16, 20))]
seasons = sorted(df_inn2["season"].unique())
n_folds = 5
fold_size = max(1, len(seasons) // n_folds)

# ── v7 OOF calibrated predictions on inn2 ────────────────────────────────────
print("\nLoading v7 model + computing inn2 OOF predictions...")
m7   = joblib.load("models/ipl_v7/champion_model.joblib")
cal7 = joblib.load("models/ipl_v7/isotonic_calibrator.pkl")

df_v7_inn2 = df_v7[df_v7["innings"] == 2].copy()
feats7 = [f for f in m7.selected_features_ if f in df_v7_inn2.columns]
raw7 = m7.predict_proba(df_v7_inn2[feats7].fillna(0))[:, 1]
po7  = cal7.get("per_over_calibrators", {})
iso2 = cal7["calibrator_innings2"]
cal7_p = np.zeros_like(raw7)
for i, (inn, ov) in enumerate(zip(df_v7_inn2["innings"].values, df_v7_inn2["over"].values)):
    key = f"inn{int(inn)}_over{int(ov)}"
    cal7_p[i] = po7[key].predict([raw7[i]])[0] if key in po7 else iso2.predict([raw7[i]])[0]
df_v7_inn2 = df_v7_inn2.copy()
df_v7_inn2["v7_cal"] = cal7_p
df_inn2 = df_inn2.merge(
    df_v7_inn2[["match_id", "over", "ball", "v7_cal"]],
    on=["match_id", "over", "ball"], how="left"
)
df_inn2["v7_cal"] = df_inn2["v7_cal"].fillna(0.5)
print(f"  v7 aligned: {(df_inn2['v7_cal'] != 0.5).sum():,} rows matched")

# ── v11 Season OOF per phase ──────────────────────────────────────────────────
print("\nRunning v11 season OOF (this takes ~3-5 min)...")
v11_oof_raw = np.full(len(df_inn2), np.nan)
v11_oof_cal = np.full(len(df_inn2), np.nan)

for phase, (lo, hi) in PHASES:
    print(f"\n  Phase: {phase} (overs {lo}-{hi})")
    phase_mask = df_inn2["over"].between(lo, hi)
    df_ph = df_inn2[phase_mask].copy().reset_index(drop=False)  # keep original index
    feat_names = [f for f in pf[phase] if f in df_ph.columns]
    print(f"    Rows: {len(df_ph):,}, Features: {len(feat_names)}")

    ph_seasons = sorted(df_ph["season"].unique())
    ph_fold_sz = max(1, len(ph_seasons) // n_folds)
    raw_oof_ph = np.full(len(df_ph), np.nan)

    for fold in range(n_folds):
        if fold < n_folds - 1:
            val_s = ph_seasons[fold * ph_fold_sz: (fold + 1) * ph_fold_sz]
        else:
            val_s = ph_seasons[fold * ph_fold_sz:]
        train_s = [s for s in ph_seasons if s not in val_s]

        tr_mask = df_ph["season"].isin(train_s)
        va_mask = df_ph["season"].isin(val_s)
        if tr_mask.sum() < 100 or va_mask.sum() < 10:
            print(f"      Fold {fold}: skip (tr={tr_mask.sum()}, va={va_mask.sum()})")
            continue

        med = df_ph.loc[tr_mask, feat_names].median()
        Xtr = df_ph.loc[tr_mask, feat_names].fillna(med)
        Xva = df_ph.loc[va_mask, feat_names].fillna(med)
        ytr = df_ph.loc[tr_mask, "is_winner"]

        m = XGBLRBlendLocal()
        m.fit(Xtr, ytr)
        preds = m.predict_proba(Xva)
        raw_oof_ph[va_mask.values] = preds
        b = brier_score_loss(df_ph.loc[va_mask, "is_winner"], preds)
        print(f"      Fold {fold}: val_seasons={val_s}  n={va_mask.sum():,}  raw_brier={b:.4f}")

    # Fill any unfitted rows with median prob
    nan_mask = np.isnan(raw_oof_ph)
    if nan_mask.sum() > 0:
        print(f"    WARNING: {nan_mask.sum()} rows without OOF preds (filled with 0.5)")
        raw_oof_ph[nan_mask] = 0.5

    # Per-over calibration on full OOF
    overs_ph = df_ph["over"].values
    cal_oof_ph = np.zeros_like(raw_oof_ph)
    for ov in sorted(np.unique(overs_ph)):
        omask = overs_ph == ov
        if omask.sum() >= 30:
            iso = IsotonicRegression(out_of_bounds="clip")
            iso.fit(raw_oof_ph[omask], df_ph.loc[omask, "is_winner"].values)
            cal_oof_ph[omask] = iso.predict(raw_oof_ph[omask])
        else:
            cal_oof_ph[omask] = raw_oof_ph[omask]

    # Write back to main arrays (using original indices)
    orig_idx = df_ph["index"].values
    v11_oof_raw[orig_idx] = raw_oof_ph
    v11_oof_cal[orig_idx] = cal_oof_ph

    ph_y = df_ph["is_winner"].values
    b_raw = brier_score_loss(ph_y[~np.isnan(raw_oof_ph)], raw_oof_ph[~np.isnan(raw_oof_ph)])
    b_cal = brier_score_loss(ph_y, cal_oof_ph)
    print(f"    {phase} raw OOF: {b_raw:.5f}, cal OOF: {b_cal:.5f}")

df_inn2["v11_oof_raw"] = v11_oof_raw
df_inn2["v11_oof_cal"] = v11_oof_cal

# Fill remaining nans (rows outside all phase ranges)
df_inn2["v11_oof_cal"] = df_inn2["v11_oof_cal"].fillna(0.5)
df_inn2["v11_oof_raw"] = df_inn2["v11_oof_raw"].fillna(0.5)

# ── Fit T on 2025+2026 OOF predictions ───────────────────────────────────────
holdout_s = [s for s in seasons if "2025" in str(s) or "2026" in str(s)]
ho_mask   = df_inn2["season"].isin(holdout_s)
print(f"\nFitting T on 2025+2026 OOF ({ho_mask.sum():,} rows, seasons={holdout_s})")

T_prod = {}
T_shadow = {}
B_shadow = {}
for phase, (lo, hi) in PHASES:
    mask = ho_mask & df_inn2["over"].between(lo, hi)
    n = mask.sum()
    if n < 30:
        T_prod[phase] = 1.0; T_shadow[phase] = 1.0; B_shadow[phase] = 0.0
        print(f"  {phase}: only {n} holdout rows → T=1.0")
        continue
    p = df_inn2.loc[mask, "v11_oof_cal"].values
    y = df_inn2.loc[mask, "is_winner"].values
    t_s, b_s = fit_T_simple(p, y)
    t_p, b_p, b_platt = fit_T_platt(p, y)
    T_prod[phase]   = round(float(t_s), 4)
    T_shadow[phase] = round(float(t_p), 4)
    B_shadow[phase] = round(float(b_p), 4)
    print(f"  {phase}: T_simple={t_s:.4f} brier={b_s:.5f} | Platt T={t_p:.4f} b={b_p:.4f} brier={b_platt:.5f} | n={n}")

# Apply T to full dataset
v11_prodT   = df_inn2["v11_oof_cal"].values.copy()
v11_shadowT = df_inn2["v11_oof_cal"].values.copy()
for phase, (lo, hi) in PHASES:
    mask = df_inn2["over"].between(lo, hi).values
    v11_prodT[mask]   = apply_T(v11_prodT[mask],   T_prod[phase])
    v11_shadowT[mask] = apply_T(v11_shadowT[mask], T_shadow[phase], B_shadow[phase])

df_inn2["v11_prodT"]   = v11_prodT
df_inn2["v11_shadowT"] = v11_shadowT

# ── Full comparison table ─────────────────────────────────────────────────────
segments = [
    ("Inn2 PP",    df_inn2["over"].between(1, 6)),
    ("Inn2 Mid",   df_inn2["over"].between(7, 15)),
    ("Inn2 Death", df_inn2["over"].between(16, 20)),
    ("Inn2 Total", pd.Series([True] * len(df_inn2))),
]

print("\n" + "=" * 92)
print(f"  v11 T-Scaling Analysis (Season OOF, {len(df_inn2):,} inn2 rows)")
print("=" * 92)
print(f"  {'Phase':<13} {'v7 cal':>9} {'v11 no-T':>10} {'v11+prodT':>11} {'v11+shadow':>12} {'prodT vs v7':>13} {'T gain':>8}")
print("-" * 92)

for label, mask in segments:
    y    = df_inn2.loc[mask, "is_winner"].values
    v7   = df_inn2.loc[mask, "v7_cal"].values
    v11  = df_inn2.loc[mask, "v11_oof_cal"].values
    pt   = df_inn2.loc[mask, "v11_prodT"].values
    st   = df_inn2.loc[mask, "v11_shadowT"].values
    b_v7 = brier_score_loss(y, v7)
    b_v11= brier_score_loss(y, v11)
    b_pt = brier_score_loss(y, pt)
    b_st = brier_score_loss(y, st)
    dpt  = (b_pt  - b_v7) / b_v7 * 100
    dst  = (b_st  - b_v7) / b_v7 * 100
    tg_p = (b_v11 - b_pt)  / b_v11 * 100
    arr_pt = "▼" if dpt < 0 else "▲"
    print(f"  {label:<13} {b_v7:>9.5f} {b_v11:>10.5f} {b_pt:>11.5f} {b_st:>12.5f}   {arr_pt}{abs(dpt):>8.1f}%  {tg_p:>+7.2f}%")

print("=" * 92)
print(f"\n  T_prod (simple):  {T_prod}")
print(f"  T_shadow (Platt): {T_shadow}")
print(f"  B_shadow (bias):  {B_shadow}")

print("\n  Reference (from oof_calibrated_results.csv):")
print("   PP:    v7=0.18026  v11=0.17043  (-5.5%)")
print("   Mid:   v7=0.14389  v11=0.13067  (-9.2%)")
print("   Death: v7=0.09260  v11=0.07708  (-16.8%)")
print("  (Above use XGBLRBlend per fold vs champion model here — small delta expected)")
