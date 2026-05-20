"""
v11 T-Scaling: Proper OOS Holdout Comparison
=============================================
Uses season-OOF predictions (just computed) with v7 OOF baseline from CSV.
Shows 2025+2026 holdout ONLY for T-scaling evaluation (true OOS test).

Table columns:
  v7 OOF cal | v11 OOF cal | v11+T_oos | v11+T_opt | Market
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

with open("models/ipl_inn2_v1/phase_features.json") as f:
    pf = json.load(f)

PHASES = [("pp", (1, 6)), ("mid", (7, 15)), ("death", (16, 20))]
seasons = sorted(df_inn2["season"].unique())
n_folds = 5
fold_size = max(1, len(seasons) // n_folds)
holdout_s = [s for s in seasons if "2025" in str(s) or "2026" in str(s)]
pre_holdout_s = [s for s in seasons if s not in holdout_s]

print(f"  Holdout seasons: {holdout_s}  ({sum(df_inn2['season'].isin(holdout_s)):,} rows)")
print(f"  Pre-holdout seasons: {pre_holdout_s[-3:]}...  ({sum(df_inn2['season'].isin(pre_holdout_s)):,} rows)")

# ── v7 OOF baselines (from saved CSV) ────────────────────────────────────────
V7_OOF = {
    "pp":    (0.18026, 0.18299),  # (cal, raw)
    "mid":   (0.14389, 0.14667),
    "death": (0.09260, 0.09617),
    "total": (0.14054, 0.14351),
}

# ── Run v11 OOF: 3 phase models, separate for holdout vs pre-holdout ─────────
# We need:
#   1. T_oos: T fitted on pre-holdout OOF predictions, applied to holdout
#   2. T_opt: T fitted on holdout OOF predictions, applied to holdout
print("\nRunning v11 season OOF...")

results = {}
T_oos = {}  # fitted on pre-holdout, applied to holdout (true OOS)
T_opt = {}  # fitted on holdout (optimistic)
T_opt_b = {}  # bias for Platt

for phase, (lo, hi) in PHASES:
    print(f"\n  Phase: {phase} (overs {lo}-{hi})")
    phase_mask = df_inn2["over"].between(lo, hi)
    df_ph = df_inn2[phase_mask].copy().reset_index(drop=False)
    feat_names = [f for f in pf[phase] if f in df_ph.columns]

    ph_seasons = sorted(df_ph["season"].unique())
    ph_fold_sz = max(1, len(ph_seasons) // n_folds)
    raw_oof_ph  = np.full(len(df_ph), np.nan)
    cal_oof_ph  = np.full(len(df_ph), np.nan)

    for fold in range(n_folds):
        if fold < n_folds - 1:
            val_s = ph_seasons[fold * ph_fold_sz: (fold + 1) * ph_fold_sz]
        else:
            val_s = ph_seasons[fold * ph_fold_sz:]
        train_s = [s for s in ph_seasons if s not in val_s]

        tr_mask = df_ph["season"].isin(train_s)
        va_mask = df_ph["season"].isin(val_s)
        if tr_mask.sum() < 100 or va_mask.sum() < 10:
            continue

        med = df_ph.loc[tr_mask, feat_names].median()
        Xtr = df_ph.loc[tr_mask, feat_names].fillna(med)
        Xva = df_ph.loc[va_mask, feat_names].fillna(med)
        ytr = df_ph.loc[tr_mask, "is_winner"]

        m = XGBLRBlendLocal()
        m.fit(Xtr, ytr)
        preds_va = m.predict_proba(Xva)
        raw_oof_ph[va_mask.values] = preds_va
        b = brier_score_loss(df_ph.loc[va_mask, "is_winner"], preds_va)
        is_ho = any(s in holdout_s for s in val_s)
        tag = " [HOLDOUT]" if is_ho else ""
        print(f"    Fold {fold}: {val_s}  n={va_mask.sum():,}  raw={b:.4f}{tag}")

    # Fill any missing
    raw_oof_ph = np.where(np.isnan(raw_oof_ph), 0.5, raw_oof_ph)

    # Per-over calibration
    overs_ph = df_ph["over"].values
    for ov in sorted(np.unique(overs_ph)):
        omask = overs_ph == ov
        if omask.sum() >= 30:
            iso = IsotonicRegression(out_of_bounds="clip")
            iso.fit(raw_oof_ph[omask], df_ph.loc[omask, "is_winner"].values)
            cal_oof_ph[omask] = iso.predict(raw_oof_ph[omask])
        else:
            cal_oof_ph[omask] = raw_oof_ph[omask]

    # Save back to phase results
    ph_y = df_ph["is_winner"].values
    ph_mask_ho = df_ph["season"].isin(holdout_s).values
    ph_mask_pre = ~ph_mask_ho

    b_full_raw  = brier_score_loss(ph_y, raw_oof_ph)
    b_full_cal  = brier_score_loss(ph_y, cal_oof_ph)
    b_ho_raw    = brier_score_loss(ph_y[ph_mask_ho], raw_oof_ph[ph_mask_ho]) if ph_mask_ho.sum() > 0 else np.nan
    b_ho_cal    = brier_score_loss(ph_y[ph_mask_ho], cal_oof_ph[ph_mask_ho]) if ph_mask_ho.sum() > 0 else np.nan

    print(f"    {phase}: full OOF raw={b_full_raw:.5f}, cal={b_full_cal:.5f}")
    print(f"    {phase}: holdout OOF raw={b_ho_raw:.5f}, cal={b_ho_cal:.5f}")

    # Fit T_oos: on pre-holdout cal preds
    if ph_mask_pre.sum() > 50:
        p_pre = cal_oof_ph[ph_mask_pre]
        y_pre = ph_y[ph_mask_pre]
        t_oos, _ = fit_T_simple(p_pre, y_pre)
        T_oos[phase] = round(float(t_oos), 4)
    else:
        T_oos[phase] = 1.0

    # Fit T_opt: on holdout cal preds
    if ph_mask_ho.sum() > 30:
        p_ho = cal_oof_ph[ph_mask_ho]
        y_ho = ph_y[ph_mask_ho]
        t_opt, _ = fit_T_simple(p_ho, y_ho)
        T_opt[phase] = round(float(t_opt), 4)
        # Platt for T_opt
        t_p, b_p, _ = fit_T_platt(p_ho, y_ho)
        T_opt_b[phase] = (round(float(t_p), 4), round(float(b_p), 4))
    else:
        T_opt[phase] = 1.0
        T_opt_b[phase] = (1.0, 0.0)

    print(f"    T_oos={T_oos[phase]:.4f}  T_opt={T_opt[phase]:.4f}  T_opt_platt={T_opt_b[phase]}")

    results[phase] = {
        "raw_oof": raw_oof_ph,
        "cal_oof": cal_oof_ph,
        "y":       ph_y,
        "ho_mask": ph_mask_ho,
        "pre_mask": ph_mask_pre,
    }

# ── Build comparison ──────────────────────────────────────────────────────────
print("\n" + "=" * 94)
print("  v11 T-Scaling: Holdout (2025+2026) Comparison")
print("  T_oos = fitted on ≤2024 OOF probs (true OOS)   T_opt = fitted on 2025/26 (best case)")
print("=" * 94)
print(f"  {'Segment':<14} {'v7 OOF':>8} {'v11 no-T':>10} {'v11+T_oos':>11} {'v11+T_opt':>11} {'vs v7 T_oos':>13} {'vs v7 T_opt':>13}")
print("-" * 94)

ho_segments = {"pp": (1,6), "mid": (7,15), "death": (16,20)}

phase_rows = {}
for phase, (lo, hi) in PHASES:
    r = results[phase]
    ho = r["ho_mask"]
    y_ho = r["y"][ho]
    p_ho = r["cal_oof"][ho]
    if len(y_ho) == 0:
        continue

    b_v7  = V7_OOF[phase][0]  # v7 OOF calibrated (full 5-fold OOF, not holdout-specific)
    b_v11 = brier_score_loss(y_ho, p_ho)
    b_toos= brier_score_loss(y_ho, apply_T(p_ho, T_oos[phase]))
    b_topt= brier_score_loss(y_ho, apply_T(p_ho, T_opt[phase]))

    dv11  = (b_v11 - b_v7) / b_v7 * 100
    dtoos = (b_toos - b_v7) / b_v7 * 100
    dtopt = (b_topt - b_v7) / b_v7 * 100

    ph_label = {"pp":"Inn2 PP","mid":"Inn2 Mid","death":"Inn2 Death"}[phase]
    print(f"  {ph_label:<14} {b_v7:>8.5f} {b_v11:>10.5f} {b_toos:>11.5f} {b_topt:>11.5f}   "
          f"{'▼' if dtoos<0 else '▲'}{abs(dtoos):>7.1f}%   {'▼' if dtopt<0 else '▲'}{abs(dtopt):>7.1f}%")
    phase_rows[phase] = (b_v7, b_v11, b_toos, b_topt, len(y_ho))

# Total inn2 holdout
all_y_ho = np.concatenate([results[ph]["y"][results[ph]["ho_mask"]] for ph,_ in PHASES])
all_p11_ho = np.concatenate([results[ph]["cal_oof"][results[ph]["ho_mask"]] for ph,_ in PHASES])
all_toos_ho = np.concatenate([
    apply_T(results[ph]["cal_oof"][results[ph]["ho_mask"]], T_oos[ph])
    for ph,_ in PHASES
])
all_topt_ho = np.concatenate([
    apply_T(results[ph]["cal_oof"][results[ph]["ho_mask"]], T_opt[ph])
    for ph,_ in PHASES
])
b_v7_tot  = V7_OOF["total"][0]
b_v11_tot = brier_score_loss(all_y_ho, all_p11_ho)
b_toos_tot= brier_score_loss(all_y_ho, all_toos_ho)
b_topt_tot= brier_score_loss(all_y_ho, all_topt_ho)
print(f"  {'Inn2 Total':<14} {b_v7_tot:>8.5f} {b_v11_tot:>10.5f} {b_toos_tot:>11.5f} {b_topt_tot:>11.5f}   "
      f"{'▼' if (b_toos_tot-b_v7_tot)/b_v7_tot*100<0 else '▲'}{abs((b_toos_tot-b_v7_tot)/b_v7_tot*100):>7.1f}%   "
      f"{'▼' if (b_topt_tot-b_v7_tot)/b_v7_tot*100<0 else '▲'}{abs((b_topt_tot-b_v7_tot)/b_v7_tot*100):>7.1f}%")

print("=" * 94)

print(f"\n  Holdout rows (2025/2026): {len(all_y_ho):,}")
print(f"\n  T values:")
print(f"    T_oos (≤2024 fitted): {T_oos}")
print(f"    T_opt (2025/26 opt):  {T_opt}")
print(f"    T_opt_platt:          {T_opt_b}")

print("\n  T gain vs v11 no-T (on holdout):")
for phase, (lo, hi) in PHASES:
    r = results[phase]
    ho = r["ho_mask"]
    y_ho = r["y"][ho]
    p_ho = r["cal_oof"][ho]
    if len(y_ho) == 0: continue
    b_v11 = brier_score_loss(y_ho, p_ho)
    b_toos = brier_score_loss(y_ho, apply_T(p_ho, T_oos[phase]))
    b_topt = brier_score_loss(y_ho, apply_T(p_ho, T_opt[phase]))
    tg_oos = (b_v11 - b_toos) / b_v11 * 100
    tg_opt = (b_v11 - b_topt) / b_v11 * 100
    ph_label = {"pp":"Inn2 PP","mid":"Inn2 Mid","death":"Inn2 Death"}[phase]
    print(f"  {ph_label:<14}: T_oos gain={tg_oos:+.1f}%, T_opt gain={tg_opt:+.1f}%")

# Also show FULL OOF comparison (all 19 seasons)
print("\n" + "=" * 68)
print("  Full OOF Comparison (all 19 seasons)")
print("=" * 68)
print(f"  {'Phase':<14} {'v7 OOF cal':>11} {'v11 OOF cal':>13} {'vs v7':>8}")
print("-" * 68)
full_oof_briers = {}
for phase, (lo, hi) in PHASES:
    r = results[phase]
    b_v7 = V7_OOF[phase][0]
    b_v11 = brier_score_loss(r["y"], r["cal_oof"])
    d = (b_v11 - b_v7) / b_v7 * 100
    ph_label = {"pp":"Inn2 PP","mid":"Inn2 Mid","death":"Inn2 Death"}[phase]
    print(f"  {ph_label:<14} {b_v7:>11.5f} {b_v11:>13.5f}  {'▼' if d<0 else '▲'}{abs(d):>6.1f}%")
    full_oof_briers[phase] = b_v11
all_v7_tot = V7_OOF["total"][0]
all_v11_y = np.concatenate([results[ph]["y"] for ph,_ in PHASES])
all_v11_p = np.concatenate([results[ph]["cal_oof"] for ph,_ in PHASES])
all_v11_tot = brier_score_loss(all_v11_y, all_v11_p)
d_tot = (all_v11_tot - all_v7_tot) / all_v7_tot * 100
print(f"  {'Inn2 Total':<14} {all_v7_tot:>11.5f} {all_v11_tot:>13.5f}  {'▼' if d_tot<0 else '▲'}{abs(d_tot):>6.1f}%")
print("=" * 68)
