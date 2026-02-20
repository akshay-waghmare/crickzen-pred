"""
Compare Isotonic vs Platt scaling per-over calibrators for all leagues.
Evaluates SSM, SSM Female, and SA20.
"""

import pandas as pd
import numpy as np
import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.isotonic import IsotonicRegression
from sklearn.model_selection import KFold
from pathlib import Path
import sys


def brier_score(y_true, y_pred):
    return np.mean((y_true - y_pred) ** 2)


def train_and_evaluate_oof(source_probs, y_true, method='isotonic', n_splits=5):
    """Train calibrator with OOF evaluation."""
    if len(source_probs) < n_splits * 10:
        n_splits = max(2, len(source_probs) // 10)
    
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


def analyze_league(league_name, features_path, model_path, iso_cal_path, output_dir):
    """Analyze a single league and save results."""
    print()
    print("=" * 80)
    print(f"{league_name} Per-Over Calibrator Comparison: Isotonic vs Platt")
    print("=" * 80)
    
    # Load data
    try:
        df = pd.read_parquet(features_path)
        model = joblib.load(model_path)
        iso_cal = joblib.load(iso_cal_path)
    except Exception as e:
        print(f"Error loading data for {league_name}: {e}")
        return None
    
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
    
    # Default source strategy
    def get_source(innings, over):
        if innings == 1:
            return 'raw'
        else:
            if over <= 6:
                return 'cal'
            else:
                return 'raw'
    
    results = []
    hybrid_calibrators = {}
    iso_wins = 0
    platt_wins = 0
    none_wins = 0
    
    print()
    print(f"{'Over':<15} {'N':>6} {'Source':<6} {'Raw Brier':>10} {'Iso Brier':>10} {'Platt Brier':>10} {'Winner':<10}")
    print("-" * 80)
    
    for innings in [1, 2]:
        for over in range(1, 21):
            key = f'inn{innings}_over{over}'
            
            mask = (df['innings'] == innings) & (df['over'] == over)
            over_df = df[mask]
            n_samples = len(over_df)
            
            if n_samples < 50:
                print(f'{key:<15} {n_samples:>6} SKIP - insufficient data')
                hybrid_calibrators[key] = {
                    'source': 'raw', 'calibrator': None, 'method': 'none', 'n_samples': n_samples
                }
                continue
            
            source = get_source(innings, over)
            if source == 'raw':
                source_probs = raw_probs[mask]
            else:
                source_probs = cal_probs[mask]
            
            y_over = over_df['is_winner'].values
            raw_brier = brier_score(y_over, source_probs)
            
            # Train isotonic
            try:
                iso_oof, iso_cal_fitted = train_and_evaluate_oof(source_probs, y_over, 'isotonic')
                iso_brier = brier_score(y_over, iso_oof)
            except:
                iso_brier = 999
                iso_cal_fitted = None
            
            # Train Platt
            try:
                platt_oof, platt_cal_fitted = train_and_evaluate_oof(source_probs, y_over, 'platt')
                platt_brier = brier_score(y_over, platt_oof)
            except:
                platt_brier = 999
                platt_cal_fitted = None
            
            # Determine winner
            candidates = [
                ('none', raw_brier, None),
                ('isotonic', iso_brier, iso_cal_fitted),
                ('platt', platt_brier, platt_cal_fitted)
            ]
            candidates.sort(key=lambda x: x[1])
            winner_method, winner_brier, winner_cal = candidates[0]
            
            if winner_method != 'none' and winner_brier > raw_brier + 0.001:
                winner_method = 'none'
                winner_cal = None
            
            if winner_method == 'isotonic':
                iso_wins += 1
            elif winner_method == 'platt':
                platt_wins += 1
            else:
                none_wins += 1
            
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
                'key': key, 'innings': innings, 'over': over, 'n_samples': n_samples,
                'source': source, 'raw_brier': raw_brier, 'iso_brier': iso_brier,
                'platt_brier': platt_brier, 'winner': winner_method
            })
    
    # Summary
    print()
    print("=" * 80)
    print(f"{league_name} SUMMARY")
    print("=" * 80)
    
    results_df = pd.DataFrame(results)
    
    print(f"\nMethod selection counts:")
    print(f"  isotonic: {iso_wins} overs")
    print(f"  platt: {platt_wins} overs")
    print(f"  none (raw): {none_wins} overs")
    
    avg_samples = results_df['n_samples'].mean()
    print(f"\nAverage samples per over: {avg_samples:.0f}")
    
    print(f"\nAverage Brier scores:")
    print(f"  Raw:      {results_df['raw_brier'].mean():.4f}")
    print(f"  Isotonic: {results_df['iso_brier'].mean():.4f}")
    print(f"  Platt:    {results_df['platt_brier'].mean():.4f}")
    
    # Save hybrid
    hybrid_path = Path(output_dir) / 'per_over_calibrators_hybrid.pkl'
    joblib.dump(hybrid_calibrators, hybrid_path)
    print(f"\nSaved hybrid calibrators to {hybrid_path}")
    
    # Save Platt-only
    platt_only = {}
    for key, info in hybrid_calibrators.items():
        if info['n_samples'] < 50:
            platt_only[key] = {'source': 'raw', 'calibrator': None, 'method': 'none', 'n_samples': info['n_samples']}
        else:
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
                'source': source, 'calibrator': platt, 'method': 'platt', 'n_samples': info['n_samples']
            }
    
    platt_path = Path(output_dir) / 'per_over_calibrators_platt.pkl'
    joblib.dump(platt_only, platt_path)
    print(f"Saved Platt-only calibrators to {platt_path}")
    
    # Recommendation
    print()
    if avg_samples >= 2000:
        recommendation = "ISOTONIC (high sample count)"
    elif iso_wins > platt_wins * 1.5:
        recommendation = "HYBRID (isotonic wins significantly more)"
    else:
        recommendation = "PLATT (safer with moderate/low samples)"
    
    print(f"RECOMMENDATION: {recommendation}")
    
    return {
        'league': league_name,
        'total_samples': len(df),
        'avg_samples_per_over': avg_samples,
        'iso_wins': iso_wins,
        'platt_wins': platt_wins,
        'none_wins': none_wins,
        'recommendation': recommendation
    }


