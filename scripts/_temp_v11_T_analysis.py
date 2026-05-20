"""
v11 T-Scaling Full Analysis
===========================
Shows: v7 calibrated | v11 no-T | v11+prodT | v11+shadowT
Per segment: Inn2 PP / Inn2 Mid / Inn2 Death / Inn2 Total

T values fitted on 2025+2026 holdout.
"""
import sys, pickle, json, warnings
sys.path.insert(0, 'src')
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import joblib
from sklearn.metrics import brier_score_loss
from scipy.optimize import minimize_scalar, minimize
from scipy.special import expit

# ── Must import before joblib.load() to unpickle both model classes ──────────
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
    """Fit single T (no bias)"""
    res = minimize_scalar(
        lambda T: brier_score_loss(y, apply_T(p, T)),
        bounds=(0.3, 2.0), method='bounded'
    )
    return res.x, res.fun

def fit_T_platt(p, y):
    """Fit T + bias (Platt)"""
    res = minimize(
        lambda x: brier_score_loss(y, apply_T(p, x[0], x[1])),
        x0=[1.0, 0.0], method='Nelder-Mead',
        options={'xatol': 1e-6, 'fatol': 1e-8, 'maxiter': 5000}
    )
    return res.x[0], res.x[1], res.fun


# ── Load data ─────────────────────────────────────────────────────────────────
print("Loading data...")
df_inn2 = pd.read_parquet("data/ipl_inn2_features_v1/training.parquet")
df_inn2 = df_inn2.sort_values(["match_id", "over", "ball"]).reset_index(drop=True)
df_v7   = pd.read_parquet("data/ipl_features_v7/training.parquet")
df_v7   = df_v7.sort_values(["match_id", "innings", "over", "ball"]).reset_index(drop=True)
print(f"  inn2 data: {df_inn2.shape}, v7 data: {df_v7.shape}")


# ── Load v7 model + calibrators ───────────────────────────────────────────────
print("Loading v7 model...")
m7    = joblib.load("models/ipl_v7/champion_model.joblib")
cal7  = joblib.load("models/ipl_v7/isotonic_calibrator.pkl")

feats7 = [f for f in m7.selected_features_ if f in df_v7.columns]
df_v7_inn2 = df_v7[df_v7["innings"] == 2].copy()

raw7 = m7.predict_proba(df_v7_inn2[feats7].fillna(0))[:, 1]
po7  = cal7.get("per_over_calibrators", {})
iso2 = cal7["calibrator_innings2"]
cal7_p = np.zeros_like(raw7)
for i, (inn, ov) in enumerate(zip(df_v7_inn2["innings"].values,
                                   df_v7_inn2["over"].values)):
    key = f"inn{int(inn)}_over{int(ov)}"
    cal7_p[i] = po7[key].predict([raw7[i]])[0] if key in po7 else iso2.predict([raw7[i]])[0]

df_v7_inn2 = df_v7_inn2.copy()
df_v7_inn2["v7_cal"] = cal7_p


# ── Load v11 phase models + OOF calibrators ───────────────────────────────────
print("Loading v11 phase models...")
with open("models/ipl_inn2_v1/phase_features.json") as f:
    pf = json.load(f)
with open("models/ipl_inn2_v1/phase_oof_calibrators.pkl", "rb") as f:
    cal_v11 = pickle.load(f)

PHASES = [("pp", (1, 6)), ("mid", (7, 15)), ("death", (16, 20))]
models_v11 = {ph: joblib.load(f"models/ipl_inn2_v1/champion_model_{ph}.joblib")
              for ph, _ in PHASES}


# ── Generate v11 calibrated predictions on ALL inn2 data ─────────────────────
print("Generating v11 predictions (full dataset)...")
v11_cal = np.zeros(len(df_inn2))
for phase, (lo, hi) in PHASES:
    mask = df_inn2["over"].between(lo, hi)
    feat_names = [f for f in pf[phase] if f in df_inn2.columns]
    med = df_inn2.loc[mask, feat_names].median()
    X = df_inn2.loc[mask, feat_names].fillna(med)
    raw = models_v11[phase].predict_proba(X)[:, 1]

    cal_ph = cal_v11.get(phase, {})
    po = cal_ph.get("per_over", {})
    pi = cal_ph.get("phase_iso")
    preds = np.zeros(mask.sum())
    for i, (ov, r) in enumerate(zip(df_inn2.loc[mask, "over"].values, raw)):
        ov = int(ov)
        if ov in po:
            preds[i] = float(po[ov].predict([r])[0])
        elif pi is not None:
            preds[i] = float(pi.predict([r])[0])
        else:
            preds[i] = float(r)

    v11_cal[np.where(mask)[0]] = preds

df_inn2["v11_cal"] = v11_cal

# Align v7 predictions
merge_df = df_v7_inn2[["match_id", "over", "ball", "v7_cal"]].copy()
df_inn2 = df_inn2.merge(merge_df, on=["match_id", "over", "ball"], how="left")
df_inn2["v7_cal"] = df_inn2["v7_cal"].fillna(0.5)


# ── Fit T on 2025+2026 holdout ────────────────────────────────────────────────
holdout_seasons = [s for s in df_inn2["season"].unique() if "2025" in str(s) or "2026" in str(s)]
ho_mask = df_inn2["season"].isin(holdout_seasons)
print(f"\nHoldout: {ho_mask.sum()} rows, seasons={sorted(holdout_seasons)}")

