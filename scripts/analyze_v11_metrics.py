"""
IPL v11 Full Metrics: Brier + ECE + LogLoss + Market-based T-scaling
=====================================================================
1. Runs 5-fold season OOF on inn2 phase models (PP/Mid/Death)
2. Computes Brier, ECE (10-bin), LogLoss for raw + calibrated OOF
3. Joins 2026 holdout with market data → finds T_vs_outcomes and T_vs_market
4. Shows full comparison table: v7 | v11-raw | v11-cal | v11+T_outcomes | v11+T_market | Market

T_vs_outcomes : T that minimises Brier vs actual match outcomes (proper scoring rule)
T_vs_market   : T that minimises MSE between model probs and market probs (track market)
"""

import sys, json, pickle, warnings
sys.path.insert(0, 'src')
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss
from sklearn.isotonic import IsotonicRegression
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from xgboost import XGBClassifier
from scipy.optimize import minimize_scalar, minimize
from scipy.special import expit

from bbl_pipeline.training.blend_model import XGBLRBlend  # noqa: F401

EPS = 1e-9

# ── helpers ───────────────────────────────────────────────────────────────────
def logit(p):
    p = np.clip(p, EPS, 1 - EPS)
    return np.log(p / (1 - p))

def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -50, 50)))

def apply_T(p, T, b=0.0):
    return np.clip(sigmoid(logit(p) / T + b), 0.01, 0.99)

def fit_T_vs_outcomes(p, y):
    """T that minimises Brier score vs actual outcomes."""
    res = minimize_scalar(lambda T: brier_score_loss(y, apply_T(p, T)),
                          bounds=(0.3, 3.0), method='bounded')
    return float(res.x), float(res.fun)

def fit_T_vs_market(p, mkt):
    """T that minimises MSE between model probs and market probs."""
    res = minimize_scalar(lambda T: np.mean((apply_T(p, T) - mkt) ** 2),
                          bounds=(0.3, 3.0), method='bounded')
    return float(res.x), float(np.mean((apply_T(p, res.x) - mkt) ** 2))

def fit_platt_vs_market(p, mkt):
    """Platt (T, bias) that minimises MSE vs market."""
    res = minimize(lambda x: np.mean((apply_T(p, x[0], x[1]) - mkt) ** 2),
                   x0=[1.0, 0.0], method='Nelder-Mead',
                   options={'xatol': 1e-6, 'fatol': 1e-9, 'maxiter': 5000})
    T, b = res.x
    mse = float(np.mean((apply_T(p, T, b) - mkt) ** 2))
    return float(T), float(b), mse

def ece_10bin(p, y):
    """Expected Calibration Error with 10 equal-width bins."""
    bins = np.linspace(0, 1, 11)
    ece = 0.0
    for i in range(len(bins) - 1):
        mask = (p >= bins[i]) & (p < bins[i + 1])
        if mask.sum() > 0:
            frac = mask.mean()
            acc = y[mask].mean()
            conf = p[mask].mean()
            ece += frac * abs(acc - conf)
    return ece


# ── Local XGBLRBlend for OOF ──────────────────────────────────────────────────
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
print("=" * 70)
print("IPL v11 Full Metrics Analysis")
print("=" * 70)

print("\nLoading training data...")
df_inn2 = pd.read_parquet("data/ipl_inn2_features_v1/training.parquet")
df_inn2 = df_inn2.sort_values(["match_id", "over", "ball"]).reset_index(drop=True)

with open("models/ipl_inn2_v1/phase_features.json") as f:
    pf = json.load(f)

print(f"Training rows: {len(df_inn2):,}  |  Seasons: {sorted(df_inn2['season'].unique())}")

# Market data (2026 inn2 matches)
print("\nLoading market data...")
mkt = pd.read_parquet("data/ipl_model_vs_market_v3.parquet")
mkt_inn2 = mkt[mkt['innings'] == 2].copy()
print(f"Market rows (inn2): {len(mkt_inn2)}")

# v7 OOF baselines
V7_OOF = {"pp": (0.18026, 0.18299), "mid": (0.14389, 0.14667), "death": (0.09260, 0.09617)}

PHASES = [("pp", (1, 6)), ("mid", (7, 15)), ("death", (16, 20))]
N_FOLDS = 5
seasons = sorted(df_inn2["season"].unique())
holdout_s = [s for s in seasons if "2025" in str(s) or "2026" in str(s)]

