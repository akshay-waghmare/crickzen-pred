"""
Experiment G: LightGBM + LR blend  
Experiment H: XGBLRBlend with tuned blend ratio  
Experiment I: Per-over PP mini-models  
"""
import sys, json
sys.path.insert(0, "src")
sys.path.insert(0, "scripts")
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.metrics import brier_score_loss, log_loss
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
import lightgbm as lgb

from ipl_v13_mid_split_common import (
    safe_X, phase_slice, PHASE_RANGES_V12, season_folds,
    fit_calibrator_bundle, apply_calibrator_bundle,
    load_training_data, ordered_unique,
)

V15_DIR = Path("models/ipl_v15_wicket_features")
V15_BRIER = 0.17032
GATE = 0.16180


def add_v16_feats(df):
    df = df.copy()
    inn1_pp_rr = (df["inn1_pp_runs"].fillna(0) / 6.0).replace(0, np.nan)
    df["inn1_pp_run_rate"]      = df["inn1_pp_runs"].fillna(0) / 6.0
    df["pp_run_rate_vs_inn1"]   = (df["current_run_rate"].fillna(0) / inn1_pp_rr).fillna(1.0).clip(0, 3)
    df["below_par_run_cushion"] = (-df["target_above_par"].fillna(0)).clip(lower=0) * (10 - df["wickets_lost"].fillna(0)).clip(lower=0) / 10
    df["above_par_wicket_cost"] = df["target_above_par"].fillna(0).clip(lower=0) * df["wickets_lost"].fillna(0) / 20
    df["chase_diff_x_wickets"]  = df["chase_difficulty"].fillna(1.0) * df["wickets_lost"].fillna(0)
    df["recovery_x_chase"]      = df["recovery_momentum"].fillna(0) * df["chase_category"].fillna(0)
    return df


class LGBMLRBlend:
    """LightGBM + LogisticRegression blend (parameterised weight)."""
    LGBM_PARAMS = dict(
        n_estimators=600, num_leaves=31, learning_rate=0.02,
        subsample=0.8, colsample_bytree=0.9, min_child_samples=20,
        reg_alpha=0.3, reg_lambda=1.0, verbose=-1, random_state=42,
        n_jobs=-1,
    )
    def __init__(self, lgbm_params=None, lr_c=0.01, lgbm_weight=0.7):
        self.lgbm_weight = lgbm_weight
        params = {**self.LGBM_PARAMS, **(lgbm_params or {})}
        self.lgbm = lgb.LGBMClassifier(**params)
        self.lr = Pipeline([
            ("imp", SimpleImputer(strategy="mean")),
            ("sc",  StandardScaler()),
            ("clf", LogisticRegression(C=lr_c, max_iter=1000, random_state=42)),
        ])

    def fit(self, X, y):
        self.lgbm.fit(X, y)
        self.lr.fit(X, y)
        return self

    def predict_proba(self, X):
        p_lgbm = self.lgbm.predict_proba(X)[:, 1]
        p_lr   = self.lr.predict_proba(X)[:, 1]
        w = self.lgbm_weight
        blend = w * p_lgbm + (1 - w) * p_lr
        return np.column_stack([1 - blend, blend])


def run_oof(pp_df, feats, ModelClass, **mkwargs):
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
        if tr.sum() == 0 or va.sum() == 0:
            continue
        m = ModelClass(**mkwargs)
        m.fit(X[tr], y[tr])
        raw[va] = m.predict_proba(X[va])[:, 1]
    bun = fit_calibrator_bundle(raw, y, overs, "isotonic")
    cal = apply_calibrator_bundle(raw, overs, bun)
    return (
        float(brier_score_loss(y, raw)),
        float(brier_score_loss(y, cal)),
        float(log_loss(y, cal.clip(1e-7, 1-1e-7))),
    )


