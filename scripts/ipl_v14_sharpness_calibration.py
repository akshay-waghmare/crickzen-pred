"""
IPL v14 sharpness calibration experiment.

Fits a second-stage monotonic calibration layer on pre-2025 OOF predictions only,
then evaluates candidates on the 2025+2026 OOS split. A candidate is promoted
only if:
  1. OOS Brier improves vs v14 baseline.
  2. OOS LogLoss improves vs v14 baseline.
  3. Overall favourite-perspective 50-60% and 80%+ bucket calibration errors
     are not worse than v14 baseline.

This avoids manually forcing any probability band to a target. All mappings are
learned from OOF predictions.
"""
from __future__ import annotations

import pickle
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from scipy.special import expit, logit
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss, log_loss

sys.path.insert(0, "src")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bbl_pipeline.training.blend_model import XGBLRBlend  # noqa: E402
from bbl_pipeline.training.calibration import PlattCalibrator  # noqa: E402
from build_ipl_v14_pitch_features import add_pitch_features  # noqa: E402
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
)


OUT_DIR = Path("models/ipl_v14_pitch_features")

PP_PITCH_FEATURES = [
    "pp_score_vs_venue",
    "pp_wkts_vs_venue",
    "death_rr_vs_venue",
    "death_wkts_vs_venue",
]
MID_PITCH_FEATURES = ["pp_wkts_vs_venue"]
DEATH_PITCH_FEATURES = [
    "inn1_pp_wickets",
    "mid_avg_boundary18_vs_venue",
    "avg_boundary18_vs_venue",
]

CONFIDENCE_BUCKETS = [
    (0.50, 0.60, "50-60"),
    (0.60, 0.70, "60-70"),
    (0.70, 0.80, "70-80"),
    (0.80, 1.01, "80+"),
]
GUARDRAIL_BUCKETS = {"50-60", "80+"}
MIN_BRIER_IMPROVEMENT_PCT = 0.05
MIN_LOGLOSS_IMPROVEMENT_PCT = 0.05


class Calibrator(Protocol):
    def fit(self, raw: np.ndarray, y: np.ndarray) -> "Calibrator":
        ...

    def transform(self, raw: np.ndarray) -> np.ndarray:
        ...


class IdentityCalibrator:
    def fit(self, raw: np.ndarray, y: np.ndarray) -> "IdentityCalibrator":
        return self

    def transform(self, raw: np.ndarray) -> np.ndarray:
        return np.asarray(raw, dtype=float)


class TemperatureCalibrator:
    """One-parameter monotonic calibration in logit space."""

    def __init__(self) -> None:
        self.temperature = 1.0
        self._eps = 1e-7

    def fit(self, raw: np.ndarray, y: np.ndarray) -> "TemperatureCalibrator":
        raw = np.clip(np.asarray(raw, dtype=float), self._eps, 1 - self._eps)
        y = np.asarray(y, dtype=float)
        logits = logit(raw)

        def objective(log_temp: float) -> float:
            temp = float(np.exp(log_temp))
            pred = expit(logits / temp)
            return float(log_loss(y, np.clip(pred, self._eps, 1 - self._eps)))

        result = minimize_scalar(objective, bounds=(-2.0, 2.0), method="bounded")
        self.temperature = float(np.exp(result.x))
        return self

    def transform(self, raw: np.ndarray) -> np.ndarray:
        raw = np.clip(np.asarray(raw, dtype=float), self._eps, 1 - self._eps)
        return expit(logit(raw) / self.temperature)


class IsotonicCalibrator:
    def __init__(self) -> None:
        self.model = IsotonicRegression(out_of_bounds="clip")

    def fit(self, raw: np.ndarray, y: np.ndarray) -> "IsotonicCalibrator":
        self.model.fit(raw, y)
        return self

    def transform(self, raw: np.ndarray) -> np.ndarray:
        return self.model.transform(raw)


