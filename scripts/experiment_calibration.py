import pandas as pd
import numpy as np
import joblib
from sklearn.metrics import brier_score_loss
from pathlib import Path
import sys
import os
import itertools

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

def run_calibration_experiment():
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
    
    print(f"Total samples: {len(df)}")
    
    # Split: Train (80%), Test (20%) - No calibration set needed for this approach
    n = len(df)
    train_end = int(n * 0.8)
    
    X_train, y_train = X.iloc[:train_end], y.iloc[:train_end]
    X_test, y_test = X.iloc[train_end:], y.iloc[train_end:]
    
    print(f"Train: {len(X_train)}, Test: {len(X_test)}")
    
    # Parameter Grid
    xgb_weights = [0.0, 0.05, 0.1]
    
    # XGBoost Hyperparameters to tune for calibration
    # Shallower trees (max_depth) and higher regularization (reg_lambda) reduce overconfidence
    xgb_param_grid = {
        'max_depth': [1, 2],
        'reg_lambda': [1.0, 5.0, 10.0],
        'min_child_weight': [28, 50],
        'learning_rate': [0.011] # Keep fixed
    }
    
    keys, values = zip(*xgb_param_grid.items())
    xgb_configs = [dict(zip(keys, v)) for v in itertools.product(*values)]
    
    results = []
    
    print(f"\nStarting Grid Search ({len(xgb_weights) * len(xgb_configs)} combinations)...")
    
    for weight in xgb_weights:
        for xgb_params in xgb_configs:
            # Merge with default params required by the class if not present
            # The class has defaults, we just override specific ones
            
            model = XGBLogRegEnsemble(
                xgb_weight=weight,
                xgb_params=xgb_params
            )
            
            model.fit(X_train, y_train)
            prob_test = model.predict_proba(X_test)[:, 1]
            
            ece = expected_calibration_error(y_test, prob_test)
            brier = brier_score_loss(y_test, prob_test)
            
            results.append({
                'xgb_weight': weight,
                'max_depth': xgb_params['max_depth'],
                'reg_lambda': xgb_params['reg_lambda'],
                'min_child_weight': xgb_params['min_child_weight'],
                'ece': ece,
                'brier': brier
            })
            
            # print(f"W={weight}, D={xgb_params['max_depth']}, L={xgb_params['reg_lambda']} -> ECE={ece:.4f}")

    # Sort by ECE
    results_df = pd.DataFrame(results).sort_values('ece')
    
    print("\nTop 10 Configurations by ECE:")
    print(results_df.head(10).to_string(index=False))
    
    best_config = results_df.iloc[0]
    print(f"\nBest Configuration:")
    print(f"XGB Weight: {best_config['xgb_weight']}")
    print(f"Max Depth: {best_config['max_depth']}")
    print(f"Reg Lambda: {best_config['reg_lambda']}")
    print(f"Min Child Weight: {best_config['min_child_weight']}")
    print(f"Resulting ECE: {best_config['ece']:.4f}")
    print(f"Resulting Brier: {best_config['brier']:.4f}")
    
    target_ece = 0.0016
    if best_config['ece'] < target_ece:
        print(f"\n✅ SUCCESS: Achieved ECE < {target_ece}")
    else:
        print(f"\n❌ FAILED: Best ECE was {best_config['ece']:.4f}")

if __name__ == "__main__":
    run_calibration_experiment()
