"""
Compare Isotonic vs Platt scaling per-over calibrators for BBL.

For each innings × over:
1. Train both isotonic and Platt calibrators
2. Evaluate OOF Brier scores for each
3. Select the method that doesn't increase Brier (or pick the better one)
4. Save hybrid calibrators that use the best method per-over
"""

import pandas as pd
import numpy as np
import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.isotonic import IsotonicRegression
from sklearn.model_selection import KFold
from pathlib import Path


def brier_score(y_true, y_pred):
    """Calculate Brier score."""
    return np.mean((y_true - y_pred) ** 2)


def ece_score(y_true, y_pred, n_bins=10):
    """Calculate Expected Calibration Error."""
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        mask = (y_pred >= bin_boundaries[i]) & (y_pred < bin_boundaries[i + 1])
        if mask.sum() > 0:
            bin_acc = y_true[mask].mean()
            bin_conf = y_pred[mask].mean()
            ece += mask.sum() * abs(bin_acc - bin_conf)
    return ece / len(y_true)


def train_and_evaluate_oof(source_probs, y_true, method='isotonic', n_splits=5):
    """
    Train calibrator with OOF evaluation to get unbiased Brier/ECE.
    Returns: (calibrated_probs_oof, fitted_calibrator_on_all_data)
    """
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=42)
    oof_probs = np.zeros(len(source_probs))
    
    for train_idx, val_idx in kf.split(source_probs):
        X_train, y_train = source_probs[train_idx], y_true[train_idx]
        X_val = source_probs[val_idx]
        
        if method == 'isotonic':
            cal = IsotonicRegression(out_of_bounds='clip')
            cal.fit(X_train, y_train)
            oof_probs[val_idx] = cal.predict(X_val)
        else:  # platt
            X_train_clipped = np.clip(X_train, 1e-6, 1 - 1e-6)
            log_odds_train = np.log(X_train_clipped / (1 - X_train_clipped)).reshape(-1, 1)
            cal = LogisticRegression(solver='lbfgs', max_iter=1000)
            cal.fit(log_odds_train, y_train)
            
            X_val_clipped = np.clip(X_val, 1e-6, 1 - 1e-6)
            log_odds_val = np.log(X_val_clipped / (1 - X_val_clipped)).reshape(-1, 1)
            oof_probs[val_idx] = cal.predict_proba(log_odds_val)[:, 1]
    
    # Fit on all data for final calibrator
    if method == 'isotonic':
        final_cal = IsotonicRegression(out_of_bounds='clip')
        final_cal.fit(source_probs, y_true)
    else:
        source_clipped = np.clip(source_probs, 1e-6, 1 - 1e-6)
        log_odds = np.log(source_clipped / (1 - source_clipped)).reshape(-1, 1)
        final_cal = LogisticRegression(solver='lbfgs', max_iter=1000)
        final_cal.fit(log_odds, y_true)
    
    return oof_probs, final_cal


