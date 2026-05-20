from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss

from bbl_pipeline.training.blend_model import XGBLRBlend
from bbl_pipeline.training.calibration import PlattCalibrator

DATA_PATH = Path("data/ipl_inn2_features_v1/training.parquet")
V12_DIR = Path("models/ipl_v12")
V13_DIR = Path("models/ipl_v13")
V13_DIR.mkdir(parents=True, exist_ok=True)

PHASE_RANGES_V12 = {
    "pp": (1, 6),
    "mid": (7, 15),
    "death": (16, 20),
}
PHASE_RANGES_V13 = {
    "pp": (1, 6),
    "early_mid": (7, 11),
    "late_mid": (12, 15),
    "death": (16, 20),
}
CAL_METHODS_V12 = {"pp": "isotonic", "mid": "platt", "death": "isotonic"}
CAL_METHODS_V13 = {"pp": "isotonic", "early_mid": "platt", "late_mid": "platt", "death": "isotonic"}

EARLY_CANDIDATES = [
    "target_clarity_index",
    "early_mid_rrr_vs_venue_avg",
    "wicket_budget_remaining",
    "chase_on_track_score",
    "early_settle_flag",
]
LATE_CANDIDATES = [
    "late_mid_urgency",
    "late_mid_run_gap",
    "momentum_shift_flag",
    "acceleration_zone",
    "late_wkt_collapse_risk",
    "finish_quality_zone",
]
CANDIDATE_GROUPS = {
    **{feature: "early_mid" for feature in EARLY_CANDIDATES},
    **{feature: "late_mid" for feature in LATE_CANDIDATES},
}
CANDIDATE_FEATURES = EARLY_CANDIDATES + LATE_CANDIDATES


def ordered_unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            out.append(item)
            seen.add(item)
    return out


def load_v12_features() -> dict[str, list[str]]:
    with open(V12_DIR / "phase_features.json", encoding="utf-8") as f:
        return json.load(f)


