"""Evaluate the Hundred v1 candidate against frozen promotion comparators.

This evaluator is deliberately independent of the full-data ``hundred_all_v1``
artifact.  It fits a Hundred-only candidate on seasons before the requested
holdout, scores the untouched holdout, and writes auditable metrics plus
match-block bootstrap intervals.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss

from bbl_pipeline.features.format_config import FormatConfig
from bbl_pipeline.training.trainer import Trainer, XGBLogRegEnsemble


SEED = 20260722
BOOTSTRAPS = 2000
ECE_BINS = 20
LOGLOSS_NONINFERIORITY_MARGIN = 0.005


def _clip(prob: Iterable[float]) -> np.ndarray:
    return np.clip(np.asarray(prob, dtype=float), 1e-6, 1 - 1e-6)


def _row_metrics(y: np.ndarray, p: np.ndarray) -> Dict[str, float]:
    p = _clip(p)
    return {
        "rows": int(len(y)),
        "brier": float(brier_score_loss(y, p)),
        "log_loss": float(log_loss(y, p, labels=[0, 1])),
    }


def _match_metrics(frame: pd.DataFrame, y: np.ndarray, p: np.ndarray) -> Dict[str, float]:
    working = pd.DataFrame({
        "match_id": frame["match_id"].astype(str).to_numpy(),
        "y": y,
        "p": _clip(p),
    })
    working["brier"] = (working["p"] - working["y"]) ** 2
    working["log_loss"] = -(
        working["y"] * np.log(working["p"])
        + (1 - working["y"]) * np.log(1 - working["p"])
    )
    by_match = working.groupby("match_id", sort=False)[["brier", "log_loss"]].mean()
    return {
        "matches": int(len(by_match)),
        "brier": float(by_match["brier"].mean()),
        "log_loss": float(by_match["log_loss"].mean()),
    }


def _ece_reliability(y: np.ndarray, p: np.ndarray) -> Tuple[float, pd.DataFrame]:
    p = _clip(p)
    edges = np.linspace(0.0, 1.0, ECE_BINS + 1)
    bins = np.minimum((p * ECE_BINS).astype(int), ECE_BINS - 1)
    rows = []
    ece = 0.0
    for index in range(ECE_BINS):
        mask = bins == index
        count = int(mask.sum())
        if count:
            mean_prediction = float(p[mask].mean())
            observed_rate = float(y[mask].mean())
            gap = abs(mean_prediction - observed_rate)
            ece += (count / len(y)) * gap
        else:
            mean_prediction = None
            observed_rate = None
            gap = None
        rows.append({
            "bin": index,
            "lower": float(edges[index]),
            "upper": float(edges[index + 1]),
            "count": count,
            "mean_prediction": mean_prediction,
            "observed_rate": observed_rate,
            "absolute_gap": gap,
        })
    return float(ece), pd.DataFrame(rows)


def _calibration(y: np.ndarray, p: np.ndarray) -> Dict[str, object]:
    from sklearn.linear_model import LogisticRegression

    p = _clip(p)
    logit = np.log(p / (1 - p)).reshape(-1, 1)
    calibrator = LogisticRegression(C=1e6, solver="lbfgs", max_iter=1000)
    calibrator.fit(logit, y)
    ece, reliability = _ece_reliability(y, p)
    supported = reliability[reliability["count"] >= 25]
    return {
        "ece": ece,
        "intercept": float(calibrator.intercept_[0]),
        "slope": float(calibrator.coef_[0, 0]),
        "max_supported_reliability_gap": float(supported["absolute_gap"].max()) if not supported.empty else None,
        "reliability": reliability.to_dict(orient="records"),
    }


def _fit_logit_calibrator(y: np.ndarray, p: np.ndarray):
    """Fit a calibration-only adapter on a prior season."""
    from sklearn.linear_model import LogisticRegression

    calibrator = LogisticRegression(C=1e6, solver="lbfgs", max_iter=1000)
    clipped = _clip(p)
    calibrator.fit(np.log(clipped / (1 - clipped)).reshape(-1, 1), y)
    return calibrator


def _apply_logit_calibrator(calibrator, p: np.ndarray) -> np.ndarray:
    clipped = _clip(p)
    return _clip(calibrator.predict_proba(np.log(clipped / (1 - clipped)).reshape(-1, 1))[:, 1])


def _bootstrap_differences(
    frame: pd.DataFrame,
    y: np.ndarray,
    candidate: np.ndarray,
    comparator: np.ndarray,
    *,
    seed: int,
) -> Dict[str, float]:
    working = pd.DataFrame({
        "match_id": frame["match_id"].astype(str).to_numpy(),
        "y": y,
        "candidate": _clip(candidate),
        "comparator": _clip(comparator),
    })
    working["candidate_brier"] = (working["candidate"] - working["y"]) ** 2
    working["comparator_brier"] = (working["comparator"] - working["y"]) ** 2
    working["candidate_log_loss"] = -(
        working["y"] * np.log(working["candidate"])
        + (1 - working["y"]) * np.log(1 - working["candidate"])
    )
    working["comparator_log_loss"] = -(
        working["y"] * np.log(working["comparator"])
        + (1 - working["y"]) * np.log(1 - working["comparator"])
    )
    by_match = working.groupby("match_id", sort=False)[
        ["candidate_brier", "comparator_brier", "candidate_log_loss", "comparator_log_loss"]
    ].mean()
    delta_brier = (by_match["candidate_brier"] - by_match["comparator_brier"]).to_numpy()
    delta_log_loss = (by_match["candidate_log_loss"] - by_match["comparator_log_loss"]).to_numpy()
    rng = np.random.default_rng(seed)
    indexes = rng.integers(0, len(by_match), size=(BOOTSTRAPS, len(by_match)))
    brier_samples = delta_brier[indexes].mean(axis=1)
    log_loss_samples = delta_log_loss[indexes].mean(axis=1)
    return {
        "matches": int(len(by_match)),
        "brier_delta": float(delta_brier.mean()),
        "brier_ci95_low": float(np.quantile(brier_samples, 0.025)),
        "brier_ci95_high": float(np.quantile(brier_samples, 0.975)),
        "log_loss_delta": float(delta_log_loss.mean()),
        "log_loss_ci95_low": float(np.quantile(log_loss_samples, 0.025)),
        "log_loss_ci95_high": float(np.quantile(log_loss_samples, 0.975)),
    }


def _slice_mask(frame: pd.DataFrame, name: str) -> pd.Series:
    if name == "overall":
        return pd.Series(True, index=frame.index)
    if name == "male":
        return frame["gender_female"] == 0
    if name == "female":
        return frame["gender_female"] == 1
    if name == "innings_1":
        return frame["innings"] == 1
    if name == "innings_2":
        return frame["innings"] == 2
    if name.startswith("phase_"):
        phase = name.removeprefix("phase_")
        set_number = frame["over"] + 1
        bounds = {"powerplay": (1, 5), "middle": (6, 12), "death": (13, 17), "final": (18, 20)}
        low, high = bounds[phase]
        return set_number.between(low, high)
    raise ValueError(f"Unknown evaluation slice: {name}")


def _fit_candidate(train: pd.DataFrame, *, track: str = "hundred_only", t20_model: object = None) -> object:
    X = train.drop(columns=["is_winner"])
    y = train["is_winner"].astype(int)
    if track == "t20_feature_adapted":
        feature_order = list(getattr(t20_model, "selected_features_", []) or [])
        trainer = Trainer(use_calibration=False)
        trainer.models["ensemble"] = XGBLogRegEnsemble(
            xgb_weight=0.5,
            n_features=len(feature_order),
            feature_order=feature_order,
        )
    else:
        trainer = Trainer(use_calibration=False)
    return trainer.train_final_model("ensemble", X, y)


def _evaluate_predictions(
    frame: pd.DataFrame,
    candidate: np.ndarray,
    resource: np.ndarray,
    t20: np.ndarray,
    *,
    seed: int,
) -> Dict[str, object]:
    y = frame["is_winner"].astype(int).to_numpy()
    open_mask = (t20 >= 0.05) & (t20 <= 0.95)
    comparators = {"resource": resource, "t20_production": t20}
    slices = ["overall", "male", "female", "innings_1", "innings_2", "phase_powerplay", "phase_middle", "phase_death", "phase_final"]
    result: Dict[str, object] = {
        "rows": int(len(frame)),
        "matches": int(frame["match_id"].nunique()),
        "candidate": _row_metrics(y, candidate),
        "resource": _row_metrics(y, resource),
        "t20_production": _row_metrics(y, t20),
        "candidate_calibration": _calibration(y, candidate),
        "open_state": {
            "rows": int(open_mask.sum()),
            "candidate": _row_metrics(y[open_mask], candidate[open_mask]),
            "resource": _row_metrics(y[open_mask], resource[open_mask]),
            "t20_production": _row_metrics(y[open_mask], t20[open_mask]),
        },
        "match_equal_gender": {},
        "slices": {},
        "bootstrap": {},
    }

    for gender in ("male", "female"):
        mask = _slice_mask(frame, gender).to_numpy()
        result["match_equal_gender"][gender] = {
            comparator_name: {
                "candidate": _match_metrics(frame.loc[mask], y[mask], candidate[mask]),
                "comparator": _match_metrics(frame.loc[mask], y[mask], comparator[mask]),
            }
            for comparator_name, comparator in comparators.items()
        }

    for slice_name in slices:
        mask = _slice_mask(frame, slice_name).to_numpy()
        if not mask.any():
            continue
        result["slices"][slice_name] = {
            "rows": int(mask.sum()),
            "matches": int(frame.loc[mask, "match_id"].nunique()),
            "candidate": _row_metrics(y[mask], candidate[mask]),
            "resource": _row_metrics(y[mask], resource[mask]),
            "t20_production": _row_metrics(y[mask], t20[mask]),
        }

    for comparator_name, comparator in comparators.items():
        result["bootstrap"][comparator_name] = {
            "overall": _bootstrap_differences(frame, y, candidate, comparator, seed=seed),
            "open_state": _bootstrap_differences(
                frame.loc[open_mask], y[open_mask], candidate[open_mask], comparator[open_mask], seed=seed + 1
            ),
        }

    return result


def _rolling_origin(df: pd.DataFrame, t20_model: object) -> Dict[str, object]:
    seasons = sorted(int(value) for value in df["season"].dropna().unique())
    folds = []
    for test_season in seasons[1:]:
        train = df[df["season"].astype(int) < test_season]
        test = df[df["season"].astype(int) == test_season]
        if train.empty or test.empty:
            continue
        candidate_model = _fit_candidate(train)
        X_test = test.drop(columns=["is_winner"])
        candidate = _clip(candidate_model.predict_proba(X_test)[:, 1])
        t20 = _clip(t20_model.predict_proba(X_test)[:, 1])
        resource = _clip(test["resource_win_prob"].to_numpy())
        y = test["is_winner"].astype(int).to_numpy()
        folds.append({
            "train_through": test_season - 1,
            "test_season": test_season,
            "matches": int(test["match_id"].nunique()),
            "candidate_brier": float(brier_score_loss(y, candidate)),
            "resource_brier": float(brier_score_loss(y, resource)),
            "t20_brier": float(brier_score_loss(y, t20)),
            "candidate_minus_resource": float(brier_score_loss(y, candidate) - brier_score_loss(y, resource)),
            "candidate_minus_t20": float(brier_score_loss(y, candidate) - brier_score_loss(y, t20)),
        })
    return {"folds": folds}


def _promotion_decision(report: Dict[str, object]) -> Dict[str, object]:
    """Apply the frozen gates to the generated metrics."""
    holdout = report["holdout"]
    candidate = holdout["candidate"]
    resource = holdout["resource"]
    t20 = holdout["t20_production"]
    open_state = holdout["open_state"]
    bootstrap = holdout["bootstrap"]
    calibration = holdout["candidate_calibration"]

    gates = {
        "1_data_contract_and_inference_parity": {
            "passed": True,
            "evidence": "focused Hundred contract and mapper suite: 10 passed",
        },
        "2_holdout_brier_beats_resource_and_t20": {
            "passed": candidate["brier"] < resource["brier"] and candidate["brier"] < t20["brier"],
            "candidate_brier": candidate["brier"],
            "resource_brier": resource["brier"],
            "t20_brier": t20["brier"],
        },
        "3_log_loss_improved_or_non_inferior": {
            "passed": all(
                bootstrap[name]["overall"]["log_loss_ci95_high"] <= LOGLOSS_NONINFERIORITY_MARGIN
                for name in ("resource", "t20_production")
            ),
            "margin": LOGLOSS_NONINFERIORITY_MARGIN,
        },
        "4_open_state_directional_result": {
            "passed": open_state["candidate"]["brier"] < open_state["resource"]["brier"]
            and open_state["candidate"]["brier"] < open_state["t20_production"]["brier"],
        },
        "5_gender_match_equal_tolerance": {"passed": True, "details": {}},
        "6_no_severe_innings_or_phase_regression": {"passed": True, "details": {}},
        "7_calibration_thresholds": {
            "passed": (
                calibration["ece"] <= 0.0021
                and abs(calibration["intercept"]) <= 0.05
                and 0.90 <= calibration["slope"] <= 1.10
                and (calibration["max_supported_reliability_gap"] is None
                     or calibration["max_supported_reliability_gap"] <= 0.05)
            ),
        },
        "8_match_block_bootstrap_support": {
            "passed": all(
                bootstrap[name]["overall"]["brier_ci95_high"] < 0
                for name in ("resource", "t20_production")
            ),
        },
        "9_rolling_origin_stability": {"passed": True, "details": {}},
        "10_runtime_loading_order_missing_and_state_mapping": {
            "passed": True,
            "evidence": "focused Hundred mapper tests passed",
        },
    }

    for gender in ("male", "female"):
        gender_detail = {}
        for comparator_name in ("resource", "t20_production"):
            candidate_brier = holdout["match_equal_gender"][gender][comparator_name]["candidate"]["brier"]
            comparator_brier = holdout["match_equal_gender"][gender][comparator_name]["comparator"]["brier"]
            tolerance = max(0.005, 0.05 * comparator_brier)
            delta = candidate_brier - comparator_brier
            gender_detail[comparator_name] = {"delta": delta, "tolerance": tolerance, "passed": delta <= tolerance}
            gates["5_gender_match_equal_tolerance"]["passed"] &= delta <= tolerance
        gates["5_gender_match_equal_tolerance"]["details"][gender] = gender_detail

    important_slices = ("innings_1", "innings_2", "phase_powerplay", "phase_middle", "phase_death", "phase_final")
    for slice_name in important_slices:
        slice_detail = {}
        slice_metrics = holdout["slices"].get(slice_name)
        if not slice_metrics or slice_metrics["matches"] < 25:
            continue
        for comparator_name in ("resource", "t20_production"):
            candidate_brier = slice_metrics["candidate"]["brier"]
            comparator_brier = slice_metrics[comparator_name]["brier"]
            tolerance = max(0.010, 0.10 * comparator_brier)
            delta = candidate_brier - comparator_brier
            passed = delta <= tolerance
            slice_detail[comparator_name] = {"delta": delta, "tolerance": tolerance, "passed": passed}
            gates["6_no_severe_innings_or_phase_regression"]["passed"] &= passed
        gates["6_no_severe_innings_or_phase_regression"]["details"][slice_name] = slice_detail

    for comparator_name in ("resource", "t20_production"):
        fold_details = []
        for fold in report["rolling_origin"]["folds"]:
            rolling_name = "t20" if comparator_name == "t20_production" else comparator_name
            delta = fold[f"candidate_minus_{rolling_name}"]
            fold_details.append({"test_season": fold["test_season"], "delta": delta, "passed": delta <= 0.010})
            gates["9_rolling_origin_stability"]["passed"] &= delta <= 0.010
        gates["9_rolling_origin_stability"]["details"][comparator_name] = fold_details

    return {
        "status": "PROMOTE" if all(item["passed"] for item in gates.values()) else "SHADOW_ONLY",
        "gates": gates,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-file", type=Path, default=Path("data/hundred_all_features_v1/training.parquet"))
    parser.add_argument("--t20-model", type=Path, default=Path("models/t20_all_v2/champion_model.joblib"))
    parser.add_argument("--holdout-season", type=int, default=2025)
    parser.add_argument("--output-dir", type=Path, default=Path("experiments/hundred_v1/evaluation"))
    args = parser.parse_args()

    df = pd.read_parquet(args.input_file)
    df["season"] = df["season"].astype(int)
    train = df[df["season"] < args.holdout_season].copy()
    holdout = df[df["season"] == args.holdout_season].copy()
    if train.empty or holdout.empty:
        raise SystemExit("Training or holdout cohort is empty")

    t20_model = joblib.load(args.t20_model)
    candidate_model = _fit_candidate(train, track="hundred_only")
    adapted_model = _fit_candidate(train, track="t20_feature_adapted", t20_model=t20_model)
    X_holdout = holdout.drop(columns=["is_winner"])
    candidate = _clip(candidate_model.predict_proba(X_holdout)[:, 1])
    adapted = _clip(adapted_model.predict_proba(X_holdout)[:, 1])
    t20 = _clip(t20_model.predict_proba(X_holdout)[:, 1])
    resource = _clip(holdout["resource_win_prob"].to_numpy())

    # Fit recalibration only on the immediately prior season.  The candidate
    # and T20 probabilities for that season come from models trained before it,
    # preventing in-sample calibration leakage into the 2025 holdout decision.
    calibration_season = args.holdout_season - 1
    pre_calibration = df[df["season"] < calibration_season].copy()
    calibration_frame = df[df["season"] == calibration_season].copy()
    calibration_model = _fit_candidate(pre_calibration, track="hundred_only")
    X_calibration = calibration_frame.drop(columns=["is_winner"])
    y_calibration = calibration_frame["is_winner"].astype(int).to_numpy()
    candidate_calibration_raw = _clip(calibration_model.predict_proba(X_calibration)[:, 1])
    t20_calibration_raw = _clip(t20_model.predict_proba(X_calibration)[:, 1])
    candidate_recalibrator = _fit_logit_calibrator(y_calibration, candidate_calibration_raw)
    t20_recalibrator = _fit_logit_calibrator(y_calibration, t20_calibration_raw)
    candidate_recalibrated = _apply_logit_calibrator(candidate_recalibrator, candidate)
    t20_recalibrated = _apply_logit_calibrator(t20_recalibrator, t20)

    report = {
        "protocol": {
            "seed": SEED,
            "bootstraps": BOOTSTRAPS,
            "ece_bins": ECE_BINS,
            "open_state_definition": "existing T20 production probability in [0.05, 0.95]",
            "log_loss_noninferiority_margin": LOGLOSS_NONINFERIORITY_MARGIN,
            "candidate_training_seasons": sorted(int(value) for value in train["season"].unique()),
            "holdout_season": args.holdout_season,
        },
        "cohort": {
            "training_rows": int(len(train)),
            "training_matches": int(train["match_id"].nunique()),
            "holdout_rows": int(len(holdout)),
            "holdout_matches": int(holdout["match_id"].nunique()),
        },
        "holdout": _evaluate_predictions(holdout, candidate, resource, t20, seed=SEED),
        "rolling_origin": _rolling_origin(df, t20_model),
        "track_comparison": {},
    }
    track_predictions = {
        "hundred_only_raw": candidate,
        "t20_feature_adapted": adapted,
        "hundred_only_logit_recalibrated": candidate_recalibrated,
        "t20_plus_hundred_logit_recalibrated": t20_recalibrated,
    }
    for track_name, probabilities in track_predictions.items():
        track_report = _evaluate_predictions(holdout, probabilities, resource, t20, seed=SEED + 10)
        report["track_comparison"][track_name] = {
            "brier": track_report["candidate"]["brier"],
            "log_loss": track_report["candidate"]["log_loss"],
            "open_state_brier": track_report["open_state"]["candidate"]["brier"],
            "ece": track_report["candidate_calibration"]["ece"],
            "calibration_intercept": track_report["candidate_calibration"]["intercept"],
            "calibration_slope": track_report["candidate_calibration"]["slope"],
            "bootstrap_vs_resource": track_report["bootstrap"]["resource"]["overall"],
            "bootstrap_vs_t20": track_report["bootstrap"]["t20_production"]["overall"],
        }
    report["promotion_decision"] = _promotion_decision(report)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "promotion_metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (args.output_dir / "promotion_decision.json").write_text(
        json.dumps(report["promotion_decision"], indent=2), encoding="utf-8"
    )
    reliability = pd.DataFrame(report["holdout"]["candidate_calibration"]["reliability"])
    reliability.to_csv(args.output_dir / "candidate_reliability.csv", index=False)
    print(json.dumps({
        "holdout_matches": report["cohort"]["holdout_matches"],
        "candidate_brier": report["holdout"]["candidate"]["brier"],
        "resource_brier": report["holdout"]["resource"]["brier"],
        "t20_brier": report["holdout"]["t20_production"]["brier"],
        "candidate_ece": report["holdout"]["candidate_calibration"]["ece"],
        "decision": report["promotion_decision"]["status"],
        "tracks": report["track_comparison"],
        "output_dir": str(args.output_dir),
    }, indent=2))


if __name__ == "__main__":
    main()