def run_oof_per_over(pp_df, feats, ModelClass, **mkwargs):
    """Train a separate model per over (0-5), isotonic calibration on raw."""
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
        if tr.sum() == 0 or va.sum() == 0:
            continue
        # Train per-over model on train set, predict on val set
        for ov in range(6):
            tr_ov = tr & (overs == ov)
            va_ov = va & (overs == ov)
            if tr_ov.sum() < 50 or va_ov.sum() == 0:
                continue
            m = ModelClass(**mkwargs)
            m.fit(X[tr_ov], y[tr_ov])
            raw[va_ov] = m.predict_proba(X[va_ov])[:, 1]
    # Calibrate per-over
    cal = np.zeros_like(raw)
    for ov in range(6):
        mask = overs == ov
        if mask.sum() < 50:
            cal[mask] = raw[mask]
            continue
        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(raw[mask], y[mask])
        cal[mask] = iso.predict(raw[mask])
    return (
        float(brier_score_loss(y, raw)),
        float(brier_score_loss(y, cal)),
        float(log_loss(y, cal.clip(1e-7, 1-1e-7))),
    )


def pct(new, old): return f"{(new-old)/old*100:+.2f}%"


def main():
    print("Loading data...")
    df = load_training_data()
    df = add_v16_feats(df)
    v15_feats = json.load(open(V15_DIR / "phase_features.json"))
    pp_df = phase_slice(df, PHASE_RANGES_V12["pp"])
    V16_NEW = [
        "chase_difficulty", "wickets_times_balls", "wickets_last_30",
        "score_per_wicket", "recovery_momentum", "balls_since_wicket",
        "boundary_pct_last_18", "dot_pct_last_12", "momentum_acceleration",
        "set_batter_exposure", "inn1_pp_run_rate", "pp_run_rate_vs_inn1",
        "below_par_run_cushion", "above_par_wicket_cost",
        "chase_diff_x_wickets", "recovery_x_chase",
    ]
    all_cols = set(df.columns)
    v16_pp = ordered_unique(v15_feats["pp"] + V16_NEW)
    v16_pp = [f for f in v16_pp if f in all_cols]
    pp = v15_feats["pp"]
    print(f"PP rows: {len(pp_df)}, v15={len(pp)}, v16={len(v16_pp)}\n")

    print("=== G: LightGBM 70% + LR 30%, v16 features ===")
    br, bc, ll = run_oof(pp_df, v16_pp, LGBMLRBlend, lgbm_weight=0.7)
    print(f"  raw={br:.5f}  cal={bc:.5f}  ll={ll:.5f}  {pct(bc, V15_BRIER)}  {'✅' if bc<=GATE else '❌'}")

    print("\n=== H: LightGBM 50% + LR 50%, v16 features ===")
    br, bc, ll = run_oof(pp_df, v16_pp, LGBMLRBlend, lgbm_weight=0.5)
    print(f"  raw={br:.5f}  cal={bc:.5f}  ll={ll:.5f}  {pct(bc, V15_BRIER)}  {'✅' if bc<=GATE else '❌'}")

    print("\n=== I: LightGBM per-over models, v16 features ===")
    br, bc, ll = run_oof_per_over(pp_df, v16_pp, LGBMLRBlend, lgbm_weight=0.7)
    print(f"  raw={br:.5f}  cal={bc:.5f}  ll={ll:.5f}  {pct(bc, V15_BRIER)}  {'✅' if bc<=GATE else '❌'}")

    print("\n=== J: LightGBM per-over + v15 features ===")
    br, bc, ll = run_oof_per_over(pp_df, pp, LGBMLRBlend, lgbm_weight=0.7)
    print(f"  raw={br:.5f}  cal={bc:.5f}  ll={ll:.5f}  {pct(bc, V15_BRIER)}  {'✅' if bc<=GATE else '❌'}")

    print("\n" + "="*60)
    print(f"V15 baseline: {V15_BRIER} | Gate: {GATE}")


if __name__ == "__main__":
    main()
