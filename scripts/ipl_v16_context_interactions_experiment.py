"""
IPL v16 candidate: context-resource interactions.

Reversible experiment only. No production files are changed.

Core form:
    logit(resource_context_interaction_prob)
      = logit(resource_win_prob)
      + phase_adjustment
      + venue_regime_adjustment
      + phase x venue_regime
      + target_bucket x venue_regime
      + narrow targeted continuous interactions

No OOS leakage:
  - 2025/26 rows are never used to fit the context adjuster.
  - Training rows use season-fold OOF context probabilities.

Candidates:
  - v14_original
  - v16_A_add_interaction_prob
  - v16_B_replace_resource
  - v16_C_both_plus_regimes
"""
from __future__ import annotations

import json
import pickle
import sys
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, logit

sys.path.insert(0, "src")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ipl_v13_mid_split_common import season_folds  # noqa: E402
from ipl_v15_context_resource_experiment import (  # noqa: E402
    BASE_PROB,
    GUARDRAIL_BUCKETS,
    build_bucket_report,
    build_v14_features,
    evaluate_oof_version,
    evaluate_oos_version,
    metric_dict,
    pct,
    prepare_data as prepare_v15_base_data,
    print_table,
    replace_resource_feature,
)


OUT_DIR = Path("models/ipl_v16_context_interactions")
CONTEXT_PROB = "resource_context_interaction_prob"
REGIME_FEATURES = ["venue_regime_code", "target_bucket_code"]
PP_ECE_MAX_ABS_WORSENING = 0.01


