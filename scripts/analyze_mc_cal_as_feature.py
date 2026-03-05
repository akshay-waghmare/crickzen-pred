"""
Analysis: Does using MC-calibrated probabilities as a feature (instead of raw
resource_win_prob) improve ML model performance on T20I Male?

Three ML models compared:
  A) Original: resource_win_prob as-is (current setup)
  B) Replace:  mc_calibrated_prob replaces resource_win_prob
  C) Both:     keeps resource_win_prob AND adds mc_calibrated_prob

All trained on pre-2024, tested on 2025+ (no leakage).
MC Platt calibrators fitted on train set only.
"""

import numpy as np
import pandas as pd
import os
import sys
from sklearn.metrics import brier_score_loss, log_loss
from sklearn.linear_model import LogisticRegression

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bbl_pipeline.training.trainer import XGBLogRegEnsemble


def ece(probs, labels, n_bins=10):
    bins = np.linspace(0, 1, n_bins + 1)
    idx = np.clip(np.digitize(probs, bins) - 1, 0, n_bins - 1)
    total = 0.0
    for b in range(n_bins):
        mask = idx == b
        if not mask.any():
            continue
        total += mask.sum() / len(probs) * abs(probs[mask].mean() - labels[mask].mean())
    return total


def safe_logit(p):
    p = np.clip(p, 0.001, 0.999)
    return np.log(p / (1 - p))


def fmt(val):
    return f"{val:.4f}"