print(f"\nHoldout seasons: {holdout_s}")
print(f"Pre-holdout seasons: {[s for s in seasons if s not in holdout_s][-3:]}...")


# ── Run 5-fold season OOF ─────────────────────────────────────────────────────
all_results = {}  # phase → {raw_oof, cal_oof, y, over, match_id, season}

for phase, (lo, hi) in PHASES:
    print(f"\n{'─'*60}")
    print(f"Phase: {phase.upper()}  (overs {lo}-{hi})")
    phase_mask = df_inn2["over"].between(lo, hi)
    df_ph = df_inn2[phase_mask].copy().reset_index(drop=False)
    feat_names = [f for f in pf[phase] if f in df_ph.columns]
    print(f"  Features used: {len(feat_names)}/{len(pf[phase])}")

    ph_seasons = sorted(df_ph["season"].unique())
    ph_fold_sz = max(1, len(ph_seasons) // N_FOLDS)
    n = len(df_ph)
    raw_oof = np.full(n, np.nan)
    cal_oof = np.full(n, np.nan)

    for fold in range(N_FOLDS):
        if fold < N_FOLDS - 1:
            val_s = ph_seasons[fold * ph_fold_sz: (fold + 1) * ph_fold_sz]
        else:
            val_s = ph_seasons[fold * ph_fold_sz:]
        train_s = [s for s in ph_seasons if s not in val_s]

        tr_mask = df_ph["season"].isin(train_s)
        va_mask = df_ph["season"].isin(val_s)
        if tr_mask.sum() < 100 or va_mask.sum() < 10:
            print(f"    Fold {fold}: skip (insufficient data)")
            continue

        med = df_ph.loc[tr_mask, feat_names].median()
        Xtr = df_ph.loc[tr_mask, feat_names].fillna(med)
        Xva = df_ph.loc[va_mask, feat_names].fillna(med)
        ytr = df_ph.loc[tr_mask, "is_winner"]

        m = XGBLRBlendLocal()
        m.fit(Xtr, ytr)
        preds_va = m.predict_proba(Xva)
        raw_oof[va_mask.values] = preds_va
        b = brier_score_loss(df_ph.loc[va_mask, "is_winner"], preds_va)
        ho_tag = " [HOLDOUT]" if any(s in holdout_s for s in val_s) else ""
        print(f"    Fold {fold}: {val_s}  n={va_mask.sum():,}  raw_brier={b:.4f}{ho_tag}")

    # Fill missing with 0.5
    raw_oof = np.where(np.isnan(raw_oof), 0.5, raw_oof)

    # Per-over isotonic calibration (OOF in-fold — proper)
    overs_ph = df_ph["over"].values
    for ov in sorted(np.unique(overs_ph)):
        omask = overs_ph == ov
        if omask.sum() >= 30:
            iso = IsotonicRegression(out_of_bounds="clip")
            iso.fit(raw_oof[omask], df_ph.loc[omask, "is_winner"].values)
            cal_oof[omask] = iso.predict(raw_oof[omask])
        else:
            cal_oof[omask] = raw_oof[omask]

    all_results[phase] = {
        "raw_oof": raw_oof,
        "cal_oof": cal_oof,
        "y":       df_ph["is_winner"].values,
        "over":    df_ph["over"].values,
        "match_id": df_ph["match_id"].values,
        "season":  df_ph["season"].values,
    }

print(f"\n{'═'*70}")
print("OOF Complete — Computing Metrics")
print(f"{'═'*70}")


# ── Compute metrics per phase ─────────────────────────────────────────────────
def metrics(p, y):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return {
        "brier": brier_score_loss(y, p),
        "ece":   ece_10bin(p, y),
        "logloss": log_loss(y, p),
        "n": len(y),
    }

print("\n── Full OOF Metrics (all seasons) ──")
header = f"{'Phase':<12} {'N':>7}  {'Brier':>7} {'ECE':>7} {'LogLoss':>8}  (raw vs cal)"
print(header)
print("─" * len(header))

phase_metrics = {}
for phase, (lo, hi) in PHASES:
    r = all_results[phase]
    raw_m  = metrics(r["raw_oof"], r["y"])
    cal_m  = metrics(r["cal_oof"], r["y"])
    phase_metrics[phase] = {"raw": raw_m, "cal": cal_m}
    print(f"  {phase.upper():<10} {raw_m['n']:>7,}  "
          f"{raw_m['brier']:.5f}/{cal_m['brier']:.5f}  "
          f"{raw_m['ece']:.5f}/{cal_m['ece']:.5f}  "
          f"{raw_m['logloss']:.4f}/{cal_m['logloss']:.4f}")


# ── Holdout-only metrics (2025+2026) ──────────────────────────────────────────
print("\n── Holdout Metrics (2025+2026 only) ──")
print(f"{'Phase':<12} {'N':>7}  {'v7 Brier':>9} {'v11 Raw':>9} {'v11 Cal':>9}  {'ECE-raw':>8} {'ECE-cal':>8}  {'LL-raw':>8} {'LL-cal':>8}")
print("─" * 100)

holdout_metrics = {}
for phase, (lo, hi) in PHASES:
    r = all_results[phase]
    hmask = np.isin(r["season"], holdout_s)
    if hmask.sum() < 10:
        print(f"  {phase.upper():<10} insufficient holdout data")
        continue
    y_h, raw_h, cal_h = r["y"][hmask], r["raw_oof"][hmask], r["cal_oof"][hmask]
    raw_m = metrics(raw_h, y_h)
    cal_m = metrics(cal_h, y_h)
    holdout_metrics[phase] = {"raw": raw_m, "cal": cal_m, "raw_h": raw_h, "cal_h": cal_h, "y_h": y_h}
    v7_b = V7_OOF[phase][0]
    print(f"  {phase.upper():<10} {raw_m['n']:>7,}  "
          f"{v7_b:.5f}  {raw_m['brier']:.5f}  {cal_m['brier']:.5f}  "
          f"{raw_m['ece']:.5f}  {cal_m['ece']:.5f}  "
          f"{raw_m['logloss']:.4f}  {cal_m['logloss']:.4f}")


# ── Market data join and T-scaling ────────────────────────────────────────────
print("\n" + "═" * 70)
print("Market-Based T-Scaling Analysis")
print("═" * 70)

# Build inn2 predictions for 2026 matches that appear in market data
print("\nJoining 2026 predictions with market data...")

joined_rows = []
for phase, (lo, hi) in PHASES:
    r = all_results[phase]
    # Filter to 2026 rows
    mask_26 = np.isin(r["season"], ["2026"])
    df_phase_26 = pd.DataFrame({
        "match_id": r["match_id"][mask_26],
        "over":     r["over"][mask_26],
        "raw_oof":  r["raw_oof"][mask_26],
        "cal_oof":  r["cal_oof"][mask_26],
        "y":        r["y"][mask_26],
        "phase":    phase,
    })
    merged = df_phase_26.merge(
        mkt_inn2[["match_id", "over", "phase", "market_p_inn1", "actual_inn1_wins"]].rename(
            columns={"actual_inn1_wins": "market_y"}
        ),
        on=["match_id", "over"], how="inner"
    )
    if len(merged) > 0:
        joined_rows.append(merged)
        print(f"  {phase.upper()}: {len(merged)} matched rows")

if not joined_rows:
    print("  ⚠️  No market data joined — market comparison skipped")
else:
    mkt_df = pd.concat(joined_rows, ignore_index=True)
    print(f"  Total joined: {len(mkt_df)}")

    # Align market probability direction: market_p_inn1 → p(batting team wins)
    # In inn2, batting team IS inn2 team, so is_winner ↔ inn2 batting team winning
    # market_p_inn1 = probability that the FIRST INNINGS team (inn1_team) wins
    # is_winner = 1 means batting team in inn2 wins = inn2 team wins = inn1 team LOSES
    # So model's p ≈ P(inn2 team wins) = 1 - market_p_inn1
    mkt_df["market_p_inn2_wins"] = 1.0 - mkt_df["market_p_inn1"]

    print("\n── Per-Phase T Analysis (2026 market data) ──")
    print(f"\n{'Phase':<8} {'N':>5}  {'Cal Brier':>10} {'Mkt Brier':>10}  "
          f"{'T_vs_out':>9} {'T-out Brier':>11}  "
          f"{'T_vs_mkt':>9} {'T_platt_T':>9} {'T_platt_b':>9}  "
          f"{'vs_mkt_before':>14} {'vs_mkt_after':>13}")
    print("─" * 120)

    t_results = {}
    all_cal, all_raw_t_out, all_raw_t_mkt, all_mkt, all_y = [], [], [], [], []

    for phase in ["pp", "mid", "death"]:
        lo, hi = {"pp": (1,6), "mid": (7,15), "death": (16,20)}[phase]
        ph_df = mkt_df[mkt_df["over"].between(lo, hi)].copy()
        if len(ph_df) < 20:
            print(f"  {phase.upper():<8} insufficient data ({len(ph_df)})")
            continue

        p_cal = ph_df["cal_oof"].values
        p_mkt = ph_df["market_p_inn2_wins"].values
        y_act = ph_df["y"].values

        brier_cal = brier_score_loss(y_act, p_cal)
        brier_mkt = brier_score_loss(y_act, p_mkt)

        # T that minimises Brier vs actual outcomes
        T_out, brier_T_out = fit_T_vs_outcomes(p_cal, y_act)
        # T that minimises MSE vs market probs (Temperature only)
        T_mkt, _ = fit_T_vs_market(p_cal, p_mkt)
        # Platt (T + bias) vs market
        T_platt, b_platt, _ = fit_platt_vs_market(p_cal, p_mkt)

        p_T_out = apply_T(p_cal, T_out)
        p_T_mkt = apply_T(p_cal, T_mkt)
        p_T_platt = apply_T(p_cal, T_platt, b_platt)

        mse_before = np.mean((p_cal - p_mkt) ** 2)
        mse_after_T = np.mean((p_T_mkt - p_mkt) ** 2)
        mse_after_platt = np.mean((p_T_platt - p_mkt) ** 2)

        t_results[phase] = {
            "n": len(ph_df), "cal_brier": brier_cal, "mkt_brier": brier_mkt,
            "T_out": T_out, "brier_T_out": brier_T_out,
            "T_mkt": T_mkt, "T_platt": T_platt, "b_platt": b_platt,
            "mse_before": mse_before, "mse_after_T": mse_after_T, "mse_after_platt": mse_after_platt,
            "brier_T_mkt": brier_score_loss(y_act, p_T_mkt),
            "brier_T_platt": brier_score_loss(y_act, p_T_platt),
        }

        all_cal.append(p_cal)
        all_raw_t_out.append(p_T_out)
        all_raw_t_mkt.append(p_T_platt)
        all_mkt.append(p_mkt)
        all_y.append(y_act)

        print(f"  {phase.upper():<8} {len(ph_df):>5}  "
              f"{brier_cal:.5f}    {brier_mkt:.5f}    "
              f"{T_out:.4f}    {brier_T_out:.5f}      "
              f"{T_mkt:.4f}    {T_platt:.4f}    {b_platt:+.4f}    "
              f"{mse_before:.5f}        {mse_after_platt:.5f}")

    # ── Combined inn2 T analysis ──────────────────────────────────────────────
    if all_cal:
        print("\n── Combined Inn2 (PP+Mid+Death) 2026 ──")
        p_all_cal = np.concatenate(all_cal)
        p_all_t_out = np.concatenate(all_raw_t_out)
        p_all_t_mkt = np.concatenate(all_raw_t_mkt)
        p_all_mkt = np.concatenate(all_mkt)
        y_all = np.concatenate(all_y)

        T_comb_out, brier_T_comb_out = fit_T_vs_outcomes(p_all_cal, y_all)
        T_comb_mkt, _ = fit_T_vs_market(p_all_cal, p_all_mkt)
        T_comb_platt, b_comb_platt, _ = fit_platt_vs_market(p_all_cal, p_all_mkt)

        print(f"  n={len(y_all)}")
        print(f"  v11 cal Brier: {brier_score_loss(y_all, p_all_cal):.5f}")
        print(f"  Market Brier:  {brier_score_loss(y_all, p_all_mkt):.5f}")
        print(f"  T_vs_outcomes: T={T_comb_out:.4f}  Brier={brier_T_comb_out:.5f}")
        print(f"  T_vs_market (simple): T={T_comb_mkt:.4f}")
        print(f"  T_vs_market (Platt):  T={T_comb_platt:.4f}  b={b_comb_platt:+.4f}")
        print(f"  Brier after T_out:    {brier_T_comb_out:.5f}")
        print(f"  Brier after Platt:    {brier_score_loss(y_all, apply_T(p_all_cal, T_comb_platt, b_comb_platt)):.5f}")

        # ── Full summary table ────────────────────────────────────────────────
        print("\n" + "═" * 90)
        print("FINAL SUMMARY TABLE — IPL v11 Inn2 (2026 holdout vs market)")
        print("═" * 90)
        print(f"{'Phase':<12} {'v7 Brier':>9} {'v11 raw':>8} {'v11 cal':>8} "
              f"{'v11+T_out':>10} {'v11+T_mkt':>10} {'Market':>8}  "
              f"{'T_out':>7} {'T_mkt':>7} {'T_mkt_b':>8}")
        print("─" * 90)
        for phase, (lo, hi) in PHASES:
            if phase not in t_results:
                continue
            tr = t_results[phase]
            v7_b = V7_OOF[phase][0]
            print(f"  {phase.upper():<10} {v7_b:.5f}  {phase_metrics[phase]['raw']['brier']:.5f}  "
                  f"{tr['cal_brier']:.5f}  "
                  f"{tr['brier_T_out']:.5f}    {tr['brier_T_platt']:.5f}  "
                  f"{tr['mkt_brier']:.5f}   "
                  f"{tr['T_out']:.3f}   {tr['T_platt']:.3f}  {tr['b_platt']:+.4f}")
        print()

        # ── ECE and LogLoss for calibrated and T-applied ──────────────────────
        print("── ECE + LogLoss ──")
        print(f"{'Phase':<12} {'ECE-raw':>8} {'ECE-cal':>8} {'ECE-T_out':>10} {'ECE-T_mkt':>10} {'ECE-mkt':>8}")
        print("─" * 60)
        for phase, (lo, hi) in PHASES:
            if phase not in t_results:
                continue
            tr = t_results[phase]
            ph_df = mkt_df[mkt_df["over"].between(lo, hi)]
            p_cal = ph_df["cal_oof"].values
            p_mkt = ph_df["market_p_inn2_wins"].values
            y_act = ph_df["y"].values
            p_T_out = apply_T(p_cal, tr["T_out"])
            p_T_mkt = apply_T(p_cal, tr["T_platt"], tr["b_platt"])
            print(f"  {phase.upper():<10} "
                  f"{ece_10bin(ph_df['raw_oof'].values, y_act):.5f}  "
                  f"{ece_10bin(p_cal, y_act):.5f}  "
                  f"{ece_10bin(p_T_out, y_act):.5f}    "
                  f"{ece_10bin(p_T_mkt, y_act):.5f}    "
                  f"{ece_10bin(p_mkt, y_act):.5f}")
        print()
        print(f"{'Phase':<12} {'LL-raw':>8} {'LL-cal':>8} {'LL-T_out':>10} {'LL-T_mkt':>10} {'LL-mkt':>8}")
        print("─" * 60)
        for phase, (lo, hi) in PHASES:
            if phase not in t_results:
                continue
            tr = t_results[phase]
            ph_df = mkt_df[mkt_df["over"].between(lo, hi)]
            p_cal = ph_df["cal_oof"].values
            p_mkt = ph_df["market_p_inn2_wins"].values
            y_act = ph_df["y"].values
            p_T_out = apply_T(p_cal, tr["T_out"])
            p_T_mkt = apply_T(p_cal, tr["T_platt"], tr["b_platt"])
            print(f"  {phase.upper():<10} "
                  f"{log_loss(y_act, ph_df['raw_oof'].values):.4f}    "
                  f"{log_loss(y_act, p_cal):.4f}    "
                  f"{log_loss(y_act, p_T_out):.4f}      "
                  f"{log_loss(y_act, p_T_mkt):.4f}      "
                  f"{log_loss(y_act, p_mkt):.4f}")

        print("\n── T Interpretation ──")
        for phase in ["pp", "mid", "death"]:
            if phase not in t_results:
                continue
            tr = t_results[phase]
            T_out = tr["T_out"]
            T_mkt = tr["T_mkt"]
            T_platt = tr["T_platt"]
            b = tr["b_platt"]
            interp_out = "sharpen" if T_out < 0.98 else ("soften" if T_out > 1.02 else "no change")
            interp_mkt = "sharpen" if T_mkt < 0.98 else ("soften" if T_mkt > 1.02 else "no change")
            print(f"  {phase.upper():<6}: T_outcomes={T_out:.3f} ({interp_out})  "
                  f"T_market={T_mkt:.3f} ({interp_mkt})  "
                  f"Platt T={T_platt:.3f} b={b:+.4f}  "
                  f"Brier gain vs cal: {(tr['cal_brier']-tr['brier_T_out'])/tr['cal_brier']*100:.1f}%")

print("\nDone.")
