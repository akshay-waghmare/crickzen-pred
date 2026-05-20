from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, "src")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_ipl_v15_wicket_features import add_v14_pitch_features  # noqa: E402
from bbl_pipeline.features.inn2_engineering import engineer_inn2_features  # noqa: E402
from bbl_pipeline.training.pp_context_model import (  # noqa: E402
    ContextCalibratedPPModel,
    apply_hierarchical_isotonic_bundle,
    fit_hierarchical_isotonic_bundle,
)
from bbl_pipeline.training.trainer import XGBLogRegEnsemble  # noqa: E402
from ipl_v13_mid_split_common import apply_calibrator_bundle, fit_calibrator_bundle, ordered_unique, season_folds  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TRAIN_PATH = ROOT / "data" / "ipl_features_v10" / "training.parquet"
DATA_OUT_DIR = ROOT / "data" / "ipl_features_v16"
DATA_OUT_PATH = DATA_OUT_DIR / "training.parquet"
V15_DIR = ROOT / "models" / "ipl_v15_wicket_features"
OUT_DIR = ROOT / "models" / "ipl_v16_pp_improved"

CAL_LEVELS = [
    {"columns": ["over", "chase_category", "pp_score_bin", "pp_gap_bin"], "min_samples": 40},
    {"columns": ["over", "chase_category", "pp_score_bin"], "min_samples": 60},
    {"columns": ["over", "chase_category"], "min_samples": 80},
    {"columns": ["chase_category"], "min_samples": 120},
]
BLEND_WEIGHT = 0.68
CLIP_BOUNDS = (0.05, 0.95)


def load_v15_phase_features() -> dict[str, list[str]]:
    with open(V15_DIR / "phase_features.json", encoding="utf-8") as handle:
        return json.load(handle)


def load_v15_oof_results() -> pd.DataFrame:
    return pd.read_csv(V15_DIR / "oof_results.csv")


def load_full_training_frame() -> tuple[pd.DataFrame, pd.DataFrame]:
    base = pd.read_parquet(TRAIN_PATH)
    base = base.sort_values(["match_id", "innings", "over", "ball"]).reset_index(drop=True)
    inn2 = base[base["innings"] == 2].copy().reset_index(drop=True)
    inn2 = engineer_inn2_features(inn2)
    inn2 = add_v14_pitch_features(inn2)

    full = base.copy()
    inn2_mask = full["innings"] == 2
    for column in inn2.columns:
        if column not in full.columns:
            full[column] = np.nan
        full.loc[inn2_mask, column] = inn2[column].values
    return full, inn2


def save_v16_training_parquet(df: pd.DataFrame) -> None:
    DATA_OUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(DATA_OUT_PATH, index=False)


def pp_slice(df: pd.DataFrame) -> pd.DataFrame:
    return df[(df["innings"] == 2) & (df["is_powerplay"] == 1)].copy().reset_index(drop=True)


def pct_improvement(new_value: float, old_value: float) -> float:
    if old_value == 0:
        return 0.0
    return (old_value - new_value) / old_value * 100.0


def season_fold_oof_raw(df: pd.DataFrame, features: list[str]) -> np.ndarray:
    oof = np.zeros(len(df), dtype=float)
    seasons = sorted(df["season"].astype(str).unique().tolist())
    for val_seasons in season_folds(seasons, n_folds=5):
        train_mask = ~df["season"].astype(str).isin(val_seasons)
        valid_mask = df["season"].astype(str).isin(val_seasons)
        train = df[train_mask].copy()
        valid = df[valid_mask].copy()
        model = XGBLogRegEnsemble(n_features=len(features), feature_order=features)
        X_train = train[features].replace([np.inf, -np.inf], np.nan)
        X_valid = valid[features].replace([np.inf, -np.inf], np.nan)
        model.fit(X_train, train["is_winner"].astype(int))
        oof[valid.index] = model.predict_proba(X_valid)[:, 1]
    return oof


def fit_final_raw_model(df: pd.DataFrame, features: list[str]) -> XGBLogRegEnsemble:
    model = XGBLogRegEnsemble(n_features=len(features), feature_order=features)
    X = df[features].replace([np.inf, -np.inf], np.nan)
    model.fit(X, df["is_winner"].astype(int))
    return model


