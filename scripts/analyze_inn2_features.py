"""
Inn2-Specific Feature Analysis for IPL
======================================
Computes XGBoost feature importances specifically for innings 2,
broken down by phase (PP / Middle / Death), to discover which features
matter for chasing — separate from the global mixed-innings importance.

Output:
  - models/ipl_inn2_analysis/inn2_feature_importance.csv
  - models/ipl_inn2_analysis/inn2_pp_feature_importance.csv
  - models/ipl_inn2_analysis/inn2_mid_feature_importance.csv
  - models/ipl_inn2_analysis/inn2_death_feature_importance.csv
  - models/ipl_inn2_analysis/inn2_eda_report.md
"""

import os
import sys
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.model_selection import cross_val_score
from xgboost import XGBClassifier
from sklearn.metrics import brier_score_loss
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer

# ── paths ─────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
FEATURES_DIR = ROOT / "data" / "ipl_features_v7"
OUT_DIR = ROOT / "models" / "ipl_inn2_analysis"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── all candidate features (v7 pool — player/rolling excluded, too noisy) ─────
ALL_FEATURES = [
    # State features
    "score_vs_par", "required_run_rate", "pressure_index", "run_rate_diff",
    "chase_difficulty", "current_run_rate", "resources_remaining", "wickets_lost",
    "projected_vs_venue_avg", "team_strength_diff",
    # Momentum
    "runs_last_12", "runs_last_18", "wickets_last_12", "boundary_pct_last_18",
    "dot_pct_last_12", "set_batter_exposure", "balls_since_wicket", "wickets_last_6",
    "wickets_last_30",
    # Team/venue strength
    "batting_team_win_rate", "bowling_team_win_rate", "batting_team_situation_wr",
    "bowling_team_situation_wr", "situation_advantage",
    # Composite
    "projected_score", "score_per_wicket", "rrr_times_wickets", "wickets_times_balls",
    "crr_times_res", "resource_pct", "expected_final_score", "dls_pressure_index",
    "resource_win_prob", "overs_remaining",
    # Inn1 carryover (chase prior)
    "inn1_defendability", "target_above_par", "inn1_wickets_lost",
    "inn1_death_rr", "inn1_pp_runs",
    # Context
    "venue_chase_success", "batting_won_toss",
    # Phase indicators
    "is_powerplay", "is_middle_overs", "is_death_overs",
    # v7 extras
    "score_adjusted_by_team", "projected_adjusted", "resource_team_adjusted", "run_rate_team_adj",
    "acceleration_potential",
]

PHASES = {
    "powerplay": (1, 6),
    "middle": (7, 15),
    "death": (16, 20),
}


def load_data():
    df = pd.read_parquet(FEATURES_DIR / "training.parquet")
    df = df.sort_values(["match_id", "innings", "over", "ball"]).reset_index(drop=True)
    return df


def available_features(df, candidates):
    return [f for f in candidates if f in df.columns]


def train_xgb_get_importance(X, y, label="all"):
    """Train a quick XGBoost and return feature importances."""
    print(f"  Fitting XGB on {len(X):,} rows, {X.shape[1]} features [{label}] ...")
    xgb = XGBClassifier(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.03,
        subsample=0.8,
        colsample_bytree=0.9,
        min_child_weight=10,
        reg_alpha=0.5,
        reg_lambda=1.5,
        tree_method="hist",
        eval_metric="logloss",
        n_jobs=-1,
        verbosity=0,
        random_state=42,
    )
    xgb.fit(X.fillna(X.median()), y)
    importance = pd.DataFrame({
        "feature": X.columns,
        "importance": xgb.feature_importances_,
    }).sort_values("importance", ascending=False).reset_index(drop=True)
    return xgb, importance


