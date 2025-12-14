import pandas as pd
import numpy as np
import sys
import os
from sklearn.metrics import brier_score_loss

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

def run_brier_breakdown():
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
    
    # Keep metadata for splitting
    meta_cols = ['innings', 'is_powerplay', 'is_middle_overs', 'is_death_overs']
    meta_df = df[meta_cols]
    
    print(f"Total samples: {len(df)}")
    
    # Split: Train (80%), Test (20%)
    n = len(df)
    train_end = int(n * 0.8)
    
    X_train, y_train = X.iloc[:train_end], y.iloc[:train_end]
    X_test, y_test = X.iloc[train_end:], y.iloc[train_end:]
    meta_test = meta_df.iloc[train_end:]
    
    print(f"Train: {len(X_train)}, Test: {len(X_test)}")
    
    # Best Configuration
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
    
    # --- Brier Score & ECE Calculations ---
    
    def calculate_and_print(name, mask):
        if mask.sum() == 0:
            print(f"{name}: No samples")
            return
            
        y_subset = y_test[mask]
        prob_subset = prob_test[mask]
        
        brier = brier_score_loss(y_subset, prob_subset)
        ece = expected_calibration_error(y_subset, prob_subset)
        
        # Bias: Positive = Overconfident (Model > Actual), Negative = Underconfident
        bias = prob_subset.mean() - y_subset.mean()
        
        print(f"{name:<25} | Samples: {len(y_subset):<6} | Brier: {brier:.4f} | ECE: {ece:.4f} | Bias: {bias:+.4f}")

    print("\n" + "="*90)
    print(f"{'Segment':<25} | {'Samples':<6} | {'Brier':<7} | {'ECE':<7} | {'Bias'}")
    print("="*90)
    
    # Overall
    calculate_and_print("Overall", np.ones(len(y_test), dtype=bool))
    print("-" * 90)
    
    # By Innings
    calculate_and_print("Innings 1", meta_test['innings'] == 1)
    calculate_and_print("Innings 2", meta_test['innings'] == 2)
    print("-" * 90)
    
    # By Phase
    calculate_and_print("Powerplay (0-5)", meta_test['is_powerplay'] == 1)
    calculate_and_print("Middle (6-14)", meta_test['is_middle_overs'] == 1)
    calculate_and_print("Death (15-19)", meta_test['is_death_overs'] == 1)
    print("-" * 90)
    
    # Detailed Breakdown
    calculate_and_print("Inn 1 - Powerplay", (meta_test['innings'] == 1) & (meta_test['is_powerplay'] == 1))
    calculate_and_print("Inn 1 - Middle", (meta_test['innings'] == 1) & (meta_test['is_middle_overs'] == 1))
    calculate_and_print("Inn 1 - Death", (meta_test['innings'] == 1) & (meta_test['is_death_overs'] == 1))
    print("-" * 90)
    calculate_and_print("Inn 2 - Powerplay", (meta_test['innings'] == 2) & (meta_test['is_powerplay'] == 1))
    calculate_and_print("Inn 2 - Middle", (meta_test['innings'] == 2) & (meta_test['is_middle_overs'] == 1))
    calculate_and_print("Inn 2 - Death", (meta_test['innings'] == 2) & (meta_test['is_death_overs'] == 1))
    print("="*90)

if __name__ == "__main__":
    run_brier_breakdown()