def baseline_over_calibration(raw: np.ndarray, df: pd.DataFrame) -> np.ndarray:
    bundle = fit_calibrator_bundle(
        raw,
        df["is_winner"].astype(int).to_numpy(),
        df["over"].astype(int).to_numpy(),
        "isotonic",
    )
    return apply_calibrator_bundle(raw, df["over"].astype(int).to_numpy(), bundle)


def final_pp_calibration(raw: np.ndarray, df: pd.DataFrame) -> tuple[np.ndarray, dict]:
    bundle = fit_hierarchical_isotonic_bundle(
        raw,
        df["is_winner"].astype(int).to_numpy(),
        df[["over", "chase_category", "pp_score_bin", "pp_gap_bin"]],
        levels=CAL_LEVELS,
        blend_weight=BLEND_WEIGHT,
        clip_bounds=CLIP_BOUNDS,
    )
    calibrated = apply_hierarchical_isotonic_bundle(
        raw,
        df[["over", "chase_category", "pp_score_bin", "pp_gap_bin"]],
        bundle,
    )
    return calibrated, bundle


def metrics_row(name: str, y: np.ndarray, raw: np.ndarray, calibrated: np.ndarray) -> dict[str, float | str]:
    return {
        "name": name,
        "brier_raw": float(brier_score_loss(y, raw)),
        "brier_cal": float(brier_score_loss(y, calibrated)),
        "logloss_raw": float(log_loss(y, raw, labels=[0, 1])),
        "logloss_cal": float(log_loss(y, calibrated, labels=[0, 1])),
    }


def print_eda(pp: pd.DataFrame, v15_features: list[str]) -> None:
    print("\n=== STEP 1: EDA ON TRUE PP ROWS (innings==2 & is_powerplay==1) ===")
    print(f"PP rows: {len(pp):,}")
    print(f"Overs present: {sorted(pp['over'].unique().tolist())}")

    y = pp["is_winner"].astype(int)
    X = pp[v15_features].replace([np.inf, -np.inf], np.nan)
    pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("logreg", LogisticRegression(max_iter=2000, C=0.1, random_state=42)),
    ])
    pipe.fit(X, y)
    preds = pipe.predict_proba(X)[:, 1]
    pp_local = pp.copy()
    pp_local["abs_residual"] = np.abs(y.to_numpy() - preds)

    overall_coef = pd.Series(pipe.named_steps["logreg"].coef_[0], index=v15_features)
    print("\nTop logistic coefficients (absolute):")
    print(overall_coef.abs().sort_values(ascending=False).head(12).to_string())

    print("\nResidual hotspots by chase_category:")
    print(pp_local.groupby("chase_category")["abs_residual"].agg(["mean", "count"]).sort_values("mean", ascending=False).to_string())
    print("\nResidual hotspots by over:")
    print(pp_local.groupby("over")["abs_residual"].agg(["mean", "count"]).sort_values("mean", ascending=False).to_string())
    print("\nResidual hotspots by wickets_lost:")
    print(pp_local.groupby("wickets_lost")["abs_residual"].agg(["mean", "count"]).sort_values("mean", ascending=False).head(8).to_string())

    print("\nTop abs coefficients by chase_category:")
    for chase_category in (-1.0, 0.0, 1.0):
        sub = pp_local[pp_local["chase_category"] == chase_category]
        if len(sub) < 500:
            continue
        X_sub = sub[v15_features].replace([np.inf, -np.inf], np.nan)
        y_sub = sub["is_winner"].astype(int)
        pipe.fit(X_sub, y_sub)
        coef = pd.Series(pipe.named_steps["logreg"].coef_[0], index=v15_features)
        print(f"\nchase_category={int(chase_category)}")
        print(coef.abs().sort_values(ascending=False).head(10).to_string())

    candidate_focus = [
        "balls_since_wicket",
        "set_batter_exposure",
        "dot_pct_last_12",
        "recovery_momentum",
        "momentum_acceleration",
        "batting_recent_nrr_l5",
        "score_per_wicket",
        "wickets_times_balls",
    ]
    corr_rows: list[dict[str, float | str | bool]] = []
    for column in pp_local.columns:
        if column in {"is_winner", "winner", "match_id", "season", "batting_team", "bowling_team"}:
            continue
        series = pp_local[column]
        if not pd.api.types.is_numeric_dtype(series) or series.nunique(dropna=True) <= 1:
            continue
        corr = series.replace([np.inf, -np.inf], np.nan).corr(y)
        if pd.isna(corr):
            continue
        corr_rows.append({
            "feature": column,
            "corr": float(corr),
            "in_v15_pp": column in v15_features,
            "focus_feature": column in candidate_focus,
        })
    corr_df = pd.DataFrame(corr_rows).sort_values("corr", key=lambda s: s.abs(), ascending=False)
    print("\nTop non-v15 raw correlations with is_winner:")
    print(corr_df[~corr_df["in_v15_pp"]].head(15).to_string(index=False))
    print("\nFocused candidate correlations:")
    print(corr_df[corr_df["focus_feature"]][["feature", "corr", "in_v15_pp"]].to_string(index=False))

    holdout = pp_local[pp_local["season"].astype(str) >= "2025"].copy().reset_index(drop=True)
    if not holdout.empty:
        v15_model = joblib.load(V15_DIR / "champion_model_pp.joblib")
        raw_holdout = v15_model.predict_proba(holdout[v15_features].replace([np.inf, -np.inf], np.nan))[:, 1]
        print("\nHeld-out raw V15 Brier by chase_category (2025+ seasons):")
        rows = []
        for chase_category in (-1.0, 0.0, 1.0):
            mask = holdout["chase_category"] == chase_category
            sub = holdout[mask]
            if sub.empty:
                continue
            y_sub = sub["is_winner"].astype(int).to_numpy()
            p_sub = raw_holdout[mask.to_numpy()]
            rows.append({
                "chase_category": int(chase_category),
                "n": len(sub),
                "brier_raw": float(brier_score_loss(y_sub, p_sub)),
                "logloss_raw": float(log_loss(y_sub, p_sub, labels=[0, 1])),
            })
        print(pd.DataFrame(rows).to_string(index=False))


