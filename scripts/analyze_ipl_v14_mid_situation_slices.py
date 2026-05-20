"""Situation-slice EDA for IPL v14 MID predictions.

Uses saved predictions from experiment_ipl_v14_mid_missing_feature_groups.py and
adds venue/chase context columns from the true-OOS MID rows.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss

sys.path.insert(0, "src")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_ipl_v14_pitch_features import add_pitch_features  # noqa: E402
from experiment_ipl_v14_mid_terminal_features import _ensure_terminal_features  # noqa: E402
from ipl_v13_mid_split_common import load_training_data, phase_slice  # noqa: E402


PRED_DIR = Path("experiments/ipl_v14_mid_missing_feature_groups")
OUT_PATH = PRED_DIR / "situation_slice_metrics.csv"


def _load_test_context() -> pd.DataFrame:
    df = load_training_data()
    df = add_pitch_features(df)
    df = _ensure_terminal_features(df)
    mid = phase_slice(df, (7, 15))
    return mid[mid["season"].astype(str) >= "2025"].copy().reset_index(drop=True)


def _bucketize(pred: pd.DataFrame) -> pd.DataFrame:
    d = pred.copy()
    d["mid_window"] = np.where(d["over"].between(12, 15), "late_12_15", "early_7_11")
    d["par_type"] = np.select(
        [d["target_above_par"] < -20, d["target_above_par"] > 20],
        ["low_target", "high_target"],
        default="par_target",
    )
    d["prob_band"] = pd.cut(
        d["cal_pred"],
        bins=[0.0, 0.5, 0.6, 0.7, 0.8, 1.01],
        labels=["00_50", "50_60", "60_70", "70_80", "80_100"],
        include_lowest=True,
        right=False,
    ).astype(str)
    d["venue_chase_bucket"] = pd.cut(
        d["venue_chase_success"],
        bins=[-0.01, 0.45, 0.55, 1.01],
        labels=["low_venue_chase", "neutral_venue_chase", "high_venue_chase"],
        include_lowest=True,
        right=False,
    ).astype(str)
    d["team_venue_bucket"] = pd.cut(
        d["batting_team_venue_wr"],
        bins=[-0.01, 0.45, 0.55, 1.01],
        labels=["low_team_venue", "neutral_team_venue", "high_team_venue"],
        include_lowest=True,
        right=False,
    ).astype(str)
    if "venue_avg_score" in d.columns:
        d["venue_score_bucket"] = pd.qcut(
            d["venue_avg_score"].rank(method="first"),
            q=3,
            labels=["low_avg_score_venue", "mid_avg_score_venue", "high_avg_score_venue"],
        ).astype(str)
    else:
        d["venue_score_bucket"] = "unknown"
    return d


def _metrics(pred: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    rows = []
    for keys, sub in pred.groupby(group_cols, dropna=False):
        if len(sub) < 40:
            continue
        y = sub["is_winner"].astype(float)
        p = sub["cal_pred"].clip(1e-6, 1 - 1e-6)
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(group_cols, keys))
        row.update(
            {
                "n": int(len(sub)),
                "brier_cal": float(brier_score_loss(y, p)),
                "logloss_cal": float(log_loss(y, p, labels=[0, 1])),
                "mean_pred": float(p.mean()),
                "actual_wr": float(y.mean()),
                "gap_pp": float((p.mean() - y.mean()) * 100.0),
                "target_above_par": float(sub["target_above_par"].mean()),
                "venue_chase_success": float(sub["venue_chase_success"].mean()),
                "batting_team_venue_wr": float(sub["batting_team_venue_wr"].mean()),
            }
        )
        if "venue_avg_score" in sub.columns:
            row["venue_avg_score"] = float(sub["venue_avg_score"].mean())
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    context = _load_test_context()
    context_cols = [
        "venue_chase_success",
        "batting_team_venue_wr",
        "team_strength_diff",
        "inn1_wickets_lost",
        "resources_remaining",
    ]
    if "venue_avg_score" in context.columns:
        context_cols.append("venue_avg_score")

    all_rows = []
    for pred_path in sorted(PRED_DIR.glob("*_predictions.csv")):
        pred = pd.read_csv(pred_path)
        if len(pred) != len(context):
            raise RuntimeError(f"{pred_path} rows={len(pred)} but context rows={len(context)}")
        candidate = pred["candidate"].iloc[0]
        pred = pd.concat([pred.reset_index(drop=True), context[context_cols].reset_index(drop=True)], axis=1)
        pred = _bucketize(pred)

        groupings = [
            ["candidate", "mid_window", "par_type", "prob_band"],
            ["candidate", "mid_window", "par_type", "venue_chase_bucket", "prob_band"],
            ["candidate", "mid_window", "par_type", "team_venue_bucket", "prob_band"],
            ["candidate", "mid_window", "par_type", "venue_score_bucket", "prob_band"],
        ]
        for group_cols in groupings:
            rows = _metrics(pred, group_cols)
            rows.insert(0, "slice", "+".join(group_cols[1:]))
            rows["candidate"] = candidate
            all_rows.append(rows)

    out = pd.concat(all_rows, ignore_index=True)
    out.to_csv(OUT_PATH, index=False)
    focus = out[
        out["candidate"].eq("baseline_mid")
        & out["mid_window"].eq("late_12_15")
        & out["par_type"].eq("par_target")
        & out["prob_band"].isin(["50_60", "60_70", "70_80"])
    ].sort_values("gap_pp")
    print(f"Saved {OUT_PATH}")
    print(focus.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