def ece(y: np.ndarray, pred: np.ndarray, n_bins: int = 10) -> float:
    pred = np.clip(np.asarray(pred, dtype=float), 1e-7, 1 - 1e-7)
    y = np.asarray(y, dtype=float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    out = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (pred >= lo) & (pred < hi)
        if not mask.any():
            continue
        out += mask.mean() * abs(float(pred[mask].mean()) - float(y[mask].mean()))
    return float(out)


@dataclass
class InteractionContextAdjuster:
    """Offset-logit adjuster with small phase/venue/target interaction design."""

    l2: float = 0.05
    eps: float = 1e-6
    venue_low_threshold_: float = 0.45
    venue_high_threshold_: float = 0.60
    intercept_: float = 0.0
    coef_: np.ndarray | None = None
    medians_: np.ndarray | None = None
    means_: np.ndarray | None = None
    scales_: np.ndarray | None = None
    feature_names_: list[str] | None = None

    def _phase_arrays(self, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        over = df["over"].astype(float).values
        pp = (over <= 6).astype(float)
        mid = ((over >= 7) & (over <= 15)).astype(float)
        death = (over >= 16).astype(float)
        return pp, mid, death

    def _raw_design(self, df: pd.DataFrame, fit: bool) -> pd.DataFrame:
        if fit:
            vcs = df["venue_chase_success"].astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.5)
            self.venue_low_threshold_ = float(vcs.quantile(0.33))
            self.venue_high_threshold_ = float(vcs.quantile(0.67))

        pp, mid, death = self._phase_arrays(df)
        vcs = df["venue_chase_success"].astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.5)
        venue_low = (vcs <= self.venue_low_threshold_).astype(float).values
        venue_high = (vcs >= self.venue_high_threshold_).astype(float).values

        target = (
            df["target_above_venue_par"]
            .astype(float)
            .replace([np.inf, -np.inf], np.nan)
            .fillna(0.0)
            .values
        )
        target_low = (target < -20.0).astype(float)
        target_high = (target > 20.0).astype(float)

        boundary_signal = (
            df.get("avg_boundary18_vs_venue", pd.Series(0.0, index=df.index))
            .astype(float)
            .replace([np.inf, -np.inf], np.nan)
            .fillna(0.0)
            .values
        )
        pp_score = (
            df.get("pp_score_vs_venue", pd.Series(0.0, index=df.index))
            .astype(float)
            .replace([np.inf, -np.inf], np.nan)
            .fillna(0.0)
            .values
        )

        data = {
            # Main effects: PP and neutral/par are baselines.
            "phase_mid": mid,
            "phase_death": death,
            "venue_low_chase": venue_low,
            "venue_high_chase": venue_high,
            "target_low": target_low,
            "target_high": target_high,
            # Small interaction set.
            "pp_x_venue_low": pp * venue_low,
            "pp_x_venue_high": pp * venue_high,
            "mid_x_venue_low": mid * venue_low,
            "mid_x_venue_high": mid * venue_high,
            "death_x_venue_low": death * venue_low,
            "death_x_venue_high": death * venue_high,
            "target_low_x_venue_low": target_low * venue_low,
            "target_low_x_venue_high": target_low * venue_high,
            "target_high_x_venue_low": target_high * venue_low,
            "target_high_x_venue_high": target_high * venue_high,
            "boundary_signal_x_death": boundary_signal * death,
            "pp_score_vs_venue_x_pp": pp_score * pp,
        }

        # Two low-risk context main effects carried over from v15 diagnostics.
        data["team_strength_diff"] = (
            df.get("team_strength_diff", pd.Series(0.0, index=df.index))
            .astype(float)
            .replace([np.inf, -np.inf], np.nan)
            .fillna(0.0)
            .values
        )
        data["toss_chasing_context"] = (
            df.get("toss_batting_or_chasing_context", pd.Series(0.5, index=df.index))
            .astype(float)
            .replace([np.inf, -np.inf], np.nan)
            .fillna(0.5)
            .values
        )
        return pd.DataFrame(data, index=df.index)

    def _prepare_fit_X(self, df: pd.DataFrame) -> np.ndarray:
        x = self._raw_design(df, fit=True)
        self.feature_names_ = list(x.columns)
        self.medians_ = x.median(numeric_only=True).fillna(0.0).values
        x = x.fillna(pd.Series(self.medians_, index=self.feature_names_))
        self.means_ = x.mean().values
        self.scales_ = x.std(ddof=0).replace(0, 1.0).fillna(1.0).values
        return ((x.values - self.means_) / self.scales_).astype(float)

    def _prepare_X(self, df: pd.DataFrame) -> np.ndarray:
        if (
            self.feature_names_ is None
            or self.medians_ is None
            or self.means_ is None
            or self.scales_ is None
        ):
            raise RuntimeError("InteractionContextAdjuster is not fitted")
        x = self._raw_design(df, fit=False)[self.feature_names_]
        x = x.fillna(pd.Series(self.medians_, index=self.feature_names_))
        return ((x.values - self.means_) / self.scales_).astype(float)

    def fit(self, df: pd.DataFrame) -> "InteractionContextAdjuster":
        x = self._prepare_fit_X(df)
        y = df["is_winner"].astype(float).values
        base = np.clip(df[BASE_PROB].astype(float).values, self.eps, 1.0 - self.eps)
        offset = logit(base)

        def objective(params: np.ndarray) -> float:
            intercept = params[0]
            coef = params[1:]
            pred = expit(offset + intercept + x @ coef)
            pred = np.clip(pred, self.eps, 1.0 - self.eps)
            metrics = metric_dict(y, pred)
            penalty = self.l2 * float(np.dot(coef, coef)) / max(len(coef), 1)
            return float(metrics["logloss"] + penalty)

        result = minimize(
            objective,
            np.zeros(x.shape[1] + 1, dtype=float),
            method="BFGS",
            options={"maxiter": 1000},
        )
        if not result.success:
            raise RuntimeError(f"Interaction context adjuster fit failed: {result.message}")
        self.intercept_ = float(result.x[0])
        self.coef_ = result.x[1:].astype(float)
        return self

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        if self.coef_ is None:
            raise RuntimeError("InteractionContextAdjuster is not fitted")
        x = self._prepare_X(df)
        base = np.clip(df[BASE_PROB].astype(float).values, self.eps, 1.0 - self.eps)
        return expit(logit(base) + self.intercept_ + x @ self.coef_)

    def coefficients(self) -> dict[str, float]:
        if self.coef_ is None or self.feature_names_ is None:
            return {}
        return {
            feature: float(coef)
            for feature, coef in zip(self.feature_names_, self.coef_)
        }


def add_regime_columns(df: pd.DataFrame, adjuster: InteractionContextAdjuster) -> pd.DataFrame:
    out = df.copy()
    vcs = out["venue_chase_success"].astype(float).fillna(0.5)
    out["venue_regime_code"] = np.select(
        [
            vcs <= adjuster.venue_low_threshold_,
            vcs >= adjuster.venue_high_threshold_,
        ],
        [-1.0, 1.0],
        default=0.0,
    )
    target = out["target_above_venue_par"].astype(float).fillna(0.0)
    out["target_bucket_code"] = np.select(
        [target < -20.0, target > 20.0],
        [-1.0, 1.0],
        default=0.0,
    )
    return out


