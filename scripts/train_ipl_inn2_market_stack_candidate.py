"""
Train an inactive IPL innings-2 market-aware stack candidate.

The candidate is a small logistic stack over:
  - logit(IPL v6 isotonic P(inn1 wins))
  - logit(market P(inn1 wins))

It is only intended for innings-2 states where market probability is available.
Production IPL v6 remains unchanged unless a later rollout task explicitly
promotes this artifact.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss


EPS = 1e-7


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train IPL innings-2 market stack candidate")
    parser.add_argument("--comparison", default="data/ipl_latest_market_vs_model.parquet")
    parser.add_argument("--eda-dir", default="experiments/ipl_inn2_gap_eda_v1")
    parser.add_argument("--output-dir", default="models/ipl_v7_inn2_market_stack_candidate")
    return parser.parse_args()


def clip_prob(prob: np.ndarray | pd.Series) -> np.ndarray:
    return np.clip(np.asarray(prob, dtype=float), EPS, 1.0 - EPS)


def logit(prob: np.ndarray | pd.Series) -> np.ndarray:
    prob = clip_prob(prob)
    return np.log(prob / (1.0 - prob))


def metric_row(name: str, y_true: np.ndarray, y_prob: np.ndarray) -> dict:
    prob = clip_prob(y_prob)
    return {
        "method": name,
        "n": int(len(prob)),
        "brier": float(brier_score_loss(y_true, prob)),
        "log_loss": float(log_loss(y_true, prob)),
        "mean_prob": float(prob.mean()),
        "actual_rate": float(y_true.mean()),
    }


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    comparison = pd.read_parquet(args.comparison)
    train = comparison[comparison["innings"].astype(int).eq(2)].copy()
    train = train.sort_values(["date", "cs_match_id", "over"]).reset_index(drop=True)
    y = train["actual_inn1_wins"].astype(int).to_numpy()
    x = np.column_stack([
        logit(train["iso_p_inn1"]),
        logit(train["market_p_inn1"]),
    ])

    model = LogisticRegression(C=0.1, max_iter=1000)
    model.fit(x, y)
    stacked = model.predict_proba(x)[:, 1]

    metrics = pd.DataFrame([
        metric_row("market", y, train["market_p_inn1"]),
        metric_row("iso_v6", y, train["iso_p_inn1"]),
        metric_row("inn2_market_stack_candidate", y, stacked),
    ])
    metrics["delta_brier_vs_market"] = metrics["brier"] - metrics.loc[metrics["method"].eq("market"), "brier"].iloc[0]
    metrics["delta_log_loss_vs_market"] = metrics["log_loss"] - metrics.loc[metrics["method"].eq("market"), "log_loss"].iloc[0]
    metrics["delta_brier_vs_iso_v6"] = metrics["brier"] - metrics.loc[metrics["method"].eq("iso_v6"), "brier"].iloc[0]
    metrics["delta_log_loss_vs_iso_v6"] = metrics["log_loss"] - metrics.loc[metrics["method"].eq("iso_v6"), "log_loss"].iloc[0]

    split_metrics_path = Path(args.eda_dir) / "candidate_chrono_splits.csv"
    split_summary = {}
    if split_metrics_path.exists():
        split_df = pd.read_csv(split_metrics_path)
        stack_splits = split_df[split_df["method"].eq("stack_iso_market")]
        split_summary = {
            "source": str(split_metrics_path),
            "splits": stack_splits.to_dict("records"),
            "mean": stack_splits[
                [
                    "brier",
                    "log_loss",
                    "delta_brier_vs_iso",
                    "delta_log_loss_vs_iso",
                    "delta_brier_vs_market",
                    "delta_log_loss_vs_market",
                ]
            ].mean().to_dict(),
        }

    artifact = {
        "model": model,
        "input_features": ["logit_iso_p_inn1", "logit_market_p_inn1"],
        "probability_space": "P(innings_1_team_wins)",
        "applies_to": "IPL innings 2 only; fallback to IPL v6 iso when market probability is unavailable",
    }
    joblib.dump(artifact, output_dir / "inn2_market_stack.joblib")
    metrics.to_csv(output_dir / "training_metrics.csv", index=False)

    metadata = {
        "model_version": "ipl_v7_inn2_market_stack_candidate",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "candidate_only_not_registered",
        "base_model": "models/ipl_v6",
        "comparison_source": str(Path(args.comparison).resolve()),
        "training_rows": int(len(train)),
        "training_matches": int(train["cs_match_id"].nunique()),
        "coefficients": {
            "intercept": float(model.intercept_[0]),
            "logit_iso_p_inn1": float(model.coef_[0][0]),
            "logit_market_p_inn1": float(model.coef_[0][1]),
        },
        "metrics": metrics.to_dict("records"),
        "chronological_holdout_summary": split_summary,
        "promotion_notes": [
            "Market-aware: requires live market probability input.",
            "Improves log loss in all tested chronological splits; Brier improves on average but has a small final-split regression vs iso_v6.",
            "Do not replace production IPL v6 without larger holdout/live dry-run validation.",
        ],
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"Saved candidate to {output_dir}")
    print(metrics.to_string(index=False))
    print(json.dumps(metadata["coefficients"], indent=2))


if __name__ == "__main__":
    main()
