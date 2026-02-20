"""
SA20 Calibration Bucket Analysis

Analyzes calibration accuracy across different probability buckets
to see how well each calibration strategy performs at different confidence levels.

Usage:
    python scripts/sa20_calibration_bucket_analysis.py
"""

import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.model_selection import KFold
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import log_loss, brier_score_loss
import structlog
import matplotlib.pyplot as plt

logger = structlog.get_logger()

# Configuration
MODEL_DIR = Path("models/sat_v1")
TRAINING_DATA = Path("data/sat_features_v1/training.parquet")
OUTPUT_DIR = Path("data/sa20_calibration_analysis")
N_SPLITS = 5
RANDOM_STATE = 42

# Probability buckets for analysis
BUCKET_EDGES = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
BUCKET_LABELS = [
    "0-10%", "10-20%", "20-30%", "30-40%", "40-50%",
    "50-60%", "60-70%", "70-80%", "80-90%", "90-100%"
]

# Top 25 features for SA20
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

            if mask.sum() > 50:
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

                inn_mask = innings == inn
                if phase == "powerplay":
                    phase_mask = over_num <= 6
                elif phase == "middle":
                    phase_mask = (over_num > 6) & (over_num <= 15)
                else:
                    phase_mask = over_num > 15

                mask = inn_mask & phase_mask

                if phase_key in calibrators["innings_phase_specific"] and mask.sum() > 0:
                    y_cal[mask] = calibrators["innings_phase_specific"][phase_key].transform(
                        y_pred_raw[mask]
                    )
        return y_cal


def analyze_bucket_calibration(y_true, y_pred, bucket_edges, bucket_labels):
    """Analyze calibration within probability buckets."""
    results = []
    
    for i, (lower, upper, label) in enumerate(zip(bucket_edges[:-1], bucket_edges[1:], bucket_labels)):
        # Find predictions in this bucket
        in_bucket = (y_pred >= lower) & (y_pred < upper)
        
        if i == len(bucket_labels) - 1:  # Last bucket includes upper edge
            in_bucket = (y_pred >= lower) & (y_pred <= upper)
        
        n_samples = in_bucket.sum()
        
        if n_samples > 0:
            actual_win_rate = y_true[in_bucket].mean()
            predicted_avg = y_pred[in_bucket].mean()
            calibration_error = abs(predicted_avg - actual_win_rate)
            
            # Calculate metrics for this bucket (handle single-class case)
            try:
                bucket_log_loss = log_loss(y_true[in_bucket], y_pred[in_bucket])
            except ValueError:
                # Only one class in bucket - log_loss undefined
                bucket_log_loss = np.nan
            bucket_brier = brier_score_loss(y_true[in_bucket], y_pred[in_bucket])
            
            results.append({
                'bucket': label,
                'bucket_lower': lower,
                'bucket_upper': upper,
                'n_samples': n_samples,
                'predicted_avg': predicted_avg,
                'actual_win_rate': actual_win_rate,
                'calibration_error': calibration_error,
                'log_loss': bucket_log_loss,
                'brier': bucket_brier,
            })
        else:
            results.append({
                'bucket': label,
                'bucket_lower': lower,
                'bucket_upper': upper,
                'n_samples': 0,
                'predicted_avg': np.nan,
                'actual_win_rate': np.nan,
                'calibration_error': np.nan,
                'log_loss': np.nan,
                'brier': np.nan,
            })
    
    return pd.DataFrame(results)