def add_interaction_probability_oof(
    df: pd.DataFrame,
    fit_mask: pd.Series,
    apply_mask: pd.Series | None = None,
    n_folds: int = 5,
) -> tuple[pd.Series, InteractionContextAdjuster]:
    out = pd.Series(np.nan, index=df.index, dtype=float)
    fit_df = df[fit_mask].copy()
    folds = season_folds(sorted(fit_df["season"].astype(str).unique().tolist()), n_folds=n_folds)

    for val_seasons in folds:
        val_mask = fit_mask & df["season"].isin(val_seasons)
        train_mask = fit_mask & ~df["season"].isin(val_seasons)
        if train_mask.sum() == 0 or val_mask.sum() == 0:
            continue
        adjuster = InteractionContextAdjuster().fit(df[train_mask])
        out.loc[val_mask] = adjuster.transform(df[val_mask])

    full_adjuster = InteractionContextAdjuster().fit(fit_df)
    missing_fit = fit_mask & out.isna()
    if missing_fit.any():
        out.loc[missing_fit] = full_adjuster.transform(df[missing_fit])
    if apply_mask is not None and apply_mask.any():
        out.loc[apply_mask] = full_adjuster.transform(df[apply_mask])
    return out, full_adjuster


def build_feature_versions(v14: dict[str, list[str]]) -> dict[str, dict[str, list[str]]]:
    return {
        "v14_original": v14,
        "v16_A_add_interaction_prob": {
            phase: list(dict.fromkeys(features + [CONTEXT_PROB]))
            for phase, features in v14.items()
        },
        "v16_B_replace_resource": {
            phase: replace_resource_feature(features)
            for phase, features in v14.items()
        },
        "v16_C_both_plus_regimes": {
            phase: list(dict.fromkeys(features + [CONTEXT_PROB] + REGIME_FEATURES))
            for phase, features in v14.items()
        },
    }


