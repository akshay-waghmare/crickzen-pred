"""Improve and compare IPL innings-2 resource baseline candidates.

This script only evaluates the resource prior. It does not retrain v14 and does
not change production artifacts.

Fit policy:
  - Fit resource_v2 candidates on seasons < 2025.
  - Judge on seasons >= 2025.
  - Training rows can receive season-fold OOF predictions for diagnostics, but
    final comparison is strictly 2025+.
"""

from __future__ import annotations

import json
import pickle
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, logit
from sklearn.metrics import brier_score_loss, log_loss

sys.path.insert(0, "src")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_ipl_v14_pitch_features import add_pitch_features  # noqa: E402
from ipl_v13_mid_split_common import load_training_data, season_folds  # noqa: E402


OUT_DIR = Path("models/ipl_resource_baseline_v2")
BASE_PROB = "resource_win_prob"
EPS = 1e-6


def _safe_div(numer: pd.Series, denom: pd.Series, default: float = 0.0) -> pd.Series:
    out = numer.astype(float) / denom.astype(float).replace(0, np.nan)
    return out.replace([np.inf, -np.inf], np.nan).fillna(default)


def add_resource_context_features(df: pd.DataFrame) -> pd.DataFrame:
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
    target_above_par = d["target_above_par"].astype(float).fillna(0.0)

    d["partnership_solidity_v2"] = d.get("partnership_solidity", 0.0).astype(float).fillna(0.0).clip(0.0, 1.0)
    d["set_batter_exposure_v2"] = (d.get("set_batter_exposure", 0.0).astype(float).fillna(0.0) / 40.0).clip(0.0, 1.0)
    d["recent_rate_edge_v2"] = (recent_rate_edge / 20.0).clip(-1.0, 1.0)
    d["recent_rate_positive_v2"] = d["recent_rate_edge_v2"].clip(lower=0.0)
    d["chase_completion_v2"] = _safe_div(current_score, target).clip(0.0, 1.0)
    d["chase_completion_effect_v2"] = (d["chase_completion_v2"] * phase_weight).clip(0.0, 1.0)
    d["wicket_safety_v2"] = ((7.0 - d["wickets_lost"].astype(float).fillna(0.0)) / 7.0).clip(0.0, 1.0)

    d["phase_pp_v2"] = (over <= 6).astype(float)
    d["phase_mid_v2"] = ((over >= 7) & (over <= 15)).astype(float)
    d["phase_late_mid_v2"] = ((over >= 12) & (over <= 15)).astype(float)
    d["phase_death_v2"] = (over >= 16).astype(float)
    d["target_below_par_v2"] = (target_above_par < -20.0).astype(float)
    d["target_above_par_v2"] = (target_above_par > 20.0).astype(float)
    d["target_par_v2"] = ((target_above_par >= -20.0) & (target_above_par <= 20.0)).astype(float)
    d["mid_accel_gate_v2"] = (
        (d["phase_mid_v2"] > 0)
        & (d["wickets_lost"].astype(float).fillna(10.0) <= 3.0)
        & (d["recent_rate_edge_v2"] > 0.0)
        & (d["chase_completion_v2"] >= 0.45)
        & (target_above_par >= -20.0)
    ).astype(float)
    d["mid_accel_strength_v2"] = (
        d["mid_accel_gate_v2"]
        * d["recent_rate_positive_v2"]
        * d["chase_completion_effect_v2"]
        * d["wicket_safety_v2"]
    ).clip(0.0, 1.0)
    return d


FEATURE_SETS: dict[str, list[str]] = {
    "context_global": [
        "partnership_solidity_v2",
        "set_batter_exposure_v2",
        "recent_rate_edge_v2",
        "chase_completion_effect_v2",
        "wicket_safety_v2",
    ],
    "phase_target_context": [
        "phase_mid_v2",
        "phase_late_mid_v2",
        "phase_death_v2",
        "target_below_par_v2",
        "target_above_par_v2",
        "partnership_solidity_v2",
        "set_batter_exposure_v2",
        "recent_rate_edge_v2",
        "recent_rate_positive_v2",
        "chase_completion_effect_v2",
        "wicket_safety_v2",
        "mid_accel_strength_v2",
    ],
    "mid_accel_gate_only": [
        "mid_accel_strength_v2",
    ],
}