def main():
    leagues = [
        {
            'name': 'SSM (Men)',
            'features': 'data/ssm_features_v1/training.parquet',
            'model': 'models/ssm_v1/champion_model.joblib',
            'iso_cal': 'models/ssm_v1/isotonic_calibrator.pkl',
            'output': 'models/ssm_v1'
        },
        {
            'name': 'SSM Female',
            'features': 'data/ssm_female_features_v1/training.parquet',
            'model': 'models/ssm_female_v1/champion_model.joblib',
            'iso_cal': 'models/ssm_female_v1/isotonic_calibrator.pkl',
            'output': 'models/ssm_female_v1'
        },
        {
            'name': 'SA20',
            'features': 'data/sat_features_v1/training.parquet',
            'model': 'models/sat_v1/champion_model.joblib',
            'iso_cal': 'models/sat_v1/isotonic_calibrator.pkl',
            'output': 'models/sat_v1'
        }
    ]
    
    all_results = []
    
    for league in leagues:
        result = analyze_league(
            league['name'],
            league['features'],
            league['model'],
            league['iso_cal'],
            league['output']
        )
        if result:
            all_results.append(result)
    
    # Final summary
    print()
    print("=" * 80)
    print("FINAL SUMMARY - ALL LEAGUES")
    print("=" * 80)
    print()
    print(f"{'League':<15} {'Samples':>10} {'Avg/Over':>10} {'Iso Wins':>10} {'Platt Wins':>12} {'Recommendation':<25}")
    print("-" * 90)
    
    for r in all_results:
        print(f"{r['league']:<15} {r['total_samples']:>10,} {r['avg_samples_per_over']:>10.0f} {r['iso_wins']:>10} {r['platt_wins']:>12} {r['recommendation']:<25}")


if __name__ == '__main__':
    main()
