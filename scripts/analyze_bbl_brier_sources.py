"""
BBL Brier Analysis: Compare Raw, Resource, and Innings-Calibrated probabilities.

This script analyzes which probability source gives the best Brier score
for each innings × over combination, then creates Brier-optimized calibrators.
"""

import pandas as pd
import numpy as np
import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.isotonic import IsotonicRegression
from sklearn.model_selection import KFold
from pathlib import Path


def brier_score(y_true, y_pred):
    return np.mean((y_true - y_pred) ** 2)


def train_calibrator_oof(source_probs, y_true, method='isotonic', n_splits=5):
    """Train calibrator with OOF evaluation."""
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
    
    # Fit on all data
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
    print("=" * 90)
    print("BBL Brier Analysis: Raw vs Resource vs Innings-Calibrated")
    print("=" * 90)
    
    # Load data
    df = pd.read_parquet('data/bbl_features_v2/training.parquet')
    model = joblib.load('models/bbl_v10/champion_model.joblib')
    iso_cal = joblib.load('models/bbl_v10/isotonic_calibrator.pkl')
    
    print(f"Total samples: {len(df):,}")
    
    # Get feature columns
    feature_cols = [c for c in df.columns if c not in ['is_winner', 'match_id', 'ball_id']]
    
    # Get all probability types
    X = df[feature_cols]
    y = df['is_winner'].values
    
    raw_probs = model.predict_proba(X)[:, 1]
    resource_probs = df['resource_win_prob'].values if 'resource_win_prob' in df.columns else raw_probs
    
    # Innings-specific calibrated
    inn_cal_probs = np.zeros(len(df))
    for innings in [1, 2]:
        mask = df['innings'] == innings
        if innings in iso_cal:
            inn_cal_probs[mask] = iso_cal[innings].predict(raw_probs[mask])
        else:
            inn_cal_probs[mask] = raw_probs[mask]
    
    # Derive over
    df['over'] = (20 - df['overs_remaining']).apply(lambda x: min(20, max(1, int(np.ceil(x)))))
    
    print()
    print("PART 1: Source Comparison (Raw Brier - No Additional Calibration)")
    print("=" * 90)
    print(f"{'Over':<12} {'N':>6} | {'Raw':>8} {'Resource':>10} {'Inn-Cal':>10} | {'Best Source':<12} {'Δ vs Raw':>10}")
    print("-" * 90)
    
    source_analysis = []
    
    for innings in [1, 2]:
        for over in range(1, 21):
            mask = (df['innings'] == innings) & (df['over'] == over)
            n = mask.sum()
            if n < 100:
                continue
            
            y_over = y[mask]
            
            # Brier for each source (uncalibrated)
            raw_brier = brier_score(y_over, raw_probs[mask])
            res_brier = brier_score(y_over, resource_probs[mask])
            cal_brier = brier_score(y_over, inn_cal_probs[mask])
            
            # Find best
            sources = [('raw', raw_brier), ('resource', res_brier), ('inn_cal', cal_brier)]
            sources.sort(key=lambda x: x[1])
            best_source, best_brier = sources[0]
            delta = raw_brier - best_brier
            
            key = f'inn{innings}_over{over}'
            print(f'{key:<12} {n:>6} | {raw_brier:>8.4f} {res_brier:>10.4f} {cal_brier:>10.4f} | {best_source:<12} {delta:>+10.4f}')
            
            source_analysis.append({
                'key': key, 'innings': innings, 'over': over, 'n': n,
                'raw_brier': raw_brier, 'res_brier': res_brier, 'cal_brier': cal_brier,
                'best_source': best_source, 'delta': delta
            })
    
    # Summary by innings
    print()
    print("Source Summary by Innings:")
    df_analysis = pd.DataFrame(source_analysis)
    for innings in [1, 2]:
        inn_df = df_analysis[df_analysis['innings'] == innings]
        source_counts = inn_df['best_source'].value_counts()
        print(f"  Innings {innings}: {dict(source_counts)}")
    
    # Overall averages
    print()
    print("Overall Average Brier (unweighted by over):")
    print(f"  Raw:      {df_analysis['raw_brier'].mean():.4f}")
    print(f"  Resource: {df_analysis['res_brier'].mean():.4f}")
    print(f"  Inn-Cal:  {df_analysis['cal_brier'].mean():.4f}")
    
    # PART 2: Create Brier-optimized calibrators
    print()
    print("=" * 90)
    print("PART 2: Creating Brier-Optimized Per-Over Calibrators")
    print("=" * 90)
    
    brier_calibrators = {}
    
    print(f"{'Over':<12} {'N':>6} | {'Best Src':<10} {'Src Brier':>10} {'+Iso':>10} {'+Platt':>10} {'Final':>10} {'Method':<10}")
    print("-" * 100)
    
    for row in source_analysis:
        key = row['key']
        innings = row['innings']
        over = row['over']
        best_source = row['best_source']
        
        mask = (df['innings'] == innings) & (df['over'] == over)
        y_over = y[mask]
        
        # Get the best source probabilities
        if best_source == 'raw':
            source_probs = raw_probs[mask]
            src_brier = row['raw_brier']
        elif best_source == 'resource':
            source_probs = resource_probs[mask]
            src_brier = row['res_brier']
        else:  # inn_cal
            source_probs = inn_cal_probs[mask]
            src_brier = row['cal_brier']
        
        # Try calibrating with isotonic
        try:
            iso_oof, iso_cal = train_calibrator_oof(source_probs, y_over, 'isotonic')
            iso_brier = brier_score(y_over, iso_oof)
        except:
            iso_brier = 999
            iso_cal = None
        
        # Try calibrating with Platt
        try:
            platt_oof, platt_cal = train_calibrator_oof(source_probs, y_over, 'platt')
            platt_brier = brier_score(y_over, platt_oof)
        except:
            platt_brier = 999
            platt_cal = None
        
        # Pick best method
        candidates = [
            ('none', src_brier, None),
            ('isotonic', iso_brier, iso_cal),
            ('platt', platt_brier, platt_cal)
        ]
        candidates.sort(key=lambda x: x[1])
        method, final_brier, calibrator = candidates[0]
        
        print(f'{key:<12} {row["n"]:>6} | {best_source:<10} {src_brier:>10.4f} {iso_brier:>10.4f} {platt_brier:>10.4f} {final_brier:>10.4f} {method:<10}')
        
        brier_calibrators[key] = {
            'source': best_source,
            'calibrator': calibrator,
            'method': method,
            'n_samples': row['n'],
            'source_brier': src_brier,
            'final_brier': final_brier
        }
    
    # Save Brier-optimized calibrators
    output_path = Path('models/bbl_v10/per_over_calibrators_brier.pkl')
    joblib.dump(brier_calibrators, output_path)
    print()
    print(f"Saved Brier-optimized calibrators to {output_path}")
    
    # PART 3: Summary comparison
    print()
    print("=" * 90)
    print("PART 3: Final Comparison")
    print("=" * 90)
    
    # Calculate overall improvement
    total_src_brier = sum(info['source_brier'] * info['n_samples'] for info in brier_calibrators.values())
    total_final_brier = sum(info['final_brier'] * info['n_samples'] for info in brier_calibrators.values())
    total_samples = sum(info['n_samples'] for info in brier_calibrators.values())
    
    weighted_src = total_src_brier / total_samples
    weighted_final = total_final_brier / total_samples
    
    print(f"Weighted Brier Scores:")
    print(f"  Best source (uncalibrated):  {weighted_src:.4f}")
    print(f"  After per-over calibration:  {weighted_final:.4f}")
    print(f"  Improvement:                 {(weighted_src - weighted_final) / weighted_src * 100:.1f}%")
    
    # Source distribution
    print()
    print("Source distribution in Brier-optimized calibrators:")
    source_counts = pd.Series([info['source'] for info in brier_calibrators.values()]).value_counts()
    for src, count in source_counts.items():
        print(f"  {src}: {count} overs")
    
    # Method distribution
    print()
    print("Calibration method distribution:")
    method_counts = pd.Series([info['method'] for info in brier_calibrators.values()]).value_counts()
    for method, count in method_counts.items():
        print(f"  {method}: {count} overs")


if __name__ == '__main__':
    main()