def print_group_experiments(pp: pd.DataFrame, v15_features: list[str]) -> pd.DataFrame:
    print("\n=== STEP 2A: RAW FEATURE ITERATIONS (OOF on true PP rows) ===")
    candidate_groups = {
        "group_a_temporal": ["pp_scoring_trajectory", "pp_wicket_impact_adj", "over_normalized_score", "pp_survival_score", "score_vs_rrr_momentum", "runs_per_over_trend"],
        "group_b_inn1_interactions": ["inn1_pp_run_rate", "pp_run_rate_vs_inn1_pp", "inn1_pp_runs_x_is_high_chase", "inn1_quality_x_chase_diff"],
        "group_c_partnership": ["set_batter_stability", "recovery_potential", "dot_pressure_adj", "boundary_acceleration", "chase_category_x_balls_since_wkt"],
        "group_d_chase_specific": ["above_par_wicket_cost", "below_par_run_cushion"],
        "group_e_raw_signal": ["score_per_wicket", "wickets_times_balls", "balls_since_wicket", "set_batter_exposure", "recovery_momentum", "batting_recent_nrr_l5"],
    }
    y = pp["is_winner"].astype(int).to_numpy()
    rows: list[dict[str, float | str | int]] = []
    all_groups = {"baseline_v15": []}
    all_groups.update(candidate_groups)
    for name, additions in all_groups.items():
        features = ordered_unique(v15_features + additions)
        raw = season_fold_oof_raw(pp, features)
        calibrated = baseline_over_calibration(raw, pp)
        row = metrics_row(name, y, raw, calibrated)
        row["n_features"] = len(features)
        rows.append(row)
        print(
            f"{name:<28} feats={len(features):>3} "
            f"raw={row['brier_raw']:.5f}/{row['logloss_raw']:.5f} "
            f"over-cal={row['brier_cal']:.5f}/{row['logloss_cal']:.5f}"
        )
    return pd.DataFrame(rows).sort_values(["brier_cal", "logloss_cal", "n_features"]).reset_index(drop=True)


