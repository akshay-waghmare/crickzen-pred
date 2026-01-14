"""
SA20 OOF Calibration Comparison
Compares 4 calibration strategies using 5-fold CV on out-of-fold predictions:
1. Raw model probabilities (no calibration)
2. Combined (global isotonic calibration)
3. Innings-specific isotonic calibration
4. Innings×Phase specific isotonic calibration

Usage:
    python scripts/sa20_oof_calibration_comparison.py
"""

import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.model_selection import KFold
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import log_loss, brier_score_loss
from sklearn.calibration import calibration_curve
import structlog

logger = structlog.get_logger()

# Configuration
MODEL_DIR = Path("models/sat_v1")
TRAINING_DATA = Path("data/sat_features_v1/training.parquet")
OUTPUT_DIR = Path("data/sa20_calibration_analysis")
N_SPLITS = 5
RANDOM_STATE = 42

# Top 25 features for SA20 (same as BBL)
TOP_25_FEATURES = [
    "resource_win_prob",
    "score_vs_par",
    "batting_team_win_rate",
    "bowling_team_win_rate",
    "runs_scored",
    "wickets_lost",
    "current_run_rate",
    "required_run_rate",
    "batting_team_bat_first_wr",
    "batting_team_bowl_first_wr",
    "bowling_team_bat_first_wr",
    "bowling_team_bowl_first_wr",
    "venue_win_rate",
    "bat_sr_rolling_avg",
    "bowl_sr_rolling_avg",
    "bat_avg_rolling_avg",
    "bowl_avg_rolling_avg",
    "balls_faced",
    "balls_bowled",
    "total_runs",
    "partnership_runs",
    "partnership_balls",
    "wickets_in_hand",
    "required_runs",
    "team_strength_diff",
]


def prepare_features(df: pd.DataFrame, features: list) -> tuple:
    """Prepare features for training."""
    available_features = [f for f in features if f in df.columns]
    X = df[available_features].copy()
    X = X.fillna(0)
    y = df["is_winner"].values
    return X, y, available_features


def get_phase_key(innings: int, over: float) -> str:
    """Get phase key from innings and over number."""
    if over <= 6:
        phase = "powerplay"
    elif over <= 15:
        phase = "middle"
    else:
        phase = "death"
    return f"inn{innings}_{phase}"


def calculate_ece(y_true, y_prob, n_bins=10):
    """Calculate Expected Calibration Error."""
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    bin_lowers = bin_boundaries[:-1]
    bin_uppers = bin_boundaries[1:]

    ece = 0.0
    for bin_lower, bin_upper in zip(bin_lowers, bin_uppers):
        in_bin = (y_prob > bin_lower) & (y_prob <= bin_upper)
        prop_in_bin = in_bin.mean()

        if prop_in_bin > 0:
            accuracy_in_bin = y_true[in_bin].mean()
            avg_confidence_in_bin = y_prob[in_bin].mean()
            ece += np.abs(avg_confidence_in_bin - accuracy_in_bin) * prop_in_bin

    return ece


def train_calibrators(y_true, y_pred_raw, innings, over_num):
    """Train all calibrator types."""
    calibrators = {}

    # 1. Combined (global) calibrator
    iso_combined = IsotonicRegression(y_min=0.01, y_max=0.99, out_of_bounds="clip")
    iso_combined.fit(y_pred_raw, y_true)
    calibrators["combined"] = iso_combined

    # 2. Innings-specific calibrators
    calibrators["innings_specific"] = {}
    for inn in [1, 2]:
        mask = innings == inn
        if mask.sum() > 100:
            iso_inn = IsotonicRegression(y_min=0.01, y_max=0.99, out_of_bounds="clip")
            iso_inn.fit(y_pred_raw[mask], y_true[mask])
            calibrators["innings_specific"][inn] = iso_inn

    # 3. Innings×Phase specific calibrators
    calibrators["innings_phase_specific"] = {}
    for inn in [1, 2]:
        for phase in ["powerplay", "middle", "death"]:
            phase_key = f"inn{inn}_{phase}"

            # Create mask for this innings+phase
            inn_mask = innings == inn
            if phase == "powerplay":
                phase_mask = over_num <= 6
            elif phase == "middle":
                phase_mask = (over_num > 6) & (over_num <= 15)
            else:  # death
                phase_mask = over_num > 15

            mask = inn_mask & phase_mask

            if mask.sum() > 50:  # Minimum samples for calibration
                iso_phase = IsotonicRegression(
                    y_min=0.01, y_max=0.99, out_of_bounds="clip"
                )
                iso_phase.fit(y_pred_raw[mask], y_true[mask])
                calibrators["innings_phase_specific"][phase_key] = iso_phase

    return calibrators


