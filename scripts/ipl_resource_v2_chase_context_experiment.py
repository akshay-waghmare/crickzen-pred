"""IPL resource_v2 chase-context experiment.

This is a reversible experiment only. It does not modify v14 artifacts or
production wiring.

Goal:
  1. Keep the current IPL resource sigmoid as the base chase prior.
  2. Add a small bounded logit residual from live-available chase context.
  3. Evaluate resource-only quality and v14 add/replace variants on 2025+ OOS.

No final-holdout leakage:
  - 2025+ rows are never used to fit the resource_v2 adjuster.
  - Pre-2025 model-training rows receive season-fold OOF resource_v2 values.
"""

from __future__ import annotations

import json
import pickle
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, logit
from sklearn.metrics import brier_score_loss, log_loss

sys.path.insert(0, "src")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_ipl_v14_pitch_features import add_pitch_features  # noqa: E402
from ipl_v13_mid_split_common import load_training_data, season_folds  # noqa: E402
from ipl_v15_context_resource_experiment import (  # noqa: E402
    BASE_PROB,
    build_bucket_report,
    build_delta_summary,
    build_v14_features,
    evaluate_oos_version,
    metric_dict,
    print_table,
    replace_resource_feature,
)


OUT_DIR = Path("models/ipl_resource_v2_chase_context")
CONTEXT_PROB = "resource_win_prob_v2"
EPS = 1e-6

RAW_CONTEXT_FEATURES = [
    "partnership_solidity_v2",
    "set_batter_exposure_v2",
    "recent_rate_edge_v2",
    "chase_completion_effect_v2",
    "wicket_safety_v2",
]


@dataclass
class ChaseContextResourceAdjuster:
    """Offset-logit resource adjuster with fixed base resource slope = 1."""

    l2: float = 0.03
    eps: float = EPS
    intercept_: float = 0.0
    coef_: np.ndarray | None = None
    medians_: np.ndarray | None = None
    means_: np.ndarray | None = None
    scales_: np.ndarray | None = None

    def _prepare_fit_X(self, df: pd.DataFrame) -> np.ndarray:
        x = df[RAW_CONTEXT_FEATURES].astype(float).replace([np.inf, -np.inf], np.nan)
        self.medians_ = x.median(numeric_only=True).fillna(0.0).values
        x = x.fillna(pd.Series(self.medians_, index=RAW_CONTEXT_FEATURES))
        self.means_ = x.mean().values
        self.scales_ = x.std(ddof=0).replace(0, 1.0).fillna(1.0).values
        return ((x.values - self.means_) / self.scales_).astype(float)

    def _prepare_X(self, df: pd.DataFrame) -> np.ndarray:
        if self.medians_ is None or self.means_ is None or self.scales_ is None:
            raise RuntimeError("ChaseContextResourceAdjuster is not fitted")
        x = df[RAW_CONTEXT_FEATURES].astype(float).replace([np.inf, -np.inf], np.nan)
        x = x.fillna(pd.Series(self.medians_, index=RAW_CONTEXT_FEATURES))
        return ((x.values - self.means_) / self.scales_).astype(float)

    def fit(self, df: pd.DataFrame) -> "ChaseContextResourceAdjuster":
        x = self._prepare_fit_X(df)
        y = df["is_winner"].astype(float).values
        base = np.clip(df[BASE_PROB].astype(float).values, self.eps, 1.0 - self.eps)
        offset = logit(base)

        def objective(params: np.ndarray) -> float:
            intercept = params[0]
            coef = params[1:]
            pred = expit(offset + intercept + x @ coef)
            pred = np.clip(pred, self.eps, 1.0 - self.eps)
            penalty = self.l2 * float(np.dot(coef, coef)) / max(len(coef), 1)
            return float(log_loss(y, pred, labels=[0, 1]) + penalty)

        result = minimize(
            objective,
            np.zeros(x.shape[1] + 1, dtype=float),
            method="BFGS",
            options={"maxiter": 1000},
        )
        if not result.success:
            raise RuntimeError(f"resource_v2 adjuster fit failed: {result.message}")
        self.intercept_ = float(result.x[0])
        self.coef_ = result.x[1:].astype(float)
        return self

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        if self.coef_ is None:
            raise RuntimeError("ChaseContextResourceAdjuster is not fitted")
        x = self._prepare_X(df)
        base = np.clip(df[BASE_PROB].astype(float).values, self.eps, 1.0 - self.eps)
        return expit(logit(base) + self.intercept_ + x @ self.coef_)

    def coefficients(self) -> dict[str, float]:
        if self.coef_ is None:
            return {}
        return {
            feature: float(coef)
            for feature, coef in zip(RAW_CONTEXT_FEATURES, self.coef_)
        }


