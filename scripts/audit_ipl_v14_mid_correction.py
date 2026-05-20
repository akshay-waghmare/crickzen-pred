"""Audit the IPL v14 innings-2 middle-over par-chase correction.

Compares the current post-model calibration artifact against a candidate that
allows the existing inn2_par_pp_mid correction to fire in middle overs too.
"""

from __future__ import annotations

import copy
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss

from bbl_pipeline.inference.post_model_calibration_router import (
    PostModelCalibrationRouter,
)


PREDICTIONS_PATH = Path("models/ipl_high_chase_v1/v14_oos_predictions_by_ball.csv")
ARTIFACT_PATH = Path("models/ipl_v14_pitch_features/post_model_calibration_router.pkl")


def _phase_label(phase: str) -> str:
    return {
        "pp": "inn2_powerplay",
        "mid": "inn2_middle",
        "death": "inn2_death",
    }.get(str(phase).lower(), f"inn2_{phase}")


def _apply_router(artifact: dict, df: pd.DataFrame, probabilities: np.ndarray) -> np.ndarray:
    router = PostModelCalibrationRouter(artifact)
    outputs: list[float] = []
    for probability, phase, target_above_par in zip(
        probabilities,
        df["phase"].map(_phase_label),
        df["target_above_par"].astype(float),
    ):
        corrected, _ = router.apply(
            float(probability),
            innings=2,
            phase=phase,
            target_above_par=float(target_above_par),
        )
        outputs.append(corrected)
    return np.asarray(outputs, dtype=float)


def _metrics(y: np.ndarray, pred: np.ndarray, mask: np.ndarray) -> dict[str, float]:
    yy = y[mask]
    pp = pred[mask].clip(1e-6, 1.0 - 1e-6)
    return {
        "n": int(mask.sum()),
        "mean_pred": float(pp.mean()),
        "actual": float(yy.mean()),
        "gap_pp": float((pp.mean() - yy.mean()) * 100.0),
        "brier": float(brier_score_loss(yy, pp)),
        "logloss": float(log_loss(yy, pp, labels=[0, 1])),
    }


def _effective_match_count(df: pd.DataFrame, mask: np.ndarray) -> int | None:
    if "match_id" not in df.columns:
        return None
    return int(df.loc[mask, "match_id"].nunique())


def main() -> None:
    df = pd.read_csv(PREDICTIONS_PATH)
    y = df["y"].astype(float).to_numpy()
    phase = df["phase"].astype(str).str.lower()
    target_above_par = df["target_above_par"].astype(float)

    artifact = joblib.load(ARTIFACT_PATH)
    pp_only = copy.deepcopy(artifact)
    pp_only["inn2_par_pp_mid"]["allowed_phases"] = ["pp"]
    pp_mid = copy.deepcopy(artifact)
    pp_mid["inn2_par_pp_mid"]["allowed_phases"] = ["pp", "mid"]

    for column in ("v14_oos_raw", "v14_prod_raw"):
        raw = df[column].astype(float).clip(1e-6, 1.0 - 1e-6).to_numpy()
        current = _apply_router(pp_only, df, raw)
        widened = _apply_router(pp_mid, df, raw)

        segments = {
            "all": np.ones(len(df), dtype=bool),
            "mid_all": phase.eq("mid").to_numpy(),
            "mid_par_50_80": (
                phase.eq("mid")
                & target_above_par.between(-20.0, 20.0)
                & (raw >= 0.50)
                & (raw <= 0.80)
            ).to_numpy(),
            "mid_par_50_80_2026": (
                df["season"].eq(2026)
                & phase.eq("mid")
                & target_above_par.between(-20.0, 20.0)
                & (raw >= 0.50)
                & (raw <= 0.80)
            ).to_numpy(),
        }

        print(f"\n## {column}")
        for name, mask in segments.items():
            if not mask.any():
                continue
            base = _metrics(y, raw, mask)
            current_m = _metrics(y, current, mask)
            widened_m = _metrics(y, widened, mask)
            n_matches = _effective_match_count(df, mask)
            match_note = f" matches={n_matches:3d} " if n_matches is not None else ""
            small_sample_note = ""
            if n_matches is not None and n_matches < 10:
                small_sample_note = " [small-match-sample]"
            print(
                f"{name:20s} n={base['n']:5d} "
                f"actual={base['actual']:.3f} "
                f"raw_mean={base['mean_pred']:.3f} "
                f"pp_mid_mean={widened_m['mean_pred']:.3f} "
                f"{match_note}"
                f"raw_brier={base['brier']:.5f} "
                f"pp_only={current_m['brier']:.5f} "
                f"pp_mid={widened_m['brier']:.5f} "
                f"raw_gap={base['gap_pp']:+6.2f}pp "
                f"pp_mid_gap={widened_m['gap_pp']:+6.2f}pp "
                f"pp_mid_logloss={widened_m['logloss']:.5f}"
                f"{small_sample_note}"
            )


if __name__ == "__main__":
    main()