def mid_accel_apply_mask(df: pd.DataFrame) -> pd.Series:
    return df["mid_accel_gate_v2"].astype(float).gt(0.0)


APPLY_GATES: dict[str, Callable[[pd.DataFrame], pd.Series] | None] = {
    "context_global": None,
    "phase_target_context": None,
    "mid_accel_gate_only": mid_accel_apply_mask,
}


@dataclass
class OffsetLogitAdjuster:
    features: list[str]
    l2: float = 0.03
    eps: float = EPS
    intercept_: float = 0.0
    coef_: np.ndarray | None = None
    medians_: np.ndarray | None = None
    means_: np.ndarray | None = None
    scales_: np.ndarray | None = None

    def _fit_matrix(self, df: pd.DataFrame) -> np.ndarray:
        x = df[self.features].astype(float).replace([np.inf, -np.inf], np.nan)
        self.medians_ = x.median(numeric_only=True).fillna(0.0).values
        x = x.fillna(pd.Series(self.medians_, index=self.features))
        self.means_ = x.mean().values
        self.scales_ = x.std(ddof=0).replace(0, 1.0).fillna(1.0).values
        return ((x.values - self.means_) / self.scales_).astype(float)

    def _matrix(self, df: pd.DataFrame) -> np.ndarray:
        if self.medians_ is None or self.means_ is None or self.scales_ is None:
            raise RuntimeError("OffsetLogitAdjuster is not fitted")
        x = df[self.features].astype(float).replace([np.inf, -np.inf], np.nan)
        x = x.fillna(pd.Series(self.medians_, index=self.features))
        return ((x.values - self.means_) / self.scales_).astype(float)

    def fit(self, df: pd.DataFrame) -> "OffsetLogitAdjuster":
        x = self._fit_matrix(df)
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
            raise RuntimeError(f"Fit failed: {result.message}")
        self.intercept_ = float(result.x[0])
        self.coef_ = result.x[1:].astype(float)
        return self

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        if self.coef_ is None:
            raise RuntimeError("OffsetLogitAdjuster is not fitted")
        x = self._matrix(df)
        base = np.clip(df[BASE_PROB].astype(float).values, self.eps, 1.0 - self.eps)
        return expit(logit(base) + self.intercept_ + x @ self.coef_)

    def coefficients(self) -> dict[str, float]:
        if self.coef_ is None:
            return {}
        return {feature: float(coef) for feature, coef in zip(self.features, self.coef_)}


def fit_candidate_oof(
    df: pd.DataFrame,
    name: str,
    fit_mask: pd.Series,
    apply_mask: pd.Series,
) -> tuple[pd.Series, OffsetLogitAdjuster]:
    features = FEATURE_SETS[name]
    gate_fn = APPLY_GATES[name]
    fit_gate = gate_fn(df) if gate_fn else pd.Series(True, index=df.index)
    fit_rows = fit_mask & fit_gate
    if fit_rows.sum() < 100:
        raise RuntimeError(f"{name}: too few fit rows after gate: {fit_rows.sum()}")

    out = df[BASE_PROB].astype(float).copy()
    fit_df = df[fit_rows].copy()
    seasons = sorted(fit_df["season"].astype(str).unique().tolist())

    for val_seasons in season_folds(seasons, n_folds=5):
        val_mask = fit_rows & df["season"].isin(val_seasons)
        train_mask = fit_rows & ~df["season"].isin(val_seasons)
        if train_mask.sum() == 0 or val_mask.sum() == 0:
            continue
        adj = OffsetLogitAdjuster(features=features).fit(df[train_mask])
        out.loc[val_mask] = adj.transform(df[val_mask])

    final_adj = OffsetLogitAdjuster(features=features).fit(fit_df)
    final_apply = apply_mask & (gate_fn(df) if gate_fn else pd.Series(True, index=df.index))
    if final_apply.any():
        out.loc[final_apply] = final_adj.transform(df[final_apply])

    missing_fit = fit_rows & out.isna()
    if missing_fit.any():
        out.loc[missing_fit] = final_adj.transform(df[missing_fit])

    return out.clip(EPS, 1.0 - EPS), final_adj