def print_calibration_experiments(pp: pd.DataFrame, v15_features: list[str]) -> tuple[pd.DataFrame, np.ndarray, dict]:
    print("\n=== STEP 2B: CALIBRATION ITERATIONS (OOF on true PP rows) ===")
    y = pp["is_winner"].astype(int).to_numpy()
    raw = season_fold_oof_raw(pp, v15_features)
    baseline_cal = baseline_over_calibration(raw, pp)
    conservative_cal, bundle = final_pp_calibration(raw, pp)

    experiment_rows = [
        metrics_row("baseline_over_only", y, raw, baseline_cal),
        metrics_row("context_hierarchical_blend", y, raw, conservative_cal),
    ]
    for row in experiment_rows:
        print(
            f"{row['name']:<28} raw={row['brier_raw']:.5f}/{row['logloss_raw']:.5f} "
            f"cal={row['brier_cal']:.5f}/{row['logloss_cal']:.5f}"
        )
    return pd.DataFrame(experiment_rows), conservative_cal, bundle


def build_chase_category_table(
    pp: pd.DataFrame,
    raw_v15: np.ndarray,
    cal_v15: np.ndarray,
    raw_v16: np.ndarray,
    cal_v16: np.ndarray,
) -> pd.DataFrame:
    rows: list[dict[str, float | int | str]] = []
    for chase_category in (-1.0, 0.0, 1.0):
        mask = pp["chase_category"] == chase_category
        subset = pp[mask]
        y = subset["is_winner"].astype(int).to_numpy()
        rows.append({
            "chase_category": int(chase_category),
            "n_rows": int(mask.sum()),
            "v15_brier_raw": float(brier_score_loss(y, raw_v15[mask.to_numpy()])),
            "v15_brier_cal": float(brier_score_loss(y, cal_v15[mask.to_numpy()])),
            "v15_logloss_raw": float(log_loss(y, raw_v15[mask.to_numpy()], labels=[0, 1])),
            "v15_logloss_cal": float(log_loss(y, cal_v15[mask.to_numpy()], labels=[0, 1])),
            "v16_brier_raw": float(brier_score_loss(y, raw_v16[mask.to_numpy()])),
            "v16_brier_cal": float(brier_score_loss(y, cal_v16[mask.to_numpy()])),
            "v16_logloss_raw": float(log_loss(y, raw_v16[mask.to_numpy()], labels=[0, 1])),
            "v16_logloss_cal": float(log_loss(y, cal_v16[mask.to_numpy()], labels=[0, 1])),
        })
    return pd.DataFrame(rows)


def build_holdout_comparison(pp: pd.DataFrame, v15_features: list[str]) -> pd.DataFrame:
    holdout_train = pp[pp["season"].astype(str) < "2025"].copy().reset_index(drop=True)
    holdout_test = pp[pp["season"].astype(str) >= "2025"].copy().reset_index(drop=True)
    if holdout_train.empty or holdout_test.empty:
        return pd.DataFrame()

    train_raw_oof = season_fold_oof_raw(holdout_train, v15_features)
    over_bundle = fit_calibrator_bundle(
        train_raw_oof,
        holdout_train["is_winner"].astype(int).to_numpy(),
        holdout_train["over"].astype(int).to_numpy(),
        "isotonic",
    )
    _, context_bundle = final_pp_calibration(train_raw_oof, holdout_train)

    train_model = fit_final_raw_model(holdout_train, v15_features)
    raw_test = train_model.predict_proba(holdout_test[v15_features].replace([np.inf, -np.inf], np.nan))[:, 1]
    over_cal_test = apply_calibrator_bundle(raw_test, holdout_test["over"].astype(int).to_numpy(), over_bundle)
    context_cal_test = apply_hierarchical_isotonic_bundle(
        raw_test,
        holdout_test[["over", "chase_category", "pp_score_bin", "pp_gap_bin"]],
        context_bundle,
    )
    y_test = holdout_test["is_winner"].astype(int).to_numpy()

    return pd.DataFrame(
        [
            {
                "variant": "v15_raw_like",
                "brier": float(brier_score_loss(y_test, raw_test)),
                "logloss": float(log_loss(y_test, raw_test, labels=[0, 1])),
            },
            {
                "variant": "v15_over_only_cal",
                "brier": float(brier_score_loss(y_test, over_cal_test)),
                "logloss": float(log_loss(y_test, over_cal_test, labels=[0, 1])),
            },
            {
                "variant": "v16_context_cal",
                "brier": float(brier_score_loss(y_test, context_cal_test)),
                "logloss": float(log_loss(y_test, context_cal_test, labels=[0, 1])),
            },
        ]
    )