class BlendedCalibrator:
    """Convex blend of identity and an OOF-fitted monotonic calibrator."""

    def __init__(self, base: Calibrator, alpha: float) -> None:
        self.base = base
        self.alpha = float(alpha)

    def fit(self, raw: np.ndarray, y: np.ndarray) -> "BlendedCalibrator":
        self.base.fit(raw, y)
        return self

    def transform(self, raw: np.ndarray) -> np.ndarray:
        raw_arr = np.asarray(raw, dtype=float)
        return (1.0 - self.alpha) * raw_arr + self.alpha * self.base.transform(raw_arr)


class SymmetricConfidenceCalibrator:
    """
    Monotonic favourite-confidence calibrator.

    It fits max(p, 1-p) against whether the predicted favourite actually won,
    then unfolds the calibrated favourite confidence back to team probability.
    This targets favourite/underdog compression without hard-coded bucket targets.
    """

    def __init__(self, base: Calibrator) -> None:
        self.base = base

    def fit(self, raw: np.ndarray, y: np.ndarray) -> "SymmetricConfidenceCalibrator":
        raw_arr = np.asarray(raw, dtype=float)
        y_arr = np.asarray(y, dtype=float)
        favourite_conf = np.where(raw_arr >= 0.5, raw_arr, 1.0 - raw_arr)
        favourite_won = np.where(raw_arr >= 0.5, y_arr, 1.0 - y_arr)
        self.base.fit(favourite_conf, favourite_won)
        return self

    def transform(self, raw: np.ndarray) -> np.ndarray:
        raw_arr = np.asarray(raw, dtype=float)
        favourite_conf = np.where(raw_arr >= 0.5, raw_arr, 1.0 - raw_arr)
        calibrated_conf = np.clip(self.base.transform(favourite_conf), 0.5, 1.0)
        return np.where(raw_arr >= 0.5, calibrated_conf, 1.0 - calibrated_conf)


@dataclass
class PhaseEvaluation:
    train_oof_cal: np.ndarray
    train_y: np.ndarray
    train_season: np.ndarray
    test_base_cal: np.ndarray
    test_y: np.ndarray