def prepare_data() -> pd.DataFrame:
    df = add_pitch_features(load_training_data())
    df["season"] = df["season"].astype(str)
    df[BASE_PROB] = df[BASE_PROB].astype(float).clip(EPS, 1.0 - EPS)
    return add_resource_context_features(df)


def ece(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.clip(np.asarray(y_prob, dtype=float), EPS, 1.0 - EPS)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    value = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (y_prob >= lo) & (y_prob < hi)
        if not mask.any():
            continue
        value += mask.mean() * abs(float(y_prob[mask].mean()) - float(y_true[mask].mean()))
    return float(value)


def metric_row(df: pd.DataFrame, pred_col: str, model: str, window: str, bucket: str) -> dict[str, float | str | int]:
    y = df["is_winner"].astype(float).values
    pred = df[pred_col].astype(float).clip(EPS, 1.0 - EPS).values
    return {
        "window": window,
        "target_bucket": bucket,
        "model": model,
        "n": int(len(df)),
        "mean_pred": float(pred.mean()),
        "actual_wr": float(y.mean()),
        "gap_pp": float((pred.mean() - y.mean()) * 100.0),
        "brier": float(brier_score_loss(y, pred)),
        "logloss": float(log_loss(y, pred, labels=[0, 1])),
        "ece": ece(y, pred),
    }


def build_benchmark(df: pd.DataFrame, pred_cols: dict[str, str]) -> pd.DataFrame:
    test = df[df["season"] >= "2025"].copy()
    test["target_bucket"] = np.select(
        [test["target_above_par"] < -20.0, test["target_above_par"] > 20.0],
        ["below_par_easy", "above_par_hard"],
        default="par",
    )
    windows = {
        "pp_0_6": test["over"].between(0, 6),
        "early_mid_7_12": test["over"].between(7, 12),
        "late_mid_13_15": test["over"].between(13, 15),
        "full_mid_7_15": test["over"].between(7, 15),
        "all_inn2": pd.Series(True, index=test.index),
    }
    rows = []
    for window, mask in windows.items():
        win_df = test[mask]
        for bucket, sub in win_df.groupby("target_bucket", dropna=False):
            if len(sub) < 30:
                continue
            for model, pred_col in pred_cols.items():
                rows.append(metric_row(sub, pred_col, model, window, bucket))
        for model, pred_col in pred_cols.items():
            rows.append(metric_row(win_df, pred_col, model, window, "all_targets"))
    return pd.DataFrame(rows)


def build_summary(benchmark: pd.DataFrame) -> pd.DataFrame:
    overall = benchmark[
        (benchmark["window"] == "all_inn2")
        & (benchmark["target_bucket"] == "all_targets")
    ].copy()
    base = overall[overall["model"] == "resource_v1"].iloc[0]
    rows = []
    for _, row in overall.iterrows():
        rows.append(
            {
                "model": row["model"],
                "brier": row["brier"],
                "brier_delta_pct": (row["brier"] - base["brier"]) / base["brier"] * 100.0,
                "logloss": row["logloss"],
                "logloss_delta_pct": (row["logloss"] - base["logloss"]) / base["logloss"] * 100.0,
                "ece": row["ece"],
                "ece_delta": row["ece"] - base["ece"],
                "mean_pred": row["mean_pred"],
                "actual_wr": row["actual_wr"],
                "gap_pp": row["gap_pp"],
            }
        )
    return pd.DataFrame(rows).sort_values(["brier", "logloss"])


def build_scorecard_replay(adjusters: dict[str, OffsetLogitAdjuster]) -> pd.DataFrame | None:
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
                "target_above_par": 181.0 - 173.45,
                "current_run_rate": current_run_rate,
                "required_run_rate": required_run_rate,
                "overs_remaining": overs_remaining,
                "balls_remaining": balls_remaining,
                BASE_PROB: resource_v1,
                "partnership_solidity": row.get("partnership_solidity", 0.0),
                "set_batter_exposure": row.get("set_batter_exposure", 0.0),
                "runs_last_18": row.get("runs_last_18", 18.0),
                "near_srh_market_prob_norm": row.get("near_srh_market_prob_norm", np.nan),
                "scorecard_replay": row.get("scorecard_replay", np.nan),
                "v7_cal": row.get("v7_cal", np.nan),
            }
        )

    scorecard = add_resource_context_features(pd.DataFrame(rows))
    for name, adj in adjusters.items():
        gate_fn = APPLY_GATES[name]
        pred = scorecard[BASE_PROB].astype(float).copy()
        mask = gate_fn(scorecard) if gate_fn else pd.Series(True, index=scorecard.index)
        if mask.any():
            pred.loc[mask] = adj.transform(scorecard[mask])
        scorecard[f"resource_{name}"] = pred
    return scorecard


