import pandas as pd
import numpy as np
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from bbl_pipeline.training.trainer import XGBLogRegEnsemble

def expected_calibration_error(y_true, y_prob, n_bins=10):
    """Calculate Expected Calibration Error (ECE)."""
    bins = np.linspace(0, 1, n_bins + 1)
    bin_indices = np.digitize(y_prob, bins[1:-1])
    
    ece = 0
    for i in range(n_bins):
        mask = bin_indices == i
        if mask.sum() > 0:
            bin_acc = y_true[mask].mean()
            bin_conf = y_prob[mask].mean()
            ece += mask.sum() / len(y_true) * abs(bin_acc - bin_conf)
    
    return ece

def run_phase_ece_check():
    print("Loading data...")
    data_path = "data/bbl_features_v2/training_sampled.parquet"
    df = pd.read_parquet(data_path)
    
    # Features
    target_col = 'is_winner'
    exclude_cols = [
        'is_winner', 'match_id', 'innings', 'over', 'ball', 'batting_team',
        'bowling_team', 'venue', 'season', 'current_score', 'wickets_lost',
        'target_runs', 'first_innings_score', 'runs_required', 'date', 'start_date',
        'is_middle_overs', 'is_death_overs', 'is_powerplay'
    ]
    
    feature_cols = [col for col in df.columns if col not in exclude_cols and not col.startswith('_')]
    numeric_df = df[feature_cols].select_dtypes(include=[np.number])
    X = numeric_df.fillna(0)
    y = df[target_col]
    
    # Keep phase columns for splitting
    is_powerplay = df['is_powerplay']
    is_middle = df['is_middle_overs']
    is_death = df['is_death_overs']
    
    print(f"Total samples: {len(df)}")
    
    # Split: Train (80%), Test (20%)
    n = len(df)
    train_end = int(n * 0.8)
    
    X_train, y_train = X.iloc[:train_end], y.iloc[:train_end]
    X_test, y_test = X.iloc[train_end:], y.iloc[train_end:]
    
    # Get test phases
    test_pp = is_powerplay.iloc[train_end:]
    test_mid = is_middle.iloc[train_end:]
    test_death = is_death.iloc[train_end:]
    
    print(f"Train: {len(X_train)}, Test: {len(X_test)}")
    
    # Best Configuration from previous run
    best_config = {
        'xgb_weight': 0.1,
        'xgb_params': {
            'max_depth': 1,
            'reg_lambda': 1.0,
            'min_child_weight': 28,
            'learning_rate': 0.011
        }
    }
    
    print(f"\nTraining model with best config: {best_config}")
    
    model = XGBLogRegEnsemble(
        xgb_weight=best_config['xgb_weight'],
        xgb_params=best_config['xgb_params']
    )
    
    model.fit(X_train, y_train)
    prob_test = model.predict_proba(X_test)[:, 1]
    
    # Overall ECE
    overall_ece = expected_calibration_error(y_test, prob_test)
    print(f"\nOverall ECE: {overall_ece:.4f}")
    
    # Phase-wise ECE
    # Powerplay: 0-5
    # Middle: 6-14
    # Death: 15-19
    
    phases = {
        'Powerplay (0-5)': (test_pp == 1),
        'Middle (6-14)': (test_mid == 1),
        'Death (15-19)': (test_death == 1)
    }
    
    print("\nPhase-wise ECE:")
    print("-" * 30)
    print(f"{'Phase':<20} | {'Samples':<8} | {'ECE':<8}")
    print("-" * 30)
    
    for phase_name, mask in phases.items():
        if mask.sum() > 0:
            phase_y = y_test[mask]
            phase_prob = prob_test[mask]
            phase_ece = expected_calibration_error(phase_y, phase_prob)
            print(f"{phase_name:<20} | {mask.sum():<8} | {phase_ece:.4f}")
        else:
            print(f"{phase_name:<20} | 0        | N/A")

if __name__ == "__main__":
    run_phase_ece_check()
