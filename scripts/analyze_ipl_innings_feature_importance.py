"""
Analyze IPL feature importance by innings and phase.

This script separates two related questions:
  1. Which features move the current saved model inside each segment?
     -> permutation importance on the saved model, scored by Brier delta.
  2. Which features would a segment-specific model learn from the same data?
     -> retrain XGBLogRegEnsemble on each segment and inspect XGB importance.

Usage:
  python scripts/analyze_ipl_innings_feature_importance.py \
    --features data/ipl_features_v6/training.parquet \
    --model-dir models/ipl_v6 \
    --output-dir experiments/ipl_innings_feature_importance_v6
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, roc_auc_score

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from bbl_pipeline.training.trainer import XGBLogRegEnsemble  # noqa: E402


PHASE_ORDER = ["powerplay", "middle", "death"]
MIN_SEGMENT_ROWS = 500


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="IPL innings/phase feature importance analysis"
    )
    parser.add_argument(
        "--features",
        default="data/ipl_features_v6/training.parquet",
        help="Training parquet with v6 features and is_winner target",
    )
    parser.add_argument(
        "--model-dir",
        default="models/ipl_v6",
        help="Directory containing champion_model.joblib",
    )
    parser.add_argument(
        "--output-dir",
        default="experiments/ipl_innings_feature_importance_v6",
        help="Directory for report and CSV artifacts",
    )
    parser.add_argument(
        "--sample-per-segment",
        type=int,
        default=30000,
        help="Maximum rows per segment for permutation importance",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=3,
        help="Shuffle repeats per feature for permutation importance",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for sampling and shuffling",
    )
    parser.add_argument(
        "--segment-model-scope",
        choices=["none", "innings", "all"],
        default="innings",
        help="Which segment-specific models to train for comparison",
    )
    return parser.parse_args()


def phase_from_overs_remaining(overs_remaining: pd.Series) -> pd.Series:
    overs_done = 20.0 - overs_remaining.astype(float)
    phase = np.where(
        overs_done < 6.0,
        "powerplay",
        np.where(overs_done < 15.0, "middle", "death"),
    )
    return pd.Series(phase, index=overs_remaining.index)


def segment_masks(df: pd.DataFrame) -> dict[str, pd.Series]:
    masks: dict[str, pd.Series] = {}
    phases = phase_from_overs_remaining(df["overs_remaining"])
    for innings in [1, 2]:
        inn_mask = df["innings"].astype(int).eq(innings)
        masks[f"innings_{innings}"] = inn_mask
        for phase in PHASE_ORDER:
            masks[f"innings_{innings}_{phase}"] = inn_mask & phases.eq(phase)
    return masks


def get_model_features(model: object, df: pd.DataFrame) -> list[str]:
    features = list(getattr(model, "selected_features_", []) or [])
    if not features:
        features = [f for f in XGBLogRegEnsemble.TOP_FEATURES if f in df.columns]
    missing = [f for f in features if f not in df.columns]
    if missing:
        raise ValueError(f"Feature columns missing from dataset: {missing}")
    return features


def sample_segment(
    X: pd.DataFrame,
    y: pd.Series,
    max_rows: int,
    rng: np.random.Generator,
) -> tuple[pd.DataFrame, pd.Series]:
    if len(X) <= max_rows:
        return X.reset_index(drop=True), y.reset_index(drop=True)
    idx = rng.choice(len(X), size=max_rows, replace=False)
    return X.iloc[idx].reset_index(drop=True), y.iloc[idx].reset_index(drop=True)


def permutation_importance_for_segment(
    model: object,
    X: pd.DataFrame,
    y: pd.Series,
    segment: str,
    repeats: int,
    rng: np.random.Generator,
) -> tuple[list[dict], dict]:
    base_prob = model.predict_proba(X)[:, 1]
    base_brier = float(brier_score_loss(y, base_prob))
    rows: list[dict] = []

    for feature in X.columns:
        deltas: list[float] = []
        for _ in range(repeats):
            X_perm = X.copy()
            X_perm[feature] = rng.permutation(X_perm[feature].to_numpy())
            prob = model.predict_proba(X_perm)[:, 1]
            deltas.append(float(brier_score_loss(y, prob) - base_brier))
        rows.append(
            {
                "segment": segment,
                "feature": feature,
                "importance_brier_delta": float(np.mean(deltas)),
                "importance_std": float(np.std(deltas)),
                "baseline_brier": base_brier,
                "n": len(X),
                "method": "saved_model_permutation",
            }
        )

    meta = {
        "segment": segment,
        "n": len(X),
        "baseline_brier": base_brier,
        "mean_prediction": float(np.mean(base_prob)),
        "actual_win_rate": float(np.mean(y)),
    }
    return rows, meta


def fit_segment_model_importance(
    df: pd.DataFrame,
    feature_cols: list[str],
    segment: str,
) -> list[dict]:
    y = df["is_winner"].astype(int)
    X = df[feature_cols]
    model = XGBLogRegEnsemble(n_features=len(feature_cols))
    model.fit(X, y)
    fi = model.get_feature_importance().copy()
    fi["segment"] = segment
    fi["n"] = len(df)
    fi["method"] = "segment_model_xgb"
    fi = fi.rename(columns={"importance": "importance_xgb"})
    return fi.to_dict("records")


def single_feature_signal(
    df: pd.DataFrame,
    feature_cols: Iterable[str],
    segment: str,
) -> list[dict]:
    y = df["is_winner"].astype(int)
    rows: list[dict] = []
    for feature in feature_cols:
        s = pd.to_numeric(df[feature], errors="coerce")
        valid = s.notna() & y.notna()
        if valid.sum() < MIN_SEGMENT_ROWS or s[valid].nunique() < 2:
            continue
        xv = s[valid].astype(float)
        yv = y[valid].astype(int)
        corr = float(xv.corr(yv))
        try:
            auc = float(roc_auc_score(yv, xv))
            auc_abs = max(auc, 1.0 - auc)
        except ValueError:
            auc = np.nan
            auc_abs = np.nan
        rows.append(
            {
                "segment": segment,
                "feature": feature,
                "n": int(valid.sum()),
                "winner_mean": float(xv[yv == 1].mean()),
                "loser_mean": float(xv[yv == 0].mean()),
                "winner_minus_loser": float(xv[yv == 1].mean() - xv[yv == 0].mean()),
                "corr_with_target": corr,
                "auc_raw": auc,
                "auc_abs": auc_abs,
            }
        )
    return rows


def top_features(df: pd.DataFrame, segment: str, metric: str, top_n: int = 10) -> list[str]:
    part = df[df["segment"] == segment].sort_values(metric, ascending=False).head(top_n)
    return [f"`{r.feature}` ({getattr(r, metric):.4f})" for r in part.itertuples()]


def write_report(
    output_dir: Path,
    metadata: dict,
    perm_df: pd.DataFrame,
    segment_model_df: pd.DataFrame,
    signal_df: pd.DataFrame,
) -> None:
    lines = [
        "# IPL Innings Feature Importance",
        "",
        "This report separates current-model sensitivity from segment-specific learnability.",
        "",
        "## Inputs",
        "",
        f"- Features: `{metadata['features']}`",
        f"- Model: `{metadata['model_dir']}`",
        f"- Rows: {metadata['rows']:,}",
        f"- Features analyzed: {metadata['n_features']}",
        f"- Permutation repeats: {metadata['repeats']}",
        f"- Sample per segment: {metadata['sample_per_segment']:,}",
        "",
        "## Saved v6 Model: Permutation Importance",
        "",
        "Higher Brier delta means the saved model depends more on that feature inside the segment.",
        "",
    ]

    for segment in ["innings_1", "innings_2"]:
        if segment in set(perm_df["segment"]):
            lines += [
                f"### {segment}",
                "",
                ", ".join(top_features(perm_df, segment, "importance_brier_delta")),
                "",
            ]

    lines += [
        "## Segment-Specific Models",
        "",
        "These rankings show what the same model family learns when trained only on a segment.",
        "",
    ]

    if not segment_model_df.empty:
        for segment in ["innings_1", "innings_2"]:
            if segment in set(segment_model_df["segment"]):
                lines += [
                    f"### {segment}",
                    "",
                    ", ".join(top_features(segment_model_df, segment, "importance_xgb")),
                    "",
                ]
    else:
        lines += ["_Skipped._", ""]

    lines += [
        "## Carryover Feature Read",
        "",
        "The v6 chase-prior features should be interpreted mainly through innings 2.",
        "",
    ]

    carryover = [
        "venue_chase_success",
        "target_above_par",
        "inn1_defendability",
        "inn1_wickets_lost",
        "inn1_death_rr",
        "inn1_pp_runs",
        "batting_won_toss",
    ]
    cols = ["segment", "feature", "importance_brier_delta"]
    available = [c for c in cols if c in perm_df.columns]
    carry = perm_df[
        perm_df["segment"].isin(["innings_1", "innings_2"])
        & perm_df["feature"].isin(carryover)
    ][available].sort_values(["segment", "importance_brier_delta"], ascending=[True, False])
    if not carry.empty:
        lines += ["| Segment | Feature | Brier Delta |", "|---------|---------|-------------|"]
        for row in carry.itertuples():
            lines.append(f"| {row.segment} | `{row.feature}` | {row.importance_brier_delta:.5f} |")
        lines.append("")

    lines += [
        "## Artifacts",
        "",
        "- `saved_model_permutation_importance.csv`",
        "- `segment_model_feature_importance.csv`",
        "- `single_feature_signal.csv`",
        "- `segment_metrics.json`",
        "",
    ]

    report_path = output_dir / "REPORT.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    features_path = Path(args.features)
    model_dir = Path(args.model_dir)
    model_path = model_dir / "champion_model.joblib"

    print(f"Loading features: {features_path}")
    df = pd.read_parquet(features_path)
    if "is_winner" not in df.columns or "innings" not in df.columns:
        raise ValueError("Input must include is_winner and innings columns")
    if "overs_remaining" not in df.columns:
        raise ValueError("Input must include overs_remaining for phase analysis")

    print(f"Loading model: {model_path}")
    model = joblib.load(model_path)
    feature_cols = get_model_features(model, df)
    masks = segment_masks(df)
    rng = np.random.default_rng(args.seed)

    perm_rows: list[dict] = []
    segment_metrics: list[dict] = []
    signal_rows: list[dict] = []
    segment_model_rows: list[dict] = []

    print("Running saved-model permutation importance...")
    for segment, mask in masks.items():
        seg_df = df.loc[mask].copy()
        if len(seg_df) < MIN_SEGMENT_ROWS:
            continue
        X_seg, y_seg = sample_segment(
            seg_df[feature_cols],
            seg_df["is_winner"].astype(int),
            args.sample_per_segment,
            rng,
        )
        rows, meta = permutation_importance_for_segment(
            model=model,
            X=X_seg,
            y=y_seg,
            segment=segment,
            repeats=args.repeats,
            rng=rng,
        )
        perm_rows.extend(rows)
        segment_metrics.append(meta)
        signal_rows.extend(single_feature_signal(seg_df, feature_cols, segment))
        print(f"  {segment}: n={len(X_seg):,}, Brier={meta['baseline_brier']:.4f}")

    if args.segment_model_scope != "none":
        print("Training segment-specific models for comparison...")
        for segment, mask in masks.items():
            if args.segment_model_scope == "innings" and segment not in {"innings_1", "innings_2"}:
                continue
            seg_df = df.loc[mask].copy()
            if len(seg_df) < MIN_SEGMENT_ROWS:
                continue
            segment_model_rows.extend(
                fit_segment_model_importance(seg_df, feature_cols, segment)
            )
            print(f"  {segment}: trained on {len(seg_df):,} rows")

    perm_df = pd.DataFrame(perm_rows).sort_values(
        ["segment", "importance_brier_delta"], ascending=[True, False]
    )
    segment_model_df = pd.DataFrame(segment_model_rows)
    if not segment_model_df.empty:
        segment_model_df = segment_model_df.sort_values(
            ["segment", "importance_xgb"], ascending=[True, False]
        )
    signal_df = pd.DataFrame(signal_rows)
    if not signal_df.empty:
        signal_df = signal_df.sort_values(["segment", "auc_abs"], ascending=[True, False])

    perm_df.to_csv(output_dir / "saved_model_permutation_importance.csv", index=False)
    segment_model_df.to_csv(output_dir / "segment_model_feature_importance.csv", index=False)
    signal_df.to_csv(output_dir / "single_feature_signal.csv", index=False)
    (output_dir / "segment_metrics.json").write_text(
        json.dumps(segment_metrics, indent=2), encoding="utf-8"
    )

    metadata = {
        "features": str(features_path),
        "model_dir": str(model_dir),
        "rows": len(df),
        "n_features": len(feature_cols),
        "sample_per_segment": args.sample_per_segment,
        "repeats": args.repeats,
    }
    write_report(output_dir, metadata, perm_df, segment_model_df, signal_df)

    print(f"Artifacts written to: {output_dir}")
    print("Top saved-model permutation features:")
    for segment in ["innings_1", "innings_2"]:
        top = perm_df[perm_df["segment"] == segment].head(8)
        print(f"\n{segment}")
        print(top[["feature", "importance_brier_delta"]].to_string(index=False))


if __name__ == "__main__":
    main()