def print_table(df: pd.DataFrame, title: str) -> None:
    print(f"\n{title}")
    print("=" * len(title))
    print(df.to_string(index=False, float_format=lambda value: f"{value:.6f}"))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Loading IPL innings-2 feature data...")
    df = prepare_data()

    fit_mask = df["season"] < "2025"
    apply_mask = df["season"] >= "2025"
    pred_cols = {"resource_v1": BASE_PROB}
    adjusters: dict[str, OffsetLogitAdjuster] = {}

    for name in FEATURE_SETS:
        print(f"Fitting {name}...")
        pred, adjuster = fit_candidate_oof(df, name, fit_mask, apply_mask)
        col = f"resource_{name}"
        df[col] = pred
        pred_cols[name] = col
        adjusters[name] = adjuster
        print("  coefficients:")
        for feature, coef in adjuster.coefficients().items():
            print(f"    {feature:<32s} {coef:+.6f}")

    # Guarded candidates: the first pass showed context residuals can damage
    # below-par/easy chases, so keep v1 for below-par and apply context only
    # where IPL chases most often need sharper interpretation.
    if "resource_context_global" in df.columns:
        df["resource_context_global_guarded"] = np.where(
            df["target_below_par_v2"].astype(float).gt(0.0),
            df[BASE_PROB].astype(float),
            df["resource_context_global"].astype(float),
        )
        pred_cols["context_global_guarded"] = "resource_context_global_guarded"
    if "resource_phase_target_context" in df.columns:
        df["resource_phase_target_guarded"] = np.where(
            df["target_below_par_v2"].astype(float).gt(0.0),
            df[BASE_PROB].astype(float),
            df["resource_phase_target_context"].astype(float),
        )
        pred_cols["phase_target_guarded"] = "resource_phase_target_guarded"

    benchmark = build_benchmark(df, pred_cols)
    summary = build_summary(benchmark)
    benchmark.to_csv(OUT_DIR / "resource_benchmark.csv", index=False)
    summary.to_csv(OUT_DIR / "candidate_summary.csv", index=False)

    metadata = {
        "base_probability": BASE_PROB,
        "fit_policy": "fit seasons < 2025; judge seasons >= 2025",
        "feature_sets": FEATURE_SETS,
        "coefficients": {name: adjuster.coefficients() for name, adjuster in adjusters.items()},
    }
    (OUT_DIR / "resource_candidates.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    with open(OUT_DIR / "resource_adjusters_pre2025.pkl", "wb") as fh:
        pickle.dump(adjusters, fh)

    scorecard = build_scorecard_replay(adjusters)
    if scorecard is not None:
        scorecard.to_csv(OUT_DIR / "scorecard_replay_resource_candidates_csk_srh_2026_05_18.csv", index=False)

    print_table(summary, "Resource baseline candidate summary")
    focus = benchmark[
        benchmark["window"].isin(["early_mid_7_12", "late_mid_13_15", "all_inn2"])
        & benchmark["target_bucket"].isin(["par", "below_par_easy", "above_par_hard", "all_targets"])
    ].sort_values(["window", "target_bucket", "brier"])
    print_table(focus, "Focused OOS slices")
    if scorecard is not None:
        cols = [
            "overs",
            "score",
            BASE_PROB,
            "resource_context_global",
            "resource_phase_target_context",
            "resource_mid_accel_gate_only",
            "near_srh_market_prob_norm",
            "scorecard_replay",
        ]
        print_table(
            scorecard[scorecard["overs"].isin([6.0, 7.0, 8.0, 10.0, 12.0, 12.2, 12.5, 13.5, 14.2, 15.0])][cols],
            "CSK-SRH scorecard replay",
        )
    print(f"\nSaved outputs to {OUT_DIR}")


if __name__ == "__main__":
    main()
