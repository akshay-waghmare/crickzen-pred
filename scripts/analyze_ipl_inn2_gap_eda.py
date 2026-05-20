"""
IPL innings-2 model-vs-market gap EDA and candidate post-processor tests.

The goal is to understand where IPL v6 differs from market in chase states and
whether a candidate can improve v6 while still beating market in Brier and log
loss. Candidate tests use chronological match splits to avoid fitting on the
same labels they score.

Usage:
  python scripts/analyze_ipl_inn2_gap_eda.py
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


EPS = 1e-7


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="IPL innings-2 gap EDA")
    parser.add_argument("--comparison", default="data/ipl_latest_market_vs_model.parquet")
    parser.add_argument("--features", default="data/ipl_features_latest/training.parquet")
    parser.add_argument("--output-dir", default="experiments/ipl_inn2_gap_eda_v1")
    return parser.parse_args()


def clip_prob(prob: np.ndarray | pd.Series) -> np.ndarray:
    return np.clip(np.asarray(prob, dtype=float), EPS, 1.0 - EPS)


def logit(prob: np.ndarray | pd.Series) -> np.ndarray:
    prob = clip_prob(prob)
    return np.log(prob / (1.0 - prob))


def metric_pair(y_true: np.ndarray, y_prob: np.ndarray) -> tuple[float, float]:
    prob = clip_prob(y_prob)
    return float(brier_score_loss(y_true, prob)), float(log_loss(y_true, prob))


def join_market_features(comparison_path: Path, features_path: Path) -> pd.DataFrame:
    comparison = pd.read_parquet(comparison_path)
    features = pd.read_parquet(features_path)
    features = features.sort_values(["match_id", "innings", "over", "ball"]).copy()
    end_over = features.groupby(["match_id", "innings", "over"], as_index=False).tail(1).copy()
    end_over["cs_match_id"] = end_over["match_id"].astype(str)
    end_over["over_market"] = end_over["over"].astype(int) + 1
    end_over = end_over.rename(columns={"over": "feature_over_0idx", "ball": "feature_ball"})
    joined = comparison.merge(
        end_over,
        left_on=["cs_match_id", "innings", "over"],
        right_on=["cs_match_id", "innings", "over_market"],
        how="inner",
        suffixes=("_market", "_feature"),
    )
    joined = joined[joined["innings"].astype(int).eq(2)].copy()
    joined = joined.sort_values(["date", "cs_match_id", "over"]).reset_index(drop=True)
    y = joined["actual_inn1_wins"].astype(float)
    joined["market_sqerr"] = (joined["market_p_inn1"] - y) ** 2
    joined["raw_sqerr"] = (joined["raw_p_inn1"] - y) ** 2
    joined["iso_sqerr"] = (joined["iso_p_inn1"] - y) ** 2
    joined["model_market_gap"] = joined["iso_p_inn1"] - joined["market_p_inn1"]
    joined["abs_model_market_gap"] = joined["model_market_gap"].abs()
    joined["model_brier_advantage"] = joined["market_sqerr"] - joined["iso_sqerr"]
    return joined


def summarize_segments(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for segment, group in [("innings_2", df), *[(f"innings_2_{p}", g) for p, g in df.groupby("phase")]]:
        y = group["actual_inn1_wins"].astype(float).to_numpy()
        for col in ["market_p_inn1", "raw_p_inn1", "iso_p_inn1"]:
            brier, logloss = metric_pair(y, group[col].to_numpy())
            rows.append({
                "segment": segment,
                "probability": col,
                "n": len(group),
                "brier": brier,
                "log_loss": logloss,
                "mean_prob": float(group[col].mean()),
                "actual_rate": float(group["actual_inn1_wins"].mean()),
                "avg_model_market_gap": float(group["model_market_gap"].mean()),
                "avg_abs_model_market_gap": float(group["abs_model_market_gap"].mean()),
            })
    return pd.DataFrame(rows)


def feature_correlations(df: pd.DataFrame) -> pd.DataFrame:
    excluded = {
        "actual_inn1_wins", "market_p_inn1", "raw_p_inn1", "iso_p_inn1",
        "market_sqerr", "raw_sqerr", "iso_sqerr", "model_market_gap",
        "abs_model_market_gap", "model_brier_advantage",
    }
    rows = []
    for col in df.columns:
        if col in excluded or not pd.api.types.is_numeric_dtype(df[col]):
            continue
        x = pd.to_numeric(df[col], errors="coerce")
        if x.notna().sum() < 50 or x.nunique(dropna=True) < 3:
            continue
        rows.append({
            "feature": col,
            "corr_model_market_gap": float(x.corr(df["model_market_gap"])),
            "corr_abs_gap": float(x.corr(df["abs_model_market_gap"])),
            "corr_model_brier_advantage": float(x.corr(df["model_brier_advantage"])),
        })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["abs_corr_model_brier_advantage"] = out["corr_model_brier_advantage"].abs()
    return out.sort_values("abs_corr_model_brier_advantage", ascending=False)


def feature_bins(df: pd.DataFrame, corr_df: pd.DataFrame, top_n: int = 8) -> pd.DataFrame:
    rows = []
    for feature in corr_df.head(top_n)["feature"]:
        x = pd.to_numeric(df[feature], errors="coerce")
        if x.nunique(dropna=True) < 4:
            continue
        try:
            bins = pd.qcut(x, q=4, duplicates="drop")
        except ValueError:
            continue
        for bin_label, group in df.groupby(bins, observed=True):
            rows.append({
                "feature": feature,
                "bin": str(bin_label),
                "n": len(group),
                "avg_gap": float(group["model_market_gap"].mean()),
                "avg_abs_gap": float(group["abs_model_market_gap"].mean()),
                "model_brier_advantage": float(group["model_brier_advantage"].mean()),
                "market_brier": float(group["market_sqerr"].mean()),
                "iso_brier": float(group["iso_sqerr"].mean()),
            })
    return pd.DataFrame(rows)


def candidate_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "raw_p_inn1", "iso_p_inn1", "market_p_inn1", "over", "phase",
        "wickets_lost", "required_run_rate", "current_run_rate",
        "target_above_par", "inn1_defendability", "venue_chase_success",
        "rrr_times_wickets", "chase_difficulty", "dls_pressure_index",
        "resource_win_prob",
    ]
    out = df[[c for c in columns if c in df.columns]].copy()
    for col in ["raw_p_inn1", "iso_p_inn1", "market_p_inn1", "resource_win_prob"]:
        if col in out:
            out[col] = logit(out[col])
    return out


def evaluate_candidates(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    matches = df[["cs_match_id", "date"]].drop_duplicates().sort_values(["date", "cs_match_id"])
    rows = []
    settings = {}
    for frac in [0.33, 0.50, 0.67]:
        cut = max(3, int(len(matches) * frac))
        train_ids = set(matches.iloc[:cut]["cs_match_id"].astype(str))
        test_ids = set(matches.iloc[cut:]["cs_match_id"].astype(str))
        train = df[df["cs_match_id"].astype(str).isin(train_ids)].copy()
        test = df[df["cs_match_id"].astype(str).isin(test_ids)].copy()
        y_train = train["actual_inn1_wins"].astype(int).to_numpy()
        y_test = test["actual_inn1_wins"].astype(int).to_numpy()

        candidates: dict[str, np.ndarray] = {
            "market": test["market_p_inn1"].to_numpy(),
            "raw_v6": test["raw_p_inn1"].to_numpy(),
            "iso_v6": test["iso_p_inn1"].to_numpy(),
            "iso_95_market_05": 0.95 * test["iso_p_inn1"].to_numpy() + 0.05 * test["market_p_inn1"].to_numpy(),
            "iso_90_market_10": 0.90 * test["iso_p_inn1"].to_numpy() + 0.10 * test["market_p_inn1"].to_numpy(),
            "iso_80_market_20": 0.80 * test["iso_p_inn1"].to_numpy() + 0.20 * test["market_p_inn1"].to_numpy(),
        }

        weights = np.linspace(0.0, 1.0, 101)
        best_weight = min(
            weights,
            key=lambda w: log_loss(
                y_train,
                clip_prob(w * train["iso_p_inn1"].to_numpy() + (1 - w) * train["market_p_inn1"].to_numpy()),
            ),
        )
        settings[f"split_{frac:.2f}_best_model_blend_weight"] = float(best_weight)
        candidates["train_opt_iso_market_blend"] = (
            best_weight * test["iso_p_inn1"].to_numpy()
            + (1 - best_weight) * test["market_p_inn1"].to_numpy()
        )

        for name, cols in {
            "platt_iso_only": ["iso_p_inn1"],
            "platt_raw_iso": ["raw_p_inn1", "iso_p_inn1"],
        }.items():
            x_train = np.column_stack([logit(train[col]) for col in cols])
            x_test = np.column_stack([logit(test[col]) for col in cols])
            model = LogisticRegression(C=1.0, max_iter=1000)
            model.fit(x_train, y_train)
            candidates[name] = model.predict_proba(x_test)[:, 1]

        x_train = np.column_stack([logit(train["iso_p_inn1"]), logit(train["market_p_inn1"])])
        x_test = np.column_stack([logit(test["iso_p_inn1"]), logit(test["market_p_inn1"])])
        stack = LogisticRegression(C=0.1, max_iter=1000)
        stack.fit(x_train, y_train)
        candidates["stack_iso_market"] = stack.predict_proba(x_test)[:, 1]

        x_train_df = candidate_feature_frame(train)
        x_test_df = candidate_feature_frame(test)
        numeric_cols = [c for c in x_train_df.columns if c != "phase"]
        categorical_cols = ["phase"] if "phase" in x_train_df.columns else []
        feature_stack = Pipeline([
            ("prep", ColumnTransformer([
                ("num", StandardScaler(), numeric_cols),
                ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_cols),
            ])),
            ("lr", LogisticRegression(C=0.05, max_iter=1000)),
        ])
        feature_stack.fit(x_train_df, y_train)
        candidates["stack_market_features"] = feature_stack.predict_proba(x_test_df)[:, 1]

        iso_brier, iso_logloss = metric_pair(y_test, test["iso_p_inn1"].to_numpy())
        market_brier, market_logloss = metric_pair(y_test, test["market_p_inn1"].to_numpy())
        for method, prediction in candidates.items():
            brier, ll = metric_pair(y_test, prediction)
            rows.append({
                "split_train_frac": frac,
                "train_matches": len(train_ids),
                "test_matches": len(test_ids),
                "test_rows": len(test),
                "test_start": test["date"].min(),
                "test_end": test["date"].max(),
                "method": method,
                "brier": brier,
                "log_loss": ll,
                "delta_brier_vs_iso": brier - iso_brier,
                "delta_log_loss_vs_iso": ll - iso_logloss,
                "delta_brier_vs_market": brier - market_brier,
                "delta_log_loss_vs_market": ll - market_logloss,
            })
    return pd.DataFrame(rows), settings


def write_report(
    output_dir: Path,
    segment_df: pd.DataFrame,
    corr_df: pd.DataFrame,
    bin_df: pd.DataFrame,
    candidate_df: pd.DataFrame,
    settings: dict,
) -> None:
    overall = segment_df[segment_df["segment"].eq("innings_2")]
    candidate_mean = (
        candidate_df.groupby("method")
        .agg(
            splits=("split_train_frac", "nunique"),
            brier=("brier", "mean"),
            log_loss=("log_loss", "mean"),
            delta_brier_vs_iso=("delta_brier_vs_iso", "mean"),
            delta_log_loss_vs_iso=("delta_log_loss_vs_iso", "mean"),
            delta_brier_vs_market=("delta_brier_vs_market", "mean"),
            delta_log_loss_vs_market=("delta_log_loss_vs_market", "mean"),
        )
        .reset_index()
        .sort_values("brier")
    )

    candidate_pass = candidate_mean[
        candidate_mean["delta_brier_vs_iso"].lt(0)
        & candidate_mean["delta_log_loss_vs_iso"].lt(0)
        & candidate_mean["delta_brier_vs_market"].lt(0)
        & candidate_mean["delta_log_loss_vs_market"].lt(0)
    ]

    lines = [
        "# IPL Innings-2 Gap EDA",
        "",
        f"**Generated**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Current innings-2 accuracy",
        "",
        "| Probability | N | Brier | LogLoss | Mean Prob | Actual |",
        "|-------------|---|-------|---------|-----------|--------|",
    ]
    for row in overall.itertuples():
        lines.append(
            f"| `{row.probability}` | {row.n} | {row.brier:.4f} | "
            f"{row.log_loss:.4f} | {row.mean_prob:.4f} | {row.actual_rate:.4f} |"
        )

    lines += [
        "",
        "## Top feature correlations",
        "",
        "Positive `corr_model_brier_advantage` means the model beats market more as the feature increases.",
        "",
        "| Feature | Corr Gap | Corr Abs Gap | Corr Model Advantage |",
        "|---------|----------|--------------|----------------------|",
    ]
    for row in corr_df.head(15).itertuples():
        lines.append(
            f"| `{row.feature}` | {row.corr_model_market_gap:+.3f} | "
            f"{row.corr_abs_gap:+.3f} | {row.corr_model_brier_advantage:+.3f} |"
        )

    lines += [
        "",
        "## Candidate chronological split means",
        "",
        "| Method | Splits | Brier | LogLoss | ΔBrier vs iso | ΔLogLoss vs iso | ΔBrier vs market | ΔLogLoss vs market |",
        "|--------|--------|-------|---------|----------------|-----------------|------------------|-------------------|",
    ]
    for row in candidate_mean.itertuples():
        lines.append(
            f"| `{row.method}` | {row.splits} | {row.brier:.4f} | {row.log_loss:.4f} | "
            f"{row.delta_brier_vs_iso:+.4f} | {row.delta_log_loss_vs_iso:+.4f} | "
            f"{row.delta_brier_vs_market:+.4f} | {row.delta_log_loss_vs_market:+.4f} |"
        )

    lines += ["", "## Recommendation", ""]
    if candidate_pass.empty:
        lines.append(
            "No tested post-processor consistently improves IPL v6 iso on both Brier and log loss "
            "while also beating market. Keep IPL v6 iso for innings 2 and focus next on feature-level "
            "retraining with chase-state candidates rather than post-hoc calibration."
        )
    else:
        best = candidate_pass.iloc[0]
        lines.append(
            f"Candidate `{best['method']}` improves v6 iso on average and still beats market. "
            "Treat it as candidate-only until a larger holdout confirms the gain."
        )

    lines += [
        "",
        "## Blend settings",
        "",
        "```json",
        json.dumps(settings, indent=2),
        "```",
    ]

    (output_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    joined = join_market_features(Path(args.comparison), Path(args.features))
    segment_df = summarize_segments(joined)
    corr_df = feature_correlations(joined)
    bin_df = feature_bins(joined, corr_df)
    candidate_df, settings = evaluate_candidates(joined)

    joined.to_parquet(output_dir / "joined_inn2.parquet", index=False)
    segment_df.to_csv(output_dir / "segment_metrics.csv", index=False)
    corr_df.to_csv(output_dir / "feature_correlations.csv", index=False)
    bin_df.to_csv(output_dir / "feature_bins.csv", index=False)
    candidate_df.to_csv(output_dir / "candidate_chrono_splits.csv", index=False)
    (output_dir / "candidate_settings.json").write_text(json.dumps(settings, indent=2), encoding="utf-8")
    write_report(output_dir, segment_df, corr_df, bin_df, candidate_df, settings)

    print(f"Rows: {len(joined)}, matches: {joined['cs_match_id'].nunique()}")
    print(segment_df[segment_df["segment"].eq("innings_2")].to_string(index=False))
    print("\nTop feature correlations:")
    print(corr_df.head(12).to_string(index=False))
    print("\nCandidate means:")
    print(
        candidate_df.groupby("method")
        .agg(
            brier=("brier", "mean"),
            log_loss=("log_loss", "mean"),
            delta_brier_vs_iso=("delta_brier_vs_iso", "mean"),
            delta_log_loss_vs_iso=("delta_log_loss_vs_iso", "mean"),
            delta_brier_vs_market=("delta_brier_vs_market", "mean"),
            delta_log_loss_vs_market=("delta_log_loss_vs_market", "mean"),
        )
        .sort_values("brier")
        .to_string()
    )
    print(f"Wrote artifacts to {output_dir}")


if __name__ == "__main__":
    main()
