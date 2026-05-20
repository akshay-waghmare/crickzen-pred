"""
Retrain experiment: horseshoe-screened candidate features vs IPL v6 baseline.

This does not use market data. It uses an empirical horseshoe-style screen to
choose stable engineered candidates from training data, then compares:
  - baseline_v6_features: the current 32 IPL v6 features
  - augmented_all_candidates: baseline + all candidate features
  - augmented_horseshoe_selected: baseline + candidates that survive shrinkage

Recommended clean check:
  python scripts/train_ipl_horseshoe_feature_experiment.py \
    --features data/ipl_features_v6/training.parquet \
    --output-dir experiments/ipl_horseshoe_retrain_v1 \
    --mode holdout-2026

Fast EDA check:
  python scripts/train_ipl_horseshoe_feature_experiment.py \
    --features data/ipl_features_v6/training_sampled.parquet \
    --output-dir experiments/ipl_horseshoe_retrain_v1_sampled \
    --mode cv
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from bbl_pipeline.training.trainer import XGBLogRegEnsemble  # noqa: E402


EPS = 1e-8


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train/evaluate horseshoe-screened IPL feature candidates"
    )
    parser.add_argument("--features", default="data/ipl_features_v6/training.parquet")
    parser.add_argument("--output-dir", default="experiments/ipl_horseshoe_retrain_v1")
    parser.add_argument("--mode", choices=["holdout-2026", "cv"], default="holdout-2026")
    parser.add_argument("--n-splits", type=int, default=5)
    parser.add_argument("--bootstraps", type=int, default=80)
    parser.add_argument("--keep-threshold", type=float, default=0.05)
    parser.add_argument("--min-screen-rows", type=int, default=150)
    parser.add_argument("--xgb-estimators", type=int, default=400)
    parser.add_argument("--xgb-depth", type=int, default=5)
    parser.add_argument(
        "--max-train-rows",
        type=int,
        default=0,
        help="For holdout mode, keep only the most recent N training rows before 2026",
    )
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def phase_from_overs_remaining(overs_remaining: pd.Series) -> pd.Series:
    overs_done = 20.0 - overs_remaining.astype(float)
    return pd.Series(
        np.where(overs_done < 6.0, "powerplay", np.where(overs_done < 15.0, "middle", "death")),
        index=overs_remaining.index,
    )


def add_candidate_features(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, pd.Series]]:
    out = df.copy()
    phase = phase_from_overs_remaining(out["overs_remaining"])
    inn1_death = out["innings"].eq(1) & phase.eq("death")
    inn2 = out["innings"].eq(2)
    inn2_pp = inn2 & phase.eq("powerplay")
    inn2_mid = inn2 & phase.eq("middle")
    inn2_death = inn2 & phase.eq("death")

    overs_done = (20.0 - out["overs_remaining"].astype(float)).clip(lower=0.0)
    wickets_lost = out["wickets_lost"].astype(float).clip(lower=0.0, upper=10.0)
    wickets_in_hand = (10.0 - wickets_lost).clip(lower=0.0)
    target_above_par = out.get("target_above_par", 0.0).astype(float)
    venue_chase = out.get("venue_chase_success", 0.5).astype(float)
    inn1_def = out.get("inn1_defendability", 0.5).astype(float)
    batting_wr = out.get("batting_team_win_rate", 0.5).astype(float)
    bowling_sit_wr = out.get("bowling_team_situation_wr", 0.5).astype(float)
    boundary_recent = out.get("boundary_pct_last_18", 0.0).astype(float)
    projected_vs_venue = out.get("projected_vs_venue_avg", 0.0).astype(float)
    score_vs_par = out.get("score_vs_par", 0.0).astype(float)

    def gated(name: str, value: pd.Series, mask: pd.Series) -> None:
        out[name] = np.where(mask.to_numpy(), value.astype(float).to_numpy(), 0.0)

    early_shock = wickets_lost / overs_done.clip(lower=0.5)
    req_minus_crr = out["required_run_rate"].astype(float) - out["current_run_rate"].astype(float)

    gated("hs_i2pp_target_above_par_x_wickets", target_above_par * (wickets_lost + 1.0), inn2_pp)
    gated("hs_i2pp_target_above_par_x_venue_chase", target_above_par * venue_chase, inn2_pp)
    gated("hs_i2pp_inn1_def_x_batting_wr", inn1_def * batting_wr, inn2_pp)
    gated("hs_i2pp_required_minus_current_rr", req_minus_crr, inn2_pp)
    gated("hs_i2pp_early_chase_wicket_shock", early_shock, inn2_pp)
    gated("hs_i2pp_target_x_early_wicket_shock", target_above_par * early_shock, inn2_pp)

    gated("hs_i2_target_above_par_x_wickets", target_above_par * (wickets_lost + 1.0), inn2)
    gated("hs_i2_inn1_def_x_required_rr", inn1_def * out["required_run_rate"].astype(float), inn2)
    gated("hs_i2_resource_pressure", out["required_run_rate"].astype(float) * (wickets_lost + 1.0), inn2)
    gated("hs_i2mid_dls_x_resource", out["dls_pressure_index"].astype(float) * out["resource_win_prob"].astype(float), inn2_mid)
    gated("hs_i2death_target_x_venue_chase", target_above_par * venue_chase, inn2_death)
    gated("hs_i2death_dls_x_chase_difficulty", out["dls_pressure_index"].astype(float) * out["chase_difficulty"].astype(float), inn2_death)

    gated("hs_i1death_wickets_in_hand", wickets_in_hand, inn1_death)
    gated("hs_i1death_score_vs_par_x_wih", score_vs_par * wickets_in_hand, inn1_death)
    gated("hs_i1death_expected_final_x_wih", out["expected_final_score"].astype(float) * wickets_in_hand, inn1_death)
    gated("hs_i1death_projected_vs_venue_x_wih", projected_vs_venue * wickets_in_hand, inn1_death)
    gated("hs_i1death_boundary_x_wih", boundary_recent * wickets_in_hand, inn1_death)
    gated("hs_i1death_bowling_situation_x_wih", bowling_sit_wr * wickets_in_hand, inn1_death)
    gated("hs_i1death_resource_pressure", out["overs_remaining"].astype(float) / (wickets_in_hand + 1.0), inn1_death)

    scopes = {
        c: (
            inn2_pp if c.startswith("hs_i2pp_")
            else inn2_mid if c.startswith("hs_i2mid_")
            else inn2_death if c.startswith("hs_i2death_")
            else inn2 if c.startswith("hs_i2_")
            else inn1_death
        )
        for c in out.columns
        if c.startswith("hs_")
    }
    return out, scopes


def standardize_frame(X: pd.DataFrame) -> np.ndarray:
    X = X.replace([np.inf, -np.inf], np.nan)
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ]).fit_transform(X)


def safe_logreg_coef(X: np.ndarray, y: np.ndarray) -> float | None:
    if len(np.unique(y)) < 2:
        return None
    try:
        model = LogisticRegression(C=1.0, max_iter=1000, solver="lbfgs")
        model.fit(X, y)
        return float(model.coef_[0][-1])
    except Exception:
        return None


def screen_candidates(
    train_df: pd.DataFrame,
    candidates: list[str],
    scopes: dict[str, pd.Series],
    bootstraps: int,
    seed: int,
    keep_threshold: float,
    min_screen_rows: int,
) -> tuple[list[str], pd.DataFrame]:
    rng = np.random.default_rng(seed)
    controls = [
        c for c in [
            "resource_win_prob",
            "expected_final_score",
            "score_vs_par",
            "dls_pressure_index",
            "required_run_rate",
            "wickets_lost",
            "overs_remaining",
            "target_above_par",
            "inn1_defendability",
            "venue_chase_success",
            "team_strength_diff",
        ]
        if c in train_df.columns
    ]
    rows = []
    for cand in candidates:
        local_mask = scopes[cand].reindex(train_df.index, fill_value=False)
        sub = train_df.loc[local_mask].copy()
        if len(sub) < min_screen_rows or sub["is_winner"].nunique() < 2 or sub[cand].nunique() < 2:
            continue

        feature_cols = controls + [cand]
        X_all = standardize_frame(sub[feature_cols])
        y_all = sub["is_winner"].astype(int).to_numpy()
        beta = safe_logreg_coef(X_all, y_all)
        if beta is None:
            continue

        groups = sub["match_id"].astype(str).to_numpy() if "match_id" in sub.columns else np.arange(len(sub))
        unique_groups = np.unique(groups)
        boot = []
        for _ in range(bootstraps):
            sampled = rng.choice(unique_groups, size=len(unique_groups), replace=True)
            idx = np.concatenate([np.where(groups == g)[0] for g in sampled])
            b = safe_logreg_coef(X_all[idx], y_all[idx])
            if b is not None:
                boot.append(b)
        if len(boot) < max(5, bootstraps // 3):
            continue
        boot = np.asarray(boot)
        se = float(np.std(boot, ddof=1))
        z = abs(beta) / (se + EPS)
        rows.append({
            "feature": cand,
            "scope_n": int(len(sub)),
            "effect": beta,
            "bootstrap_se": se,
            "z": z,
            "sign_stability": float(max(np.mean(boot > 0), np.mean(boot < 0))),
        })

    screen = pd.DataFrame(rows)
    if screen.empty:
        return [], screen
    tau = max(float(screen["z"].median() / np.sqrt(len(screen) + 1.0)), 0.05)
    local = screen["z"].clip(lower=EPS)
    screen["global_tau"] = tau
    screen["keep_weight"] = (tau * tau * local * local) / (1.0 + tau * tau * local * local)
    screen["shrunk_effect"] = screen["effect"] * screen["keep_weight"]
    screen["selected"] = (
        (screen["keep_weight"] >= keep_threshold)
        & (screen["sign_stability"] >= 0.70)
    )
    selected = screen.loc[screen["selected"], "feature"].tolist()
    return selected, screen.sort_values("keep_weight", ascending=False)


class FeatureEnsemble:
    def __init__(
        self,
        features: list[str],
        seed: int = 42,
        n_estimators: int = 400,
        max_depth: int = 5,
    ):
        self.features = features
        self.seed = seed
        self.xgb = XGBClassifier(
            objective="binary:logistic",
            eval_metric="logloss",
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=0.02,
            subsample=0.8,
            colsample_bytree=0.9,
            min_child_weight=10,
            reg_alpha=0.5,
            reg_lambda=1.5,
            tree_method="hist",
            n_jobs=-1,
            verbosity=0,
            random_state=seed,
        )
        self.lr = Pipeline([
            ("imputer", SimpleImputer(strategy="mean")),
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(C=0.01, max_iter=1000, random_state=seed)),
        ])

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "FeatureEnsemble":
        Xs = X[self.features].replace([np.inf, -np.inf], np.nan).fillna(0.0)
        self.xgb.fit(Xs, y)
        self.lr.fit(Xs, y)
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        Xs = X[self.features].replace([np.inf, -np.inf], np.nan).fillna(0.0)
        px = self.xgb.predict_proba(Xs)[:, 1]
        pl = self.lr.predict_proba(Xs)[:, 1]
        p = 0.5 * px + 0.5 * pl
        return np.column_stack([1.0 - p, p])

    def feature_importance(self) -> pd.DataFrame:
        return pd.DataFrame({
            "feature": self.features,
            "importance": self.xgb.feature_importances_,
        }).sort_values("importance", ascending=False)


def make_cv_splits(n: int, n_splits: int) -> list[tuple[np.ndarray, np.ndarray]]:
    fold_size = n // n_splits
    splits = []
    for k in range(1, n_splits):
        train_end = k * fold_size
        val_end = (k + 1) * fold_size if k < n_splits - 1 else n
        splits.append((np.arange(0, train_end), np.arange(train_end, val_end)))
    return splits


def evaluate_predictions(df: pd.DataFrame, prob_cols: list[str]) -> pd.DataFrame:
    phase = phase_from_overs_remaining(df["overs_remaining"])
    masks = {
        "overall": pd.Series(True, index=df.index),
        "innings_1": df["innings"].eq(1),
        "innings_2": df["innings"].eq(2),
        "innings_1_powerplay": df["innings"].eq(1) & phase.eq("powerplay"),
        "innings_1_middle": df["innings"].eq(1) & phase.eq("middle"),
        "innings_1_death": df["innings"].eq(1) & phase.eq("death"),
        "innings_2_powerplay": df["innings"].eq(2) & phase.eq("powerplay"),
        "innings_2_middle": df["innings"].eq(2) & phase.eq("middle"),
        "innings_2_death": df["innings"].eq(2) & phase.eq("death"),
    }
    rows = []
    y_all = df["is_winner"].astype(int).to_numpy()
    for method in prob_cols:
        p_all = df[method].to_numpy()
        for segment, mask in masks.items():
            idx = mask.to_numpy()
            if idx.sum() < 20:
                continue
            y = y_all[idx]
            p = np.clip(p_all[idx], EPS, 1 - EPS)
            rows.append({
                "method": method,
                "segment": segment,
                "n": int(idx.sum()),
                "brier": float(brier_score_loss(y, p)),
                "log_loss": float(log_loss(y, p)),
                "mean_prediction": float(p.mean()),
                "actual_rate": float(y.mean()),
            })
    metrics = pd.DataFrame(rows)
    base = metrics[metrics["method"] == "baseline_v6_features"][["segment", "brier", "log_loss"]]
    base = base.rename(columns={"brier": "baseline_brier", "log_loss": "baseline_log_loss"})
    metrics = metrics.merge(base, on="segment", how="left")
    metrics["brier_delta"] = metrics["brier"] - metrics["baseline_brier"]
    metrics["log_loss_delta"] = metrics["log_loss"] - metrics["baseline_log_loss"]
    return metrics


def run_holdout(df: pd.DataFrame, base_features: list[str], candidates: list[str], scopes: dict[str, pd.Series], args) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if "season" not in df.columns:
        raise ValueError("holdout-2026 mode requires a season column")
    train = df[~df["season"].astype(str).eq("2026")].copy()
    test = df[df["season"].astype(str).eq("2026")].copy()
    if args.max_train_rows and len(train) > args.max_train_rows:
        train = train.tail(args.max_train_rows).copy()
    selected, screen = screen_candidates(
        train, candidates, scopes, args.bootstraps, args.seed, args.keep_threshold, args.min_screen_rows
    )
    variants = {
        "baseline_v6_features": base_features,
        "augmented_all_candidates": base_features + candidates,
        "augmented_horseshoe_selected": base_features + selected,
    }
    pred_df = test.copy()
    fi_parts = []
    for name, features in variants.items():
        model = FeatureEnsemble(
            features,
            seed=args.seed,
            n_estimators=args.xgb_estimators,
            max_depth=args.xgb_depth,
        ).fit(train, train["is_winner"].astype(int))
        pred_df[name] = model.predict_proba(test)[:, 1]
        fi = model.feature_importance()
        fi["method"] = name
        fi_parts.append(fi)
    return evaluate_predictions(pred_df, list(variants)), screen, pd.concat(fi_parts, ignore_index=True)


def run_cv(df: pd.DataFrame, base_features: list[str], candidates: list[str], scopes: dict[str, pd.Series], args) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    pred_df = df.copy()
    methods = ["baseline_v6_features", "augmented_all_candidates", "augmented_horseshoe_selected"]
    for m in methods:
        pred_df[m] = np.nan
    screen_parts = []
    fi_parts = []
    for fold, (tr_idx, va_idx) in enumerate(make_cv_splits(len(df), args.n_splits), start=1):
        train = df.iloc[tr_idx].copy()
        val = df.iloc[va_idx].copy()
        selected, screen = screen_candidates(
            train, candidates, scopes, args.bootstraps, args.seed + fold, args.keep_threshold, args.min_screen_rows
        )
        if not screen.empty:
            screen["fold"] = fold
            screen_parts.append(screen)
        variants = {
            "baseline_v6_features": base_features,
            "augmented_all_candidates": base_features + candidates,
            "augmented_horseshoe_selected": base_features + selected,
        }
        for name, features in variants.items():
            model = FeatureEnsemble(
                features,
                seed=args.seed + fold,
                n_estimators=args.xgb_estimators,
                max_depth=args.xgb_depth,
            ).fit(train, train["is_winner"].astype(int))
            pred_df.loc[pred_df.index[va_idx], name] = model.predict_proba(val)[:, 1]
            fi = model.feature_importance()
            fi["method"] = name
            fi["fold"] = fold
            fi_parts.append(fi)
    valid = pred_df[methods].notna().all(axis=1)
    metrics = evaluate_predictions(pred_df.loc[valid].copy(), methods)
    screen_df = pd.concat(screen_parts, ignore_index=True) if screen_parts else pd.DataFrame()
    fi_df = pd.concat(fi_parts, ignore_index=True) if fi_parts else pd.DataFrame()
    return metrics, screen_df, fi_df


def write_report(output_dir: Path, metrics: pd.DataFrame, screen: pd.DataFrame, mode: str) -> None:
    lines = [
        "# IPL Horseshoe Retrain Experiment",
        "",
        f"Mode: `{mode}`",
        "",
        "## Metrics",
        "",
        "| Method | Segment | N | Brier | Delta | LogLoss | Delta | Mean Pred | Actual |",
        "|--------|---------|---|-------|-------|---------|-------|-----------|--------|",
    ]
    display = metrics.sort_values(["segment", "method"])
    for row in display.itertuples():
        lines.append(
            f"| {row.method} | {row.segment} | {int(row.n)} | {row.brier:.5f} | "
            f"{row.brier_delta:+.5f} | {row.log_loss:.5f} | {row.log_loss_delta:+.5f} | "
            f"{row.mean_prediction:.4f} | {row.actual_rate:.4f} |"
        )

    lines += ["", "## Horseshoe Screen", ""]
    if screen.empty:
        lines.append("_No candidates screened._")
    else:
        summary = screen.copy()
        if "fold" in summary.columns:
            summary = (
                summary.groupby("feature")
                .agg(
                    mean_keep=("keep_weight", "mean"),
                    selected_rate=("selected", "mean"),
                    mean_effect=("effect", "mean"),
                    mean_z=("z", "mean"),
                    n=("feature", "size"),
                )
                .reset_index()
                .sort_values(["selected_rate", "mean_keep"], ascending=False)
            )
            lines += ["| Feature | Mean Keep | Selected Rate | Mean Effect | Mean Z |", "|---------|-----------|---------------|-------------|--------|"]
            for row in summary.itertuples():
                lines.append(f"| `{row.feature}` | {row.mean_keep:.3f} | {row.selected_rate:.2f} | {row.mean_effect:+.4f} | {row.mean_z:.2f} |")
        else:
            summary = summary.sort_values("keep_weight", ascending=False)
            lines += ["| Feature | Keep | Selected | Effect | Z | Scope N |", "|---------|------|----------|--------|---|---------|"]
            for row in summary.itertuples():
                lines.append(f"| `{row.feature}` | {row.keep_weight:.3f} | {bool(row.selected)} | {row.effect:+.4f} | {row.z:.2f} | {int(row.scope_n)} |")

    (output_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_parquet(args.features).reset_index(drop=True)
    df, scopes = add_candidate_features(df)
    candidates = sorted(scopes)
    base_features = [f for f in XGBLogRegEnsemble.TOP_FEATURES if f in df.columns]

    if args.mode == "holdout-2026":
        metrics, screen, fi = run_holdout(df, base_features, candidates, scopes, args)
    else:
        metrics, screen, fi = run_cv(df, base_features, candidates, scopes, args)

    metrics.to_csv(output_dir / "metrics.csv", index=False)
    screen.to_csv(output_dir / "horseshoe_screen.csv", index=False)
    fi.to_csv(output_dir / "feature_importance.csv", index=False)
    (output_dir / "config.json").write_text(json.dumps(vars(args), indent=2), encoding="utf-8")
    write_report(output_dir, metrics, screen, args.mode)

    print(f"Artifacts written to: {output_dir}")
    print(metrics[metrics["segment"].isin(["overall", "innings_2", "innings_2_powerplay", "innings_2_middle", "innings_1_death"])].to_string(index=False))


if __name__ == "__main__":
    main()
