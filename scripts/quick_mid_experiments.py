"""
Quick experiments for IPL v12 MID improvement:
  Exp A: dls_pressure_index feature boost (late-MID weighted feature)
  Exp B: XGB blend ratio sweep (50/50 vs 70/30 vs 80/20 vs 100/0)
  Compares OOF Brier on full MID + sub-phases.
"""
import warnings; warnings.filterwarnings("ignore")
import sys, json
sys.path.insert(0, "src")
import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss, log_loss
from sklearn.linear_model import LogisticRegression
from scipy.special import logit
import xgboost as xgb

from bbl_pipeline.training.blend_model import XGBLRBlend
from bbl_pipeline.training.calibration import PlattCalibrator

DATA = Path("data/ipl_inn2_features_v1/training.parquet")
V12_FEATS_FILE = Path("models/ipl_v12/phase_features.json")

# ── load data ─────────────────────────────────────────────────────────────────
print("Loading data...")
df = pd.read_parquet(DATA)
df = df.sort_values(["match_id","innings","over","ball"]).reset_index(drop=True)
df = df[df["innings"] == 2].copy()

with open(V12_FEATS_FILE) as f:
    v12_feats = json.load(f)

MID_FEATS = v12_feats["mid"]   # 71 features
mid_df = df[df["over"].between(7, 15)].copy().reset_index(drop=True)
ALL_SEASONS = sorted(mid_df["season"].unique())

print(f"MID rows: {len(mid_df):,}  |  features: {len(MID_FEATS)}")
print(f"Seasons: {ALL_SEASONS}\n")

# ── helpers ────────────────────────────────────────────────────────────────────
def safe_X(d, feats):
    avail = [f for f in feats if f in d.columns]
    med = d[avail].median()
    return d[avail].fillna(med).values, avail

