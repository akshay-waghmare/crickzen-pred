"""
IPL v15 candidate: context-aware resource probability.

This is a reversible experiment only. It does not modify v14 artifacts or
production wiring.

Core form:
    logit(resource_context_win_prob)
      = logit(resource_win_prob) + contextual_adjustment

The context adjustment is fitted only on historical OOF folds / pre-2025 data.
The 2025+2026 OOS split is never used for fitting.

Versions compared:
  - v14_original
  - v15_add_context_resource: keep resource_win_prob and add resource_context_win_prob
  - v15_replace_resource: replace direct resource_win_prob with resource_context_win_prob
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
from sklearn.metrics import brier_score_loss, log_loss

sys.path.insert(0, "src")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bbl_pipeline.training.blend_model import XGBLRBlend  # noqa: E402
from build_ipl_v14_pitch_features import (  # noqa: E402
    DEATH_PITCH_FEATURES,
    MID_PITCH_FEATURES,
    PP_PITCH_FEATURES,
    add_pitch_features,
)
from ipl_v13_mid_split_common import (  # noqa: E402
    CAL_METHODS_V12,
    PHASE_RANGES_V12,
    apply_calibrator_bundle,
    fit_calibrator_bundle,
    load_training_data,
    load_v12_features,
    oof_phase_predictions,
    ordered_unique,
    phase_slice,
    safe_X,
    season_folds,
)


OUT_DIR = Path("models/ipl_v15_context_resource")
CONTEXT_FEATURES = [
    "venue_chase_success",
    "team_strength_diff",
    "target_above_venue_par",
    "pp_score_vs_venue",
    "death_rr_vs_venue",
    "toss_batting_or_chasing_context",
]
CONTEXT_PROB = "resource_context_win_prob"
BASE_PROB = "resource_win_prob"
GUARDRAIL_BUCKETS = {"50-60", "80+"}


@dataclass
class OffsetLogitContextAdjuster:
    """Offset logistic regression with fixed `logit(resource_win_prob)` slope=1."""

    l2: float = 0.02
    eps: float = 1e-6
    intercept_: float = 0.0
    coef_: np.ndarray | None = None
    medians_: np.ndarray | None = None
    means_: np.ndarray | None = None
    scales_: np.ndarray | None = None

    def _prepare_fit_X(self, df: pd.DataFrame) -> np.ndarray:
        x = df[CONTEXT_FEATURES].astype(float).replace([np.inf, -np.inf], np.nan)
        self.medians_ = x.median(numeric_only=True).fillna(0.0).values
        x = x.fillna(pd.Series(self.medians_, index=CONTEXT_FEATURES))
        self.means_ = x.mean().values
        self.scales_ = x.std(ddof=0).replace(0, 1.0).fillna(1.0).values
        return ((x.values - self.means_) / self.scales_).astype(float)

    def _prepare_X(self, df: pd.DataFrame) -> np.ndarray:
        if self.medians_ is None or self.means_ is None or self.scales_ is None:
            raise RuntimeError("OffsetLogitContextAdjuster is not fitted")
        x = df[CONTEXT_FEATURES].astype(float).replace([np.inf, -np.inf], np.nan)
        x = x.fillna(pd.Series(self.medians_, index=CONTEXT_FEATURES))
        return ((x.values - self.means_) / self.scales_).astype(float)

    def fit(self, df: pd.DataFrame) -> "OffsetLogitContextAdjuster":
        x = self._prepare_fit_X(df)
        y = df["is_winner"].astype(float).values
        base = np.clip(df[BASE_PROB].astype(float).values, self.eps, 1.0 - self.eps)
        offset = logit(base)

        def objective(params: np.ndarray) -> float:
            intercept = params[0]
            coef = params[1:]
            pred = expit(offset + intercept + x @ coef)
            pred = np.clip(pred, self.eps, 1.0 - self.eps)
            loss = log_loss(y, pred)
            penalty = self.l2 * float(np.dot(coef, coef)) / max(len(coef), 1)
            return float(loss + penalty)

        init = np.zeros(x.shape[1] + 1, dtype=float)
        result = minimize(objective, init, method="BFGS", options={"maxiter": 1000})
        if not result.success:
            raise RuntimeError(f"Context adjuster fit failed: {result.message}")
        self.intercept_ = float(result.x[0])
        self.coef_ = result.x[1:].astype(float)
        return self

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        if self.coef_ is None:
            raise RuntimeError("OffsetLogitContextAdjuster is not fitted")
        x = self._prepare_X(df)
        base = np.clip(df[BASE_PROB].astype(float).values, self.eps, 1.0 - self.eps)
        return expit(logit(base) + self.intercept_ + x @ self.coef_)

    def coefficients(self) -> dict[str, float]:
        if self.coef_ is None:
            return {}
        return {
            feature: float(coef)
            for feature, coef in zip(CONTEXT_FEATURES, self.coef_)
        }


def pct(new: float, old: float) -> float:
    return (new - old) / old * 100.0 if old else np.nan


def metric_dict(y: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    pred = np.clip(np.asarray(pred, dtype=float), 1e-7, 1 - 1e-7)
    return {
        "brier": float(brier_score_loss(y, pred)),
        "logloss": float(log_loss(y, pred)),
        "n": int(len(y)),
    }


def prepare_data() -> pd.DataFrame:
    df = add_pitch_features(load_training_data())
    df["season"] = df["season"].astype(str)

    # In processor.py, target_above_par is already first_innings_score - venue_avg_score.
    # Keep an explicit name for this experiment so the context model is readable.
    if "first_innings_score" in df.columns and "venue_avg_score" in df.columns:
        df["target_above_venue_par"] = (
            df["first_innings_score"].astype(float)
            - df["venue_avg_score"].astype(float)
        )
    else:
        df["target_above_venue_par"] = df.get("target_above_par", 0.0)

    # For innings 2, batting team is the chasing team; this captures whether
    # the chasing side won the toss/chose the chase context.
    df["toss_batting_or_chasing_context"] = df.get("batting_won_toss", 0.5)

    for col in CONTEXT_FEATURES:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = df[col].astype(float).replace([np.inf, -np.inf], np.nan)

    df[BASE_PROB] = df[BASE_PROB].astype(float).clip(1e-6, 1 - 1e-6)
    return df


def add_context_probability_oof(
    df: pd.DataFrame,
    fit_mask: pd.Series,
    apply_mask: pd.Series | None = None,
    n_folds: int = 5,
) -> tuple[pd.Series, OffsetLogitContextAdjuster]:
    """Return OOF context probs on fit rows and full-fit probs on apply rows."""
    out = pd.Series(np.nan, index=df.index, dtype=float)
    fit_df = df[fit_mask].copy()
    seasons = sorted(fit_df["season"].astype(str).unique().tolist())
    folds = season_folds(seasons, n_folds=n_folds)

    for val_seasons in folds:
        val_mask = fit_mask & df["season"].isin(val_seasons)
        train_mask = fit_mask & ~df["season"].isin(val_seasons)
        if train_mask.sum() == 0 or val_mask.sum() == 0:
            continue
        adjuster = OffsetLogitContextAdjuster().fit(df[train_mask])
        out.loc[val_mask] = adjuster.transform(df[val_mask])

    full_adjuster = OffsetLogitContextAdjuster().fit(fit_df)
    missing_fit = fit_mask & out.isna()
    if missing_fit.any():
        out.loc[missing_fit] = full_adjuster.transform(df[missing_fit])

    if apply_mask is not None and apply_mask.any():
        out.loc[apply_mask] = full_adjuster.transform(df[apply_mask])

    return out, full_adjuster


def build_v14_features() -> dict[str, list[str]]:
    v12 = load_v12_features()
    return {
        "pp": ordered_unique(v12["pp"] + PP_PITCH_FEATURES),
        "mid": ordered_unique(v12["mid"] + MID_PITCH_FEATURES),
        "death": ordered_unique(v12["death"] + DEATH_PITCH_FEATURES),
    }


def replace_resource_feature(features: list[str]) -> list[str]:
    return ordered_unique([
        CONTEXT_PROB if feature == BASE_PROB else feature
        for feature in features
    ])


def build_feature_versions(v14: dict[str, list[str]]) -> dict[str, dict[str, list[str]]]:
    return {
        "v14_original": v14,
        "v15_add_context_resource": {
            phase: ordered_unique(features + [CONTEXT_PROB])
            for phase, features in v14.items()
        },
        "v15_replace_resource": {
            phase: replace_resource_feature(features)
            for phase, features in v14.items()
        },
    }


def evaluate_oos_version(
    df: pd.DataFrame,
    phase_features: dict[str, list[str]],
) -> tuple[pd.DataFrame, dict[str, np.ndarray]]:
    train_seasons = {s for s in sorted(df["season"].unique()) if s < "2025"}
    test_seasons = {s for s in sorted(df["season"].unique()) if s >= "2025"}

    rows = []
    all_y = []
    all_raw = []
    all_cal = []
    phase_payload: dict[str, np.ndarray] = {}

    for phase, over_range in PHASE_RANGES_V12.items():
        pf = phase_slice(df, over_range)
        train_df = pf[pf["season"].isin(train_seasons)].copy().reset_index(drop=True)
        test_df = pf[pf["season"].isin(test_seasons)].copy().reset_index(drop=True)

        train_oof = oof_phase_predictions(train_df, phase_features[phase])
        bundle = fit_calibrator_bundle(
            train_oof["raw"],
            train_oof["y"],
            train_oof["over"],
            CAL_METHODS_V12[phase],
        )

        x_train, _ = safe_X(train_df, phase_features[phase])
        x_test, _ = safe_X(test_df, phase_features[phase])
        y_train = train_df["is_winner"].values
        y_test = test_df["is_winner"].values.astype(float)
        over_test = test_df["over"].values.astype(int)

        model = XGBLRBlend()
        model.fit(x_train, y_train)
        raw = model.predict_proba(x_test)[:, 1]
        cal = apply_calibrator_bundle(raw, over_test, bundle)

        raw_m = metric_dict(y_test, raw)
        cal_m = metric_dict(y_test, cal)
        rows.append(
            {
                "phase": phase,
                "n": len(y_test),
                "raw_brier": raw_m["brier"],
                "cal_brier": cal_m["brier"],
                "raw_logloss": raw_m["logloss"],
                "cal_logloss": cal_m["logloss"],
            }
        )
        all_y.append(y_test)
        all_raw.append(raw)
        all_cal.append(cal)
        phase_payload[f"{phase}_y"] = y_test
        phase_payload[f"{phase}_cal"] = cal

    y_all = np.concatenate(all_y)
    raw_all = np.concatenate(all_raw)
    cal_all = np.concatenate(all_cal)
    raw_m = metric_dict(y_all, raw_all)
    cal_m = metric_dict(y_all, cal_all)
    rows.append(
        {
            "phase": "overall",
            "n": len(y_all),
            "raw_brier": raw_m["brier"],
            "cal_brier": cal_m["brier"],
            "raw_logloss": raw_m["logloss"],
            "cal_logloss": cal_m["logloss"],
        }
    )
    phase_payload["overall_y"] = y_all
    phase_payload["overall_cal"] = cal_all
    return pd.DataFrame(rows), phase_payload


def evaluate_oof_version(
    df: pd.DataFrame,
    phase_features: dict[str, list[str]],
) -> pd.DataFrame:
    rows = []
    all_y = []
    all_raw = []
    all_cal = []
    for phase, over_range in PHASE_RANGES_V12.items():
        pf = phase_slice(df, over_range)
        oof = oof_phase_predictions(pf, phase_features[phase])
        bundle = fit_calibrator_bundle(
            oof["raw"],
            oof["y"],
            oof["over"],
            CAL_METHODS_V12[phase],
        )
        cal = apply_calibrator_bundle(oof["raw"], oof["over"], bundle)
        raw_m = metric_dict(oof["y"], oof["raw"])
        cal_m = metric_dict(oof["y"], cal)
        rows.append(
            {
                "phase": phase,
                "n": len(oof["y"]),
                "raw_brier": raw_m["brier"],
                "cal_brier": cal_m["brier"],
                "raw_logloss": raw_m["logloss"],
                "cal_logloss": cal_m["logloss"],
            }
        )
        all_y.append(oof["y"])
        all_raw.append(oof["raw"])
        all_cal.append(cal)

    y_all = np.concatenate(all_y)
    raw_all = np.concatenate(all_raw)
    cal_all = np.concatenate(all_cal)
    raw_m = metric_dict(y_all, raw_all)
    cal_m = metric_dict(y_all, cal_all)
    rows.append(
        {
            "phase": "overall",
            "n": len(y_all),
            "raw_brier": raw_m["brier"],
            "cal_brier": cal_m["brier"],
            "raw_logloss": raw_m["logloss"],
            "cal_logloss": cal_m["logloss"],
        }
    )
    return pd.DataFrame(rows)


def favourite_buckets(y: np.ndarray, pred: np.ndarray) -> pd.DataFrame:
    pred = np.asarray(pred, dtype=float)
    y = np.asarray(y, dtype=float)
    p_fav = np.where(pred >= 0.5, pred, 1.0 - pred)
    y_fav = np.where(pred >= 0.5, y, 1.0 - y)
    rows = []
    for lo, hi, label in [
        (0.50, 0.60, "50-60"),
        (0.60, 0.70, "60-70"),
        (0.70, 0.80, "70-80"),
        (0.80, 1.01, "80+"),
    ]:
        mask = (p_fav >= lo) & (p_fav < hi)
        if mask.sum() == 0:
            continue
        mean_pred = float(p_fav[mask].mean())
        actual = float(y_fav[mask].mean())
        rows.append(
            {
                "bucket": label,
                "n": int(mask.sum()),
                "mean_pred": mean_pred,
                "actual_wr": actual,
                "cal_error": abs(mean_pred - actual),
            }
        )
    return pd.DataFrame(rows)


def build_bucket_report(payloads: dict[str, dict[str, np.ndarray]]) -> pd.DataFrame:
    rows = []
    for version, payload in payloads.items():
        for phase in ["pp", "mid", "death", "overall"]:
            bucket_df = favourite_buckets(
                payload[f"{phase}_y"],
                payload[f"{phase}_cal"],
            )
            bucket_df["version"] = version
            bucket_df["phase"] = phase
            rows.append(bucket_df)
    return pd.concat(rows, ignore_index=True)


def build_delta_summary(
    oos_metrics: pd.DataFrame,
    bucket_report: pd.DataFrame,
) -> pd.DataFrame:
    base = oos_metrics[
        (oos_metrics["version"] == "v14_original")
        & (oos_metrics["phase"] == "overall")
    ].iloc[0]
    base_buckets = bucket_report[
        (bucket_report["version"] == "v14_original")
        & (bucket_report["phase"] == "overall")
    ]
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
        rows.append(
            {
                "version": version,
                "oos_brier": row["cal_brier"],
                "oos_brier_delta_pct": pct(row["cal_brier"], base["cal_brier"]),
                "oos_logloss": row["cal_logloss"],
                "oos_logloss_delta_pct": pct(row["cal_logloss"], base["cal_logloss"]),
                "guardrails_50_60_80_ok": guardrails_ok,
                "bucket_70_80_improved": compression_improved,
                "promote": (
                    version != "v14_original"
                    and row["cal_brier"] < base["cal_brier"]
                    and row["cal_logloss"] < base["cal_logloss"]
                    and guardrails_ok
                    and compression_improved
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["promote", "oos_logloss", "oos_brier"],
        ascending=[False, True, True],
    )


def print_table(df: pd.DataFrame, title: str) -> None:
    print(f"\n{title}")
    print("=" * len(title))
    print(df.to_string(index=False, float_format=lambda x: f"{x:.6f}"))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Loading IPL v14 data and adding context-resource feature...")
    df = prepare_data()

    pre_2025 = df["season"] < "2025"
    oos_2025 = df["season"] >= "2025"
    all_rows = pd.Series(True, index=df.index)

    # OOS-safe feature: train rows get pre-2025 OOF context probability; test rows
    # get probability from adjuster fit on all pre-2025 data.
    oos_context_prob, final_adjuster = add_context_probability_oof(
        df,
        fit_mask=pre_2025,
        apply_mask=oos_2025,
    )
    df_oos = df.copy()
    df_oos[CONTEXT_PROB] = oos_context_prob

    # Full historical OOF feature for OOF comparison only.
    all_context_prob, _ = add_context_probability_oof(
        df,
        fit_mask=all_rows,
        apply_mask=None,
    )
    df_oof = df.copy()
    df_oof[CONTEXT_PROB] = all_context_prob

    print("Context adjuster coefficients (fit on pre-2025 only):")
    for feature, coef in sorted(
        final_adjuster.coefficients().items(),
        key=lambda item: abs(item[1]),
        reverse=True,
    ):
        print(f"  {feature:<34} {coef:+.4f}")

    v14_features = build_v14_features()
    versions = build_feature_versions(v14_features)

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
    summary = build_delta_summary(oos_metrics, bucket_report)

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
    with open(OUT_DIR / "context_adjuster_pre2025.pkl", "wb") as f:
        pickle.dump(final_adjuster, f)
    with open(OUT_DIR / "context_features.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "base_probability": BASE_PROB,
                "context_probability": CONTEXT_PROB,
                "context_features": CONTEXT_FEATURES,
                "formula": "logit(resource_context_win_prob)=logit(resource_win_prob)+contextual_adjustment",
                "fit_policy": "pre-2025 OOF for training rows; 2025/26 OOS transformed by pre-2025 adjuster",
            },
            f,
            indent=2,
        )

    promoted = summary[summary["promote"]]
    if promoted.empty:
        print("\nVerdict: KEEP v14. Context-resource candidate did not pass all OOS guardrails.")
        for stale in [
            OUT_DIR / "champion_context_adjuster.pkl",
            OUT_DIR / "champion_feature_version.json",
        ]:
            if stale.exists():
                stale.unlink()
        return

    best = promoted.iloc[0]["version"]
    joblib.dump(final_adjuster, OUT_DIR / "champion_context_adjuster.pkl")
    with open(OUT_DIR / "champion_feature_version.json", "w", encoding="utf-8") as f:
        json.dump({"promoted_candidate": best}, f, indent=2)
    print(f"\nVerdict: PROMOTE candidate for next model build: {best}")


if __name__ == "__main__":
    main()
