"""
IPL v16 PP — Hyperparameter tuning + chase-category routing experiments.
Try 3 approaches and pick the best:
  A) Stronger XGB params (max_depth=6, n_est=600)
  B) Chase-category routed (3 separate PP sub-models)
  C) A + B combined
"""
from __future__ import annotations
import sys, json, pickle
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss

sys.path.insert(0, "src")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ipl_v13_mid_split_common import (
    XGBLRBlend, safe_X, phase_slice, PHASE_RANGES_V12,
    oof_phase_predictions, fit_calibrator_bundle, apply_calibrator_bundle,
    CAL_METHODS_V12, load_training_data, season_folds,
)

ALL_FEATURES_PATH = Path("data/ipl_features_v10/training.parquet")
V15_DIR = Path("models/ipl_v15_wicket_features")
V15_PP_BRIER_CAL = 0.17032
GATE = 0.16180


def add_v16_pp_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    inn1_pp_rr = (out["inn1_pp_runs"].fillna(0) / 6.0).replace(0, np.nan)
    out["inn1_pp_run_rate"]    = out["inn1_pp_runs"].fillna(0) / 6.0
    out["pp_run_rate_vs_inn1"] = (out["current_run_rate"].fillna(0) / inn1_pp_rr).fillna(1.0).clip(0, 3)
    below_c = (-out["target_above_par"].fillna(0)).clip(lower=0)
    wrem    = (10 - out["wickets_lost"].fillna(0)).clip(lower=0)
    out["below_par_run_cushion"]  = below_c * wrem / 10.0
    out["above_par_wicket_cost"]  = out["target_above_par"].fillna(0).clip(lower=0) * out["wickets_lost"].fillna(0) / 20.0
    out["chase_diff_x_wickets"]   = out["chase_difficulty"].fillna(1.0) * out["wickets_lost"].fillna(0)
    out["recovery_x_chase"]       = out["recovery_momentum"].fillna(0) * out["chase_category"].fillna(0)
    return out


def oof_with_params(phase_df, feats, xgb_params=None, n_folds=5):
    """Run season-fold OOF with custom xgb_params."""
    phase_df = phase_df.reset_index(drop=True)
    raw = np.zeros(len(phase_df), dtype=float)
    y   = phase_df["is_winner"].values.astype(float)
    overs   = phase_df["over"].values.astype(int)
    seasons = sorted(phase_df["season"].astype(str).unique().tolist())
    folds   = season_folds(seasons, n_folds=n_folds)
    for _, val_seasons in enumerate(folds):
        tr_mask = ~phase_df["season"].isin(val_seasons)
        va_mask =  phase_df["season"].isin(val_seasons)
        if tr_mask.sum() == 0 or va_mask.sum() == 0:
            continue
        X_tr, avail = safe_X(phase_df[tr_mask], feats)
        X_va, _     = safe_X(phase_df[va_mask], feats)
        y_tr = phase_df.loc[tr_mask, "is_winner"].values
        model = XGBLRBlend(xgb_params=xgb_params)
        model.fit(X_tr, y_tr)
        raw[va_mask.values] = model.predict_proba(X_va)[:, 1]
    brier = float(brier_score_loss(y, raw))
    ll    = float(log_loss(y, np.clip(raw, 1e-7, 1-1e-7)))
    return raw, y, overs, brier, ll


def oof_routed(phase_df, feats, xgb_params=None, n_folds=5):
    """Chase-category routed OOF: train separate model per category."""
    phase_df = phase_df.reset_index(drop=True)
    raw = np.zeros(len(phase_df), dtype=float)
    y   = phase_df["is_winner"].values.astype(float)
    overs   = phase_df["over"].values.astype(int)
    seasons = sorted(phase_df["season"].astype(str).unique().tolist())
    folds   = season_folds(seasons, n_folds=n_folds)

    for _, val_seasons in enumerate(folds):
        tr_mask = ~phase_df["season"].isin(val_seasons)
        va_mask =  phase_df["season"].isin(val_seasons)
        if tr_mask.sum() == 0 or va_mask.sum() == 0:
            continue
        tr_df = phase_df[tr_mask]
        va_df = phase_df[va_mask]

        # Train one model per chase category
        for cat in [-1, 0, 1]:
            cat_tr = tr_df[tr_df["chase_category"] == cat]
            cat_va = va_df[va_df["chase_category"] == cat]
            if len(cat_tr) < 100 or len(cat_va) == 0:
                continue
            X_tr, avail = safe_X(cat_tr, feats)
            X_va, _     = safe_X(cat_va, feats)
            y_tr = cat_tr["is_winner"].values
            model = XGBLRBlend(xgb_params=xgb_params)
            model.fit(X_tr, y_tr)
            va_idx = va_df.index[va_df["chase_category"] == cat]
            raw[va_idx] = model.predict_proba(X_va)[:, 1]

    brier = float(brier_score_loss(y, raw))
    ll    = float(log_loss(y, np.clip(raw, 1e-7, 1-1e-7)))
    return raw, y, overs, brier, ll


def pct(new, old):
    return f"{(new-old)/old*100:+.2f}%"


