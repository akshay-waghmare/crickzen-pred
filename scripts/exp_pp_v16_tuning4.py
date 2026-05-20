"""
Targeted experiments:
K: Per-over × chase_category calibration (18 calibrators)
L: Recency-weighted training (2015+ seasons = 2x weight)
M: MLP (neural net) blend
"""
import sys, json
sys.path.insert(0, "src")
sys.path.insert(0, "scripts")
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.metrics import brier_score_loss, log_loss
from sklearn.isotonic import IsotonicRegression
from sklearn.neural_network import MLPClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer

from ipl_v13_mid_split_common import (
    safe_X, phase_slice, PHASE_RANGES_V12, season_folds,
    fit_calibrator_bundle, apply_calibrator_bundle,
    load_training_data, ordered_unique, XGBLRBlend,
)

V15_DIR = Path("models/ipl_v15_wicket_features")
V15_BRIER = 0.17032
GATE = 0.16180


def run_oof_v15(pp_df, feats):
    """Return OOF raw predictions using v15 XGBLRBlend."""
    pp_df = pp_df.reset_index(drop=True)
    X, _ = safe_X(pp_df, feats)
    y = pp_df["is_winner"].values
    seasons = sorted(pp_df["season"].astype(str).unique().tolist())
    folds = season_folds(seasons, 5)
    raw = np.zeros(len(pp_df))
    for val_seasons in folds:
        tr = ~pp_df["season"].isin(val_seasons)
        va =  pp_df["season"].isin(val_seasons)
        if tr.sum() == 0 or va.sum() == 0: continue
        m = XGBLRBlend()
        m.fit(X[tr], y[tr])
        raw[va] = m.predict_proba(X[va])[:, 1]
    return raw, y


def per_cell_calibrate(raw, y, overs, categories):
    """Calibrate per (over, chase_category) cell."""
    cal = raw.copy()
    for ov in range(6):
        for cat in [-1, 0, 1]:
            mask = (overs == ov) & (categories == cat)
            if mask.sum() < 30:
                continue
            iso = IsotonicRegression(out_of_bounds="clip")
            iso.fit(raw[mask], y[mask])
            cal[mask] = iso.predict(raw[mask])
    return cal


def run_oof_weighted(pp_df, feats, weight_fn):
    """OOF with sample weights from weight_fn(df)."""
    pp_df = pp_df.reset_index(drop=True)
    X, _ = safe_X(pp_df, feats)
    y = pp_df["is_winner"].values
    overs = pp_df["over"].values
    seasons = sorted(pp_df["season"].astype(str).unique().tolist())
    folds = season_folds(seasons, 5)
    raw = np.zeros(len(pp_df))
    w = weight_fn(pp_df)
    for val_seasons in folds:
        tr = ~pp_df["season"].isin(val_seasons)
        va =  pp_df["season"].isin(val_seasons)
        if tr.sum() == 0 or va.sum() == 0: continue
        m = XGBLRBlend()
        m.fit(X[tr], y[tr], sample_weight=w[tr])
        raw[va] = m.predict_proba(X[va])[:, 1]
    bun = fit_calibrator_bundle(raw, y, overs, "isotonic")
    cal = apply_calibrator_bundle(raw, overs, bun)
    return (
        float(brier_score_loss(y, raw)),
        float(brier_score_loss(y, cal)),
        float(log_loss(y, cal.clip(1e-7, 1-1e-7))),
    )