def season_folds(seasons, n=5):
    sz = max(1, len(seasons)//n)
    folds = []
    for i in range(n):
        val = seasons[i*sz:(i+1)*sz] if i < n-1 else seasons[i*sz:]
        tr  = [s for s in seasons if s not in val]
        folds.append((tr, val))
    return folds

def oof_brier(phase_df, feats, model_factory, label="", verbose=True):
    """5-fold OOF Brier, returns (overall, early_mid, late_mid) Brier."""
    n = len(phase_df)
    raw = np.zeros(n)
    y   = phase_df["is_winner"].values.copy()
    ov  = phase_df["over"].values.copy()

    for tr_s, val_s in season_folds(ALL_SEASONS):
        tr_m  = phase_df["season"].isin(tr_s)
        val_m = phase_df["season"].isin(val_s)
        Xtr, _ = safe_X(phase_df[tr_m], feats)
        Xva, _ = safe_X(phase_df[val_m], feats)
        ytr    = phase_df.loc[tr_m, "is_winner"].values
        m = model_factory()
        m.fit(Xtr, ytr)
        raw[val_m.values] = m.predict_proba(Xva)[:, 1]

    # Platt calibrate (same as v12 MID)
    cal_raw = PlattCalibrator(C=1.0)
    cal_raw.fit(raw, y)
    cal = cal_raw.transform(raw)

    b_overall = brier_score_loss(y, cal)
    b_early   = brier_score_loss(y[ov<=11], cal[ov<=11])
    b_late    = brier_score_loss(y[ov>=12], cal[ov>=12])
    ll_overall = log_loss(y, np.clip(cal, 1e-7, 1-1e-7))

    if verbose:
        print(f"  {label:30s}  Overall={b_overall:.5f}  Early={b_early:.5f}  Late={b_late:.5f}  LL={ll_overall:.5f}")
    return b_overall, b_early, b_late, ll_overall


# ── Baseline (v12 50/50 blend) ─────────────────────────────────────────────────
print("=" * 80)
print("BASELINE — v12 MID (50/50 XGBLRBlend, 71 features, Platt cal)")
print("=" * 80)
b0_all, b0_early, b0_late, ll0 = oof_brier(mid_df, MID_FEATS, XGBLRBlend, "v12 baseline (50/50)")

# ── Experiment B: Blend ratio sweep ───────────────────────────────────────────
print("\n" + "=" * 80)
print("EXP B — XGB Blend Ratio Sweep (MID only, same 71 features)")
print("=" * 80)

class XGBLRBlendCustom:
    """XGBLRBlend with configurable xgb_weight."""
    def __init__(self, xgb_weight=0.5, lr_C=1.0):
        self.xgb_weight = xgb_weight
        self.lr_C = lr_C
        self._xgb = None
        self._lr  = None

    def fit(self, X, y):
        self._xgb = xgb.XGBClassifier(
            n_estimators=300, max_depth=4, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8,
            use_label_encoder=False, eval_metric="logloss",
            random_state=42, verbosity=0
        )
        self._xgb.fit(X, y)
        self._lr = LogisticRegression(C=self.lr_C, max_iter=2000, random_state=42)
        self._lr.fit(X, y)
        return self

    def predict_proba(self, X):
        p_xgb = self._xgb.predict_proba(X)[:, 1]
        p_lr  = self._lr.predict_proba(X)[:, 1]
        blend = self.xgb_weight * p_xgb + (1 - self.xgb_weight) * p_lr
        return np.column_stack([1 - blend, blend])

blend_results = {}
for xw, label in [(0.5, "50/50 XGB/LR"), (0.6, "60/40 XGB/LR"),
                   (0.7, "70/30 XGB/LR"), (0.8, "80/20 XGB/LR"),
                   (0.9, "90/10 XGB/LR"), (1.0, "XGB only"),
                   (0.0, "LR only (C=1)")]:
    factory = (lambda w: lambda: XGBLRBlendCustom(xgb_weight=w))(xw)
    b_all, b_e, b_l, ll = oof_brier(mid_df, MID_FEATS, factory, label)
    blend_results[label] = (b_all, b_e, b_l, ll)

# ── Experiment A: dls_pressure_index boost ────────────────────────────────────
print("\n" + "=" * 80)
print("EXP A — dls_pressure_index Boost (add interaction features for late-MID)")
print("=" * 80)

# Check if dls_pressure_index is already in features
print(f"\n  'dls_pressure_index' in MID feats: {'dls_pressure_index' in MID_FEATS}")
print(f"  dls_pressure_index corr w/ is_winner (early 7-11): {mid_df[mid_df['over']<=11]['dls_pressure_index'].corr(mid_df[mid_df['over']<=11]['is_winner']):.4f}")
print(f"  dls_pressure_index corr w/ is_winner (late 12-15):  {mid_df[mid_df['over']>=12]['dls_pressure_index'].corr(mid_df[mid_df['over']>=12]['is_winner']):.4f}")
print()

# Build new features: dls interactions that amplify its signal in late MID
mid_aug = mid_df.copy()

# Interaction 1: dls × late-over weight (amplified in late MID)
mid_aug["dls_x_late_over"] = mid_aug["dls_pressure_index"] * (mid_aug["over"] - 6) / 9.0

# Interaction 2: dls × wickets_lost (pressure compounds with wickets)
mid_aug["dls_x_wickets"] = mid_aug["dls_pressure_index"] * mid_aug["wickets_lost"].clip(0, 8) / 8.0

# Interaction 3: dls × rrr (combined pressure)
mid_aug["dls_x_rrr"] = mid_aug["dls_pressure_index"] * mid_aug["required_run_rate"].clip(0, 20) / 20.0

# Interaction 4: dls × resource_win_prob  (already-low WP + dls pressure = very bad)
mid_aug["dls_x_win_prob"] = mid_aug["dls_pressure_index"] * (1.0 - mid_aug["resource_win_prob"].clip(0,1))

NEW_DLS_FEATS = ["dls_x_late_over", "dls_x_wickets", "dls_x_rrr", "dls_x_win_prob"]
MID_FEATS_DLS = MID_FEATS + NEW_DLS_FEATS

print(f"  Adding {len(NEW_DLS_FEATS)} dls interaction features: {NEW_DLS_FEATS}")
print(f"  New feature set size: {len(MID_FEATS_DLS)}")
for f in NEW_DLS_FEATS:
    ce = mid_aug[mid_aug["over"]<=11][f].corr(mid_aug[mid_aug["over"]<=11]["is_winner"])
    cl = mid_aug[mid_aug["over"]>=12][f].corr(mid_aug[mid_aug["over"]>=12]["is_winner"])
    print(f"  {f:25s}  corr_early={ce:.4f}  corr_late={cl:.4f}  drift={abs(ce-cl):.4f}")
print()

b_dls, b_dls_e, b_dls_l, ll_dls = oof_brier(mid_aug, MID_FEATS_DLS, XGBLRBlend, "v12 + dls interactions (50/50)")

# ── Combined: Best blend + dls boost ──────────────────────────────────────────
print("\n" + "=" * 80)
print("EXP C — Best blend ratio + dls interactions combined")
print("=" * 80)

# find best blend ratio from exp B
best_label = min(blend_results, key=lambda k: blend_results[k][0])
best_xw = [xw for xw, l in [(0.5,"50/50 XGB/LR"),(0.6,"60/40 XGB/LR"),(0.7,"70/30 XGB/LR"),
                              (0.8,"80/20 XGB/LR"),(0.9,"90/10 XGB/LR"),(1.0,"XGB only"),(0.0,"LR only (C=1)")] if l==best_label][0]
print(f"\n  Best blend from Exp B: {best_label} (xgb_weight={best_xw})")

factory_best = (lambda w: lambda: XGBLRBlendCustom(xgb_weight=w))(best_xw)
b_comb, b_comb_e, b_comb_l, ll_comb = oof_brier(mid_aug, MID_FEATS_DLS, factory_best, f"best blend + dls ({best_label})")

# ── Summary table ─────────────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("SUMMARY — MID OOF Brier (Platt-calibrated)")
print("=" * 80)
print(f"  {'Experiment':<38}  {'Overall':>8}  {'Early(7-11)':>11}  {'Late(12-15)':>11}  {'LogLoss':>8}  {'Δ Overall':>9}")
print(f"  {'-'*38}  {'-'*8}  {'-'*11}  {'-'*11}  {'-'*8}  {'-'*9}")

rows = [("v12 baseline (50/50)", b0_all, b0_early, b0_late, ll0)]
for lbl, (ba, be, bl, ll) in blend_results.items():
    rows.append((lbl, ba, be, bl, ll))
rows.append(("v12 + dls interactions", b_dls, b_dls_e, b_dls_l, ll_dls))
rows.append((f"best blend + dls combined", b_comb, b_comb_e, b_comb_l, ll_comb))

for name, ba, be, bl, ll in rows:
    delta = (ba - b0_all) / b0_all * 100
    sign = "▼" if delta < -0.1 else ("▲" if delta > 0.1 else "≈")
    print(f"  {name:<38}  {ba:.5f}  {be:.5f}      {bl:.5f}      {ll:.5f}  {sign}{delta:+.2f}%")

print()
print("Key question: does Late-MID improve?")
print(f"  Baseline late: {b0_late:.5f}")
print(f"  dls boost late: {b_dls_l:.5f}  ({(b_dls_l-b0_late)/b0_late*100:+.2f}%)")
print(f"  best blend late: {blend_results[best_label][2]:.5f}  ({(blend_results[best_label][2]-b0_late)/b0_late*100:+.2f}%)")
print(f"  combined late:  {b_comb_l:.5f}  ({(b_comb_l-b0_late)/b0_late*100:+.2f}%)")
