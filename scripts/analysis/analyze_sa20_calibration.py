"""
Analyze SA20 calibration methods to find one that beats brier_optimized.

Current best (brier_optimized):
- Brier: 0.1597
- ECE: 0.0000
- LogLoss: 0.4634

Methods to try:
1. Per-over Platt scaling (instead of isotonic)
2. Hybrid: isotonic + Platt blend
3. Temperature scaling (single parameter)
4. Beta calibration
5. Per-over histogram binning with more bins
"""

import pandas as pd
import numpy as np
import joblib
from pathlib import Path
from sklearn.model_selection import StratifiedKFold
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import calibration_curve
import warnings
warnings.filterwarnings('ignore')

# Metrics
def brier_score(y_true, y_pred):
    return np.mean((y_pred - y_true) ** 2)

def expected_calibration_error(y_true, y_pred, n_bins=10):
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        mask = (y_pred >= bin_boundaries[i]) & (y_pred < bin_boundaries[i + 1])
        if mask.sum() > 0:
            avg_pred = y_pred[mask].mean()
            avg_true = y_true[mask].mean()
            ece += mask.sum() * abs(avg_pred - avg_true)
    return ece / len(y_true)

def log_loss(y_true, y_pred, eps=1e-15):
    y_pred = np.clip(y_pred, eps, 1 - eps)
    return -np.mean(y_true * np.log(y_pred) + (1 - y_true) * np.log(1 - y_pred))


def temperature_scaling(y_pred, y_true):
    """Single-parameter temperature scaling."""
    from scipy.optimize import minimize_scalar
    
    def neg_log_likelihood(T):
        scaled = 1 / (1 + np.exp(-np.log(y_pred / (1 - y_pred + 1e-15)) / T))
        scaled = np.clip(scaled, 1e-15, 1 - 1e-15)
        return -np.mean(y_true * np.log(scaled) + (1 - y_true) * np.log(1 - scaled))
    
    result = minimize_scalar(neg_log_likelihood, bounds=(0.1, 10), method='bounded')
    return result.x


def beta_calibration(y_pred, y_true):
    """Beta calibration (3-parameter)."""
    from scipy.optimize import minimize
    
    def neg_log_likelihood(params):
        a, b, c = params
        # Transform predictions
        eps = 1e-15
        y_pred_clipped = np.clip(y_pred, eps, 1 - eps)
        logit = np.log(y_pred_clipped / (1 - y_pred_clipped))
        calibrated = 1 / (1 + np.exp(-(a * logit + b * np.log(y_pred_clipped) + c)))
        calibrated = np.clip(calibrated, eps, 1 - eps)
        return -np.mean(y_true * np.log(calibrated) + (1 - y_true) * np.log(1 - calibrated))
    
    result = minimize(neg_log_likelihood, x0=[1.0, 0.0, 0.0], method='L-BFGS-B',
                     bounds=[(0.01, 10), (-5, 5), (-5, 5)])
    return result.x


def evaluate_method(y_true, y_pred, name):
    """Evaluate a calibration method."""
    return {
        'method': name,
        'brier': brier_score(y_true, y_pred),
        'ece': expected_calibration_error(y_true, y_pred),
        'logloss': log_loss(y_true, y_pred)
    }