def main():
    print("Loading training data + v16 features...")
    df = load_training_data()
    df = add_v16_pp_features(df)

    v15_feats = json.load(open(V15_DIR / "phase_features.json"))
    pp_df = phase_slice(df, PHASE_RANGES_V12["pp"])

    V16_PP_NEW = [
        "chase_difficulty", "wickets_times_balls", "wickets_last_30",
        "score_per_wicket", "recovery_momentum", "balls_since_wicket",
        "boundary_pct_last_18", "dot_pct_last_12", "momentum_acceleration",
        "set_batter_exposure",
        "inn1_pp_run_rate", "pp_run_rate_vs_inn1",
        "below_par_run_cushion", "above_par_wicket_cost",
        "chase_diff_x_wickets", "recovery_x_chase",
    ]
    from ipl_v13_mid_split_common import ordered_unique
    v16_pp_feats = ordered_unique(v15_feats["pp"] + V16_PP_NEW)
    all_cols = set(df.columns)
    v16_pp_feats = [f for f in v16_pp_feats if f in all_cols]

    print(f"PP features: {len(v15_feats['pp'])} (v15) -> {len(v16_pp_feats)} (v16)\n")

    # ─── Experiment A: Stronger XGB hyperparams ───────────────────────────────
    print("=== Experiment A: Stronger XGB (max_depth=6, n_est=600, lr=0.015) ===")
    xgb_strong = dict(
        n_estimators=600, max_depth=6, learning_rate=0.015,
        subsample=0.8, colsample_bytree=0.85, min_child_weight=8,
        reg_alpha=0.3, reg_lambda=1.2, tree_method="hist",
        eval_metric="logloss", n_jobs=-1, verbosity=0, random_state=42,
    )
    raw_a, y_a, ov_a, brier_a, ll_a = oof_with_params(pp_df, v16_pp_feats, xgb_params=xgb_strong)
    bun_a = fit_calibrator_bundle(raw_a, y_a, ov_a, CAL_METHODS_V12["pp"])
    cal_a = apply_calibrator_bundle(raw_a, ov_a, bun_a)
    brier_a_cal = float(brier_score_loss(y_a, cal_a))
    ll_a_cal    = float(log_loss(y_a, np.clip(cal_a, 1e-7, 1-1e-7)))
    gate_a = "✅ GATE MET" if brier_a_cal <= GATE else "❌"
    print(f"  raw={brier_a:.5f}  cal={brier_a_cal:.5f}  ll={ll_a_cal:.5f}  vs v15: {pct(brier_a_cal, V15_PP_BRIER_CAL)}  {gate_a}")

    # ─── Experiment B: Chase-category routing (v15 feats, default params) ─────
    print("\n=== Experiment B: Chase-category routing (3 sub-models, v15 feats) ===")
    raw_b, y_b, ov_b, brier_b, ll_b = oof_routed(pp_df, v15_feats["pp"])
    bun_b = fit_calibrator_bundle(raw_b, y_b, ov_b, CAL_METHODS_V12["pp"])
    cal_b = apply_calibrator_bundle(raw_b, ov_b, bun_b)
    brier_b_cal = float(brier_score_loss(y_b, cal_b))
    ll_b_cal    = float(log_loss(y_b, np.clip(cal_b, 1e-7, 1-1e-7)))
    gate_b = "✅ GATE MET" if brier_b_cal <= GATE else "❌"
    print(f"  raw={brier_b:.5f}  cal={brier_b_cal:.5f}  ll={ll_b_cal:.5f}  vs v15: {pct(brier_b_cal, V15_PP_BRIER_CAL)}  {gate_b}")

    # ─── Experiment C: Routing + stronger XGB + v16 feats ──────────────────────
    print("\n=== Experiment C: Routing + stronger XGB + v16 features ===")
    raw_c, y_c, ov_c, brier_c, ll_c = oof_routed(pp_df, v16_pp_feats, xgb_params=xgb_strong)
    bun_c = fit_calibrator_bundle(raw_c, y_c, ov_c, CAL_METHODS_V12["pp"])
    cal_c = apply_calibrator_bundle(raw_c, ov_c, bun_c)
    brier_c_cal = float(brier_score_loss(y_c, cal_c))
    ll_c_cal    = float(log_loss(y_c, np.clip(cal_c, 1e-7, 1-1e-7)))
    gate_c = "✅ GATE MET" if brier_c_cal <= GATE else "❌"
    print(f"  raw={brier_c:.5f}  cal={brier_c_cal:.5f}  ll={ll_c_cal:.5f}  vs v15: {pct(brier_c_cal, V15_PP_BRIER_CAL)}  {gate_c}")

    # ─── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "="*60)
    print("EXPERIMENT SUMMARY")
    print("="*60)
    print(f"  V15 baseline:    cal=0.17032")
    print(f"  A (strong XGB):  cal={brier_a_cal:.5f}  ({pct(brier_a_cal, V15_PP_BRIER_CAL)})  {gate_a}")
    print(f"  B (routing):     cal={brier_b_cal:.5f}  ({pct(brier_b_cal, V15_PP_BRIER_CAL)})  {gate_b}")
    print(f"  C (route+XGB+v16feat): cal={brier_c_cal:.5f}  ({pct(brier_c_cal, V15_PP_BRIER_CAL)})  {gate_c}")
    print(f"  Gate: <= {GATE}")


if __name__ == "__main__":
    main()