T_prod = {}   # single T per phase
T_platt = {}  # T + bias per phase (shadow)
B_platt = {}
for phase, (lo, hi) in PHASES:
    mask = ho_mask & df_inn2["over"].between(lo, hi)
    n = mask.sum()
    if n < 30:
        print(f"  {phase}: only {n} holdout rows → T=1.0")
        T_prod[phase] = 1.0
        T_platt[phase] = 1.0
        B_platt[phase] = 0.0
        continue
    p = df_inn2.loc[mask, "v11_cal"].values
    y = df_inn2.loc[mask, "is_winner"].values
    t_s, brier_s = fit_T_simple(p, y)
    t_p, b_p, brier_p = fit_T_platt(p, y)
    T_prod[phase]  = round(float(t_s), 4)
    T_platt[phase] = round(float(t_p), 4)
    B_platt[phase] = round(float(b_p), 4)
    print(f"  {phase}: T_simple={t_s:.4f} brier={brier_s:.5f} | Platt T={t_p:.4f} b={b_p:.4f} brier={brier_p:.5f} | n={n}")

# Apply T to full dataset
v11_prodT   = df_inn2["v11_cal"].values.copy()
v11_shadowT = df_inn2["v11_cal"].values.copy()
for phase, (lo, hi) in PHASES:
    mask = df_inn2["over"].between(lo, hi).values
    v11_prodT[mask]   = apply_T(v11_prodT[mask],   T_prod[phase])
    v11_shadowT[mask] = apply_T(v11_shadowT[mask], T_platt[phase], B_platt[phase])

df_inn2["v11_prodT"]   = v11_prodT
df_inn2["v11_shadowT"] = v11_shadowT


# ── Comparison table ──────────────────────────────────────────────────────────
segments = [
    ("Inn2 PP",    df_inn2["over"].between(1, 6)),
    ("Inn2 Mid",   df_inn2["over"].between(7, 15)),
    ("Inn2 Death", df_inn2["over"].between(16, 20)),
    ("Inn2 Total", pd.Series([True] * len(df_inn2))),
]

print("\n" + "=" * 90)
print(f"  v11 T-Scaling Analysis (full OOF, {len(df_inn2):,} inn2 rows)")
print("=" * 90)
print(f"{'Phase':<15} {'v7 cal':>9} {'v11 no-T':>10} {'v11+prodT':>11} {'v11+shadowT':>13} {'prodT vs v7':>12} {'shwT vs v7':>12}")
print("-" * 90)

for label, mask in segments:
    y    = df_inn2.loc[mask, "is_winner"].values
    v7   = df_inn2.loc[mask, "v7_cal"].values
    v11  = df_inn2.loc[mask, "v11_cal"].values
    pt   = df_inn2.loc[mask, "v11_prodT"].values
    st   = df_inn2.loc[mask, "v11_shadowT"].values
    b_v7 = brier_score_loss(y, v7)
    b_v11= brier_score_loss(y, v11)
    b_pt = brier_score_loss(y, pt)
    b_st = brier_score_loss(y, st)
    dpt  = (b_pt  - b_v7) / b_v7 * 100
    dst  = (b_st  - b_v7) / b_v7 * 100
    tg_p = (b_v11 - b_pt)  / b_v11 * 100
    tg_s = (b_v11 - b_st)  / b_v11 * 100
    arrow_p = "▼" if dpt < 0 else "▲"
    arrow_s = "▼" if dst < 0 else "▲"
    print(f"  {label:<13} {b_v7:>9.5f} {b_v11:>10.5f} {b_pt:>11.5f} {b_st:>13.5f}   {arrow_p}{abs(dpt):>8.1f}%  {arrow_s}{abs(dst):>8.1f}%")

print("=" * 90)
print(f"\n  T values (simple, prod):  {T_prod}")
print(f"  T values (Platt, shadow): {T_platt}")
print(f"  B values (Platt bias):    {B_platt}")

# T gain vs no-T
print("\n  T gain vs v11 no-T (how much T scaling improves predictions):")
for label, mask in segments:
    v11 = df_inn2.loc[mask, "v11_cal"].values
    pt  = df_inn2.loc[mask, "v11_prodT"].values
    st  = df_inn2.loc[mask, "v11_shadowT"].values
    y   = df_inn2.loc[mask, "is_winner"].values
    b_v11 = brier_score_loss(y, v11)
    gain_p = (b_v11 - brier_score_loss(y, pt)) / b_v11 * 100
    gain_s = (b_v11 - brier_score_loss(y, st)) / b_v11 * 100
    print(f"  {label:<13}: prodT gain={gain_p:+.2f}%, shadow gain={gain_s:+.2f}%")

# Final verdict
print("\n  Final verdict:")
ov = df_inn2["over"].between(1, 20)
b_v7_tot   = brier_score_loss(df_inn2.loc[ov, "is_winner"].values, df_inn2.loc[ov, "v7_cal"].values)
b_v11_tot  = brier_score_loss(df_inn2.loc[ov, "is_winner"].values, df_inn2.loc[ov, "v11_cal"].values)
b_pt_tot   = brier_score_loss(df_inn2.loc[ov, "is_winner"].values, df_inn2.loc[ov, "v11_prodT"].values)
b_st_tot   = brier_score_loss(df_inn2.loc[ov, "is_winner"].values, df_inn2.loc[ov, "v11_shadowT"].values)
print(f"  v7 cal         : {b_v7_tot:.5f}")
print(f"  v11 no-T       : {b_v11_tot:.5f}  ({(b_v11_tot-b_v7_tot)/b_v7_tot*100:+.1f}% vs v7)")
print(f"  v11 + prodT    : {b_pt_tot:.5f}  ({(b_pt_tot-b_v7_tot)/b_v7_tot*100:+.1f}% vs v7)")
print(f"  v11 + shadowT  : {b_st_tot:.5f}  ({(b_st_tot-b_v7_tot)/b_v7_tot*100:+.1f}% vs v7)")