def _safe_div(numer: pd.Series, denom: pd.Series, default: float = 0.0) -> pd.Series:
    out = numer.astype(float) / denom.astype(float).replace(0, np.nan)
    return out.replace([np.inf, -np.inf], np.nan).fillna(default)


def add_chase_context_features(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    legal_balls = (d["over"].astype(float) * 6.0 + d["ball"].astype(float)).clip(1, 120)
    overs_bowled = legal_balls / 6.0
    current_score = d["current_run_rate"].astype(float).fillna(0.0) * overs_bowled
    runs_to_get = d["required_run_rate"].astype(float).fillna(0.0) * d["overs_remaining"].astype(float).fillna(0.0)
    target = (current_score + runs_to_get).clip(lower=1.0)

    required_runs_last_18 = d["required_run_rate"].astype(float).fillna(0.0) * 3.0
    recent_rate_edge = d["runs_last_18"].astype(float).fillna(18.0) - required_runs_last_18

    over = d["over"].astype(float)
    phase_weight = np.select(
        [over <= 6, over <= 11, over <= 15],
        [0.25, 0.60, 1.00],
        default=1.00,
    )

    d["partnership_solidity_v2"] = d.get("partnership_solidity", 0.0)
    d["partnership_solidity_v2"] = d["partnership_solidity_v2"].astype(float).fillna(0.0).clip(0.0, 1.0)
    d["set_batter_exposure_v2"] = (d.get("set_batter_exposure", 0.0).astype(float).fillna(0.0) / 40.0).clip(0.0, 1.0)
    d["recent_rate_edge_v2"] = (recent_rate_edge / 20.0).clip(-1.0, 1.0)
    d["chase_completion_v2"] = _safe_div(current_score, target).clip(0.0, 1.0)
    d["chase_completion_effect_v2"] = (d["chase_completion_v2"] * phase_weight).clip(0.0, 1.0)
    d["wicket_safety_v2"] = ((7.0 - d["wickets_lost"].astype(float).fillna(0.0)) / 7.0).clip(0.0, 1.0)
    return d


def prepare_data() -> pd.DataFrame:
    df = add_pitch_features(load_training_data())
    df["season"] = df["season"].astype(str)
    df[BASE_PROB] = df[BASE_PROB].astype(float).clip(EPS, 1.0 - EPS)
    return add_chase_context_features(df)


def add_resource_v2_oof(
    df: pd.DataFrame,
    fit_mask: pd.Series,
    apply_mask: pd.Series | None = None,
    n_folds: int = 5,
) -> tuple[pd.Series, ChaseContextResourceAdjuster]:
    out = pd.Series(np.nan, index=df.index, dtype=float)
    fit_df = df[fit_mask].copy()
    seasons = sorted(fit_df["season"].astype(str).unique().tolist())

    for val_seasons in season_folds(seasons, n_folds=n_folds):
        val_mask = fit_mask & df["season"].isin(val_seasons)
        train_mask = fit_mask & ~df["season"].isin(val_seasons)
        if train_mask.sum() == 0 or val_mask.sum() == 0:
            continue
        adjuster = ChaseContextResourceAdjuster().fit(df[train_mask])
        out.loc[val_mask] = adjuster.transform(df[val_mask])

    final_adjuster = ChaseContextResourceAdjuster().fit(fit_df)
    missing_fit = fit_mask & out.isna()
    if missing_fit.any():
        out.loc[missing_fit] = final_adjuster.transform(df[missing_fit])

    if apply_mask is not None and apply_mask.any():
        out.loc[apply_mask] = final_adjuster.transform(df[apply_mask])

    return out.clip(EPS, 1.0 - EPS), final_adjuster


def build_feature_versions(v14: dict[str, list[str]]) -> dict[str, dict[str, list[str]]]:
    return {
        "v14_original": v14,
        "resource_v2_add": {
            phase: list(dict.fromkeys(features + [CONTEXT_PROB]))
            for phase, features in v14.items()
        },
        "resource_v2_replace": {
            phase: replace_resource_feature(features)
            for phase, features in v14.items()
        },
    }


def resource_benchmark(df: pd.DataFrame) -> pd.DataFrame:
    test = df[df["season"] >= "2025"].copy()
    test["target_bucket"] = np.select(
        [test["target_above_par"] < -20.0, test["target_above_par"] > 20.0],
        ["below_par_easy", "above_par_hard"],
        default="par",
    )
    windows = {
        "pp_1_6": test["over"].between(1, 6),
        "early_mid_7_12": test["over"].between(7, 12),
        "late_mid_13_15": test["over"].between(13, 15),
        "full_mid_7_15": test["over"].between(7, 15),
        "all_inn2": pd.Series(True, index=test.index),
    }

    rows = []
    for window, mask in windows.items():
        for bucket, sub in test[mask].groupby("target_bucket", dropna=False):
            if len(sub) < 30:
                continue
            y = sub["is_winner"].astype(float).values
            for label, col in [("resource_v1", BASE_PROB), ("resource_v2", CONTEXT_PROB)]:
                pred = sub[col].astype(float).clip(EPS, 1.0 - EPS).values
                metrics = metric_dict(y, pred)
                rows.append(
                    {
                        "window": window,
                        "target_bucket": bucket,
                        "model": label,
                        "n": len(sub),
                        "mean_pred": float(pred.mean()),
                        "actual_wr": float(y.mean()),
                        "gap_pp": float((pred.mean() - y.mean()) * 100.0),
                        "brier": metrics["brier"],
                        "logloss": metrics["logloss"],
                    }
                )
    return pd.DataFrame(rows)


def build_resource_scorecard_replay(final_adjuster: ChaseContextResourceAdjuster) -> pd.DataFrame | None:
    replay_path = Path("experiments/ipl_v14_mid_missing_feature_groups/scorecard_replay_with_betx21_market_csk_srh_2026_05_18.csv")
    if not replay_path.exists():
        return None

    from bbl_pipeline.features.calculator import ResourceFeatureCalculator  # noqa: WPS433
    from bbl_pipeline.features.format_config import FormatConfig  # noqa: WPS433

    calc = ResourceFeatureCalculator(FormatConfig.ipl())
    replay = pd.read_csv(replay_path)
    rows = []
    for _, row in replay.iterrows():
        over_decimal = float(row["overs"])
        over_int = int(over_decimal)
        ball = int(round((over_decimal - over_int) * 10))
        legal = over_int * 6 + ball
        balls_remaining = int(max(0, 120 - legal))
        overs_remaining = balls_remaining / 6.0
        score = float(row["score"])
        wickets = int(row["wickets"])
        current_run_rate = score / max(legal / 6.0, 1e-6)
        runs_required = 181.0 - score
        required_run_rate = runs_required / max(overs_remaining, 1e-6)
        resource_pct = calc.calculate_resource_percentage(overs_remaining, wickets)
        resource_v1 = calc.calculate_resource_win_probability(
            innings=2,
            expected_final_score=0.0,
            target_runs=181.0,
            resource_pct=resource_pct,
            current_run_rate=current_run_rate,
            required_run_rate=required_run_rate,
            current_score=score,
            balls_remaining=balls_remaining,
            wickets_lost=wickets,
        )
        rows.append(
            {
                "season": "2026",
                "over": over_int,
                "ball": max(ball, 1),
                "overs": over_decimal,
                "score": score,
                "wickets_lost": wickets,
                "current_run_rate": current_run_rate,
                "required_run_rate": required_run_rate,
                "overs_remaining": overs_remaining,
                "balls_remaining": balls_remaining,
                "resource_win_prob": resource_v1,
                "partnership_solidity": row.get("partnership_solidity", 0.0),
                "set_batter_exposure": row.get("set_batter_exposure", 0.0),
                "runs_last_18": row.get("runs_last_18", 18.0),
                "near_srh_market_prob_norm": row.get("near_srh_market_prob_norm", np.nan),
                "scorecard_replay": row.get("scorecard_replay", np.nan),
                "v7_cal": row.get("v7_cal", np.nan),
            }
        )

    scorecard = add_chase_context_features(pd.DataFrame(rows))
    scorecard[CONTEXT_PROB] = final_adjuster.transform(scorecard)
    return scorecard


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Loading IPL inn2 data and building resource_v2 context features...")
    df = prepare_data()

    pre_2025 = df["season"] < "2025"
    oos_2025 = df["season"] >= "2025"
    resource_v2, final_adjuster = add_resource_v2_oof(
        df,
        fit_mask=pre_2025,
        apply_mask=oos_2025,
    )
    df[CONTEXT_PROB] = resource_v2

    print("resource_v2 coefficients (fit on pre-2025 only):")
    for feature, coef in final_adjuster.coefficients().items():
        print(f"  {feature:<32s} {coef:+.6f}")

    with open(OUT_DIR / "resource_v2_adjuster_pre2025.pkl", "wb") as fh:
        pickle.dump(final_adjuster, fh)

    resource_metrics = resource_benchmark(df)
    resource_metrics.to_csv(OUT_DIR / "resource_benchmark.csv", index=False)

    print("Evaluating v14 variants with resource_v2 feature...")
    v14_features = build_v14_features()
    versions = build_feature_versions(v14_features)
    oos_metrics = []
    payloads = {}
    for version, features in versions.items():
        metrics, payload = evaluate_oos_version(df, features)
        metrics["version"] = version
        oos_metrics.append(metrics)
        payloads[version] = payload

    oos_metrics_df = pd.concat(oos_metrics, ignore_index=True)
    bucket_report = build_bucket_report(payloads)
    summary = build_delta_summary(oos_metrics_df, bucket_report)

    oos_metrics_df.to_csv(OUT_DIR / "oos_phase_metrics.csv", index=False)
    bucket_report.to_csv(OUT_DIR / "oos_bucket_report.csv", index=False)
    summary.to_csv(OUT_DIR / "candidate_summary.csv", index=False)

    metadata = {
        "base_probability": BASE_PROB,
        "context_probability": CONTEXT_PROB,
        "context_features": RAW_CONTEXT_FEATURES,
        "formula": "logit(resource_win_prob_v2)=logit(resource_win_prob)+bounded_chase_context_adjustment",
        "fit_policy": "pre-2025 season-fold OOF for training rows; 2025+ OOS transformed by pre-2025 adjuster",
        "coefficients": final_adjuster.coefficients(),
    }
    (OUT_DIR / "resource_v2_features.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    scorecard = build_resource_scorecard_replay(final_adjuster)
    if scorecard is not None:
        scorecard.to_csv(OUT_DIR / "scorecard_replay_resource_v2_csk_srh_2026_05_18.csv", index=False)

    print_table(resource_metrics, "Resource-only OOS benchmark")
    print_table(oos_metrics_df, "v14 OOS phase metrics")
    print_table(summary, "Candidate summary")
    print(f"\nSaved outputs to {OUT_DIR}")


if __name__ == "__main__":
    main()
