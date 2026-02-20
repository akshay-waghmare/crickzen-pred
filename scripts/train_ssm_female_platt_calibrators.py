"""
Train Platt-scaled per-over calibrators for SSM Female model.

Platt scaling uses logistic regression on log-odds, which is smoother
and less prone to overfitting than isotonic regression on sparse data.
"""

import pandas as pd
import numpy as np
import joblib
from sklearn.linear_model import LogisticRegression
from pathlib import Path


def main():
    # Load data
    df = pd.read_parquet('data/ssm_female_features_v1/training.parquet')
    model = joblib.load('models/ssm_female_v1/champion_model.joblib')
    iso_cal = joblib.load('models/ssm_female_v1/isotonic_calibrator.pkl')
    
    # Get feature columns
    feature_cols = [c for c in df.columns if c not in ['is_winner', 'match_id', 'ball_id']]
    
    print('Training Platt-scaled per-over calibrators for SSM Female...')
    print('=' * 70)
    
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
    
    # SSM Female source strategy: Inn1=Raw, Inn2 PP=Cal, Inn2 Mid+Death=Raw
    def get_source_probs(row_innings, row_over, raw_p, cal_p):
        if row_innings == 1:
            return raw_p  # Inn1 always Raw
        else:  # Inn2
            if row_over <= 6:
                return cal_p  # Inn2 PP uses Cal
            else:
                return raw_p  # Inn2 Mid+Death uses Raw
    
    platt_calibrators = {}
    
    for innings in [1, 2]:
        for over in range(1, 21):
            key = f'inn{innings}_over{over}'
            
            # Get data for this over
            mask = (df['innings'] == innings) & (df['over'] == over)
            over_df = df[mask]
            
            if len(over_df) < 50:
                print(f'{key}: SKIP (only {len(over_df)} samples)')
                platt_calibrators[key] = {'source': 'raw', 'calibrator': None, 'n_samples': len(over_df)}
                continue
            
            # Get source probabilities based on strategy
            source = 'raw' if innings == 1 or over > 6 else 'cal'
            source_probs = np.array([
                get_source_probs(innings, over, raw_probs[i], cal_probs[i])
                for i in over_df.index
            ])
            
            y_over = over_df['is_winner'].values
            
            # Train Platt scaling (logistic regression on log-odds)
            # Clip to avoid log(0)
            source_probs_clipped = np.clip(source_probs, 1e-6, 1 - 1e-6)
            log_odds = np.log(source_probs_clipped / (1 - source_probs_clipped)).reshape(-1, 1)
            
            platt = LogisticRegression(solver='lbfgs', max_iter=1000)
            platt.fit(log_odds, y_over)
            
            # Test calibration at key points
            test_probs = [0.3, 0.5, 0.7]
            test_results = []
            for p in test_probs:
                p_clipped = np.clip(p, 1e-6, 1 - 1e-6)
                lo = np.log(p_clipped / (1 - p_clipped)).reshape(-1, 1)
                calibrated = platt.predict_proba(lo)[0, 1]
                test_results.append(f'{p:.0%}->{calibrated:.0%}')
            
            print(f'{key}: n={len(over_df):4d}, source={source}, tests: {" | ".join(test_results)}')
            
            platt_calibrators[key] = {
                'source': source,
                'calibrator': platt,
                'n_samples': len(over_df),
                'method': 'platt'
            }
    
    # Save
    output_path = Path('models/ssm_female_v1/per_over_calibrators_platt.pkl')
    joblib.dump(platt_calibrators, output_path)
    print()
    print(f'Saved {len(platt_calibrators)} Platt-scaled calibrators to {output_path}')
    
    # Compare with isotonic on a few test cases
    print()
    print('Comparison: Isotonic vs Platt at 40% raw probability')
    print('-' * 50)
    
    iso_cal_over = joblib.load('models/ssm_female_v1/per_over_calibrators.pkl')
    
    for key in ['inn1_over18', 'inn2_over18', 'inn2_over1']:
        iso_info = iso_cal_over[key]
        platt_info = platt_calibrators[key]
        
        raw_p = 0.4
        
        # Isotonic
        if iso_info['calibrator'] is not None:
            try:
                iso_result = iso_info['calibrator'].predict([raw_p])[0]
            except:
                iso_result = raw_p
        else:
            iso_result = raw_p
        
        # Platt
        if platt_info['calibrator'] is not None:
            p_clipped = np.clip(raw_p, 1e-6, 1 - 1e-6)
            lo = np.log(p_clipped / (1 - p_clipped)).reshape(-1, 1)
            platt_result = platt_info['calibrator'].predict_proba(lo)[0, 1]
        else:
            platt_result = raw_p
        
        print(f'{key}: Raw 40% -> Isotonic {iso_result:.1%} | Platt {platt_result:.1%}')


if __name__ == '__main__':
    main()