def metric_row(y: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    pred = np.clip(np.asarray(pred, dtype=float), 1e-7, 1 - 1e-7)
    return {
        "brier": float(brier_score_loss(y, pred)),
        "logloss": float(log_loss(y, pred)),
        "n": int(len(y)),
    }


def build_v14_features() -> dict[str, list[str]]:
    v12 = load_v12_features()
    return {
        "pp": ordered_unique(v12["pp"] + PP_PITCH_FEATURES),
        "mid": ordered_unique(v12["mid"] + MID_PITCH_FEATURES),
        "death": ordered_unique(v12["death"] + DEATH_PITCH_FEATURES),
    }


def evaluate_phase(df: pd.DataFrame, phase: str, features: list[str]) -> PhaseEvaluation:
    train_seasons = {s for s in sorted(df["season"].unique()) if s < "2025"}
    test_seasons = {s for s in sorted(df["season"].unique()) if s >= "2025"}

    pf = phase_slice(df, PHASE_RANGES_V12[phase])
    pf_train = pf[pf["season"].isin(train_seasons)].copy().reset_index(drop=True)
    pf_test = pf[pf["season"].isin(test_seasons)].copy().reset_index(drop=True)

    train_oof = oof_phase_predictions(pf_train, features)
    base_bundle = fit_calibrator_bundle(
        train_oof["raw"],
        train_oof["y"],
        train_oof["over"],
        CAL_METHODS_V12[phase],
    )
    train_oof_cal = apply_calibrator_bundle(
        train_oof["raw"],
        train_oof["over"],
        base_bundle,
    )

    x_train, _ = safe_X(pf_train, features)
    x_test, _ = safe_X(pf_test, features)
    y_train = pf_train["is_winner"].values
    y_test = pf_test["is_winner"].values.astype(float)
    over_test = pf_test["over"].values.astype(int)

    model = XGBLRBlend()
    model.fit(x_train, y_train)
    test_raw = model.predict_proba(x_test)[:, 1]
    test_base_cal = apply_calibrator_bundle(test_raw, over_test, base_bundle)

    return PhaseEvaluation(
        train_oof_cal=train_oof_cal,
        train_y=train_oof["y"].astype(float),
        train_season=pf_train["season"].astype(str).values,
        test_base_cal=test_base_cal,
        test_y=y_test,
    )


def make_calibrator(kind: str) -> Calibrator:
    if kind == "identity":
        return IdentityCalibrator()
    if kind == "temperature":
        return TemperatureCalibrator()
    if kind == "platt":
        return PlattCalibrator(C=1.0)
    if kind == "isotonic":
        return IsotonicCalibrator()
    raise ValueError(f"Unknown calibrator kind: {kind}")


def make_blended_calibrator(kind: str, alpha: float) -> Calibrator:
    return BlendedCalibrator(make_calibrator(kind), alpha)


def make_symmetric_calibrator(kind: str) -> Calibrator:
    return SymmetricConfidenceCalibrator(make_calibrator(kind))


def make_blended_symmetric_calibrator(kind: str, alpha: float) -> Calibrator:
    return BlendedCalibrator(SymmetricConfidenceCalibrator(make_calibrator(kind)), alpha)


def fit_global(
    phase_eval: dict[str, PhaseEvaluation],
    kind: str,
) -> dict[str, Calibrator]:
    train_pred = np.concatenate([phase_eval[p].train_oof_cal for p in PHASE_RANGES_V12])
    train_y = np.concatenate([phase_eval[p].train_y for p in PHASE_RANGES_V12])
    cal = make_calibrator(kind).fit(train_pred, train_y)
    return {phase: cal for phase in PHASE_RANGES_V12}


def recent_phase_eval(
    phase_eval: dict[str, PhaseEvaluation],
    min_season: str,
) -> dict[str, PhaseEvaluation]:
    recent: dict[str, PhaseEvaluation] = {}
    for phase, pe in phase_eval.items():
        mask = pe.train_season >= min_season
        if mask.sum() == 0:
            raise ValueError(f"No OOF rows for {phase} with season >= {min_season}")
        recent[phase] = PhaseEvaluation(
            train_oof_cal=pe.train_oof_cal[mask],
            train_y=pe.train_y[mask],
            train_season=pe.train_season[mask],
            test_base_cal=pe.test_base_cal,
            test_y=pe.test_y,
        )
    return recent


def fit_global_blended(
    phase_eval: dict[str, PhaseEvaluation],
    kind: str,
    alpha: float,
) -> dict[str, Calibrator]:
    train_pred = np.concatenate([phase_eval[p].train_oof_cal for p in PHASE_RANGES_V12])
    train_y = np.concatenate([phase_eval[p].train_y for p in PHASE_RANGES_V12])
    cal = make_blended_calibrator(kind, alpha).fit(train_pred, train_y)
    return {phase: cal for phase in PHASE_RANGES_V12}


def fit_global_symmetric(
    phase_eval: dict[str, PhaseEvaluation],
    kind: str,
) -> dict[str, Calibrator]:
    train_pred = np.concatenate([phase_eval[p].train_oof_cal for p in PHASE_RANGES_V12])
    train_y = np.concatenate([phase_eval[p].train_y for p in PHASE_RANGES_V12])
    cal = make_symmetric_calibrator(kind).fit(train_pred, train_y)
    return {phase: cal for phase in PHASE_RANGES_V12}


def fit_global_symmetric_blended(
    phase_eval: dict[str, PhaseEvaluation],
    kind: str,
    alpha: float,
) -> dict[str, Calibrator]:
    train_pred = np.concatenate([phase_eval[p].train_oof_cal for p in PHASE_RANGES_V12])
    train_y = np.concatenate([phase_eval[p].train_y for p in PHASE_RANGES_V12])
    cal = make_blended_symmetric_calibrator(kind, alpha).fit(train_pred, train_y)
    return {phase: cal for phase in PHASE_RANGES_V12}


def fit_phase(
    phase_eval: dict[str, PhaseEvaluation],
    kind: str,
) -> dict[str, Calibrator]:
    return {
        phase: make_calibrator(kind).fit(pe.train_oof_cal, pe.train_y)
        for phase, pe in phase_eval.items()
    }


def fit_phase_symmetric(
    phase_eval: dict[str, PhaseEvaluation],
    kind: str,
) -> dict[str, Calibrator]:
    return {
        phase: make_symmetric_calibrator(kind).fit(pe.train_oof_cal, pe.train_y)
        for phase, pe in phase_eval.items()
    }


def fit_phase_symmetric_blended(
    phase_eval: dict[str, PhaseEvaluation],
    kind: str,
    alpha: float,
) -> dict[str, Calibrator]:
    return {
        phase: make_blended_symmetric_calibrator(kind, alpha).fit(pe.train_oof_cal, pe.train_y)
        for phase, pe in phase_eval.items()
    }


def fit_phase_blended(
    phase_eval: dict[str, PhaseEvaluation],
    kind: str,
    alpha: float,
) -> dict[str, Calibrator]:
    return {
        phase: make_blended_calibrator(kind, alpha).fit(pe.train_oof_cal, pe.train_y)
        for phase, pe in phase_eval.items()
    }


def apply_candidate(
    phase_eval: dict[str, PhaseEvaluation],
    calibrators: dict[str, Calibrator],
) -> tuple[np.ndarray, np.ndarray, dict[str, np.ndarray]]:
    all_y: list[np.ndarray] = []
    all_pred: list[np.ndarray] = []
    phase_preds: dict[str, np.ndarray] = {}
    for phase, pe in phase_eval.items():
        pred = np.clip(calibrators[phase].transform(pe.test_base_cal), 1e-7, 1 - 1e-7)
        phase_preds[phase] = pred
        all_pred.append(pred)
        all_y.append(pe.test_y)
    return np.concatenate(all_y), np.concatenate(all_pred), phase_preds


def favourite_bucket_table(y: np.ndarray, pred: np.ndarray) -> pd.DataFrame:
    p_fav = np.where(pred >= 0.5, pred, 1.0 - pred)
    y_fav = np.where(pred >= 0.5, y, 1.0 - y)
    rows = []
    for lo, hi, label in CONFIDENCE_BUCKETS:
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


def score_candidate(
    name: str,
    phase_eval: dict[str, PhaseEvaluation],
    calibrators: dict[str, Calibrator],
    baseline_metrics: dict[str, float],
    baseline_buckets: pd.DataFrame,
) -> dict[str, object]:
    y, pred, _ = apply_candidate(phase_eval, calibrators)
    candidate_metrics = metric_row(y, pred)
    candidate_buckets = favourite_bucket_table(y, pred)

    bucket_guardrails = []
    for bucket in sorted(GUARDRAIL_BUCKETS):
        base = baseline_buckets[baseline_buckets["bucket"] == bucket]
        cand = candidate_buckets[candidate_buckets["bucket"] == bucket]
        if base.empty or cand.empty:
            bucket_guardrails.append(False)
            continue
        bucket_guardrails.append(
            float(cand.iloc[0]["cal_error"]) <= float(base.iloc[0]["cal_error"]) + 1e-12
        )

    brier_delta_pct = (
        (candidate_metrics["brier"] - baseline_metrics["brier"])
        / baseline_metrics["brier"]
        * 100
    )
    logloss_delta_pct = (
        (candidate_metrics["logloss"] - baseline_metrics["logloss"])
        / baseline_metrics["logloss"]
        * 100
    )
    passed = (
        brier_delta_pct <= -MIN_BRIER_IMPROVEMENT_PCT
        and logloss_delta_pct <= -MIN_LOGLOSS_IMPROVEMENT_PCT
        and all(bucket_guardrails)
    )
    return {
        "name": name,
        "calibrators": calibrators,
        "metrics": candidate_metrics,
        "buckets": candidate_buckets,
        "passed": passed,
    }


def summarize_phase_metrics(
    phase_eval: dict[str, PhaseEvaluation],
    calibrators: dict[str, Calibrator],
) -> pd.DataFrame:
    rows = []
    for phase, pe in phase_eval.items():
        base = metric_row(pe.test_y, pe.test_base_cal)
        sharp = metric_row(pe.test_y, calibrators[phase].transform(pe.test_base_cal))
        rows.append(
            {
                "phase": phase,
                "n": base["n"],
                "base_brier": base["brier"],
                "sharp_brier": sharp["brier"],
                "brier_delta_pct": (sharp["brier"] - base["brier"]) / base["brier"] * 100,
                "base_logloss": base["logloss"],
                "sharp_logloss": sharp["logloss"],
                "logloss_delta_pct": (sharp["logloss"] - base["logloss"]) / base["logloss"] * 100,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    print("Loading IPL v14 data and pitch features...")
    df = add_pitch_features(load_training_data())
    phase_features = build_v14_features()

    print("Building baseline v14 OOF calibrators on train<2025 and OOS predictions...")
    phase_eval = {
        phase: evaluate_phase(df, phase, phase_features[phase])
        for phase in PHASE_RANGES_V12
    }

    base_y = np.concatenate([phase_eval[p].test_y for p in PHASE_RANGES_V12])
    base_pred = np.concatenate([phase_eval[p].test_base_cal for p in PHASE_RANGES_V12])
    baseline_metrics = metric_row(base_y, base_pred)
    baseline_buckets = favourite_bucket_table(base_y, base_pred)

    candidates = []
    candidate_groups = [("full", phase_eval)]
    for min_season in ["2021", "2022"]:
        candidate_groups.append((f"recent_{min_season}", recent_phase_eval(phase_eval, min_season)))

    for group_name, fit_eval in candidate_groups:
        scopes = ["global", "phase"] if group_name == "full" else ["global"]
        kinds = ["temperature", "platt", "isotonic"] if group_name == "full" else ["temperature", "platt", "isotonic"]
        for scope in scopes:
            for kind in kinds:
                print(f"Fitting {group_name}_{scope}_{kind} sharpness layer on OOF...")
                calibrators = (
                    fit_global(fit_eval, kind)
                    if scope == "global"
                    else fit_phase(fit_eval, kind)
                )
                candidates.append(
                    score_candidate(
                        f"{group_name}_{scope}_{kind}",
                        phase_eval,
                        calibrators,
                        baseline_metrics,
                        baseline_buckets,
                    )
                )
            for kind in ["platt", "isotonic"]:
                for alpha in [0.25, 0.50, 0.75]:
                    print(f"Fitting {group_name}_{scope}_{kind}_blend_{alpha:.2f} sharpness layer on OOF...")
                    calibrators = (
                        fit_global_blended(fit_eval, kind, alpha)
                        if scope == "global"
                        else fit_phase_blended(fit_eval, kind, alpha)
                    )
                    candidates.append(
                        score_candidate(
                            f"{group_name}_{scope}_{kind}_blend_{alpha:.2f}",
                            phase_eval,
                            calibrators,
                            baseline_metrics,
                            baseline_buckets,
                        )
                    )
            for kind in ["temperature", "platt", "isotonic"]:
                print(f"Fitting {group_name}_{scope}_symmetric_{kind} sharpness layer on OOF...")
                calibrators = (
                    fit_global_symmetric(fit_eval, kind)
                    if scope == "global"
                    else fit_phase_symmetric(fit_eval, kind)
                )
                candidates.append(
                    score_candidate(
                        f"{group_name}_{scope}_symmetric_{kind}",
                        phase_eval,
                        calibrators,
                        baseline_metrics,
                        baseline_buckets,
                    )
                )
            for kind in ["platt", "isotonic"]:
                for alpha in [0.25, 0.50, 0.75]:
                    print(f"Fitting {group_name}_{scope}_symmetric_{kind}_blend_{alpha:.2f} sharpness layer on OOF...")
                    calibrators = (
                        fit_global_symmetric_blended(fit_eval, kind, alpha)
                        if scope == "global"
                        else fit_phase_symmetric_blended(fit_eval, kind, alpha)
                    )
                    candidates.append(
                        score_candidate(
                            f"{group_name}_{scope}_symmetric_{kind}_blend_{alpha:.2f}",
                            phase_eval,
                            calibrators,
                            baseline_metrics,
                            baseline_buckets,
                        )
                    )

    summary_rows = []
    for candidate in candidates:
        metrics = candidate["metrics"]
        summary_rows.append(
            {
                "candidate": candidate["name"],
                "passed_guardrails": bool(candidate["passed"]),
                "brier": metrics["brier"],
                "brier_delta_pct": (metrics["brier"] - baseline_metrics["brier"])
                / baseline_metrics["brier"]
                * 100,
                "logloss": metrics["logloss"],
                "logloss_delta_pct": (metrics["logloss"] - baseline_metrics["logloss"])
                / baseline_metrics["logloss"]
                * 100,
            }
        )

    summary = pd.DataFrame(summary_rows).sort_values(
        ["passed_guardrails", "logloss", "brier"],
        ascending=[False, True, True],
    )

    print("\nBaseline v14 OOS:")
    print(
        f"  Brier={baseline_metrics['brier']:.5f} "
        f"LogLoss={baseline_metrics['logloss']:.5f}"
    )
    print("\nCandidate summary:")
    print(summary.to_string(index=False, float_format=lambda x: f"{x:.6f}"))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary.to_csv(OUT_DIR / "v14_sharpness_candidate_summary.csv", index=False)
    baseline_buckets.assign(candidate="baseline_v14").to_csv(
        OUT_DIR / "v14_sharpness_baseline_buckets.csv",
        index=False,
    )
    all_buckets = []
    for candidate in candidates:
        all_buckets.append(candidate["buckets"].assign(candidate=candidate["name"]))
    pd.concat(all_buckets, ignore_index=True).to_csv(
        OUT_DIR / "v14_sharpness_all_candidate_buckets.csv",
        index=False,
    )

    passing = [c for c in candidates if c["passed"]]
    if not passing:
        print("\nVerdict: DO NOT PROMOTE sharpness layer.")
        print(
            "No OOF-fitted monotonic candidate produced a material OOS Brier/LogLoss "
            "improvement while preserving 50-60 and 80+ bucket guardrails."
        )
        for stale in [
            OUT_DIR / "sharpness_calibrators.pkl",
            OUT_DIR / "v14_sharpness_promoted_buckets.csv",
            OUT_DIR / "v14_sharpness_promoted_phase_metrics.csv",
        ]:
            if stale.exists():
                stale.unlink()
        return

    best = sorted(
        passing,
        key=lambda c: (c["metrics"]["logloss"], c["metrics"]["brier"]),
    )[0]
    best_name = str(best["name"])
    best_metrics = best["metrics"]
    best_buckets = best["buckets"]
    best_calibrators = best["calibrators"]

    print(f"\nVerdict: PROMOTE {best_name}.")
    print(
        f"  Brier {baseline_metrics['brier']:.5f} -> {best_metrics['brier']:.5f}; "
        f"LogLoss {baseline_metrics['logloss']:.5f} -> {best_metrics['logloss']:.5f}"
    )

    best_buckets.assign(candidate=best_name).to_csv(
        OUT_DIR / "v14_sharpness_promoted_buckets.csv",
        index=False,
    )
    phase_metrics = summarize_phase_metrics(phase_eval, best_calibrators)
    phase_metrics.to_csv(OUT_DIR / "v14_sharpness_promoted_phase_metrics.csv", index=False)

    payload = {
        "description": "Second-stage monotonic sharpness calibration fitted on pre-2025 OOF predictions only.",
        "candidate": best_name,
        "guardrails": {
            "oos_brier_improves": True,
            "oos_logloss_improves": True,
            "overall_buckets_not_damaged": sorted(GUARDRAIL_BUCKETS),
        },
        "baseline_metrics": baseline_metrics,
        "promoted_metrics": best_metrics,
        "calibrators": best_calibrators,
    }
    with open(OUT_DIR / "sharpness_calibrators.pkl", "wb") as f:
        pickle.dump(payload, f)
    print(f"  Saved: {OUT_DIR / 'sharpness_calibrators.pkl'}")
    print(f"  Saved: {OUT_DIR / 'v14_sharpness_promoted_phase_metrics.csv'}")
    print(f"  Saved: {OUT_DIR / 'v14_sharpness_promoted_buckets.csv'}")


if __name__ == "__main__":
    main()