def main():
    # Load data
    print("Loading SA20 training data...")
    df = pd.read_parquet('data/sat_features_v2/training.parquet')
    
    # Load model
    model = joblib.load('models/sat_v2/champion_model.joblib')
    
    # Get features - use actual SA20 columns
    feature_cols = [
        'run_rate_diff', 'wickets_times_balls', 'overs_remaining', 'score_per_wicket',
        'required_run_rate', 'rrr_times_wickets', 'is_powerplay', 'batting_team_win_rate',
        'bowling_team_win_rate', 'team_strength_diff', 'situation_advantage',
        'batting_team_situation_wr', 'bowling_team_situation_wr', 'projected_score',
        'expected_final_score', 'score_vs_par', 'projected_vs_venue_avg', 'pressure_index',
        'dls_pressure_index', 'chase_difficulty', 'resource_win_prob', 'runs_last_12',
        'runs_last_18', 'wickets_last_12', 'boundary_pct_last_18'
    ]
    
    # Check which columns exist
    available_cols = [c for c in feature_cols if c in df.columns]
    missing_cols = [c for c in feature_cols if c not in df.columns]
    if missing_cols:
        print(f"Missing columns: {missing_cols}")
    print(f"Using {len(available_cols)} features")
    
    X = df[available_cols].values
    y = df['is_winner'].values
    innings = df['innings'].values
    # Derive current_over from overs_remaining (overs_remaining = 20 - current_over)
    overs = (20 - df['overs_remaining']).astype(int).values
    
    print(f"Samples: {len(df)}, Features: {len(feature_cols)}")
    
    # Generate OOF predictions
    print("\nGenerating OOF predictions...")
    n_splits = 5
    kfold = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    
    X_df = df[available_cols]  # Keep as DataFrame for model
    oof_preds = np.zeros(len(df))
    for fold, (train_idx, val_idx) in enumerate(kfold.split(X, y)):
        X_train, X_val = X_df.iloc[train_idx], X_df.iloc[val_idx]
        y_train = y[train_idx]
        
        # Clone and train model
        from bbl_pipeline.training.trainer import XGBLogRegEnsemble
        fold_model = XGBLogRegEnsemble()
        fold_model.fit(X_train, y_train)
        proba = fold_model.predict_proba(X_val)
        # Handle both 1D and 2D output
        if len(proba.shape) == 2:
            oof_preds[val_idx] = proba[:, 1]
        else:
            oof_preds[val_idx] = proba
        print(f"  Fold {fold+1} complete")
    
    # Baseline: Raw predictions
    results = []
    results.append(evaluate_method(y, oof_preds, 'raw'))
    print(f"\nRaw: Brier={results[-1]['brier']:.4f}, ECE={results[-1]['ece']:.4f}, LL={results[-1]['logloss']:.4f}")
    
    # Method 1: Combined Isotonic (current)
    iso = IsotonicRegression(out_of_bounds='clip')
    iso.fit(oof_preds, y)
    iso_preds = iso.predict(oof_preds)
    results.append(evaluate_method(y, iso_preds, 'combined_isotonic'))
    print(f"Combined Isotonic: Brier={results[-1]['brier']:.4f}, ECE={results[-1]['ece']:.4f}, LL={results[-1]['logloss']:.4f}")
    
    # Method 2: Per-over Isotonic (brier_optimized baseline)
    per_over_preds = np.zeros_like(oof_preds)
    for inn in [1, 2]:
        for over in range(1, 21):
            mask = (innings == inn) & (overs == over)
            if mask.sum() > 10:
                iso = IsotonicRegression(out_of_bounds='clip')
                iso.fit(oof_preds[mask], y[mask])
                per_over_preds[mask] = iso.predict(oof_preds[mask])
            else:
                per_over_preds[mask] = oof_preds[mask]
    results.append(evaluate_method(y, per_over_preds, 'per_over_isotonic'))
    print(f"Per-Over Isotonic (brier_opt): Brier={results[-1]['brier']:.4f}, ECE={results[-1]['ece']:.4f}, LL={results[-1]['logloss']:.4f}")
    
    # Method 3: Temperature Scaling
    T = temperature_scaling(oof_preds, y)
    temp_preds = 1 / (1 + np.exp(-np.log(oof_preds / (1 - oof_preds + 1e-15)) / T))
    results.append(evaluate_method(y, temp_preds, f'temperature_scaling_T={T:.2f}'))
    print(f"Temperature Scaling (T={T:.2f}): Brier={results[-1]['brier']:.4f}, ECE={results[-1]['ece']:.4f}, LL={results[-1]['logloss']:.4f}")
    
    # Method 4: Per-innings Temperature Scaling
    per_inn_temp_preds = np.zeros_like(oof_preds)
    for inn in [1, 2]:
        mask = innings == inn
        T = temperature_scaling(oof_preds[mask], y[mask])
        per_inn_temp_preds[mask] = 1 / (1 + np.exp(-np.log(oof_preds[mask] / (1 - oof_preds[mask] + 1e-15)) / T))
    results.append(evaluate_method(y, per_inn_temp_preds, 'per_innings_temperature'))
    print(f"Per-Innings Temperature: Brier={results[-1]['brier']:.4f}, ECE={results[-1]['ece']:.4f}, LL={results[-1]['logloss']:.4f}")
    
    # Method 5: Per-over Platt Scaling
    per_over_platt_preds = np.zeros_like(oof_preds)
    for inn in [1, 2]:
        for over in range(1, 21):
            mask = (innings == inn) & (overs == over)
            if mask.sum() > 20:
                lr = LogisticRegression()
                lr.fit(oof_preds[mask].reshape(-1, 1), y[mask])
                per_over_platt_preds[mask] = lr.predict_proba(oof_preds[mask].reshape(-1, 1))[:, 1]
            else:
                per_over_platt_preds[mask] = oof_preds[mask]
    results.append(evaluate_method(y, per_over_platt_preds, 'per_over_platt'))
    print(f"Per-Over Platt: Brier={results[-1]['brier']:.4f}, ECE={results[-1]['ece']:.4f}, LL={results[-1]['logloss']:.4f}")
    
    # Method 6: Hybrid Isotonic + Temperature (blend)
    hybrid_preds = 0.7 * per_over_preds + 0.3 * temp_preds
    results.append(evaluate_method(y, hybrid_preds, 'hybrid_iso_temp_70_30'))
    print(f"Hybrid Iso+Temp (70/30): Brier={results[-1]['brier']:.4f}, ECE={results[-1]['ece']:.4f}, LL={results[-1]['logloss']:.4f}")
    
    # Method 7: Per-over Isotonic + Per-over Platt blend
    hybrid2_preds = 0.7 * per_over_preds + 0.3 * per_over_platt_preds
    results.append(evaluate_method(y, hybrid2_preds, 'hybrid_iso_platt_70_30'))
    print(f"Hybrid Iso+Platt (70/30): Brier={results[-1]['brier']:.4f}, ECE={results[-1]['ece']:.4f}, LL={results[-1]['logloss']:.4f}")
    
    # Method 8: Per-over Isotonic then Temperature
    iso_then_temp_preds = 1 / (1 + np.exp(-np.log(per_over_preds / (1 - per_over_preds + 1e-15)) / T))
    results.append(evaluate_method(y, iso_then_temp_preds, 'iso_then_temperature'))
    print(f"Isotonic then Temperature: Brier={results[-1]['brier']:.4f}, ECE={results[-1]['ece']:.4f}, LL={results[-1]['logloss']:.4f}")
    
    # Method 9: Per-phase Isotonic with more granularity (6 phases)
    phases = []
    for idx in range(len(df)):
        inn = innings[idx]
        over = overs[idx]
        if over <= 6:
            phases.append(f'inn{inn}_powerplay')
        elif over <= 15:
            phases.append(f'inn{inn}_middle')
        else:
            phases.append(f'inn{inn}_death')
    phases = np.array(phases)
    
    per_phase_preds = np.zeros_like(oof_preds)
    for phase in np.unique(phases):
        mask = phases == phase
        iso = IsotonicRegression(out_of_bounds='clip')
        iso.fit(oof_preds[mask], y[mask])
        per_phase_preds[mask] = iso.predict(oof_preds[mask])
    results.append(evaluate_method(y, per_phase_preds, 'per_phase_isotonic'))
    print(f"Per-Phase Isotonic (6): Brier={results[-1]['brier']:.4f}, ECE={results[-1]['ece']:.4f}, LL={results[-1]['logloss']:.4f}")
    
    # Method 10: Per-over Isotonic with smoothing across neighbors
    smooth_per_over_preds = np.zeros_like(oof_preds)
    for inn in [1, 2]:
        for over in range(1, 21):
            # Include neighboring overs for smoothing
            mask = (innings == inn) & (overs == over)
            neighbor_mask = (innings == inn) & (overs >= max(1, over-1)) & (overs <= min(20, over+1))
            
            if mask.sum() > 0 and neighbor_mask.sum() > 20:
                iso = IsotonicRegression(out_of_bounds='clip')
                iso.fit(oof_preds[neighbor_mask], y[neighbor_mask])
                smooth_per_over_preds[mask] = iso.predict(oof_preds[mask])
            else:
                smooth_per_over_preds[mask] = oof_preds[mask]
    results.append(evaluate_method(y, smooth_per_over_preds, 'smooth_per_over_isotonic'))
    print(f"Smoothed Per-Over Isotonic: Brier={results[-1]['brier']:.4f}, ECE={results[-1]['ece']:.4f}, LL={results[-1]['logloss']:.4f}")
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY: All Methods Ranked by Brier Score")
    print("="*70)
    
    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values('brier')
    print(results_df.to_string(index=False))
    
    # Check if any method beats per_over_isotonic
    baseline = results_df[results_df['method'] == 'per_over_isotonic'].iloc[0]
    print(f"\n\nBaseline (per_over_isotonic): Brier={baseline['brier']:.4f}, ECE={baseline['ece']:.4f}, LL={baseline['logloss']:.4f}")
    
    better_methods = results_df[results_df['brier'] < baseline['brier']]
    if len(better_methods) > 0:
        print("\n🎉 Methods that BEAT brier_optimized:")
        print(better_methods.to_string(index=False))
    else:
        print("\n❌ No method beats per_over_isotonic on Brier score")
    
    # Check for better LogLoss
    ll_better = results_df[results_df['logloss'] < baseline['logloss']]
    if len(ll_better) > 0:
        print("\n📊 Methods with better LogLoss:")
        print(ll_better.to_string(index=False))
    
    return results_df


if __name__ == '__main__':
    main()