def main():
    """Run bucket calibration analysis."""
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Load training data
    logger.info("Loading training data", path=str(TRAINING_DATA))
    df = pd.read_parquet(TRAINING_DATA)

    # Load champion model
    logger.info("Loading champion model", path=str(MODEL_DIR / "champion_model.joblib"))
    import joblib
    model = joblib.load(MODEL_DIR / "champion_model.joblib")

    # Prepare features
    X, y, available_features = prepare_features(df, TOP_25_FEATURES)
    logger.info(f"Using {len(available_features)} features for {len(df)} samples")

    # Get innings and over information
    innings = df["innings"].values
    # Calculate over number from overs_remaining (20 - overs_remaining)
    over_num = (20 - df["overs_remaining"]).values

    # Initialize K-Fold
    kf = KFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE)

    # Store OOF predictions and metadata
    oof_predictions = {
        "raw": np.zeros(len(df)),
        "combined": np.zeros(len(df)),
        "innings_specific": np.zeros(len(df)),
        "innings_phase_specific": np.zeros(len(df)),
    }

    logger.info(f"Starting {N_SPLITS}-fold OOF calibration")

    # Run cross-validation
    for fold_idx, (train_idx, val_idx) in enumerate(kf.split(X), 1):
        logger.info(f"Processing fold {fold_idx}/{N_SPLITS}")

        # Split data
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y[train_idx], y[val_idx]
        innings_train, innings_val = innings[train_idx], innings[val_idx]
        over_train, over_val = over_num[train_idx], over_num[val_idx]

        # Train model on this fold
        model.fit(X_train, y_train)

        # Get raw predictions
        y_pred_raw_val = model.predict_proba(X_val)[:, 1]

        # Store raw predictions
        oof_predictions["raw"][val_idx] = y_pred_raw_val

        # Train calibrators on training fold
        y_pred_raw_train = model.predict_proba(X_train)[:, 1]
        calibrators = train_calibrators(
            y_train, y_pred_raw_train, innings_train, over_train
        )

        # Apply calibrations to validation fold
        for strategy in ["combined", "innings_specific", "innings_phase_specific"]:
            y_cal = apply_calibration(
                y_pred_raw_val, strategy, calibrators, innings_val, over_val
            )
            oof_predictions[strategy][val_idx] = y_cal

    logger.info("Analyzing calibration by probability buckets")

    # Analyze each strategy by bucket
    all_bucket_results = []
    
    for strategy in ["raw", "combined", "innings_specific", "innings_phase_specific"]:
        logger.info(f"Analyzing strategy: {strategy}")
        
        bucket_df = analyze_bucket_calibration(
            y, oof_predictions[strategy], BUCKET_EDGES, BUCKET_LABELS
        )
        bucket_df['strategy'] = strategy
        all_bucket_results.append(bucket_df)
    
    # Combine all results
    results_df = pd.concat(all_bucket_results, ignore_index=True)
    
    # Save detailed results
    output_file = OUTPUT_DIR / "bucket_calibration_analysis.csv"
    results_df.to_csv(output_file, index=False)
    logger.info(f"Saved bucket analysis to {output_file}")
    
    # Create summary pivot tables
    print("\n" + "="*80)
    print("SA20 CALIBRATION BY PROBABILITY BUCKET")
    print("="*80)
    
    # Pivot table: Calibration Error by bucket
    print("\n📊 CALIBRATION ERROR BY BUCKET")
    print("(Lower is better - measures |predicted - actual|)")
    pivot_cal_error = results_df.pivot(
        index='bucket', columns='strategy', values='calibration_error'
    )
    pivot_cal_error = pivot_cal_error[['raw', 'combined', 'innings_specific', 'innings_phase_specific']]
    print(pivot_cal_error.to_string(float_format=lambda x: f'{x:.4f}'))
    
    # Pivot table: Sample counts
    print("\n📈 SAMPLE COUNTS BY BUCKET")
    pivot_samples = results_df[results_df['strategy'] == 'raw'].pivot(
        index='bucket', columns='strategy', values='n_samples'
    )
    print(pivot_samples['raw'].to_string(float_format=lambda x: f'{x:.0f}'))
    
    # Pivot table: Predicted vs Actual
    print("\n🎯 PREDICTED vs ACTUAL WIN RATE BY BUCKET (Innings-Specific)")
    inn_specific = results_df[results_df['strategy'] == 'innings_specific'].copy()
    print("\nBucket          | N     | Predicted | Actual  | Error")
    print("-" * 60)
    for _, row in inn_specific.iterrows():
        if row['n_samples'] > 0:
            print(f"{row['bucket']:15s} | {row['n_samples']:5.0f} | {row['predicted_avg']:.3f}     | {row['actual_win_rate']:.3f}   | {row['calibration_error']:.4f}")
    
    # Weighted average calibration error (similar to ECE)
    print("\n📏 WEIGHTED AVERAGE CALIBRATION ERROR (ECE-like)")
    for strategy in ['raw', 'combined', 'innings_specific', 'innings_phase_specific']:
        strategy_data = results_df[results_df['strategy'] == strategy].copy()
        total_samples = strategy_data['n_samples'].sum()
        strategy_data['weight'] = strategy_data['n_samples'] / total_samples
        weighted_ce = (strategy_data['calibration_error'] * strategy_data['weight']).sum()
        print(f"{strategy:25s}: {weighted_ce:.4f}")
    
    # Create calibration plot
    print("\n📊 Creating calibration plots...")
    fig, axes = plt.subplots(2, 2, figsize=(14, 12))
    fig.suptitle('SA20 Calibration by Probability Bucket', fontsize=16, fontweight='bold')
    
    strategies = ['raw', 'combined', 'innings_specific', 'innings_phase_specific']
    strategy_labels = ['Raw', 'Combined', 'Innings-Specific', 'Innings×Phase']
    
    for ax, strategy, label in zip(axes.flat, strategies, strategy_labels):
        strategy_data = results_df[results_df['strategy'] == strategy].copy()
        strategy_data = strategy_data[strategy_data['n_samples'] > 0]
        
        # Plot predicted vs actual
        ax.plot([0, 1], [0, 1], 'k--', label='Perfect Calibration', linewidth=2)
        ax.scatter(
            strategy_data['predicted_avg'],
            strategy_data['actual_win_rate'],
            s=strategy_data['n_samples'] / 10,
            alpha=0.6,
            label='Bucket Performance'
        )
        
        # Add bucket labels
        for _, row in strategy_data.iterrows():
            ax.annotate(
                row['bucket'],
                (row['predicted_avg'], row['actual_win_rate']),
                fontsize=8,
                alpha=0.7
            )
        
        ax.set_xlabel('Predicted Win Probability', fontsize=11)
        ax.set_ylabel('Actual Win Rate', fontsize=11)
        ax.set_title(f'{label} Strategy', fontsize=12, fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.set_xlim(-0.05, 1.05)
        ax.set_ylim(-0.05, 1.05)
    
    plt.tight_layout()
    plot_file = OUTPUT_DIR / "bucket_calibration_plot.png"
    plt.savefig(plot_file, dpi=150, bbox_inches='tight')
    logger.info(f"Saved calibration plot to {plot_file}")
    
    # Create detailed comparison plot for innings-specific
    print("\n📊 Creating detailed innings-specific calibration plot...")
    fig, ax = plt.subplots(1, 1, figsize=(12, 8))
    
    inn_specific = results_df[results_df['strategy'] == 'innings_specific'].copy()
    inn_specific = inn_specific[inn_specific['n_samples'] > 0]
    
    # Perfect calibration line
    ax.plot([0, 1], [0, 1], 'k--', label='Perfect Calibration', linewidth=2, alpha=0.7)
    
    # Plot each bucket
    colors = plt.cm.viridis(np.linspace(0, 1, len(inn_specific)))
    for idx, (_, row) in enumerate(inn_specific.iterrows()):
        ax.scatter(
            row['predicted_avg'],
            row['actual_win_rate'],
            s=row['n_samples'] / 5,
            color=colors[idx],
            alpha=0.6,
            edgecolors='black',
            linewidth=1
        )
        ax.annotate(
            f"{row['bucket']}\n(n={row['n_samples']:.0f})",
            (row['predicted_avg'], row['actual_win_rate']),
            fontsize=9,
            ha='center',
            bbox=dict(boxstyle='round,pad=0.3', facecolor=colors[idx], alpha=0.3)
        )
        
        # Draw error bars
        ax.plot(
            [row['predicted_avg'], row['predicted_avg']],
            [row['predicted_avg'], row['actual_win_rate']],
            color='red',
            alpha=0.3,
            linestyle=':'
        )
    
    ax.set_xlabel('Predicted Win Probability', fontsize=13, fontweight='bold')
    ax.set_ylabel('Actual Win Rate', fontsize=13, fontweight='bold')
    ax.set_title('SA20 Innings-Specific Calibration by Probability Bucket\n(Bubble size = sample count)', 
                 fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 1.05)
    
    plt.tight_layout()
    detailed_plot = OUTPUT_DIR / "innings_specific_bucket_calibration.png"
    plt.savefig(detailed_plot, dpi=150, bbox_inches='tight')
    logger.info(f"Saved detailed plot to {detailed_plot}")
    
    print("\n✅ Bucket calibration analysis complete!")
    print(f"📁 Results saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
