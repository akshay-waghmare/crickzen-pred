"""
IPL v14 high-chase calibration curve analysis.

Runs a true OOS evaluation (train seasons <2025, test seasons >=2025) for the
current IPL v14 innings-2 phase router feature set, then reports raw vs existing
v14 calibrated performance across chase situations.
"""
from __future__ import annotations

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
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
)


OUT_DIR = Path("models/ipl_high_chase_v1")
V7_MODEL_DIR = Path("models/ipl_v7")
V14_MODEL_DIR = Path("models/ipl_v14_pitch_features")
HIGH_CHASE_THRESHOLD = 20.0
CAL_BINS = np.linspace(0.0, 1.0, 11)
BOOTSTRAP_SAMPLES = 500


def ece(y_true: np.ndarray, pred: np.ndarray, n_bins: int = 10) -> float:
    y_true = np.asarray(y_true, dtype=float)
    pred = np.asarray(pred, dtype=float)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    total = len(y_true)
    if total == 0:
        return float("nan")
    value = 0.0
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (pred >= lo) & (pred < hi)
        if mask.sum() == 0:
            continue
        value += (mask.sum() / total) * abs(float(pred[mask].mean()) - float(y_true[mask].mean()))
    return float(value)


def safe_log_loss(y_true: np.ndarray, pred: np.ndarray) -> float:
    pred = np.clip(np.asarray(pred, dtype=float), 1e-7, 1 - 1e-7)
    return float(log_loss(y_true, pred, labels=[0, 1]))


def pct_delta(new_value: float, old_value: float) -> float:
    if old_value == 0 or np.isnan(old_value):
        return float("nan")
    return float((new_value - old_value) / old_value * 100.0)


def build_v14_features() -> dict[str, list[str]]:
    v12_feats = load_v12_features()
    return {
        "pp": ordered_unique(v12_feats["pp"] + PP_PITCH_FEATURES),
        "mid": ordered_unique(v12_feats["mid"] + MID_PITCH_FEATURES),
        "death": ordered_unique(v12_feats["death"] + DEATH_PITCH_FEATURES),
    }


def _apply_per_over_bundle(raw: np.ndarray, overs: np.ndarray, bundle: dict) -> np.ndarray:
    """Apply per-over isotonic calibrators, falling back to phase_iso."""
    per_over = bundle.get("per_over", {})
    phase_iso = bundle.get("phase_iso")
    out = raw.copy()
    for i, (r, ov) in enumerate(zip(raw, overs)):
        cal = per_over.get(int(ov)) or phase_iso
        if cal is not None:
            out[i] = float(cal.predict([r])[0])
    return out


