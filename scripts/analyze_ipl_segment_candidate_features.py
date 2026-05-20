"""
Test candidate segment-specific features for IPL v6 improvement.

The goal is a fast EDA gate before changing the production feature pipeline.
It derives candidate interaction features from the existing v6 parquet and
compares baseline vs augmented feature sets on targeted weak segments:
  - innings_2_powerplay
  - innings_1_death

Usage:
  python scripts/analyze_ipl_segment_candidate_features.py \
    --features data/ipl_features_v6/training_sampled.parquet \
    --output-dir experiments/ipl_segment_candidate_features_v1
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


SEGMENTS = ("innings_2_powerplay", "innings_1_death")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate candidate IPL segment-specific features"
    )
    parser.add_argument(
        "--features",
        default="data/ipl_features_v6/training_sampled.parquet",
        help="IPL v6 training parquet",
    )
    parser.add_argument(
        "--output-dir",
        default="experiments/ipl_segment_candidate_features_v1",
        help="Output directory for CSV/report artifacts",
    )
    parser.add_argument("--n-splits", type=int, default=5, help="Sequential CV folds")
    parser.add_argument("--seed", type=int, default=42, help="Model random seed")
    return parser.parse_args()


def phase_from_overs_remaining(overs_remaining: pd.Series) -> pd.Series:
    overs_done = 20.0 - overs_remaining.astype(float)
    phase = np.where(
        overs_done < 6.0,
        "powerplay",
        np.where(overs_done < 15.0, "middle", "death"),
    )
    return pd.Series(phase, index=overs_remaining.index)


def add_candidate_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
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

    out["cand_target_above_par_x_wickets"] = target_above_par * (wickets_lost + 1.0)
    out["cand_target_above_par_x_venue_chase"] = target_above_par * venue_chase
    out["cand_inn1_def_x_batting_wr"] = inn1_def * batting_wr
    out["cand_required_minus_current_rr"] = (
        out["required_run_rate"].astype(float) - out["current_run_rate"].astype(float)
    )
    out["cand_early_chase_wicket_shock"] = wickets_lost / overs_done.clip(lower=0.5)
    out["cand_target_x_early_wicket_shock"] = (
        target_above_par * out["cand_early_chase_wicket_shock"]
    )

    out["cand_wickets_in_hand"] = wickets_in_hand
    out["cand_score_vs_par_x_wickets_in_hand"] = score_vs_par * wickets_in_hand
    out["cand_expected_final_x_wickets_in_hand"] = (
        out["expected_final_score"].astype(float) * wickets_in_hand
    )
    out["cand_projected_vs_venue_x_wickets_in_hand"] = projected_vs_venue * wickets_in_hand
    out["cand_boundary_x_wickets_in_hand"] = boundary_recent * wickets_in_hand
    out["cand_bowling_situation_x_wickets_in_hand"] = bowling_sit_wr * wickets_in_hand
    out["cand_death_resource_pressure"] = out["overs_remaining"].astype(float) / (
        wickets_in_hand + 1.0
    )
    return out


def segment_mask(df: pd.DataFrame, segment: str) -> pd.Series:
    phase = phase_from_overs_remaining(df["overs_remaining"])
    if segment == "innings_2_powerplay":
        return df["innings"].eq(2) & phase.eq("powerplay")
    if segment == "innings_1_death":
        return df["innings"].eq(1) & phase.eq("death")
    raise ValueError(f"Unknown segment: {segment}")


def make_splits(n: int, n_splits: int) -> list[tuple[np.ndarray, np.ndarray]]:
    fold_size = n // n_splits
    splits: list[tuple[np.ndarray, np.ndarray]] = []
    for k in range(1, n_splits):
        train_end = k * fold_size
        val_start = train_end
        val_end = (k + 1) * fold_size if k < n_splits - 1 else n
        if train_end < 100 or val_end <= val_start:
            continue
        splits.append((np.arange(0, train_end), np.arange(val_start, val_end)))
    return splits


def compute_ece(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    y_prob = np.clip(y_prob, 0.0, 1.0)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(y_prob, bins) - 1, 0, n_bins - 1)
    total = 0.0
    for b in range(n_bins):
        mask = idx == b
        if not mask.any():
            continue
        total += mask.sum() / len(y_prob) * abs(y_prob[mask].mean() - y_true[mask].mean())
    return float(total)


def fit_predict_xgb(
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    X_val: pd.DataFrame,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    model = XGBClassifier(
        objective="binary:logistic",
        eval_metric="logloss",
        n_estimators=250,
        max_depth=4,
        learning_rate=0.025,
        subsample=0.85,
        colsample_bytree=0.9,
        min_child_weight=8,
        reg_alpha=0.5,
        reg_lambda=1.5,
        tree_method="hist",
        n_jobs=-1,
        verbosity=0,
        random_state=seed,
    )
    model.fit(X_train, y_train)
    return model.predict_proba(X_val)[:, 1], model.feature_importances_


def fit_predict_logreg(
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    X_val: pd.DataFrame,
    seed: int,
) -> np.ndarray:
    model = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="mean")),
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(C=0.01, max_iter=1000, random_state=seed)),
        ]
    )
    model.fit(X_train, y_train)
    return model.predict_proba(X_val)[:, 1]


def evaluate_feature_set(
    df: pd.DataFrame,
    features: list[str],
    segment: str,
    variant: str,
    n_splits: int,
    seed: int,
) -> tuple[dict, pd.DataFrame]:
    y = df["is_winner"].astype(int).to_numpy()
    X = df[features].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    oof = np.full(len(df), np.nan)
    fi_rows = []

    for fold, (train_idx, val_idx) in enumerate(make_splits(len(df), n_splits), start=1):
        pxgb, imp = fit_predict_xgb(X.iloc[train_idx], y[train_idx], X.iloc[val_idx], seed + fold)
        plr = fit_predict_logreg(X.iloc[train_idx], y[train_idx], X.iloc[val_idx], seed + fold)
        oof[val_idx] = 0.5 * pxgb + 0.5 * plr
        for feature, importance in zip(features, imp):
            fi_rows.append(
                {
                    "segment": segment,
                    "variant": variant,
                    "fold": fold,
                    "feature": feature,
                    "importance": float(importance),
                }
            )

    valid = ~np.isnan(oof)
    metrics = {
        "segment": segment,
        "variant": variant,
        "n": int(valid.sum()),
        "brier": float(brier_score_loss(y[valid], oof[valid])),
        "log_loss": float(log_loss(y[valid], np.clip(oof[valid], 1e-7, 1 - 1e-7))),
        "ece": compute_ece(y[valid], oof[valid]),
        "mean_prediction": float(oof[valid].mean()),
        "actual_win_rate": float(y[valid].mean()),
    }
    return metrics, pd.DataFrame(fi_rows)


def candidate_features_for_segment(segment: str) -> list[str]:
    if segment == "innings_2_powerplay":
        return [
            "cand_target_above_par_x_wickets",
            "cand_target_above_par_x_venue_chase",
            "cand_inn1_def_x_batting_wr",
            "cand_required_minus_current_rr",
            "cand_early_chase_wicket_shock",
            "cand_target_x_early_wicket_shock",
        ]
    if segment == "innings_1_death":
        return [
            "cand_wickets_in_hand",
            "cand_score_vs_par_x_wickets_in_hand",
            "cand_expected_final_x_wickets_in_hand",
            "cand_projected_vs_venue_x_wickets_in_hand",
            "cand_boundary_x_wickets_in_hand",
            "cand_bowling_situation_x_wickets_in_hand",
            "cand_death_resource_pressure",
        ]
    raise ValueError(f"Unknown segment: {segment}")


def write_report(output_dir: Path, metrics_df: pd.DataFrame, fi_df: pd.DataFrame) -> None:
    lines = [
        "# IPL Segment Candidate Feature Experiment",
        "",
        "Sequential OOF comparison of baseline v6 features vs derived segment candidates.",
        "",
        "## Metrics",
        "",
        "| Segment | Variant | N | Brier | Delta | LogLoss | ECE | Mean Pred | Actual |",
        "|---------|---------|---|-------|-------|---------|-----|-----------|--------|",
    ]

    base_by_segment = (
        metrics_df[metrics_df["variant"] == "baseline"]
        .set_index("segment")["brier"]
        .to_dict()
    )
    for row in metrics_df.sort_values(["segment", "variant"]).itertuples():
        delta = row.brier - base_by_segment.get(row.segment, row.brier)
        lines.append(
            f"| {row.segment} | {row.variant} | {int(row.n)} | {row.brier:.5f} | "
            f"{delta:+.5f} | {row.log_loss:.5f} | {row.ece:.5f} | "
            f"{row.mean_prediction:.4f} | {row.actual_win_rate:.4f} |"
        )

    lines += ["", "## Top Candidate Importances", ""]
    cand_fi = fi_df[fi_df["feature"].str.startswith("cand_")]
    if not cand_fi.empty:
        summary = (
            cand_fi.groupby(["segment", "variant", "feature"])["importance"]
            .mean()
            .reset_index()
            .sort_values(["segment", "variant", "importance"], ascending=[True, True, False])
        )
        for segment in SEGMENTS:
            part = summary[(summary["segment"] == segment) & (summary["variant"] == "augmented")]
            lines += [f"### {segment}", ""]
            for row in part.head(10).itertuples():
                lines.append(f"- `{row.feature}`: {row.importance:.5f}")
            lines.append("")
    else:
        lines.append("_No candidate feature importance found._")

    (output_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(args.features).reset_index(drop=True)
    df = add_candidate_features(df)
    base_features = [f for f in XGBLogRegEnsemble.TOP_FEATURES if f in df.columns]

    metrics_rows = []
    fi_parts = []
    for segment in SEGMENTS:
        seg_df = df.loc[segment_mask(df, segment)].reset_index(drop=True)
        candidates = candidate_features_for_segment(segment)
        print(f"{segment}: {len(seg_df):,} rows, candidates={len(candidates)}")

        metrics, fi = evaluate_feature_set(
            seg_df, base_features, segment, "baseline", args.n_splits, args.seed
        )
        metrics_rows.append(metrics)
        fi_parts.append(fi)

        augmented_features = base_features + candidates
        metrics, fi = evaluate_feature_set(
            seg_df, augmented_features, segment, "augmented", args.n_splits, args.seed
        )
        metrics_rows.append(metrics)
        fi_parts.append(fi)

    metrics_df = pd.DataFrame(metrics_rows)
    fi_df = pd.concat(fi_parts, ignore_index=True)
    fi_summary = (
        fi_df.groupby(["segment", "variant", "feature"])["importance"]
        .mean()
        .reset_index()
        .sort_values(["segment", "variant", "importance"], ascending=[True, True, False])
    )

    metrics_df.to_csv(output_dir / "metrics.csv", index=False)
    fi_df.to_csv(output_dir / "fold_feature_importance.csv", index=False)
    fi_summary.to_csv(output_dir / "feature_importance.csv", index=False)
    (output_dir / "config.json").write_text(
        json.dumps(vars(args), indent=2), encoding="utf-8"
    )
    write_report(output_dir, metrics_df, fi_df)

    print(f"Artifacts written to: {output_dir}")
    print(metrics_df.to_string(index=False))


if __name__ == "__main__":
    main()