def main():
    print("=" * 80)
    print("BBL Per-Over Calibrator Comparison: Isotonic vs Platt")
    print("=" * 80)
    
    # Load data
    df = pd.read_parquet('data/bbl_features_v2/training.parquet')
    model = joblib.load('models/bbl_v10/champion_model.joblib')
    iso_cal = joblib.load('models/bbl_v10/isotonic_calibrator.pkl')
    
    print(f"Total samples: {len(df):,}")
    
    # Get feature columns
    feature_cols = [c for c in df.columns if c not in ['is_winner', 'match_id', 'ball_id']]
    
    # Get predictions
    X = df[feature_cols]
    y = df['is_winner'].values
    raw_probs = model.predict_proba(X)[:, 1]
    
    # Get innings-specific calibrated probs
    cal_probs = np.zeros(len(df))
    for innings in [1, 2]:
        mask = df['innings'] == innings
        if innings in iso_cal:
            cal_probs[mask] = iso_cal[innings].predict(raw_probs[mask])
        else:
            cal_probs[mask] = raw_probs[mask]
    
    # Derive over from overs_remaining
    df['over'] = (20 - df['overs_remaining']).apply(lambda x: min(20, max(1, int(np.ceil(x)))))
    
    # BBL source strategy (from analysis):
    # Inn1: Raw for all overs
    # Inn2: PP(1-6)=Cal, Mid(7-15)=varies, Death(16-20)=Raw
    def get_source(innings, over):
        if innings == 1:
            return 'raw'
        else:  # innings 2
            if over <= 6:
                return 'cal'
            elif over <= 15:
                return 'cal'  # Middle overs - cal is usually better
            else:
                return 'raw'  # Death overs
    
    results = []
    hybrid_calibrators = {}
    
    print()
    print(f"{'Over':<15} {'N':>6} {'Source':<6} {'Raw Brier':>10} {'Iso Brier':>10} {'Platt Brier':>10} {'Winner':<10}")
    print("-" * 80)
    
    for innings in [1, 2]:
        for over in range(1, 21):
            key = f'inn{innings}_over{over}'
            
            # Get data for this over
            mask = (df['innings'] == innings) & (df['over'] == over)
            over_df = df[mask]
            n_samples = len(over_df)
            
            if n_samples < 100:
                print(f'{key:<15} {n_samples:>6} SKIP - insufficient data')
                hybrid_calibrators[key] = {
                    'source': 'raw',
                    'calibrator': None,
                    'method': 'none',
                    'n_samples': n_samples
                }
                continue
            
            # Get source probabilities
            source = get_source(innings, over)
            if source == 'raw':
                source_probs = raw_probs[mask]
            else:
                source_probs = cal_probs[mask]
            
            y_over = over_df['is_winner'].values
            
            # Baseline: raw source Brier
            raw_brier = brier_score(y_over, source_probs)
            
            # Train isotonic with OOF
            try:
                iso_oof, iso_cal_fitted = train_and_evaluate_oof(source_probs, y_over, 'isotonic')
                iso_brier = brier_score(y_over, iso_oof)
            except Exception as e:
                iso_brier = 999
                iso_cal_fitted = None
            
            # Train Platt with OOF
            try:
                platt_oof, platt_cal_fitted = train_and_evaluate_oof(source_probs, y_over, 'platt')
                platt_brier = brier_score(y_over, platt_oof)
            except Exception as e:
                platt_brier = 999
                platt_cal_fitted = None
            
            # Determine winner
            # Rule: Pick method with lowest Brier that doesn't increase vs raw
            candidates = [
                ('none', raw_brier, None),
                ('isotonic', iso_brier, iso_cal_fitted),
                ('platt', platt_brier, platt_cal_fitted)
            ]
            
            # Sort by Brier (ascending)
            candidates.sort(key=lambda x: x[1])
            
            winner_method, winner_brier, winner_cal = candidates[0]
            
            # If calibration increases Brier vs raw, use raw
            if winner_method != 'none' and winner_brier > raw_brier + 0.001:
                winner_method = 'none'
                winner_cal = None
            
            print(f'{key:<15} {n_samples:>6} {source:<6} {raw_brier:>10.4f} {iso_brier:>10.4f} {platt_brier:>10.4f} {winner_method:<10}')
            
            hybrid_calibrators[key] = {
                'source': source,
                'calibrator': winner_cal,
                'method': winner_method,
                'n_samples': n_samples,
                'raw_brier': raw_brier,
                'iso_brier': iso_brier,
                'platt_brier': platt_brier
            }
            
            results.append({
                'key': key,
                'innings': innings,
                'over': over,
                'n_samples': n_samples,
                'source': source,
                'raw_brier': raw_brier,
                'iso_brier': iso_brier,
                'platt_brier': platt_brier,
                'winner': winner_method
            })
    
    # Summary
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    results_df = pd.DataFrame(results)
    
    winner_counts = results_df['winner'].value_counts()
    print(f"\nMethod selection counts:")
    for method, count in winner_counts.items():
        print(f"  {method}: {count} overs")
    
    # Average Brier by method
    print(f"\nAverage Brier scores:")
    print(f"  Raw:      {results_df['raw_brier'].mean():.4f}")
    print(f"  Isotonic: {results_df['iso_brier'].mean():.4f}")
    print(f"  Platt:    {results_df['platt_brier'].mean():.4f}")
    
    # Save hybrid calibrators
    output_path = Path('models/bbl_v10/per_over_calibrators_hybrid.pkl')
    joblib.dump(hybrid_calibrators, output_path)
    print(f"\nSaved hybrid calibrators to {output_path}")
    
    # Also save pure Platt for comparison
    platt_only = {}
    for key, info in hybrid_calibrators.items():
        if info['n_samples'] < 100:
            platt_only[key] = {'source': 'raw', 'calibrator': None, 'method': 'none', 'n_samples': info['n_samples']}
        else:
            # Re-train Platt on all data
            mask = (df['innings'] == int(key[3])) & (df['over'] == int(key.split('_over')[1]))
            over_df = df[mask]
            source = info['source']
            if source == 'raw':
                source_probs = raw_probs[mask]
            else:
                source_probs = cal_probs[mask]
            
            source_clipped = np.clip(source_probs, 1e-6, 1 - 1e-6)
            log_odds = np.log(source_clipped / (1 - source_clipped)).reshape(-1, 1)
            platt = LogisticRegression(solver='lbfgs', max_iter=1000)
            platt.fit(log_odds, over_df['is_winner'].values)
            
            platt_only[key] = {
                'source': source,
                'calibrator': platt,
                'method': 'platt',
                'n_samples': info['n_samples']
            }
    
    platt_path = Path('models/bbl_v10/per_over_calibrators_platt.pkl')
    joblib.dump(platt_only, platt_path)
    print(f"Saved Platt-only calibrators to {platt_path}")
    
    print()
    print("Recommendation:")
    if winner_counts.get('isotonic', 0) > winner_counts.get('platt', 0):
        print("  -> Use HYBRID (per_over_calibrators_hybrid.pkl) - isotonic wins more overs")
    else:
        print("  -> Use PLATT-ONLY (per_over_calibrators_platt.pkl) - smoother, less overfitting risk")


if __name__ == '__main__':
    main()