def apply_calibration(y_pred_raw, strategy, calibrators, innings, over_num):
    """Apply calibration based on strategy."""
    if strategy == "raw":
        return y_pred_raw

    elif strategy == "combined":
        return calibrators["combined"].transform(y_pred_raw)

    elif strategy == "innings_specific":
        y_cal = y_pred_raw.copy()
        for inn in [1, 2]:
            mask = innings == inn
            if inn in calibrators["innings_specific"]:
                y_cal[mask] = calibrators["innings_specific"][inn].transform(
                    y_pred_raw[mask]
                )
        return y_cal

    elif strategy == "innings_phase_specific":
        y_cal = y_pred_raw.copy()
        for inn in [1, 2]:
            for phase in ["powerplay", "middle", "death"]:
                phase_key = f"inn{inn}_{phase}"

                # Create mask for this innings+phase
                inn_mask = innings == inn
                if phase == "powerplay":
                    phase_mask = over_num <= 6
                elif phase == "middle":
                    phase_mask = (over_num > 6) & (over_num <= 15)
                else:  # death
                    phase_mask = over_num > 15

                mask = inn_mask & phase_mask

                if (
                    phase_key in calibrators["innings_phase_specific"]
                    and mask.sum() > 0
                ):
                    y_cal[mask] = calibrators["innings_phase_specific"][
                        phase_key
                    ].transform(y_pred_raw[mask])
        return y_cal