def permutation_importance_quick(model, X, y, n_repeat=3, label="all"):
    """
    Quick permutation importance: shuffle each feature, measure Brier increase.
    Returns DataFrame sorted by mean importance (higher = more important).
    """
    print(f"  Permutation importance on {len(X):,} rows [{label}] ...")
    X_np = X.fillna(X.median()).values
    y_np = y.values
    base_pred = model.predict_proba(X.fillna(X.median()))[:, 1]
    base_brier = brier_score_loss(y_np, base_pred)

    results = []
    rng = np.random.default_rng(42)
    for i, col in enumerate(X.columns):
        scores = []
        for _ in range(n_repeat):
            X_perm = X_np.copy()
            idx = rng.permutation(len(X_perm))
            X_perm[:, i] = X_perm[idx, i]
            X_perm_df = pd.DataFrame(X_perm, columns=X.columns)
            perm_pred = model.predict_proba(X_perm_df)[:, 1]
            scores.append(brier_score_loss(y_np, perm_pred) - base_brier)
        results.append({"feature": col, "perm_importance": np.mean(scores)})

    return pd.DataFrame(results).sort_values("perm_importance", ascending=False).reset_index(drop=True)


def analyze_phase(df_inn2, features, phase_name, over_range):
    low, high = over_range
    df_phase = df_inn2[(df_inn2["over"] >= low) & (df_inn2["over"] <= high)].copy()
    print(f"\n{'='*60}")
    print(f"Phase: Inn2 {phase_name.upper()} (overs {low}–{high}) — {len(df_phase):,} rows")

    X = df_phase[features].copy()
    y = df_phase["is_winner"]

    xgb_model, xgb_imp = train_xgb_get_importance(X, y, label=f"inn2_{phase_name}")
    perm_imp = permutation_importance_quick(xgb_model, X, y, n_repeat=3, label=f"inn2_{phase_name}")

    combined = xgb_imp.merge(perm_imp, on="feature", how="left")
    combined["rank_xgb"] = combined["importance"].rank(ascending=False).astype(int)
    combined["rank_perm"] = combined["perm_importance"].rank(ascending=False).astype(int)
    combined["mean_rank"] = ((combined["rank_xgb"] + combined["rank_perm"]) / 2).round(1)
    combined = combined.sort_values("mean_rank")

    return combined, xgb_model, df_phase