def main():
    SEP = "=" * 78

    # ── Load T20I data + dates ───────────────────────────────────────────
    print("Loading T20I Male data...")
    features = pd.read_parquet("data/t20_international_male_features_v1/training.parquet")
    dfs = []
    for root, _, files in os.walk("data/t20_international_male_raw/matches"):
        for f in files:
            if f.endswith(".parquet"):
                dfs.append(pd.read_parquet(
                    os.path.join(root, f),
                    columns=["match_id", "date", "innings", "over", "ball"],
                ))
    raw = pd.concat(dfs).sort_values(["match_id", "innings", "over", "ball"]).reset_index(drop=True)
    features["date"] = pd.to_datetime(raw["date"].values)
    features["year"] = features["date"].dt.year
    features["_innings"] = features["innings"]

    train = features[features["year"] < 2024].copy()
    test = features[features["year"] >= 2025].copy()
    print(f"Train: {len(train):,} rows | Test: {len(test):,} rows")

    # ── Fit MC Platt calibrators on TRAIN only (fair) ────────────────────
    print("\nFitting MC Platt calibrators on train set (per innings)...")
    platt_models = {}
    for inn in [1, 2]:
        mask = train["_innings"] == inn
        X_logit = safe_logit(train.loc[mask, "resource_win_prob"].values).reshape(-1, 1)
        lr = LogisticRegression(C=1e10, max_iter=1000, solver="lbfgs")
        lr.fit(X_logit, train.loc[mask, "is_winner"].values)
        platt_models[inn] = lr
        a, b = lr.coef_[0][0], lr.intercept_[0]
        print(f"  Inn {inn}: a={a:.3f}, b={b:.3f}, samples={mask.sum():,}")

    def apply_platt(df):
        out = np.zeros(len(df))
        for inn in [1, 2]:
            mask = df["_innings"].values == inn
            X = safe_logit(df.loc[mask, "resource_win_prob"].values).reshape(-1, 1)
            out[mask] = platt_models[inn].predict_proba(X)[:, 1]
        return out

    train["mc_cal_prob"] = apply_platt(train)
    test["mc_cal_prob"] = apply_platt(test)

    # ── Train 3 ML models ────────────────────────────────────────────────
    drop_cols = ["is_winner", "date", "year", "_innings"]

    # Model A: Original (resource_win_prob as-is)
    print("\nTraining Model A: ML with resource_win_prob (original)...")
    ml_a = XGBLogRegEnsemble()
    X_a = train.drop(columns=drop_cols + ["mc_cal_prob"])
    ml_a.fit(X_a, train["is_winner"])
    feats_a = ml_a.selected_features_

    # Model B: Replace resource_win_prob with mc_cal_prob
    print("Training Model B: ML with mc_cal_prob replacing resource_win_prob...")
    train_b = train.drop(columns=drop_cols + ["mc_cal_prob"]).copy()
    train_b["resource_win_prob"] = train["mc_cal_prob"].values
    ml_b = XGBLogRegEnsemble()
    ml_b.fit(train_b, train["is_winner"])
    feats_b = ml_b.selected_features_

    # Model C: Keep BOTH resource_win_prob AND mc_cal_prob
    print("Training Model C: ML with BOTH resource_win_prob + mc_cal_prob...")
    train_c = train.drop(columns=drop_cols).copy()
    ml_c = XGBLogRegEnsemble()
    ml_c.fit(train_c, train["is_winner"])
    feats_c = ml_c.selected_features_

    # ── Evaluate all on TEST ─────────────────────────────────────────────
    y = test["is_winner"].values

    # Model A
    pred_a = ml_a.predict_proba(
        pd.DataFrame(test[feats_a].fillna(0), columns=feats_a)
    )[:, 1]

    # Model B (feed mc_cal_prob as resource_win_prob)
    test_b = test[feats_b].fillna(0).copy()
    if "resource_win_prob" in feats_b:
        test_b["resource_win_prob"] = test["mc_cal_prob"].values
    pred_b = ml_b.predict_proba(
        pd.DataFrame(test_b, columns=feats_b)
    )[:, 1]

    # Model C (has both columns)
    test_c_df = test[feats_c].fillna(0).copy()
    pred_c = ml_c.predict_proba(
        pd.DataFrame(test_c_df, columns=feats_c)
    )[:, 1]

    # Standalone baselines
    mc_raw = test["resource_win_prob"].values
    mc_cal = test["mc_cal_prob"].values

    # ── Print results ────────────────────────────────────────────────────
    print(f"\n{SEP}")
    print(f"  TEST SET (2025+) T20I Male  N={len(test):,}")
    print(SEP)

    header = f"{'Method':<42}| {'Brier':>8} | {'ECE':>8} | {'LogLoss':>8}"
    divider = "-" * 78

    print(f"\n{header}")
    print(divider)
    for name, probs in [
        ("MC raw (resource_win_prob)", mc_raw),
        ("MC Platt innings (standalone)", mc_cal),
        ("ML-A: original features", pred_a),
        ("ML-B: mc_cal replaces resource_win_prob", pred_b),
        ("ML-C: both resource_win_prob + mc_cal", pred_c),
    ]:
        p = np.clip(probs, 1e-7, 1 - 1e-7)
        b = fmt(brier_score_loss(y, p))
        e = fmt(ece(p, y))
        ll = fmt(log_loss(y, p))
        print(f"{name:<42}| {b:>8} | {e:>8} | {ll:>8}")

    # Per innings
    for inn in [1, 2]:
        mask = test["_innings"].values == inn
        n = mask.sum()
        yt = y[mask]
        print(f"\n--- Innings {inn} (N={n:,}) ---")
        print(f"{'Method':<42}| {'Brier':>8} | {'ECE':>8} | {'LogLoss':>8}")
        print(divider)
        for name, probs in [
            ("MC raw", mc_raw),
            ("MC Platt innings", mc_cal),
            ("ML-A: original", pred_a),
            ("ML-B: mc_cal replace", pred_b),
            ("ML-C: both features", pred_c),
        ]:
            p = np.clip(probs[mask], 1e-7, 1 - 1e-7)
            b = fmt(brier_score_loss(yt, p))
            e = fmt(ece(p, yt))
            ll = fmt(log_loss(yt, p))
            print(f"  {name:<40}| {b:>8} | {e:>8} | {ll:>8}")

    # ── Feature importance comparison ────────────────────────────────────
    print(f"\n{SEP}")
    print("  FEATURE IMPORTANCE COMPARISON")
    print(SEP)
    for label, model in [
        ("ML-A (original)", ml_a),
        ("ML-B (mc_cal replace)", ml_b),
        ("ML-C (both)", ml_c),
    ]:
        fi = model.get_feature_importance()
        print(f"\n{label}:")
        for feat_name in ["resource_win_prob", "mc_cal_prob"]:
            row = fi[fi["feature"] == feat_name]
            if not row.empty:
                rank = list(fi["feature"]).index(feat_name) + 1
                imp = row.iloc[0]["importance"]
                print(f"  {feat_name:<24} rank #{rank:<3} importance={imp:.4f}")
        top5 = list(fi.head(5)["feature"].values)
        print(f"  Top 5: {top5}")

    # ── Delta summary ────────────────────────────────────────────────────
    brier_a = brier_score_loss(y, np.clip(pred_a, 1e-7, 1 - 1e-7))
    brier_b = brier_score_loss(y, np.clip(pred_b, 1e-7, 1 - 1e-7))
    brier_c = brier_score_loss(y, np.clip(pred_c, 1e-7, 1 - 1e-7))
    print(f"\n{SEP}")
    print("  VERDICT")
    print(SEP)
    print(f"  ML-A (original):    Brier = {brier_a:.4f}")
    print(f"  ML-B (mc_cal):      Brier = {brier_b:.4f}  delta = {(brier_b - brier_a)/brier_a*100:+.2f}%")
    print(f"  ML-C (both):        Brier = {brier_c:.4f}  delta = {(brier_c - brier_a)/brier_a*100:+.2f}%")
    best = min(brier_a, brier_b, brier_c)
    if best == brier_a:
        print("  Winner: ML-A (original resource_win_prob is already optimal)")
    elif best == brier_b:
        print("  Winner: ML-B (MC calibrated prob is a better input feature)")
    else:
        print("  Winner: ML-C (having both features helps)")


if __name__ == "__main__":
    main()