def run_oof_mlp(pp_df, feats):
    """XGB + MLP blend (replacing LR with MLP)."""
    from xgboost import XGBClassifier
    pp_df = pp_df.reset_index(drop=True)
    X, _ = safe_X(pp_df, feats)
    y = pp_df["is_winner"].values
    overs = pp_df["over"].values
    seasons = sorted(pp_df["season"].astype(str).unique().tolist())
    folds = season_folds(seasons, 5)
    raw = np.zeros(len(pp_df))
    for val_seasons in folds:
        tr = ~pp_df["season"].isin(val_seasons)
        va =  pp_df["season"].isin(val_seasons)
        if tr.sum() == 0 or va.sum() == 0: continue
        xgb = XGBClassifier(
            n_estimators=400, max_depth=5, learning_rate=0.02,
            subsample=0.8, colsample_bytree=0.9, min_child_weight=10,
            reg_alpha=0.5, reg_lambda=1.5, tree_method="hist",
            eval_metric="logloss", n_jobs=-1, verbosity=0, random_state=42,
        )
        mlp = Pipeline([
            ("imp", SimpleImputer(strategy="mean")),
            ("sc",  StandardScaler()),
            ("clf", MLPClassifier(
                hidden_layer_sizes=(128, 64), activation="relu",
                solver="adam", alpha=0.01, max_iter=200,
                early_stopping=True, n_iter_no_change=10,
                random_state=42, verbose=False,
            )),
        ])
        xgb.fit(X[tr], y[tr])
        mlp.fit(X[tr], y[tr])
        p_xgb = xgb.predict_proba(X[va])[:, 1]
        p_mlp = mlp.predict_proba(X[va])[:, 1]
        raw[va] = 0.5 * p_xgb + 0.5 * p_mlp
    bun = fit_calibrator_bundle(raw, y, overs, "isotonic")
    cal = apply_calibrator_bundle(raw, overs, bun)
    return (
        float(brier_score_loss(y, raw)),
        float(brier_score_loss(y, cal)),
        float(log_loss(y, cal.clip(1e-7, 1-1e-7))),
    )


def pct(new, old): return f"{(new-old)/old*100:+.2f}%"


def main():
    print("Loading data...")
    df = load_training_data()
    v15_feats = json.load(open(V15_DIR / "phase_features.json"))
    pp = v15_feats["pp"]
    pp_df = phase_slice(df, PHASE_RANGES_V12["pp"])
    print(f"PP rows: {len(pp_df)}, v15 features: {len(pp)}\n")

    print("=== K: Per-over × chase_category calibration (v15 model) ===")
    raw_v15, y_v15 = run_oof_v15(pp_df, pp)
    overs = pp_df["over"].values
    cats = pp_df["chase_category"].values
    cal_k = per_cell_calibrate(raw_v15, y_v15, overs, cats)
    bc_k = float(brier_score_loss(y_v15, cal_k))
    ll_k = float(log_loss(y_v15, cal_k.clip(1e-7, 1-1e-7)))
    print(f"  cal={bc_k:.5f}  ll={ll_k:.5f}  {pct(bc_k, V15_BRIER)}  {'✅' if bc_k<=GATE else '❌'}")
    print(f"  (per-cell cell sizes: {', '.join(f'ov{ov}/cat{c}={((overs==ov)&(cats==c)).sum()}' for ov in [1,3,5] for c in [1,0,-1])})")

    print("\n=== L: Recency-weighted training (year>=2015 → 2x, >=2019 → 3x) ===")
    def recency_weight(df):
        s = df["season"].astype(str)
        w = np.ones(len(df))
        w[s >= "2015"] = 2.0
        w[s >= "2019"] = 3.0
        return w
    br, bc, ll = run_oof_weighted(pp_df, pp, recency_weight)
    print(f"  raw={br:.5f}  cal={bc:.5f}  ll={ll:.5f}  {pct(bc, V15_BRIER)}  {'✅' if bc<=GATE else '❌'}")

    print("\n=== M: XGB + MLP blend (v15 features) ===")
    br, bc, ll = run_oof_mlp(pp_df, pp)
    print(f"  raw={br:.5f}  cal={bc:.5f}  ll={ll:.5f}  {pct(bc, V15_BRIER)}  {'✅' if bc<=GATE else '❌'}")

    print("\n=== L2: Recency-weighted (2019+ 5x, 2015+ 2x) ===")
    def recency_weight2(df):
        s = df["season"].astype(str)
        w = np.ones(len(df))
        w[s >= "2015"] = 2.0
        w[s >= "2019"] = 5.0
        return w
    br, bc, ll = run_oof_weighted(pp_df, pp, recency_weight2)
    print(f"  raw={br:.5f}  cal={bc:.5f}  ll={ll:.5f}  {pct(bc, V15_BRIER)}  {'✅' if bc<=GATE else '❌'}")

    print("\n" + "="*60)
    print(f"V15 baseline: {V15_BRIER} | Gate: {GATE}")


if __name__ == "__main__":
    main()