def build_delta_summary(
    oos_metrics: pd.DataFrame,
    bucket_report: pd.DataFrame,
    payloads: dict[str, dict[str, np.ndarray]],
) -> pd.DataFrame:
    base = oos_metrics[
        (oos_metrics["version"] == "v14_original")
        & (oos_metrics["phase"] == "overall")
    ].iloc[0]
    base_buckets = bucket_report[
        (bucket_report["version"] == "v14_original")
        & (bucket_report["phase"] == "overall")
    ]
    base_pp_ece = ece(payloads["v14_original"]["pp_y"], payloads["v14_original"]["pp_cal"])

    rows = []
    for version in sorted(oos_metrics["version"].unique()):
        row = oos_metrics[
            (oos_metrics["version"] == version)
            & (oos_metrics["phase"] == "overall")
        ].iloc[0]
        version_buckets = bucket_report[
            (bucket_report["version"] == version)
            & (bucket_report["phase"] == "overall")
        ]
        guardrails_ok = True
        for bucket in GUARDRAIL_BUCKETS:
            base_b = base_buckets[base_buckets["bucket"] == bucket]
            cand_b = version_buckets[version_buckets["bucket"] == bucket]
            if base_b.empty or cand_b.empty:
                guardrails_ok = False
                continue
            guardrails_ok = guardrails_ok and (
                float(cand_b.iloc[0]["cal_error"])
                <= float(base_b.iloc[0]["cal_error"]) + 1e-12
            )

        base_70 = base_buckets[base_buckets["bucket"] == "70-80"]
        cand_70 = version_buckets[version_buckets["bucket"] == "70-80"]
        compression_improved = (
            not base_70.empty
            and not cand_70.empty
            and float(cand_70.iloc[0]["cal_error"]) < float(base_70.iloc[0]["cal_error"])
        )
        pp_ece = ece(payloads[version]["pp_y"], payloads[version]["pp_cal"])
        pp_ece_delta = pp_ece - base_pp_ece

        rows.append(
            {
                "version": version,
                "oos_brier": row["cal_brier"],
                "oos_brier_delta_pct": pct(row["cal_brier"], base["cal_brier"]),
                "oos_logloss": row["cal_logloss"],
                "oos_logloss_delta_pct": pct(row["cal_logloss"], base["cal_logloss"]),
                "overall_50_60_80_guardrails_ok": guardrails_ok,
                "bucket_70_80_improved": compression_improved,
                "pp_ece": pp_ece,
                "pp_ece_delta": pp_ece_delta,
                "pp_ece_guardrail_ok": pp_ece_delta <= PP_ECE_MAX_ABS_WORSENING,
                "promote": (
                    version != "v14_original"
                    and row["cal_brier"] < base["cal_brier"]
                    and row["cal_logloss"] < base["cal_logloss"]
                    and guardrails_ok
                    and compression_improved
                    and pp_ece_delta <= PP_ECE_MAX_ABS_WORSENING
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["promote", "oos_logloss", "oos_brier"],
        ascending=[False, True, True],
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Loading IPL v14 data and adding v16 interaction context probability...")
    df = prepare_v15_base_data()
    pre_2025 = df["season"] < "2025"
    oos_2025 = df["season"] >= "2025"
    all_rows = pd.Series(True, index=df.index)

    oos_context_prob, final_adjuster = add_interaction_probability_oof(
        df,
        fit_mask=pre_2025,
        apply_mask=oos_2025,
    )
    df_oos = add_regime_columns(df, final_adjuster)
    df_oos[CONTEXT_PROB] = oos_context_prob

    all_context_prob, all_adjuster = add_interaction_probability_oof(
        df,
        fit_mask=all_rows,
        apply_mask=None,
    )
    df_oof = add_regime_columns(df, all_adjuster)
    df_oof[CONTEXT_PROB] = all_context_prob

    print("Interaction adjuster coefficients (fit on pre-2025 only):")
    for feature, coef in sorted(
        final_adjuster.coefficients().items(),
        key=lambda item: abs(item[1]),
        reverse=True,
    ):
        print(f"  {feature:<34} {coef:+.4f}")
    print(
        f"Venue regime thresholds: low<={final_adjuster.venue_low_threshold_:.4f}, "
        f"high>={final_adjuster.venue_high_threshold_:.4f}"
    )

    versions = build_feature_versions(build_v14_features())
    oos_frames = []
    oof_frames = []
    payloads = {}
    for version, feature_set in versions.items():
        print(f"\nEvaluating {version}...")
        eval_df_oos = df if version == "v14_original" else df_oos
        eval_df_oof = df if version == "v14_original" else df_oof

        oos_phase, payload = evaluate_oos_version(eval_df_oos, feature_set)
        oos_phase["version"] = version
        oos_frames.append(oos_phase)
        payloads[version] = payload

        oof_phase = evaluate_oof_version(eval_df_oof, feature_set)
        oof_phase["version"] = version
        oof_frames.append(oof_phase)

    oos_metrics = pd.concat(oos_frames, ignore_index=True)
    oof_metrics = pd.concat(oof_frames, ignore_index=True)
    bucket_report = build_bucket_report(payloads)
    summary = build_delta_summary(oos_metrics, bucket_report, payloads)

    print_table(summary, "OOS verdict summary")
    print_table(
        oos_metrics.sort_values(["phase", "version"]),
        "OOS phase metrics",
    )
    print_table(
        bucket_report[
            (bucket_report["phase"] == "overall")
            & (bucket_report["bucket"].isin(["50-60", "70-80", "80+"]))
        ].sort_values(["bucket", "version"]),
        "OOS overall favourite buckets",
    )

    oos_metrics.to_csv(OUT_DIR / "oos_phase_metrics.csv", index=False)
    oof_metrics.to_csv(OUT_DIR / "oof_phase_metrics.csv", index=False)
    bucket_report.to_csv(OUT_DIR / "oos_bucket_report.csv", index=False)
    summary.to_csv(OUT_DIR / "candidate_summary.csv", index=False)
    with open(OUT_DIR / "context_interaction_adjuster_pre2025.pkl", "wb") as f:
        pickle.dump(final_adjuster, f)
    with open(OUT_DIR / "context_interaction_features.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "base_probability": BASE_PROB,
                "context_probability": CONTEXT_PROB,
                "formula": (
                    "logit(resource_context_interaction_prob)=logit(resource_win_prob)"
                    "+phase+venue_regime+phase_x_venue_regime+target_bucket_x_venue_regime"
                ),
                "venue_low_threshold": final_adjuster.venue_low_threshold_,
                "venue_high_threshold": final_adjuster.venue_high_threshold_,
                "target_thresholds": {"low": -20.0, "high": 20.0},
                "fit_policy": "pre-2025 OOF for training rows; 2025/26 OOS transformed by pre-2025 adjuster",
                "feature_coefficients": final_adjuster.coefficients(),
            },
            f,
            indent=2,
        )

    promoted = summary[summary["promote"]]
    if promoted.empty:
        print("\nVerdict: KEEP v14. v16 interaction candidate did not pass all OOS guardrails.")
        for stale in [
            OUT_DIR / "champion_context_interaction_adjuster.pkl",
            OUT_DIR / "champion_feature_version.json",
        ]:
            if stale.exists():
                stale.unlink()
        return

    best = str(promoted.iloc[0]["version"])
    joblib.dump(final_adjuster, OUT_DIR / "champion_context_interaction_adjuster.pkl")
    with open(OUT_DIR / "champion_feature_version.json", "w", encoding="utf-8") as f:
        json.dump({"promoted_candidate": best}, f, indent=2)
    print(f"\nVerdict: PROMOTE candidate for next model build: {best}")


if __name__ == "__main__":
    main()