def main():
    """Run OOF calibration comparison."""
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Load training data
    logger.info("Loading training data", path=str(TRAINING_DATA))
    df = pd.read_parquet(TRAINING_DATA)

    # Load champion model
    logger.info("Loading champion model", path=str(MODEL_DIR / "champion_model.joblib"))
    import joblib

    model = joblib.load(MODEL_DIR / "champion_model.joblib")

    # Prepare features
    X, y, features = prepare_features(df, TOP_25_FEATURES)
    innings = df["innings"].values
    
    # Calculate over number from overs_remaining (max overs is 20)
    over_num = 20 - df["overs_remaining"].values

    logger.info(
        "Generating OOF predictions",
        rows=len(df),
        features=len(features),
        n_splits=N_SPLITS,
    )

    # Initialize arrays for OOF predictions
    oof_preds = np.zeros(len(df))

    # K-Fold CV
    kfold = KFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE)

    for fold, (train_idx, val_idx) in enumerate(kfold.split(X), 1):
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y[train_idx], y[val_idx]

        # Train model on fold (XGBLogRegEnsemble)
        from bbl_pipeline.training.trainer import XGBLogRegEnsemble
        
        fold_model = XGBLogRegEnsemble(
            xgb_weight=0.5,
            n_features=25,
        )
        fold_model.fit(X_train, y_train)

        # Get OOF predictions
        oof_preds[val_idx] = fold_model.predict_proba(X_val)[:, 1]

        logger.info(
            "OOF fold complete",
            fold=fold,
            train_size=len(train_idx),
            val_size=len(val_idx),
        )

    # Train calibrators on full OOF predictions
    logger.info("Training calibrators on OOF predictions")
    calibrators = train_calibrators(y, oof_preds, innings, over_num)

    # Evaluate all strategies
    strategies = [
        "raw",
        "combined",
        "innings_specific",
        "innings_phase_specific",
    ]

    results = []
    detailed_results = []

    for strategy in strategies:
        # Apply calibration
        y_cal = apply_calibration(oof_preds, strategy, calibrators, innings, over_num)

        # Calculate overall metrics
        ll = log_loss(y, y_cal)
        brier = brier_score_loss(y, y_cal)
        ece = calculate_ece(y, y_cal)

        results.append(
            {
                "strategy": strategy,
                "log_loss": ll,
                "brier": brier,
                "ece": ece,
                "n_samples": len(y),
            }
        )

        logger.info(
            "Strategy evaluation",
            strategy=strategy,
            log_loss=f"{ll:.6f}",
            brier=f"{brier:.6f}",
            ece=f"{ece:.6f}",
        )

        # Calculate metrics by innings and phase
        for inn in [1, 2]:
            inn_mask = innings == inn
            if inn_mask.sum() > 0:
                ll_inn = log_loss(y[inn_mask], y_cal[inn_mask])
                brier_inn = brier_score_loss(y[inn_mask], y_cal[inn_mask])
                ece_inn = calculate_ece(y[inn_mask], y_cal[inn_mask])

                detailed_results.append(
                    {
                        "strategy": strategy,
                        "innings": inn,
                        "phase": "all",
                        "log_loss": ll_inn,
                        "brier": brier_inn,
                        "ece": ece_inn,
                        "n_samples": inn_mask.sum(),
                    }
                )

                # By phase within innings
                for phase in ["powerplay", "middle", "death"]:
                    if phase == "powerplay":
                        phase_mask = over_num <= 6
                    elif phase == "middle":
                        phase_mask = (over_num > 6) & (over_num <= 15)
                    else:  # death
                        phase_mask = over_num > 15

                    mask = inn_mask & phase_mask

                    if mask.sum() > 50:
                        ll_phase = log_loss(y[mask], y_cal[mask])
                        brier_phase = brier_score_loss(y[mask], y_cal[mask])
                        ece_phase = calculate_ece(y[mask], y_cal[mask])

                        detailed_results.append(
                            {
                                "strategy": strategy,
                                "innings": inn,
                                "phase": phase,
                                "log_loss": ll_phase,
                                "brier": brier_phase,
                                "ece": ece_phase,
                                "n_samples": mask.sum(),
                            }
                        )

    # Save results
    df_summary = pd.DataFrame(results)
    df_detailed = pd.DataFrame(detailed_results)

    summary_path = OUTPUT_DIR / "oof_summary.csv"
    detailed_path = OUTPUT_DIR / "oof_detailed_results.csv"

    df_summary.to_csv(summary_path, index=False)
    df_detailed.to_csv(detailed_path, index=False)

    logger.info("Results saved", summary=str(summary_path), detailed=str(detailed_path))

    # Print summary
    print("\n" + "=" * 80)
    print("SA20 OOF CALIBRATION COMPARISON")
    print("=" * 80)
    print("\nOVERALL METRICS:")
    print(df_summary.to_string(index=False))

    # Calculate improvements vs raw
    raw_ll = df_summary[df_summary["strategy"] == "raw"]["log_loss"].values[0]
    print(f"\nLOG LOSS IMPROVEMENTS VS RAW:")
    for _, row in df_summary.iterrows():
        if row["strategy"] != "raw":
            improvement = (raw_ll - row["log_loss"]) / raw_ll * 100
            print(f"  {row['strategy']:30s}: {improvement:+6.2f}%")

    # Find best strategy by situation
    print("\n" + "=" * 80)
    print("BEST STRATEGY BY SITUATION (LOG LOSS):")
    print("=" * 80)

    for inn in [1, 2]:
        print(f"\nINNINGS {inn}:")
        for phase in ["all", "powerplay", "middle", "death"]:
            subset = df_detailed[
                (df_detailed["innings"] == inn) & (df_detailed["phase"] == phase)
            ]
            if not subset.empty:
                best = subset.loc[subset["log_loss"].idxmin()]
                print(
                    f"  {phase:12s}: {best['strategy']:30s} "
                    f"(LL={best['log_loss']:.6f}, ECE={best['ece']:.6f}, n={best['n_samples']:.0f})"
                )


if __name__ == "__main__":
    main()
