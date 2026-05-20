"""
Mid-Phase Under-Confidence Diagnosis
=====================================
Tests 4 hypotheses:
  H1: LR blend is smoothing predictions toward 0.5
  H2: Calibration flattening useful signal
  H3: Features not strong enough (low discriminative power)
  H4: Market subset biased (only 12 matches - too small)

Key signal: T_vs_outcomes≈0.4, T_vs_market≈0.6 both say "sharpen"
Prediction std is too low = predictions bunched near 0.5
"""

import sys, json, pickle, warnings
sys.path.insert(0, 'src')
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss, mutual_info_score
from sklearn.isotonic import IsotonicRegression
from sklearn.preprocessing import StandardScaler, KBinsDiscretizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from xgboost import XGBClassifier
from scipy.optimize import minimize_scalar
from scipy.special import expit
from scipy.stats import entropy

from bbl_pipeline.training.blend_model import XGBLRBlend  # noqa: F401

EPS = 1e-9

def logit(p):
    p = np.clip(p, EPS, 1-EPS)
    return np.log(p / (1-p))

def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -50, 50)))

def apply_T(p, T):
    return np.clip(sigmoid(logit(p) / T), 0.01, 0.99)

def brier(p, y): return brier_score_loss(y, p)
def ece(p, y):
    bins = np.linspace(0, 1, 11)
    e = 0.0
    for i in range(10):
        m = (p >= bins[i]) & (p < bins[i+1])
        if m.sum() > 0:
            e += m.mean() * abs(y[m].mean() - p[m].mean())
    return e

def sharpness(p):
    """Mean squared deviation from 0.5 — higher = more confident."""
    return float(np.mean((p - 0.5) ** 2))

def resolution(p, y):
    """Mean of (y - p_bar)^2 where p_bar is overall mean — how much model discriminates."""
    p_bar = y.mean()
    return float(np.mean((p - p_bar) ** 2))