def compute_inn2_brier_oof(df_inn2, features, n_folds=5, label="inn2_dedicated"):
    """Time-series OOF Brier on inn2 data by season split."""
    seasons = sorted(df_inn2["season"].unique())
    fold_size = max(1, len(seasons) // n_folds)

    oof_preds = np.zeros(len(df_inn2))
    oof_labels = df_inn2["is_winner"].values

    print(f"\n  OOF CV ({n_folds} folds by season) [{label}]")
    fold_results = []

    for fold in range(n_folds):
        val_seasons = seasons[fold * fold_size: (fold + 1) * fold_size]
        if fold == n_folds - 1:
            val_seasons = seasons[fold * fold_size:]
        train_seasons = [s for s in seasons if s not in val_seasons]

        idx_train = df_inn2["season"].isin(train_seasons)
        idx_val = df_inn2["season"].isin(val_seasons)

        X_tr = df_inn2.loc[idx_train, features].fillna(df_inn2[features].median())
        y_tr = df_inn2.loc[idx_train, "is_winner"]
        X_val = df_inn2.loc[idx_val, features].fillna(df_inn2[features].median())
        y_val = df_inn2.loc[idx_val, "is_winner"]

        if len(X_tr) < 100 or len(X_val) < 10:
            continue

        xgb = XGBClassifier(
            n_estimators=300, max_depth=5, learning_rate=0.03, subsample=0.8,
            colsample_bytree=0.9, min_child_weight=10, reg_alpha=0.5, reg_lambda=1.5,
            tree_method="hist", eval_metric="logloss", n_jobs=-1, verbosity=0, random_state=42,
        )
        lr = Pipeline([
            ("imp", SimpleImputer(strategy="mean")),
            ("sc", StandardScaler()),
            ("clf", LogisticRegression(C=0.01, max_iter=1000, random_state=42)),
        ])
        xgb.fit(X_tr, y_tr)
        lr.fit(X_tr, y_tr)

        p_xgb = xgb.predict_proba(X_val)[:, 1]
        p_lr = lr.predict_proba(X_val)[:, 1]
        p_blend = 0.5 * p_xgb + 0.5 * p_lr

        oof_preds[idx_val.values] = p_blend
        fold_brier = brier_score_loss(y_val, p_blend)
        fold_results.append({"fold": fold, "val_seasons": str(val_seasons), "brier": fold_brier, "n_val": idx_val.sum()})
        print(f"    Fold {fold}: seasons={val_seasons}, n_val={idx_val.sum():,}, Brier={fold_brier:.4f}")

    overall_brier = brier_score_loss(oof_labels, oof_preds)
    print(f"  OOF Brier [{label}]: {overall_brier:.4f}")
    return overall_brier, oof_preds, pd.DataFrame(fold_results)


def main():
    print("Loading IPL v7 training data ...")
    df = load_data()
    print(f"Full dataset: {df.shape}")

    df_inn2 = df[df["innings"] == 2].copy()
    print(f"Inn2 only: {df_inn2.shape}")
    print(f"Seasons: {sorted(df_inn2['season'].unique())}")

    features = available_features(df_inn2, ALL_FEATURES)
    print(f"\nFeatures available for analysis: {len(features)}")

    # ── 1. Overall Inn2 feature importance ────────────────────────────────────
    print("\n" + "=" * 60)
    print("SECTION 1: Inn2 Overall Feature Importance")
    X_inn2 = df_inn2[features].copy()
    y_inn2 = df_inn2["is_winner"]

    xgb_all, imp_all = train_xgb_get_importance(X_inn2, y_inn2, label="inn2_overall")
    perm_all = permutation_importance_quick(xgb_all, X_inn2, y_inn2, n_repeat=3, label="inn2_overall")

    inn2_combined = imp_all.merge(perm_all, on="feature", how="left")
    inn2_combined["rank_xgb"] = inn2_combined["importance"].rank(ascending=False).astype(int)
    inn2_combined["rank_perm"] = inn2_combined["perm_importance"].rank(ascending=False).astype(int)
    inn2_combined["mean_rank"] = ((inn2_combined["rank_xgb"] + inn2_combined["rank_perm"]) / 2).round(1)
    inn2_combined = inn2_combined.sort_values("mean_rank")
    inn2_combined.to_csv(OUT_DIR / "inn2_feature_importance.csv", index=False)
    print("\nTop-20 Inn2 features (by mean rank):")
    print(inn2_combined.head(20).to_string(index=False))

    # ── 2. Phase-wise feature importance ──────────────────────────────────────
    print("\n" + "=" * 60)
    print("SECTION 2: Phase-wise Feature Importance")
    phase_results = {}
    for phase_name, over_range in PHASES.items():
        result, xgb_phase, df_phase = analyze_phase(df_inn2, features, phase_name, over_range)
        result.to_csv(OUT_DIR / f"inn2_{phase_name}_feature_importance.csv", index=False)
        phase_results[phase_name] = result
        print(f"\nTop-15 Inn2-{phase_name} features:")
        print(result.head(15)[["feature", "importance", "perm_importance", "mean_rank"]].to_string(index=False))

    # ── 3. Inn2-specific OOF Brier: full inn2 model vs individual phases ───────
    print("\n" + "=" * 60)
    print("SECTION 3: Inn2 OOF Brier (dedicated models)")

    # Top features by phase (inn2-specific)
    top_inn2_overall = inn2_combined.head(25)["feature"].tolist()
    top_pp = phase_results["powerplay"].head(20)["feature"].tolist()
    top_mid = phase_results["middle"].head(20)["feature"].tolist()
    top_death = phase_results["death"].head(20)["feature"].tolist()

    # v7 baseline OOF on inn2 (from oof_calibration_results.csv)
    v7_inn2_brier = 0.14054  # brier_optimized, inn2

    brier_inn2_all, oof_preds_all, fold_df = compute_inn2_brier_oof(
        df_inn2, top_inn2_overall, n_folds=5, label="inn2_overall_top25"
    )

    brier_pp, _, _ = compute_inn2_brier_oof(
        df_inn2[df_inn2["over"].between(1, 6)].copy(),
        top_pp, n_folds=5, label="inn2_PP_top20"
    )
    brier_mid, _, _ = compute_inn2_brier_oof(
        df_inn2[df_inn2["over"].between(7, 15)].copy(),
        top_mid, n_folds=5, label="inn2_MID_top20"
    )
    brier_death, _, _ = compute_inn2_brier_oof(
        df_inn2[df_inn2["over"].between(16, 20)].copy(),
        top_death, n_folds=5, label="inn2_DEATH_top20"
    )

    # ── 4. Correlation between features and outcome by phase ──────────────────
    print("\n" + "=" * 60)
    print("SECTION 4: Feature-Outcome Correlation by Phase")
    corr_results = {}
    for phase_name, over_range in PHASES.items():
        low, high = over_range
        df_phase = df_inn2[(df_inn2["over"] >= low) & (df_inn2["over"] <= high)]
        corr = df_phase[features + ["is_winner"]].corr()["is_winner"].drop("is_winner")
        corr_results[phase_name] = corr.abs().sort_values(ascending=False)

    # ── 5. Summary report ─────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("Writing EDA Report ...")

    report_lines = [
        "# Inn2 Feature Analysis — IPL v7 Training Data",
        "",
        f"**Dataset:** data/ipl_features_v7/training.parquet",
        f"**Inn2 samples:** {len(df_inn2):,} (out of {len(df):,} total)",
        f"**Seasons:** {sorted(df_inn2['season'].unique())}",
        "",
        "---",
        "",
        "## Key Finding: Inn1 vs Inn2 Feature Importance",
        "",
        "The global model (all innings) computes feature importance over both inn1 and inn2.",
        "Inn1 sees `expected_final_score` / `projected_score` as top features; inn2 never has those targets.",
        "Inn2-specific analysis reveals a fundamentally different hierarchy:",
        "",
        "### Global (all innings) Top-10 vs Inn2-Only Top-10",
        "",
        "| Rank | Global Top Feature | Inn2-Only Top Feature |",
        "|:----:|-------------------|----------------------|",
    ]

    v7_global = [
        "resource_win_prob", "score_vs_par", "dls_pressure_index", "run_rate_diff",
        "venue_chase_success", "score_per_wicket", "expected_final_score", "situation_advantage",
        "team_strength_diff", "batting_team_win_rate",
    ]
    for i, (g, inn2f) in enumerate(zip(v7_global, inn2_combined["feature"].head(10)), 1):
        report_lines.append(f"| {i} | {g} | {inn2f} |")

    report_lines += [
        "",
        "---",
        "",
        "## Inn2 Feature Importance (Overall)",
        "",
        f"Top-25 features for inn2 (XGB gain + permutation Brier importance):",
        "",
        "| Rank | Feature | XGB Gain | Perm Brier Δ | Mean Rank |",
        "|:----:|---------|:--------:|:------------:|:---------:|",
    ]
    for _, row in inn2_combined.head(25).iterrows():
        report_lines.append(
            f"| {int(row['mean_rank'])} | {row['feature']} | {row['importance']:.4f} | {row['perm_importance']:.5f} | {row['mean_rank']} |"
        )

    report_lines += ["", "---", "", "## Phase-wise Feature Importance", ""]

    for phase_name in ["powerplay", "middle", "death"]:
        low, high = PHASES[phase_name]
        result = phase_results[phase_name]
        report_lines += [
            f"### Inn2 {phase_name.title()} (Overs {low}–{high})",
            "",
            "| Rank | Feature | XGB Gain | Perm Brier Δ |",
            "|:----:|---------|:--------:|:------------:|",
        ]
        for _, row in result.head(15).iterrows():
            report_lines.append(
                f"| {int(row['mean_rank'])} | {row['feature']} | {row['importance']:.4f} | {row['perm_importance']:.5f} |"
            )
        report_lines.append("")

        if phase_name in corr_results:
            report_lines += [
                f"**Top correlations with outcome ({phase_name}):**",
                "",
                "| Feature | |correlation| |",
                "|---------|:---------:|",
            ]
            for feat, corr_val in corr_results[phase_name].head(10).items():
                report_lines.append(f"| {feat} | {corr_val:.4f} |")
            report_lines.append("")
        report_lines.append("---")
        report_lines.append("")

    report_lines += [
        "## OOF Brier: Dedicated Inn2 Models vs v7 Baseline",
        "",
        f"**v7 baseline (brier_optimized, inn2):** {v7_inn2_brier:.4f}",
        "",
        "| Model | OOF Brier (Inn2) | vs v7 |",
        "|-------|:----------------:|:-----:|",
        f"| Inn2 Dedicated (top-25 inn2 features) | {brier_inn2_all:.4f} | {(brier_inn2_all - v7_inn2_brier) / v7_inn2_brier * 100:+.1f}% |",
        f"| Inn2-PP Phase Model | {brier_pp:.4f} | (PP only) |",
        f"| Inn2-Mid Phase Model | {brier_mid:.4f} | (Mid only) |",
        f"| Inn2-Death Phase Model | {brier_death:.4f} | (Death only) |",
        "",
        "---",
        "",
        "## Feature Insights by Phase",
        "",
        "### Inn2 Powerplay",
        "- Inn1 carryover features (target_above_par, inn1_defendability, inn1_pp_runs) should dominate",
        "- Team strengths and venue_chase_success are critical at chase start",
        "- Current state (1-6 overs) has little information yet",
        "",
        "### Inn2 Middle Overs",
        "- run_rate_diff and required_run_rate become critical",
        "- Momentum features (runs_last_12/18, wickets_last_12, dot_pct) capture recent pressure",
        "- Partnership features (balls_since_wicket, set_batter_exposure) signal stability",
        "",
        "### Inn2 Death Overs",
        "- Pure chase state: rrr_times_wickets and required_run_rate dominate",
        "- Wickets remaining (10 - wickets_lost) is the key risk factor",
        "- Historical features become less important; current state is everything",
        "",
        "---",
        "Generated by `scripts/analyze_inn2_features.py`",
    ]

    report_path = OUT_DIR / "inn2_eda_report.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"EDA report saved to: {report_path}")

    # Save top feature lists for use by training script
    feature_lists = {
        "inn2_overall": top_inn2_overall,
        "inn2_pp": top_pp,
        "inn2_mid": top_mid,
        "inn2_death": top_death,
    }
    import json
    with open(OUT_DIR / "inn2_top_features.json", "w") as f:
        json.dump(feature_lists, f, indent=2)
    print(f"Top feature lists saved to: {OUT_DIR / 'inn2_top_features.json'}")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"v7 baseline (inn2 brier_optimized):    {v7_inn2_brier:.4f}")
    print(f"Inn2 dedicated model OOF Brier:        {brier_inn2_all:.4f}  ({(brier_inn2_all - v7_inn2_brier) / v7_inn2_brier * 100:+.1f}% vs v7)")
    print(f"Inn2 PP model:                         {brier_pp:.4f}")
    print(f"Inn2 Mid model:                        {brier_mid:.4f}")
    print(f"Inn2 Death model:                      {brier_death:.4f}")
    print(f"\nOutputs saved to: {OUT_DIR}")


if __name__ == "__main__":
    main()