def score_v7_production(df_test: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Score test rows with the actual production v7 model (raw + inn2-isotonic calibrated)."""
    import pickle
    v7_model = joblib.load(V7_MODEL_DIR / "champion_model.joblib")
    feats = v7_model.selected_features_
    X = df_test[feats].fillna(0.0)
    raw = v7_model.predict_proba(X)[:, 1]
    with open(V7_MODEL_DIR / "inn2_isotonic_calibrator.pkl", "rb") as fh:
        bundle = pickle.load(fh)
    cal_iso = bundle["calibrator"]
    calibrated = cal_iso.predict(raw)
    return raw.astype(float), calibrated.astype(float)


def score_v14_production(df_test: pd.DataFrame, phase_features: dict[str, list[str]]) -> tuple[np.ndarray, np.ndarray]:
    """Score test rows with the actual production v14 phase models (raw + per-over calibrated)."""
    import pickle
    with open(V14_MODEL_DIR / "phase_oof_calibrators.pkl", "rb") as fh:
        phase_cals = pickle.load(fh)
    phase_models = {
        ph: joblib.load(V14_MODEL_DIR / f"champion_model_{ph}.joblib")
        for ph in ["pp", "mid", "death"]
    }
    raw_all = np.full(len(df_test), np.nan)
    cal_all = np.full(len(df_test), np.nan)
    for ph, over_range in PHASE_RANGES_V12.items():
        mask = (df_test["phase"] == ph).values
        if mask.sum() == 0:
            continue
        sub = df_test[mask]
        X, _ = safe_X(sub, phase_features[ph])
        raw = phase_models[ph].predict_proba(X)[:, 1]
        overs = sub["over"].values.astype(int)
        cal = _apply_per_over_bundle(raw, overs, phase_cals[ph])
        idx = np.where(mask)[0]
        raw_all[idx] = raw
        cal_all[idx] = cal
    return raw_all.astype(float), cal_all.astype(float)


def run_v14_oos(df: pd.DataFrame, phase_features: dict[str, list[str]]) -> pd.DataFrame:
    train_seasons = {s for s in sorted(df["season"].unique()) if s < "2025"}
    test_seasons = {s for s in sorted(df["season"].unique()) if s >= "2025"}
    outputs: list[pd.DataFrame] = []

    for phase, over_range in PHASE_RANGES_V12.items():
        pf = phase_slice(df, over_range)
        pf_tr = pf[pf["season"].isin(train_seasons)].copy().reset_index(drop=True)
        pf_te = pf[pf["season"].isin(test_seasons)].copy().reset_index(drop=True)
        if pf_te.empty:
            continue

        print(
            f"Scoring {phase.upper():<5} train_rows={len(pf_tr):,} "
            f"test_rows={len(pf_te):,}"
        )
        train_oof = oof_phase_predictions(pf_tr, phase_features[phase])
        bundle = fit_calibrator_bundle(
            train_oof["raw"],
            train_oof["y"],
            train_oof["over"],
            CAL_METHODS_V12[phase],
        )

        x_train, _ = safe_X(pf_tr, phase_features[phase])
        x_test, _ = safe_X(pf_te, phase_features[phase])
        y_train = pf_tr["is_winner"].values
        over_test = pf_te["over"].values.astype(int)

        model = XGBLRBlend()
        model.fit(x_train, y_train)
        raw = model.predict_proba(x_test)[:, 1]
        cal = apply_calibrator_bundle(raw, over_test, bundle)

        keep_cols = [
            "match_id",
            "season",
            "over",
            "ball",
            "is_winner",
            "target_above_par",
            "required_run_rate",
            "current_run_rate",
            "score_vs_par",
            "resource_win_prob",
            "wickets_lost",
            "wickets_remaining",
            "venue_chase_success",
            "pp_score_vs_venue",
            "pp_wkts_vs_venue",
            "death_rr_vs_venue",
            "death_wkts_vs_venue",
            "avg_boundary18_vs_venue",
            "mid_avg_boundary18_vs_venue",
        ]
        out = pf_te[[c for c in keep_cols if c in pf_te.columns]].copy()
        out["phase"] = phase
        out["v14_oos_raw"] = raw    # retrained OOS model, NO calibration
        out["v14_oos_cal"] = cal    # retrained OOS model, OOF calibration
        out["raw_pred"] = raw       # keep alias for backwards compat
        out["cal_pred"] = cal       # keep alias for backwards compat
        out["y"] = pf_te["is_winner"].astype(float).values
        if "wickets_remaining" not in out.columns:
            out["wickets_remaining"] = (10 - out["wickets_lost"].fillna(0)).clip(0, 10)
        outputs.append(out)

    if not outputs:
        raise RuntimeError("No OOS rows were produced")
    result = pd.concat(outputs, ignore_index=True)
    # Sort by match_id/over/ball to have consistent order for production scoring
    result = result.sort_values(["match_id", "over", "ball"], ignore_index=True)
    return result


def add_situation_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    tap = out["target_above_par"].astype(float)
    out["is_high_chase"] = tap > HIGH_CHASE_THRESHOLD
    out["chase_bucket"] = np.select(
        [tap < -20, tap > HIGH_CHASE_THRESHOLD],
        ["low", "high"],
        default="par",
    )
    out["target_band"] = pd.cut(
        tap,
        bins=[-np.inf, -40, -20, 0, 20, 40, np.inf],
        labels=["<=-40", "-40:-20", "-20:0", "0:20", "20:40", "40+"],
    ).astype(str)
    out["rrr_band"] = pd.cut(
        out["required_run_rate"].astype(float),
        bins=[-np.inf, 8, 10, 12, 14, np.inf],
        labels=["<=8", "8:10", "10:12", "12:14", "14+"],
    ).astype(str)
    out["score_vs_par_band"] = pd.cut(
        out["score_vs_par"].astype(float),
        bins=[-np.inf, -40, -20, 0, 20, 40, np.inf],
        labels=["<=-40", "-40:-20", "-20:0", "0:20", "20:40", "40+"],
    ).astype(str)
    out["wickets_remaining_band"] = pd.cut(
        out["wickets_remaining"].astype(float),
        bins=[-np.inf, 3, 6, 10],
        labels=["0:3", "4:6", "7:10"],
    ).astype(str)
    out["resource_prob_band"] = pd.cut(
        out["resource_win_prob"].astype(float),
        bins=[-np.inf, 0.2, 0.4, 0.6, 0.8, np.inf],
        labels=["<=20", "20:40", "40:60", "60:80", "80+"],
    ).astype(str)
    return out


def summarize_slice(segment: str, situation: str, df: pd.DataFrame) -> dict[str, object]:
    y = df["y"].values.astype(float)
    raw = df["raw_pred"].values.astype(float)
    cal = df["cal_pred"].values.astype(float)
    actual = float(y.mean())
    raw_mean = float(raw.mean())
    cal_mean = float(cal.mean())
    raw_brier = float(brier_score_loss(y, raw))
    cal_brier = float(brier_score_loss(y, cal))
    raw_logloss = safe_log_loss(y, raw)
    cal_logloss = safe_log_loss(y, cal)
    return {
        "segment": segment,
        "situation": situation,
        "n": int(len(df)),
        "matches": int(df["match_id"].nunique()),
        "actual_wr": actual,
        "raw_mean": raw_mean,
        "cal_mean": cal_mean,
        "raw_bias": raw_mean - actual,
        "cal_bias": cal_mean - actual,
        "raw_abs_error": abs(raw_mean - actual),
        "cal_abs_error": abs(cal_mean - actual),
        "raw_brier": raw_brier,
        "cal_brier": cal_brier,
        "brier_delta_cal_minus_raw": cal_brier - raw_brier,
        "brier_delta_pct": pct_delta(cal_brier, raw_brier),
        "raw_logloss": raw_logloss,
        "cal_logloss": cal_logloss,
        "logloss_delta_pct": pct_delta(cal_logloss, raw_logloss),
        "raw_ece": ece(y, raw),
        "cal_ece": ece(y, cal),
    }


def build_situation_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    def add_groups(segment: str, group_cols: list[str], data: pd.DataFrame) -> None:
        if not group_cols:
            rows.append(summarize_slice(segment, "all", data))
            return
        for key, group in data.groupby(group_cols, dropna=False):
            if len(group) < 20:
                continue
            if not isinstance(key, tuple):
                key = (key,)
            situation = "|".join(f"{col}={value}" for col, value in zip(group_cols, key))
            rows.append(summarize_slice(segment, situation, group))

    add_groups("overall", [], df)
    add_groups("phase", ["phase"], df)
    add_groups("chase_bucket", ["chase_bucket"], df)
    add_groups("phase_x_chase_bucket", ["phase", "chase_bucket"], df)
    add_groups("target_band", ["target_band"], df)
    add_groups("phase_x_target_band", ["phase", "target_band"], df)

    high = df[df["is_high_chase"]].copy()
    add_groups("high_phase", ["phase"], high)
    add_groups("high_phase_over", ["phase", "over"], high)
    add_groups("high_rrr_band", ["phase", "rrr_band"], high)
    add_groups("high_score_vs_par_band", ["phase", "score_vs_par_band"], high)
    add_groups("high_wickets_remaining_band", ["phase", "wickets_remaining_band"], high)
    add_groups("high_resource_prob_band", ["phase", "resource_prob_band"], high)
    return pd.DataFrame(rows)


def build_calibration_curve(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    segment_frames = [
        ("overall", "all", df),
    ]
    for phase, group in df.groupby("phase", dropna=False):
        segment_frames.append(("phase", f"phase={phase}", group))
    for chase_bucket, group in df.groupby("chase_bucket", dropna=False):
        segment_frames.append(("chase_bucket", f"chase_bucket={chase_bucket}", group))
    for (phase, chase_bucket), group in df.groupby(["phase", "chase_bucket"], dropna=False):
        segment_frames.append(
            ("phase_x_chase_bucket", f"phase={phase}|chase_bucket={chase_bucket}", group)
        )

    for segment, situation, data in segment_frames:
        for model_label, pred_col in [("raw", "raw_pred"), ("calibrated", "cal_pred")]:
            bin_series = pd.cut(
                data[pred_col],
                bins=CAL_BINS,
                include_lowest=True,
                right=False,
            )
            for pred_bin, group in data.groupby(bin_series, observed=True):
                if len(group) < 10:
                    continue
                mean_pred = float(group[pred_col].mean())
                actual = float(group["y"].mean())
                rows.append(
                    {
                        "segment": segment,
                        "situation": situation,
                        "model": model_label,
                        "pred_bin": str(pred_bin),
                        "n": int(len(group)),
                        "matches": int(group["match_id"].nunique()),
                        "mean_pred": mean_pred,
                        "actual_wr": actual,
                        "bias": mean_pred - actual,
                        "abs_error": abs(mean_pred - actual),
                    }
                )
    return pd.DataFrame(rows)


def bootstrap_raw_cal_deltas(
    df: pd.DataFrame,
    segment_name: str,
    group_cols: list[str],
    min_matches: int = 10,
    samples: int = BOOTSTRAP_SAMPLES,
) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    rows: list[dict[str, object]] = []

    for key, group in df.groupby(group_cols, dropna=False):
        if not isinstance(key, tuple):
            key = (key,)
        matches = group["match_id"].dropna().unique()
        if len(matches) < min_matches:
            continue

        match_indices = {
            match_id: group.index[group["match_id"] == match_id].to_numpy()
            for match_id in matches
        }
        brier_deltas = []
        abs_error_deltas = []
        for _ in range(samples):
            sampled_matches = rng.choice(matches, size=len(matches), replace=True)
            sampled_idx = np.concatenate([match_indices[mid] for mid in sampled_matches])
            boot = df.loc[sampled_idx]
            y = boot["y"].values.astype(float)
            raw = boot["raw_pred"].values.astype(float)
            cal = boot["cal_pred"].values.astype(float)
            actual = float(y.mean())
            brier_deltas.append(float(brier_score_loss(y, cal) - brier_score_loss(y, raw)))
            abs_error_deltas.append(abs(float(cal.mean()) - actual) - abs(float(raw.mean()) - actual))

        situation = "|".join(f"{col}={value}" for col, value in zip(group_cols, key))
        rows.append(
            {
                "segment": segment_name,
                "situation": situation,
                "n": int(len(group)),
                "matches": int(len(matches)),
                "brier_delta_cal_minus_raw": float(np.mean(brier_deltas)),
                "brier_delta_ci_low": float(np.quantile(brier_deltas, 0.025)),
                "brier_delta_ci_high": float(np.quantile(brier_deltas, 0.975)),
                "abs_error_delta_cal_minus_raw": float(np.mean(abs_error_deltas)),
                "abs_error_delta_ci_low": float(np.quantile(abs_error_deltas, 0.025)),
                "abs_error_delta_ci_high": float(np.quantile(abs_error_deltas, 0.975)),
                "bootstrap_samples": samples,
            }
        )
    return pd.DataFrame(rows)


def smooth_gate(target_above_par: pd.Series, threshold: float, width: float) -> np.ndarray:
    z = (target_above_par.astype(float).to_numpy() - threshold) / width
    z = np.clip(z, -50, 50)
    return 1.0 / (1.0 + np.exp(-z))


def candidate_predictions(df: pd.DataFrame) -> dict[str, np.ndarray]:
    raw = df["raw_pred"].to_numpy(dtype=float)
    cal = df["cal_pred"].to_numpy(dtype=float)
    high = df["is_high_chase"].to_numpy(dtype=bool)
    mid_death = df["phase"].isin(["mid", "death"]).to_numpy()
    mid = (df["phase"] == "mid").to_numpy()
    death = (df["phase"] == "death").to_numpy()

    candidates = {
        "v14_calibrated": cal,
        "v14_raw_all": raw,
        "raw_for_high_all_phases": np.where(high, raw, cal),
        "raw_for_high_mid_death": np.where(high & mid_death, raw, cal),
        "raw_for_high_mid_only": np.where(high & mid, raw, cal),
        "raw_for_high_death_only": np.where(high & death, raw, cal),
    }
    for width in [5.0, 10.0, 15.0]:
        weight = smooth_gate(df["target_above_par"], HIGH_CHASE_THRESHOLD, width)
        weighted_raw = cal + weight * (raw - cal)
        candidates[f"smooth_raw_mid_death_w{int(width)}"] = np.where(mid_death, weighted_raw, cal)
    return candidates


def metric_row(
    candidate: str,
    segment: str,
    situation: str,
    df: pd.DataFrame,
    pred: np.ndarray,
    baseline_pred: np.ndarray,
) -> dict[str, object]:
    y = df["y"].to_numpy(dtype=float)
    pred = np.clip(np.asarray(pred, dtype=float), 1e-7, 1 - 1e-7)
    baseline_pred = np.clip(np.asarray(baseline_pred, dtype=float), 1e-7, 1 - 1e-7)
    brier = float(brier_score_loss(y, pred))
    baseline_brier = float(brier_score_loss(y, baseline_pred))
    ll = safe_log_loss(y, pred)
    baseline_ll = safe_log_loss(y, baseline_pred)
    mean_pred = float(pred.mean())
    actual = float(y.mean())
    return {
        "candidate": candidate,
        "segment": segment,
        "situation": situation,
        "n": int(len(df)),
        "matches": int(df["match_id"].nunique()),
        "brier": brier,
        "brier_delta_vs_v14": brier - baseline_brier,
        "brier_delta_pct_vs_v14": pct_delta(brier, baseline_brier),
        "logloss": ll,
        "logloss_delta_pct_vs_v14": pct_delta(ll, baseline_ll),
        "mean_pred": mean_pred,
        "actual_wr": actual,
        "bias": mean_pred - actual,
        "abs_error": abs(mean_pred - actual),
        "ece": ece(y, pred),
    }


def build_candidate_ablation(df: pd.DataFrame) -> pd.DataFrame:
    preds = candidate_predictions(df)
    baseline = preds["v14_calibrated"]
    rows: list[dict[str, object]] = []

    segment_frames: list[tuple[str, str, np.ndarray]] = [
        ("overall", "all", np.ones(len(df), dtype=bool)),
        ("high_chase", "all_high", df["is_high_chase"].to_numpy(dtype=bool)),
    ]
    for phase in ["pp", "mid", "death"]:
        phase_mask = (df["phase"] == phase).to_numpy()
        segment_frames.append(("phase", f"phase={phase}", phase_mask))
        segment_frames.append(
            (
                "high_phase",
                f"phase={phase}",
                phase_mask & df["is_high_chase"].to_numpy(dtype=bool),
            )
        )

    for candidate, pred in preds.items():
        for segment, situation, mask in segment_frames:
            if mask.sum() < 20:
                continue
            rows.append(
                metric_row(
                    candidate,
                    segment,
                    situation,
                    df.loc[mask],
                    pred[mask],
                    baseline[mask],
                )
            )
    return pd.DataFrame(rows)


def print_key_tables(summary: pd.DataFrame) -> None:
    cols = [
        "segment",
        "situation",
        "n",
        "matches",
        "actual_wr",
        "raw_mean",
        "cal_mean",
        "raw_brier",
        "cal_brier",
        "brier_delta_cal_minus_raw",
        "raw_ece",
        "cal_ece",
    ]
    print("\nOverall and phase calibration:")
    print(
        summary[summary["segment"].isin(["overall", "phase"])][cols]
        .to_string(index=False, float_format=lambda x: f"{x:.5f}")
    )

    print("\nPhase x chase bucket calibration:")
    print(
        summary[summary["segment"] == "phase_x_chase_bucket"][cols]
        .sort_values(["situation"])
        .to_string(index=False, float_format=lambda x: f"{x:.5f}")
    )

    print("\nHigh-chase phase calibration:")
    print(
        summary[summary["segment"] == "high_phase"][cols]
        .sort_values(["situation"])
        .to_string(index=False, float_format=lambda x: f"{x:.5f}")
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading IPL innings-2 data and v14 pitch features...")
    df = add_pitch_features(load_training_data())
    df["season"] = df["season"].astype(str)
    phase_features = build_v14_features()

    print("\nRunning OOS retrain (train<2025, test>=2025)...")
    predictions = add_situation_columns(run_v14_oos(df, phase_features))

    # ── Add production v7 model predictions ───────────────────────────────────
    print("\nScoring with production v7 model (37 features)...")
    test_df = df[df["season"] >= "2025"].copy()
    # Align to predictions dataframe order
    test_key = predictions[["match_id", "over", "ball"]].copy()
    test_df = test_df.reset_index(drop=True)
    v7_raw, v7_cal = score_v7_production(test_df.loc[
        test_df.set_index(["match_id","over","ball"]).index.isin(
            pd.MultiIndex.from_frame(test_key)
        )
    ] if False else test_df)  # score all test rows then merge

    # merge v7 predictions by match_id+over+ball
    test_df["v7_raw"] = v7_raw
    test_df["v7_cal"] = v7_cal
    pred_merge = predictions.merge(
        test_df[["match_id","over","ball","v7_raw","v7_cal"]],
        on=["match_id","over","ball"],
        how="left",
    )
    predictions["v7_raw"] = pred_merge["v7_raw"].values
    predictions["v7_cal"] = pred_merge["v7_cal"].values

    # ── Add production v14 model predictions (loaded from disk) ───────────────
    print("Scoring with production v14 models (loaded from disk)...")
    # Add phase column to test_df (needed by score_v14_production)
    def _phase_from_over(ov):
        for ph, r in PHASE_RANGES_V12.items():
            if r[0] <= ov <= r[1]:
                return ph
        return "mid"
    test_df["phase"] = test_df["over"].map(_phase_from_over)
    v14p_raw, v14p_cal = score_v14_production(test_df, phase_features)
    test_df["v14_prod_raw"] = v14p_raw
    test_df["v14_prod_cal"] = v14p_cal
    pred_merge2 = predictions.merge(
        test_df[["match_id","over","ball","v14_prod_raw","v14_prod_cal"]],
        on=["match_id","over","ball"],
        how="left",
    )
    predictions["v14_prod_raw"] = pred_merge2["v14_prod_raw"].values
    predictions["v14_prod_cal"] = pred_merge2["v14_prod_cal"].values

    # Print production model comparison summary
    y = predictions["y"].values
    v7r = predictions["v7_raw"].values
    v7c = predictions["v7_cal"].values
    v14pr = predictions["v14_prod_raw"].values
    v14pc = predictions["v14_prod_cal"].values
    oosraw = predictions["v14_oos_raw"].values
    ooscal = predictions["v14_oos_cal"].values
    print("\n=== Production Model Comparison (OOS 2025+) ===")
    from sklearn.metrics import brier_score_loss
    for lbl, p in [("v7 raw (prod)",v7r),("v7 cal (prod inn2-iso)",v7c),
                   ("v14 prod raw",v14pr),("v14 prod cal (current)",v14pc),
                   ("v14 oos-retrain raw",oosraw),("v14 oos-retrain cal",ooscal)]:
        valid = ~np.isnan(p)
        b = brier_score_loss(y[valid], p[valid])
        print(f"  {lbl:<30}: Brier={b:.5f}  n={valid.sum():,}")

    summary = build_situation_summary(predictions)
    curve = build_calibration_curve(predictions)
    candidate_ablation = build_candidate_ablation(predictions)
    bootstrap = pd.concat(
        [
            bootstrap_raw_cal_deltas(
                predictions,
                "phase_x_chase_bucket",
                ["phase", "chase_bucket"],
            ),
            bootstrap_raw_cal_deltas(
                predictions[predictions["is_high_chase"]],
                "high_phase",
                ["phase"],
            ),
        ],
        ignore_index=True,
    )

    predictions.to_csv(OUT_DIR / "v14_oos_predictions_by_ball.csv", index=False)
    summary.to_csv(OUT_DIR / "v14_oos_calibration_by_situation.csv", index=False)
    curve.to_csv(OUT_DIR / "v14_oos_calibration_curves.csv", index=False)
    candidate_ablation.to_csv(OUT_DIR / "v14_oos_candidate_rule_ablation.csv", index=False)
    bootstrap.to_csv(OUT_DIR / "v14_oos_match_bootstrap_raw_vs_cal.csv", index=False)

    print_key_tables(summary)
    print("\nCandidate rule ablation, overall:")
    print(
        candidate_ablation[candidate_ablation["segment"] == "overall"]
        .sort_values(["brier", "logloss"])
        .to_string(index=False, float_format=lambda x: f"{x:.5f}")
    )
    print("\nCandidate rule ablation, high chase by phase:")
    print(
        candidate_ablation[candidate_ablation["segment"] == "high_phase"]
        .sort_values(["situation", "brier"])
        .to_string(index=False, float_format=lambda x: f"{x:.5f}")
    )
    print("\nSaved artifacts:")
    print(f"  {OUT_DIR / 'v14_oos_predictions_by_ball.csv'}")
    print(f"  {OUT_DIR / 'v14_oos_calibration_by_situation.csv'}")
    print(f"  {OUT_DIR / 'v14_oos_calibration_curves.csv'}")
    print(f"  {OUT_DIR / 'v14_oos_candidate_rule_ablation.csv'}")
    print(f"  {OUT_DIR / 'v14_oos_match_bootstrap_raw_vs_cal.csv'}")


if __name__ == "__main__":
    main()