def prob_hist_str(p, n_bins=10):
    edges = np.linspace(0, 1, n_bins+1)
    counts, _ = np.histogram(p, bins=edges)
    bar = "".join("█" * max(1, c // max(1, counts.max() // 15)) if c > 0 else "." for c in counts)
    return f"[{bar}]  std={p.std():.3f}  mean={p.mean():.3f}"


# ── Local blend for OOF ───────────────────────────────────────────────────────
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

    def predict_xgb(self, X):
        return self.xgb.predict_proba(X)[:, 1]

    def predict_lr(self, X):
        return self.lr.predict_proba(X)[:, 1]

    def predict_blend(self, X):
        return 0.5 * self.predict_xgb(X) + 0.5 * self.predict_lr(X)

    def predict_xgb_heavy(self, X):
        return 0.7 * self.predict_xgb(X) + 0.3 * self.predict_lr(X)

    def predict_xgb_only(self, X):
        return self.predict_xgb(X)


# ── Load data ─────────────────────────────────────────────────────────────────
print("=" * 70)
print("Mid-Phase Under-Confidence Diagnosis")
print("=" * 70)

df = pd.read_parquet("data/ipl_inn2_features_v1/training.parquet")
df = df.sort_values(["match_id", "over", "ball"]).reset_index(drop=True)

with open("models/ipl_inn2_v1/phase_features.json") as f:
    pf = json.load(f)

# Focus on 2026 (true holdout), train on pre-2025
seasons = sorted(df["season"].unique())
holdout_s  = ["2025", "2026"]
train_s    = [s for s in seasons if s not in holdout_s]

MID_LO, MID_HI = 7, 15
PP_LO, PP_HI   = 1, 6

df_mid = df[df["over"].between(MID_LO, MID_HI)].copy().reset_index(drop=True)
df_pp  = df[df["over"].between(PP_LO,  PP_HI)].copy().reset_index(drop=True)

feat_mid = [f for f in pf["mid"] if f in df_mid.columns]
feat_pp  = [f for f in pf["pp"]  if f in df_pp.columns]

tr_mid = df_mid["season"].isin(train_s)
va_mid = df_mid["season"].isin(holdout_s)
tr_pp  = df_pp["season"].isin(train_s)
va_pp  = df_pp["season"].isin(holdout_s)

print(f"\nMid: train={tr_mid.sum():,}  holdout={va_mid.sum():,}")
print(f"PP:  train={tr_pp.sum():,}   holdout={va_pp.sum():,}")

med_mid = df_mid.loc[tr_mid, feat_mid].median()
med_pp  = df_pp.loc[tr_pp,  feat_pp].median()

Xtr_m = df_mid.loc[tr_mid, feat_mid].fillna(med_mid)
Xva_m = df_mid.loc[va_mid, feat_mid].fillna(med_mid)
ytr_m = df_mid.loc[tr_mid, "is_winner"]
yva_m = df_mid.loc[va_mid, "is_winner"].values

Xtr_p = df_pp.loc[tr_pp, feat_pp].fillna(med_pp)
Xva_p = df_pp.loc[va_pp, feat_pp].fillna(med_pp)
ytr_p = df_pp.loc[tr_pp, "is_winner"]
yva_p = df_pp.loc[va_pp, "is_winner"].values

print("\nTraining models...")
m_mid = XGBLRBlendLocal(); m_mid.fit(Xtr_m, ytr_m)
m_pp  = XGBLRBlendLocal(); m_pp.fit(Xtr_p, ytr_p)
print("Done.")


# ═══════════════════════════════════════════════════════════════════════════════
# H1: Is LR blend smoothing predictions?
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("H1: LR BLEND SMOOTHING ANALYSIS")
print("=" * 70)

for phase, m, Xva, yva, label in [("MID", m_mid, Xva_m, yva_m, ""), ("PP", m_pp, Xva_p, yva_p, "(for comparison)")]:
    p_xgb   = m.predict_xgb(Xva)
    p_lr    = m.predict_lr(Xva)
    p_blend = m.predict_blend(Xva)
    p_xgb70 = m.predict_xgb_heavy(Xva)

    print(f"\n{phase} {label}:")
    print(f"  {'Component':<20} {'Brier':>8} {'Sharpness':>11} {'Resolution':>11} {'Prob dist'}")
    print(f"  {'-'*20} {'-'*8} {'-'*11} {'-'*11} {'-'*40}")
    for name, p in [("XGB-only", p_xgb), ("LR-only", p_lr), ("50/50 blend", p_blend), ("70/30 blend", p_xgb70)]:
        b = brier(p, yva)
        sharp = sharpness(p)
        res = resolution(p, yva)
        hist = prob_hist_str(p)
        print(f"  {name:<20} {b:.5f}    {sharp:.5f}     {res:.5f}   {hist}")

    # Optimal weight search
    best_w, best_b = 0.5, brier(p_blend, yva)
    for w in np.arange(0.4, 1.01, 0.05):
        p_test = w * p_xgb + (1-w) * p_lr
        b_test = brier(p_test, yva)
        if b_test < best_b:
            best_b = b_test
            best_w = w
    print(f"  Optimal XGB weight: {best_w:.2f}  (Brier: {best_b:.5f} vs blend 50/50: {brier(p_blend,yva):.5f})")


# ═══════════════════════════════════════════════════════════════════════════════
# H2: Is calibration flattening signal?
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("H2: CALIBRATION EFFECT ON SHARPNESS")
print("=" * 70)

for phase, m, df_ph, va_mask, Xva, yva, feats in [
    ("MID", m_mid, df_mid, va_mid, Xva_m, yva_m, feat_mid),
    ("PP",  m_pp,  df_pp,  va_pp,  Xva_p, yva_p,  feat_pp)
]:
    p_raw = m.predict_blend(Xva)
    overs = df_ph.loc[va_mask, "over"].values

    # Fit isotonic per over on train data
    p_train = m.predict_blend(df_ph.loc[~va_mask, feats].fillna(df_ph.loc[~va_mask, feats].median()))
    y_train = df_ph.loc[~va_mask, "is_winner"].values
    overs_train = df_ph.loc[~va_mask, "over"].values

    iso_map = {}
    for ov in np.unique(overs_train):
        omask = overs_train == ov
        if omask.sum() >= 30:
            iso = IsotonicRegression(out_of_bounds="clip")
            iso.fit(p_train[omask], y_train[omask])
            iso_map[ov] = iso

    p_cal = p_raw.copy()
    for ov in np.unique(overs):
        omask = overs == ov
        if ov in iso_map:
            p_cal[omask] = iso_map[ov].predict(p_raw[omask])

    print(f"\n{phase}:")
    print(f"  {'Stage':<20} {'Brier':>8} {'Sharpness':>11} {'ECE':>8}  {'std':>6}  prob dist")
    print(f"  {'-'*20} {'-'*8} {'-'*11} {'-'*8}  {'-'*6}  {'-'*30}")
    for name, p in [("Raw blend", p_raw), ("Calibrated", p_cal)]:
        print(f"  {name:<20} {brier(p,yva):.5f}    {sharpness(p):.5f}   {ece(p,yva):.5f}  {p.std():.4f}  {prob_hist_str(p)}")

    # Does calibration expand or shrink prediction range?
    q05r, q95r = np.percentile(p_raw, 5), np.percentile(p_raw, 95)
    q05c, q95c = np.percentile(p_cal, 5), np.percentile(p_cal, 95)
    print(f"  Range P5-P95: raw=[{q05r:.3f}, {q95r:.3f}]  cal=[{q05c:.3f}, {q95c:.3f}]")
    pct_extreme = np.mean((p_cal < 0.2) | (p_cal > 0.8))
    print(f"  Predictions outside [0.2, 0.8]: {pct_extreme:.1%}")

    # Check per-over calibration mapping
    print(f"  Per-over calibration effect (raw→cal):")
    for ov in sorted(np.unique(overs))[:5]:
        omask = overs == ov
        print(f"    Over {ov}: raw_std={p_raw[omask].std():.4f}  cal_std={p_cal[omask].std():.4f}  "
              f"raw_rng=[{p_raw[omask].min():.3f},{p_raw[omask].max():.3f}]  "
              f"cal_rng=[{p_cal[omask].min():.3f},{p_cal[omask].max():.3f}]")


# ═══════════════════════════════════════════════════════════════════════════════
# H3: Feature signal strength
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("H3: FEATURE DISCRIMINATIVE POWER (holdout)")
print("=" * 70)

print("\nMID: Top 15 features by abs-correlation with outcome:")
corr_mid = df_mid.loc[va_mid, feat_mid].corrwith(df_mid.loc[va_mid, "is_winner"]).abs().sort_values(ascending=False)
for i, (f, c) in enumerate(corr_mid.head(15).items()):
    print(f"  {i+1:2d}. {f:<40} |r|={c:.4f}")

print("\nPP: Top 15 features by abs-correlation with outcome:")
corr_pp = df_pp.loc[va_pp, feat_pp].corrwith(df_pp.loc[va_pp, "is_winner"]).abs().sort_values(ascending=False)
for i, (f, c) in enumerate(corr_pp.head(15).items()):
    print(f"  {i+1:2d}. {f:<40} |r|={c:.4f}")

# Prediction entropy comparison
print("\nPrediction entropy comparison (lower = more confident):")
for phase, m, Xva, yva in [("MID", m_mid, Xva_m, yva_m), ("PP", m_pp, Xva_p, yva_p)]:
    p = np.clip(m.predict_blend(Xva), EPS, 1-EPS)
    ent = -p * np.log(p) - (1-p) * np.log(1-p)
    print(f"  {phase}: mean_entropy={ent.mean():.4f}  (max possible=0.6931 at p=0.5)")
    print(f"        % predictions in [0.35, 0.65]: {np.mean((p > 0.35) & (p < 0.65)):.1%}  (overconfidence zone: p>0.8 or p<0.2: {np.mean((p>0.8)|(p<0.2)):.1%})")


# ═══════════════════════════════════════════════════════════════════════════════
# H4: Market subset bias
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("H4: MARKET SUBSET BIAS ANALYSIS")
print("=" * 70)

mkt = pd.read_parquet("data/ipl_model_vs_market_v3.parquet")
mkt_inn2 = mkt[mkt['innings'] == 2].copy()
mkt_inn2_mid = mkt_inn2[mkt_inn2['over'].between(7, 15)]
n_matches = mkt_inn2['match_id'].nunique()
print(f"\nMarket data: {n_matches} matches (VERY small sample!)")
print(f"Market inn2 mid rows: {len(mkt_inn2_mid)}")

# Compare market match characteristics vs full holdout
mkt_match_ids = set(mkt_inn2['match_id'].unique())
all_2026_mid = df_mid[df_mid['season'] == '2026']
mkt_mid_balls = all_2026_mid[all_2026_mid['match_id'].isin(mkt_match_ids)]
nonmkt_mid_balls = all_2026_mid[~all_2026_mid['match_id'].isin(mkt_match_ids)]

print(f"\n2026 mid-over balls: {len(all_2026_mid)} total")
print(f"  In market matches:  {len(mkt_mid_balls)} ({len(mkt_mid_balls)/len(all_2026_mid):.0%})")
print(f"  Not in market:      {len(nonmkt_mid_balls)} ({len(nonmkt_mid_balls)/len(all_2026_mid):.0%})")

# Are market matches more contested?
if len(mkt_mid_balls) > 0 and len(nonmkt_mid_balls) > 0:
    print("\nWin rate comparison (is_winner=1 means batting team wins):")
    print(f"  Market matches:     {mkt_mid_balls['is_winner'].mean():.3f}")
    print(f"  Non-market matches: {nonmkt_mid_balls['is_winner'].mean():.3f}")
    print(f"  Full 2026 mid:      {all_2026_mid['is_winner'].mean():.3f}")

    print("\nKey feature distributions (market vs non-market):")
    for feat in ['score_vs_par', 'required_run_rate', 'wickets_lost', 'rr_vs_rrr']:
        if feat in df_mid.columns:
            m_val = mkt_mid_balls[feat].mean() if feat in mkt_mid_balls.columns else "N/A"
            nm_val = nonmkt_mid_balls[feat].mean() if feat in nonmkt_mid_balls.columns else "N/A"
            print(f"  {feat:<35}: market={m_val:.3f}  non-market={nm_val:.3f}")

# What's the theoretical T sample size reliability?
print("\n--- T Sample Size Analysis ---")
print(f"2026 market inn2 mid balls joined: ~604 (from prior run)")
n = 604
# Bootstrap CI would require many samples, but rule of thumb:
# T fitted on N points has standard error ≈ 1/sqrt(N) in logit space
# With N=604 and 1 parameter, the uncertainty is roughly ±0.1-0.2 on T
print(f"With ~{n} ball-rows: T estimate standard error ~ ±{1/np.sqrt(n):.3f}")
print(f"Equivalent to {n / 6:.0f} overs, {n / 6 / 9:.0f} over-runs in Mid (9 overs/innings)")
print(f"Rule of thumb: need 5000+ rows for stable T → current data is {5000/n:.1f}x too small")


# ═══════════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("DIAGNOSIS SUMMARY")
print("=" * 70)
p_xgb_m = m_mid.predict_xgb(Xva_m)
p_lr_m   = m_mid.predict_lr(Xva_m)
p_bld_m  = m_mid.predict_blend(Xva_m)

xgb_sharp = sharpness(p_xgb_m)
lr_sharp  = sharpness(p_lr_m)
bld_sharp = sharpness(p_bld_m)
lr_drag   = (xgb_sharp - bld_sharp) / xgb_sharp * 100

print(f"\nMID sharpness: XGB={xgb_sharp:.5f}  LR={lr_sharp:.5f}  Blend={bld_sharp:.5f}")
print(f"LR drag on sharpness: {lr_drag:.1f}% reduction from XGB-only")
print(f"\nMID max feature |r| = {corr_mid.max():.4f}  (PP = {corr_pp.max():.4f})")
print(f"Market data: only {n_matches} matches — T values from this subset are unreliable")

print("\nRoot causes ranked:")
causes = [
    ("LR blend smoothing",    f"LR sharpness {lr_sharp:.4f} vs XGB {xgb_sharp:.4f} — drag {lr_drag:.1f}%"),
    ("Feature signal",        f"Max |r| = {corr_mid.max():.4f} (PP = {corr_pp.max():.4f})"),
    ("Market sample size",    f"Only {n_matches} matches — T from this is noise, not signal"),
    ("Calibration flattening","Check per-over range expansion/contraction above"),
]
for i, (cause, detail) in enumerate(causes, 1):
    print(f"  {i}. {cause}: {detail}")