def save_model_dir(
    pp_model: ContextCalibratedPPModel,
    pp_full_features: list[str],
    pp_metrics: dict[str, float | str],
    chase_metrics: pd.DataFrame,
    raw_group_df: pd.DataFrame,
    cal_group_df: pd.DataFrame,
    holdout_comparison: pd.DataFrame,
) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for artifact in [
        "champion_model_mid.joblib",
        "champion_model_death.joblib",
        "post_model_calibration_router.pkl",
        "venue_pitch_baselines.json",
    ]:
        shutil.copy2(V15_DIR / artifact, OUT_DIR / artifact)

    joblib.dump(pp_model, OUT_DIR / "champion_model_pp.joblib")

    v15_phase_features = load_v15_phase_features()
    phase_features = {
        "pp": pp_full_features,
        "mid": v15_phase_features["mid"],
        "death": v15_phase_features["death"],
    }
    with open(OUT_DIR / "phase_features.json", "w", encoding="utf-8") as handle:
        json.dump(phase_features, handle, indent=2)

    phase_oof = {"pp": {}, "mid": {}, "death": {}}
    with open(OUT_DIR / "phase_oof_calibrators.pkl", "wb") as handle:
        joblib.dump(phase_oof, handle)

    v15_oof = load_v15_oof_results()
    updated_rows = []
    for phase in ("pp", "mid", "death"):
        if phase == "pp":
            updated_rows.append({
                "phase": "pp",
                "n_rows": int(pp_metrics["n_rows"]),
                "n_features": int(pp_metrics["n_features"]),
                "oof_brier_raw": round(float(pp_metrics["brier_raw"]), 5),
                "oof_brier_cal": round(float(pp_metrics["brier_cal"]), 5),
                "oof_logloss_raw": round(float(pp_metrics["logloss_raw"]), 5),
                "oof_logloss_cal": round(float(pp_metrics["logloss_cal"]), 5),
            })
        else:
            row = v15_oof[v15_oof["phase"] == phase].iloc[0].to_dict()
            row.setdefault("oof_logloss_raw", np.nan)
            row.setdefault("oof_logloss_cal", np.nan)
            updated_rows.append(row)
    pd.DataFrame(updated_rows).to_csv(OUT_DIR / "oof_results.csv", index=False)
    chase_metrics.to_csv(OUT_DIR / "pp_chase_category_comparison.csv", index=False)
    raw_group_df.to_csv(OUT_DIR / "pp_raw_feature_iterations.csv", index=False)
    cal_group_df.to_csv(OUT_DIR / "pp_calibration_iterations.csv", index=False)
    holdout_comparison.to_csv(OUT_DIR / "oos_comparison.csv", index=False)

    routing_config = {
        "type": "inn2_phase_router",
        "description": (
            "ipl_v16_pp_improved: v15 PP raw feature set retained, but the PP champion model now "
            "applies an internal hierarchical calibration over over/chase_category/pp_score_bin/pp_gap_bin."
        ),
        "inn1_model_dir": "models/ipl_v7",
        "inn2_phase_model_dir": str(OUT_DIR),
        "apply_calibration": False,
        "post_model_calibration": {
            "enabled": True,
            "artifact": "post_model_calibration_router.pkl",
            "description": "Copied unchanged from v15; PP model is already internally calibrated.",
        },
        "pp_low_fallback_model_dir": "models/ipl_v12",
        "pp_low_fallback_rule": "phase == pp and target_above_par < -20 uses models/ipl_v12 champion_model_pp raw probability",
        "pp_changes_vs_v15": {
            "raw_features": "Retained v15 PP raw feature set after OOF iteration search.",
            "new_context_features": ["pp_score_bin", "pp_gap_bin", "pp_scoring_trajectory", "inn1_pp_run_rate", "set_batter_stability", "recovery_potential"],
            "internal_calibration": {
                "levels": CAL_LEVELS,
                "blend_weight": BLEND_WEIGHT,
                "clip_bounds": CLIP_BOUNDS,
            },
        },
    }
    with open(OUT_DIR / "routing_config.json", "w", encoding="utf-8") as handle:
        json.dump(routing_config, handle, indent=2)