def add_pp_easy_chase_features(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    rrr = d.get("required_run_rate", pd.Series(0.1, index=d.index)).fillna(0.1).clip(lower=0.1)
    tap = d.get("target_above_par", pd.Series(0.0, index=d.index)).fillna(0.0)
    vcs = d.get("venue_chase_success", pd.Series(0.5, index=d.index)).fillna(0.5)
    res = d.get("resources_remaining", pd.Series(0.0, index=d.index)).fillna(0.0)
    d["pp_ease_score"] = (-tap) / rrr
    d["pp_rrr_ease"] = 10.0 - rrr
    d["chase_ease_x_venue"] = (-tap.clip(upper=0)) * vcs
    d["low_target_strong_venue"] = (tap < -15).astype(float) * vcs
    d["pp_resources_adj_ease"] = (-tap) * res
    return d


def add_mid_split_features(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    overs_remaining = d.get("overs_remaining", pd.Series(0.0, index=d.index)).fillna(0.0)
    wickets_lost = d.get("wickets_lost", pd.Series(0.0, index=d.index)).fillna(0.0)
    wickets_remaining = d.get("wickets_remaining", 10 - wickets_lost).fillna(10 - wickets_lost)
    required_run_rate = d.get("required_run_rate", pd.Series(0.0, index=d.index)).fillna(0.0)
    target_above_par = d.get("target_above_par", pd.Series(0.0, index=d.index)).fillna(0.0)
    score_vs_par = d.get("score_vs_par", pd.Series(0.0, index=d.index)).fillna(0.0)
    resources_remaining = d.get("resources_remaining", pd.Series(0.0, index=d.index)).fillna(0.0)
    runs_last_12 = d.get("runs_last_12", pd.Series(0.0, index=d.index)).fillna(0.0)
    momentum_score = d.get("momentum_score", pd.Series(0.0, index=d.index)).fillna(0.0)
    scoring_rate_gap = d.get("scoring_rate_gap", pd.Series(0.0, index=d.index)).fillna(0.0)
    crr_vs_rrr_ratio = d.get("crr_vs_rrr_ratio", pd.Series(1.0, index=d.index)).fillna(1.0)
    wickets_last_6 = d.get("wickets_last_6", pd.Series(0.0, index=d.index)).fillna(0.0)
    projected_score = d.get("projected_score", pd.Series(160.0, index=d.index)).fillna(160.0)
    projected_vs_venue_avg = d.get("projected_vs_venue_avg", pd.Series(0.0, index=d.index)).fillna(0.0)
    venue_avg_score = (projected_score - projected_vs_venue_avg).replace(0, np.nan).fillna(projected_score.clip(lower=120.0))

    d["target_clarity_index"] = target_above_par / (overs_remaining + 1.0)
    d["early_mid_rrr_vs_venue_avg"] = (required_run_rate / venue_avg_score.replace(0, np.nan) * 20.0).fillna(0.0)
    d["wicket_budget_remaining"] = wickets_remaining - (overs_remaining * 0.4)
    d["chase_on_track_score"] = score_vs_par * (resources_remaining + 0.01)
    d["early_settle_flag"] = ((wickets_lost <= 2) & (score_vs_par >= 0)).astype(float)

    d["late_mid_urgency"] = required_run_rate * (1.0 + wickets_lost / 10.0)
    d["late_mid_run_gap"] = runs_last_12 - (required_run_rate * 2.0)
    d["momentum_shift_flag"] = ((momentum_score > 0.5) & (scoring_rate_gap < 0)).astype(float)
    d["acceleration_zone"] = ((overs_remaining <= 4) & (crr_vs_rrr_ratio >= 0.9)).astype(float)
    d["late_wkt_collapse_risk"] = ((wickets_last_6 >= 2) & (required_run_rate > 9)).astype(float)
    d["finish_quality_zone"] = wickets_remaining * (1.0 / (required_run_rate + 0.1))
    return d


def load_training_data() -> pd.DataFrame:
    df = pd.read_parquet(DATA_PATH)
    df = df.sort_values(["match_id", "innings", "over", "ball"]).reset_index(drop=True)
    df = df[df["innings"] == 2].copy()
    df["season"] = df["season"].astype(str)
    df = add_pp_easy_chase_features(df)
    return add_mid_split_features(df)


def phase_slice(df: pd.DataFrame, over_range: tuple[int, int]) -> pd.DataFrame:
    lo, hi = over_range
    return df[(df["over"] >= lo) & (df["over"] <= hi)].copy().reset_index(drop=True)


def safe_X(df_s: pd.DataFrame, feats: list[str]) -> tuple[np.ndarray, list[str]]:
    avail = [f for f in feats if f in df_s.columns]
    if not avail:
        raise ValueError("No requested features are available")
    med = df_s[avail].median(numeric_only=True)
    return df_s[avail].fillna(med).values, avail


def corr_with_target(series: pd.Series, y: pd.Series) -> float:
    if series.nunique(dropna=False) <= 1 or y.nunique(dropna=False) <= 1:
        return 0.0
    value = float(series.corr(y))
    return 0.0 if np.isnan(value) else value


def fit_blend(df_s: pd.DataFrame, feats: list[str], xgb_params: dict[str, Any] | None = None) -> tuple[XGBLRBlend, list[str]]:
    X, avail = safe_X(df_s, feats)
    y = df_s["is_winner"].values
    model = XGBLRBlend(xgb_params=xgb_params)
    model.fit(X, y)
    return model, avail


def xgb_gain_table(df_s: pd.DataFrame, feats: list[str], xgb_params: dict[str, Any] | None = None) -> pd.DataFrame:
    model, avail = fit_blend(df_s, feats, xgb_params=xgb_params)
    booster = model.xgb.get_booster()
    gains = booster.get_score(importance_type="gain")
    rows = []
    for idx, feature in enumerate(avail):
        rows.append({"feature": feature, "gain": float(gains.get(f"f{idx}", 0.0))})
    return pd.DataFrame(rows).sort_values(["gain", "feature"], ascending=[False, True]).reset_index(drop=True)


def build_feature_drift_table(
    early_df: pd.DataFrame,
    late_df: pd.DataFrame,
    feats: list[str],
    xgb_params: dict[str, Any] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    early_imp = xgb_gain_table(early_df, feats, xgb_params=xgb_params).rename(columns={"gain": "gain_early"})
    late_imp = xgb_gain_table(late_df, feats, xgb_params=xgb_params).rename(columns={"gain": "gain_late"})
    merged = pd.DataFrame({"feature": feats})
    merged = merged.merge(early_imp, on="feature", how="left").merge(late_imp, on="feature", how="left")
    merged[["gain_early", "gain_late"]] = merged[["gain_early", "gain_late"]].fillna(0.0)
    merged["rank_early"] = merged["gain_early"].rank(method="min", ascending=False).astype(int)
    merged["rank_late"] = merged["gain_late"].rank(method="min", ascending=False).astype(int)

    rows = []
    early_y = early_df["is_winner"]
    late_y = late_df["is_winner"]
    for feature in feats:
        es = early_df[feature] if feature in early_df.columns else pd.Series(0.0, index=early_df.index)
        ls = late_df[feature] if feature in late_df.columns else pd.Series(0.0, index=late_df.index)
        rows.append(
            {
                "feature": feature,
                "mean_early": float(es.mean()),
                "std_early": float(es.std(ddof=0)),
                "corr_early": corr_with_target(es, early_y),
                "mean_late": float(ls.mean()),
                "std_late": float(ls.std(ddof=0)),
                "corr_late": corr_with_target(ls, late_y),
            }
        )
    stats = pd.DataFrame(rows)
    stats["abs_corr_early"] = stats["corr_early"].abs()
    stats["abs_corr_late"] = stats["corr_late"].abs()
    stats["abs_diff"] = (stats["corr_early"] - stats["corr_late"]).abs()
    full = merged.merge(stats, on="feature", how="left")
    full["gain_max"] = full[["gain_early", "gain_late"]].max(axis=1)
    full["gain_sum"] = full["gain_early"] + full["gain_late"]
    full = full.sort_values(["gain_max", "gain_sum", "abs_diff", "feature"], ascending=[False, False, False, True]).reset_index(drop=True)
    return early_imp, late_imp, full


def candidate_feature_summary(early_df: pd.DataFrame, late_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    early_y = early_df["is_winner"]
    late_y = late_df["is_winner"]
    for feature in CANDIDATE_FEATURES:
        corr_early = corr_with_target(early_df[feature], early_y)
        corr_late = corr_with_target(late_df[feature], late_y)
        abs_corr_early = abs(corr_early)
        abs_corr_late = abs(corr_late)
        abs_diff = abs(corr_early - corr_late)
        strongest = max(abs_corr_early, abs_corr_late)
        if strongest < 0.01:
            verdict = "neither"
        elif abs_diff > 0.02 and abs_corr_early > abs_corr_late:
            verdict = "early_only"
        elif abs_diff > 0.02 and abs_corr_late > abs_corr_early:
            verdict = "late_only"
        else:
            verdict = "both"
        rows.append(
            {
                "feature": feature,
                "candidate_group": CANDIDATE_GROUPS[feature],
                "corr_early": corr_early,
                "corr_late": corr_late,
                "abs_corr_early": abs_corr_early,
                "abs_corr_late": abs_corr_late,
                "abs_diff": abs_diff,
                "verdict": verdict,
            }
        )
    summary = pd.DataFrame(rows)
    summary["priority_early"] = summary["verdict"].map({"early_only": 2, "both": 1}).fillna(0).astype(int)
    summary["priority_late"] = summary["verdict"].map({"late_only": 2, "both": 1}).fillna(0).astype(int)
    return summary.sort_values(["abs_diff", "feature"], ascending=[False, True]).reset_index(drop=True)


def pick_candidate_additions(candidate_df: pd.DataFrame, phase: str, limit: int = 5) -> list[str]:
    priority_col = "priority_early" if phase == "early_mid" else "priority_late"
    corr_col = "abs_corr_early" if phase == "early_mid" else "abs_corr_late"
    chosen = candidate_df[
        (candidate_df["candidate_group"] == phase) & (candidate_df[priority_col] > 0)
    ].sort_values(
        [priority_col, corr_col, "abs_diff", "feature"],
        ascending=[False, False, False, True],
    )
    return chosen["feature"].head(limit).tolist()


def recommend_feature_removals(feature_df: pd.DataFrame) -> dict[str, list[str]]:
    early_drop = feature_df[
        (feature_df["abs_diff"] > 0.02)
        & (feature_df["abs_corr_early"] < feature_df["abs_corr_late"])
        & (feature_df["gain_early"] < feature_df["gain_late"])
        & (feature_df["rank_early"] > 25)
    ].sort_values(["abs_diff", "rank_early"], ascending=[False, False])

    late_drop = feature_df[
        (feature_df["abs_diff"] > 0.02)
        & (feature_df["abs_corr_late"] < feature_df["abs_corr_early"])
        & (feature_df["gain_late"] < feature_df["gain_early"])
        & (feature_df["rank_late"] > 25)
    ].sort_values(["abs_diff", "rank_late"], ascending=[False, False])

    return {
        "early_mid": early_drop["feature"].tolist(),
        "late_mid": late_drop["feature"].tolist(),
    }


def season_folds(seasons: list[str], n_folds: int = 5) -> list[list[str]]:
    seasons = sorted([str(s) for s in seasons])
    if not seasons:
        return []
    fold_size = max(1, len(seasons) // n_folds)
    folds: list[list[str]] = []
    for fold in range(n_folds):
        start = fold * fold_size
        stop = (fold + 1) * fold_size if fold < n_folds - 1 else len(seasons)
        val = seasons[start:stop]
        if val:
            folds.append(val)
    return folds


def oof_phase_predictions(
    phase_df: pd.DataFrame,
    feats: list[str],
    n_folds: int = 5,
    xgb_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    phase_df = phase_df.reset_index(drop=True)
    raw = np.zeros(len(phase_df), dtype=float)
    y = phase_df["is_winner"].values.astype(float)
    overs = phase_df["over"].values.astype(int)
    seasons = sorted(phase_df["season"].astype(str).unique().tolist())
    folds = season_folds(seasons, n_folds=n_folds)
    for fold_idx, val_seasons in enumerate(folds):
        tr_mask = ~phase_df["season"].isin(val_seasons)
        va_mask = phase_df["season"].isin(val_seasons)
        if tr_mask.sum() == 0 or va_mask.sum() == 0:
            continue
        X_tr, avail = safe_X(phase_df[tr_mask], feats)
        X_va, _ = safe_X(phase_df[va_mask], feats)
        y_tr = phase_df.loc[tr_mask, "is_winner"].values
        model = XGBLRBlend(xgb_params=xgb_params)
        model.fit(X_tr, y_tr)
        raw[va_mask.values] = model.predict_proba(X_va)[:, 1]
    return {
        "raw": raw,
        "y": y,
        "over": overs,
        "brier": float(brier_score_loss(y, raw)),
        "n": len(phase_df),
    }


def prediction_distribution_summary(preds: np.ndarray, y: np.ndarray) -> dict[str, float]:
    neutral = ((preds >= 0.45) & (preds <= 0.55)).mean() * 100.0
    extreme = (((preds >= 0.70) & (preds <= 1.00)) | ((preds >= 0.00) & (preds <= 0.30))).mean() * 100.0
    return {
        "mean_pred": float(np.mean(preds)),
        "std_pred": float(np.std(preds)),
        "pct_45_55": float(neutral),
        "pct_extreme": float(extreme),
        "brier": float(brier_score_loss(y, preds)),
    }


def build_prediction_comparison(mid_df: pd.DataFrame, early_df: pd.DataFrame, late_df: pd.DataFrame, feats: list[str]) -> pd.DataFrame:
    shared = oof_phase_predictions(mid_df, feats)
    early_sep = oof_phase_predictions(early_df, feats)
    late_sep = oof_phase_predictions(late_df, feats)

    rows = []
    early_mask = (mid_df["over"] >= 7) & (mid_df["over"] <= 11)
    late_mask = (mid_df["over"] >= 12) & (mid_df["over"] <= 15)
    for phase, label, preds, y in [
        ("early_mid", "shared_mid", shared["raw"][early_mask.values], shared["y"][early_mask.values]),
        ("early_mid", "separate", early_sep["raw"], early_sep["y"]),
        ("late_mid", "shared_mid", shared["raw"][late_mask.values], shared["y"][late_mask.values]),
        ("late_mid", "separate", late_sep["raw"], late_sep["y"]),
    ]:
        stats = prediction_distribution_summary(preds, y)
        stats.update({"phase": phase, "model_scope": label, "n": int(len(y))})
        rows.append(stats)
    return pd.DataFrame(rows)


def build_mid_split_analysis(df: pd.DataFrame, mid_features: list[str]) -> dict[str, Any]:
    early_df = phase_slice(df, (7, 11))
    late_df = phase_slice(df, (12, 15))
    mid_df = phase_slice(df, (7, 15))

    quick_params = {"n_estimators": 250, "max_depth": 4, "learning_rate": 0.03}
    early_imp, late_imp, feature_df = build_feature_drift_table(early_df, late_df, mid_features, xgb_params=quick_params)
    top20_early = early_imp.head(20)["feature"].tolist()
    top20_late = late_imp.head(20)["feature"].tolist()
    only_early = [f for f in top20_early if f not in top20_late]
    only_late = [f for f in top20_late if f not in top20_early]
    shared = [f for f in top20_early if f in top20_late]

    top30 = feature_df.head(30).copy()
    candidate_df = candidate_feature_summary(early_df, late_df)
    additions = {
        "early_mid": pick_candidate_additions(candidate_df, "early_mid"),
        "late_mid": pick_candidate_additions(candidate_df, "late_mid"),
    }
    removals = recommend_feature_removals(feature_df)
    pred_df = build_prediction_comparison(mid_df, early_df, late_df, mid_features)

    return {
        "early_df": early_df,
        "late_df": late_df,
        "mid_df": mid_df,
        "importance_early": early_imp,
        "importance_late": late_imp,
        "feature_drift": feature_df,
        "top30_stats": top30,
        "only_early": only_early,
        "only_late": only_late,
        "shared_top20": shared,
        "candidate_summary": candidate_df,
        "recommended_additions": additions,
        "recommended_removals": removals,
        "prediction_comparison": pred_df,
    }


def make_calibrator(method: str):
    if method == "platt":
        return PlattCalibrator(C=1.0)
    return IsotonicRegression(out_of_bounds="clip")


def fit_calibrator_bundle(raw: np.ndarray, y: np.ndarray, overs: np.ndarray, method: str) -> dict[str, Any]:
    phase_iso = make_calibrator(method)
    phase_iso.fit(raw, y)
    per_over: dict[int, Any] = {}
    for ov in sorted(np.unique(overs)):
        mask = overs == ov
        if mask.sum() >= 40:
            cal = make_calibrator(method)
            cal.fit(raw[mask], y[mask])
            per_over[int(ov)] = cal
    return {"per_over": per_over, "phase_iso": phase_iso}


def apply_calibrator_bundle(raw: np.ndarray, overs: np.ndarray, bundle: dict[str, Any]) -> np.ndarray:
    out = np.empty_like(raw)
    phase_iso = bundle.get("phase_iso")
    per_over = bundle.get("per_over", {})
    for ov in np.unique(overs):
        mask = overs == ov
        cal = per_over.get(int(ov), phase_iso)
        if cal is None:
            out[mask] = raw[mask]
        else:
            out[mask] = cal.transform(raw[mask])
    return out


def train_champion_models(df: pd.DataFrame, phase_ranges: dict[str, tuple[int, int]], phase_features: dict[str, list[str]]) -> dict[str, tuple[XGBLRBlend, list[str]]]:
    models: dict[str, tuple[XGBLRBlend, list[str]]] = {}
    for phase, over_range in phase_ranges.items():
        pf = phase_slice(df, over_range)
        X, avail = safe_X(pf, phase_features[phase])
        y = pf["is_winner"].values
        model = XGBLRBlend()
        model.fit(X, y)
        models[phase] = (model, avail)
    return models


def evaluate_oos(
    df: pd.DataFrame,
    phase_ranges: dict[str, tuple[int, int]],
    phase_features: dict[str, list[str]],
    cal_methods: dict[str, str],
) -> dict[str, Any]:
    train_seasons = {s for s in sorted(df["season"].unique()) if s < "2025"}
    test_seasons = {s for s in sorted(df["season"].unique()) if s >= "2025"}
    phase_outputs: dict[str, Any] = {}
    all_raw: list[float] = []
    all_cal: list[float] = []
    all_y: list[float] = []

    for phase, over_range in phase_ranges.items():
        pf = phase_slice(df, over_range)
        pf_tr = pf[pf["season"].isin(train_seasons)].copy().reset_index(drop=True)
        pf_te = pf[pf["season"].isin(test_seasons)].copy().reset_index(drop=True)
        if pf_te.empty:
            continue

        train_oof = oof_phase_predictions(pf_tr, phase_features[phase])
        bundle = fit_calibrator_bundle(train_oof["raw"], train_oof["y"], train_oof["over"], cal_methods[phase])

        X_tr, avail = safe_X(pf_tr, phase_features[phase])
        X_te, _ = safe_X(pf_te, phase_features[phase])
        y_tr = pf_tr["is_winner"].values
        y_te = pf_te["is_winner"].values
        over_te = pf_te["over"].values.astype(int)

        model = XGBLRBlend()
        model.fit(X_tr, y_tr)
        raw_te = model.predict_proba(X_te)[:, 1]
        cal_te = apply_calibrator_bundle(raw_te, over_te, bundle)

        phase_outputs[phase] = {
            "raw": raw_te,
            "cal": cal_te,
            "y": y_te,
            "over": over_te,
            "n": int(len(y_te)),
            "brier_raw": float(brier_score_loss(y_te, raw_te)),
            "brier_cal": float(brier_score_loss(y_te, cal_te)),
            "calibrators": bundle,
            "features": avail,
        }
        all_raw.extend(raw_te.tolist())
        all_cal.extend(cal_te.tolist())
        all_y.extend(y_te.tolist())

    all_raw_arr = np.array(all_raw)
    all_cal_arr = np.array(all_cal)
    all_y_arr = np.array(all_y)
    return {
        "train_seasons": sorted(train_seasons),
        "test_seasons": sorted(test_seasons),
        "phases": phase_outputs,
        "overall_raw": float(brier_score_loss(all_y_arr, all_raw_arr)),
        "overall_cal": float(brier_score_loss(all_y_arr, all_cal_arr)),
    }


def summarize_segment(eval_result: dict[str, Any], phase: str, over_range: tuple[int, int] | None = None) -> dict[str, float]:
    phase_result = eval_result["phases"][phase]
    raw = phase_result["raw"]
    cal = phase_result["cal"]
    y = phase_result["y"]
    overs = phase_result["over"]
    if over_range is not None:
        lo, hi = over_range
        mask = (overs >= lo) & (overs <= hi)
        raw = raw[mask]
        cal = cal[mask]
        y = y[mask]
    return {
        "n": int(len(y)),
        "brier_raw": float(brier_score_loss(y, raw)),
        "brier_cal": float(brier_score_loss(y, cal)),
    }


def weighted_mid_summary(parts: list[dict[str, float]]) -> dict[str, float]:
    total_n = sum(part["n"] for part in parts)
    if total_n == 0:
        return {"n": 0, "brier_raw": float("nan"), "brier_cal": float("nan")}
    raw = sum(part["brier_raw"] * part["n"] for part in parts) / total_n
    cal = sum(part["brier_cal"] * part["n"] for part in parts) / total_n
    return {"n": int(total_n), "brier_raw": float(raw), "brier_cal": float(cal)}