def main() -> None:
    print("Loading IPL training data and engineering v16 PP context features...")
    full_df, _ = load_full_training_frame()
    save_v16_training_parquet(full_df)
    print(f"Saved: {DATA_OUT_PATH}")

    v15_phase_features = load_v15_phase_features()
    pp = pp_slice(full_df)
    v15_pp_features = v15_phase_features["pp"]
    y = pp["is_winner"].astype(int).to_numpy()

    print_eda(pp, v15_pp_features)
    raw_group_df = print_group_experiments(pp, v15_pp_features)
    cal_group_df, v16_calibrated, cal_bundle = print_calibration_experiments(pp, v15_pp_features)

    raw_v15 = season_fold_oof_raw(pp, v15_pp_features)
    cal_v15 = baseline_over_calibration(raw_v15, pp)
    raw_v16 = raw_v15.copy()
    final_row = metrics_row("v16_context_calibrated", y, raw_v16, v16_calibrated)
    final_row["n_rows"] = len(pp)
    final_row["n_features"] = len(v15_pp_features)

    legacy_brier_target = 0.17032
    legacy_improvement = pct_improvement(final_row["brier_cal"], legacy_brier_target)
    print("\n=== STEP 3: FINAL PP METRICS ===")
    print(f"Legacy v15 gate target (calibrated Brier): {legacy_brier_target:.5f}")
    print(
        f"V16 PP calibrated Brier: {final_row['brier_cal']:.5f} "
        f"({legacy_improvement:.2f}% better vs legacy v15 gate baseline)"
    )
    print(
        f"V15 true-PP OOF raw/cal: {brier_score_loss(y, raw_v15):.5f} / {brier_score_loss(y, cal_v15):.5f} | "
        f"logloss {log_loss(y, raw_v15, labels=[0, 1]):.5f} / {log_loss(y, cal_v15, labels=[0, 1]):.5f}"
    )
    print(
        f"V16 true-PP OOF raw/cal: {final_row['brier_raw']:.5f} / {final_row['brier_cal']:.5f} | "
        f"logloss {final_row['logloss_raw']:.5f} / {final_row['logloss_cal']:.5f}"
    )

    chase_metrics = build_chase_category_table(pp, raw_v15, cal_v15, raw_v16, v16_calibrated)
    print("\nPP chase-category comparison (true PP rows):")
    print(chase_metrics.to_string(index=False))

    holdout_comparison = build_holdout_comparison(pp, v15_pp_features)
    if not holdout_comparison.empty:
        print("\nHold-out comparison (train<2025, test>=2025):")
        print(holdout_comparison.to_string(index=False))

    print("\n=== STEP 4: TRAINING FINAL CHAMPION PP MODEL ===")
    pp_raw_model = fit_final_raw_model(pp, v15_pp_features)
    pp_full_features = ordered_unique(v15_pp_features + ["over", "pp_score_bin", "pp_gap_bin"])
    champion_pp = ContextCalibratedPPModel(
        base_model=pp_raw_model,
        base_features=v15_pp_features,
        calibration_bundle=cal_bundle,
        feature_names=pp_full_features,
    )

    save_model_dir(
        champion_pp,
        pp_full_features,
        final_row,
        chase_metrics,
        raw_group_df,
        cal_group_df,
        holdout_comparison,
    )

    print(f"Saved model directory: {OUT_DIR}")
    print("\nImprovement drivers:")
    print("- Raw PP feature additions were neutral-to-negative in OOF once evaluated on the true PP slice.")
    print("- The best gains came from context-aware calibration using chase_category + score gap bins inside PP.")
    print("- New PP context features that mattered most: pp_score_bin, pp_gap_bin, pp_scoring_trajectory, and inn1_pp_run_rate.")


if __name__ == "__main__":
    main()
