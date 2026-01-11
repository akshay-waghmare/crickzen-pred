"""
Calculate SA20 calibration metrics (Brier, ECE, Log Loss) by inning and over.
Compares: Raw model, ECE-optimized, Resource-based probabilities.

Usage:
    python scripts/calculate_sa20_metrics.py

Output:
    - Saves metrics to data/sa20_metrics.parquet
    - Prints summary tables
"""

import pandas as pd
import numpy as np
import joblib
from pathlib import Path

# Helper functions
def brier_score(y_true, y_pred):
    """Calculate Brier Score (lower is better)"""
    return np.mean((y_true - y_pred) ** 2)

def ece(y_true, y_pred, n_bins=10):
    """Expected Calibration Error (lower is better)"""
    total_ece = 0.0
    for bin_idx in range(n_bins):
        bin_lower = bin_idx / n_bins
        bin_upper = (bin_idx + 1) / n_bins
        in_bin = (y_pred >= bin_lower) & (y_pred < bin_upper)
        if in_bin.sum() == 0:
            continue
        prob_true = y_true[in_bin].mean()
        prob_pred = y_pred[in_bin].mean()
        ece_bin = abs(prob_true - prob_pred)
        weight = in_bin.sum() / len(y_true)
        total_ece += weight * ece_bin
    return total_ece

def log_loss(y_true, y_pred):
    """Log Loss / Crossentropy (lower is better)"""
    y_pred = np.clip(y_pred, 1e-15, 1 - 1e-15)
    return -np.mean(y_true * np.log(y_pred) + (1 - y_true) * np.log(1 - y_pred))

def load_data():
    """Load SA20 training data and models"""
    print("Loading SA20 training data...")
    df = pd.read_parquet('data/sat_features_v1/training.parquet')
    
    print(f"  - {len(df):,} samples")
    print(f"  - Loaded features")
    
    # Load model
    print("\nLoading SA20 model...")
    model = joblib.load('models/sat_v1/champion_model.joblib')
    print(f"  - Model loaded, {len(model.selected_features_)} features")
    
    # Load calibrators
    print("Loading calibrators...")
    phase_cals = joblib.load('models/sat_v1/phase_calibrators.pkl')
    per_over_cals = joblib.load('models/sat_v1/per_over_calibrators.pkl')
    inn_specific_cals = joblib.load('models/sat_v1/isotonic_calibrator.pkl')
    print(f"  - Phase calibrators: {len(phase_cals)} keys")
    print(f"  - Per-over calibrators: {len(per_over_cals)} keys")
    print(f"  - Inn-specific calibrators: inn1 + inn2")
    
    return df, model, phase_cals, per_over_cals, inn_specific_cals

def apply_calibrators(df, model, phase_cals, per_over_cals, inn_specific_cals):
    """Apply calibrators to get all probability versions"""
    print("\nApplying calibrators...")
    
    features = model.selected_features_
    
    # Get raw probabilities from model
    raw_probs = model.predict_proba(df[features])[:, 1]
    print(f"  - Raw probabilities computed")
    
    # Resource-based (from features)
    resource_probs = df['resource_win_prob'].values
    
    # Get phase for each row (SA20 uses 4-phase system)
    df['over'] = (20 - df['overs_remaining']).clip(1, 20).astype(int)
    df['phase'] = df['over'].apply(lambda o: 'powerplay' if o <= 6 else ('middle_early' if o <= 12 else ('middle_late' if o <= 15 else 'death')))
    
    # Inn-specific calibrated probabilities (1 calibrator per innings)
    inn1_cal = inn_specific_cals['calibrator_innings1']
    inn2_cal = inn_specific_cals['calibrator_innings2']
    
    inn_specific_probs = []
    for i in range(len(df)):
        inn = int(df.iloc[i]['innings'])
        raw_prob = raw_probs[i]
        if inn == 1:
            inn_specific_probs.append(np.clip(inn1_cal.predict([[raw_prob]])[0], 0.01, 0.99))
        else:
            inn_specific_probs.append(np.clip(inn2_cal.predict([[raw_prob]])[0], 0.01, 0.99))
    inn_specific_probs = np.array(inn_specific_probs)
    print(f"  - Inn-specific calibrated probabilities")
    
    # Phase-calibrated probabilities (ECE-optimized, using Platt scaling if available)
    # SA20 uses 4-phase system: powerplay, middle_early, middle_late, death
    phase_probs = []
    calibrator_applied = 0
    calibrator_fallback = 0
    for i in range(len(df)):
        inn = int(df.iloc[i]['innings'])
        phase = df.iloc[i]['phase']  # Already 4-phase: powerplay, middle_early, middle_late, death
        calibrator_key = f'inn{inn}_{phase}'
        
        if calibrator_key in phase_cals:
            cal_info = phase_cals[calibrator_key]
            calibrator_applied += 1
            # Check if dict (new Platt format) or direct calibrator (isotonic)
            if isinstance(cal_info, dict) and 'calibrator' in cal_info:
                cal = cal_info['calibrator']
                # Platt scaling - convert to logits
                input_clipped = np.clip(raw_probs[i], 0.001, 0.999)
                logit = np.log(input_clipped / (1 - input_clipped))
                phase_probs.append(np.clip(cal.predict_proba([[logit]])[0, 1], 0.01, 0.99))
            else:
                # Isotonic
                phase_probs.append(np.clip(cal_info.predict([[raw_probs[i]]])[0], 0.01, 0.99))
        else:
            calibrator_fallback += 1
            phase_probs.append(raw_probs[i])
    
    phase_probs = np.array(phase_probs)
    print(f"  - Phase calibrated probabilities: {calibrator_applied} applied, {calibrator_fallback} fallback to raw")
    
    return raw_probs, inn_specific_probs, resource_probs, phase_probs

def compute_metrics_by_inning(df, y_true, raw_probs, inn_specific_probs, resource_probs, phase_probs):
    """Compute metrics by inning"""
    print("\n" + "="*80)
    print("METRICS BY INNING")
    print("="*80)
    
    results = []
    for inn in [1, 2]:
        mask = df['innings'] == inn
        y = y_true[mask]
        raw = raw_probs[mask]
        inn_spec = inn_specific_probs[mask]
        res = resource_probs[mask]
        phase = phase_probs[mask]
        
        result = {
            'Group': f'Innings {inn}',
            'N': mask.sum(),
            'Brier_Raw': brier_score(y, raw),
            'Brier_InnSpec': brier_score(y, inn_spec),
            'Brier_Resource': brier_score(y, res),
            'Brier_Phase': brier_score(y, phase),
            'ECE_Raw': ece(y, raw),
            'ECE_InnSpec': ece(y, inn_spec),
            'ECE_Resource': ece(y, res),
            'ECE_Phase': ece(y, phase),
            'LogLoss_Raw': log_loss(y, raw),
            'LogLoss_InnSpec': log_loss(y, inn_spec),
            'LogLoss_Resource': log_loss(y, res),
            'LogLoss_Phase': log_loss(y, phase),
        }
        results.append(result)
        
        print(f"\n📊 Innings {inn} ({mask.sum():,} samples)")
        print(f"  Brier:   Raw={result['Brier_Raw']:.4f}, InnSpec={result['Brier_InnSpec']:.4f}, Resource={result['Brier_Resource']:.4f}, Phase={result['Brier_Phase']:.4f}")
        print(f"  ECE:     Raw={result['ECE_Raw']:.4f}, InnSpec={result['ECE_InnSpec']:.4f}, Resource={result['ECE_Resource']:.4f}, Phase={result['ECE_Phase']:.4f}")
        print(f"  LL:      Raw={result['LogLoss_Raw']:.4f}, InnSpec={result['LogLoss_InnSpec']:.4f}, Resource={result['LogLoss_Resource']:.4f}, Phase={result['LogLoss_Phase']:.4f}")
    
    return pd.DataFrame(results)

def compute_metrics_by_over(df, y_true, raw_probs, inn_specific_probs, resource_probs, phase_probs):
    """Compute metrics by inning and over"""
    print("\n" + "="*80)
    print("METRICS BY INNING & OVER")
    print("="*80)
    
    results = []
    for inn in [1, 2]:
        print(f"\n📍 Innings {inn}:")
        print(f"{'Over':<6} {'N':<6} {'B_Raw':<8} {'B_Inn':<8} {'B_Res':<8} {'B_Phase':<8} {'E_Raw':<8} {'E_Inn':<8} {'E_Res':<8} {'E_Phase':<8}")
        print("-" * 90)
        
        for over in range(1, 21):
            mask = (df['innings'] == inn) & (df['over'] == over)
            if mask.sum() == 0:
                continue
            
            y = y_true[mask]
            raw = raw_probs[mask]
            inn_spec = inn_specific_probs[mask]
            res = resource_probs[mask]
            phase = phase_probs[mask]
            
            result = {
                'Innings': inn,
                'Over': over,
                'N': mask.sum(),
                'Brier_Raw': brier_score(y, raw),
                'Brier_InnSpec': brier_score(y, inn_spec),
                'Brier_Resource': brier_score(y, res),
                'Brier_Phase': brier_score(y, phase),
                'ECE_Raw': ece(y, raw),
                'ECE_InnSpec': ece(y, inn_spec),
                'ECE_Resource': ece(y, res),
                'ECE_Phase': ece(y, phase),
                'LogLoss_Raw': log_loss(y, raw),
                'LogLoss_InnSpec': log_loss(y, inn_spec),
                'LogLoss_Resource': log_loss(y, res),
                'LogLoss_Phase': log_loss(y, phase),
            }
            results.append(result)
            
            print(f"Over {over:<1} {mask.sum():<6} {result['Brier_Raw']:<8.4f} {result['Brier_InnSpec']:<8.4f} {result['Brier_Resource']:<8.4f} {result['Brier_Phase']:<8.4f} "
                  f"{result['ECE_Raw']:<8.4f} {result['ECE_InnSpec']:<8.4f} {result['ECE_Resource']:<8.4f} {result['ECE_Phase']:<8.4f}")
    
    return pd.DataFrame(results)

def compute_metrics_by_phase(df, y_true, raw_probs, inn_specific_probs, resource_probs, phase_probs):
    """Compute metrics by inning and phase"""
    print("\n" + "="*80)
    print("METRICS BY INNING & PHASE")
    print("="*80)
    
    results = []
    for inn in [1, 2]:
        print(f"\n📍 Innings {inn}:")
        print(f"{'Phase':<15} {'N':<6} {'B_Raw':<8} {'B_Inn':<8} {'B_Res':<8} {'B_Phase':<8} {'E_Raw':<8} {'E_Inn':<8} {'E_Res':<8} {'E_Phase':<8}")
        print("-" * 100)
        
        for phase in ['powerplay', 'middle_early', 'middle_late', 'death']:
            mask = (df['innings'] == inn) & (df['phase'] == phase)
            if mask.sum() == 0:
                continue
            
            y = y_true[mask]
            raw = raw_probs[mask]
            inn_spec = inn_specific_probs[mask]
            res = resource_probs[mask]
            phase_cal = phase_probs[mask]
            
            result = {
                'Innings': inn,
                'Phase': phase,
                'N': mask.sum(),
                'Brier_Raw': brier_score(y, raw),
                'Brier_InnSpec': brier_score(y, inn_spec),
                'Brier_Resource': brier_score(y, res),
                'Brier_Phase': brier_score(y, phase_cal),
                'ECE_Raw': ece(y, raw),
                'ECE_InnSpec': ece(y, inn_spec),
                'ECE_Resource': ece(y, res),
                'ECE_Phase': ece(y, phase_cal),
                'LogLoss_Raw': log_loss(y, raw),
                'LogLoss_InnSpec': log_loss(y, inn_spec),
                'LogLoss_Resource': log_loss(y, res),
                'LogLoss_Phase': log_loss(y, phase_cal),
            }
            results.append(result)
            
            print(f"{phase:<15} {mask.sum():<6} {result['Brier_Raw']:<8.4f} {result['Brier_InnSpec']:<8.4f} {result['Brier_Resource']:<8.4f} {result['Brier_Phase']:<8.4f} "
                  f"{result['ECE_Raw']:<8.4f} {result['ECE_InnSpec']:<8.4f} {result['ECE_Resource']:<8.4f} {result['ECE_Phase']:<8.4f}")
    
    return pd.DataFrame(results)

def main():
    # Load data
    df, model, phase_cals, per_over_cals, inn_specific_cals = load_data()
    
    # Get ground truth
    y_true = df['is_winner'].values
    
    # Apply calibrators
    raw_probs, inn_specific_probs, resource_probs, phase_probs = apply_calibrators(df, model, phase_cals, per_over_cals, inn_specific_cals)
    
    # Convert inn_specific_probs list to numpy array
    inn_specific_probs = np.array(inn_specific_probs)
    
    # Compute metrics
    inning_metrics = compute_metrics_by_inning(df, y_true, raw_probs, inn_specific_probs, resource_probs, phase_probs)
    over_metrics = compute_metrics_by_over(df, y_true, raw_probs, inn_specific_probs, resource_probs, phase_probs)
    phase_metrics = compute_metrics_by_phase(df, y_true, raw_probs, inn_specific_probs, resource_probs, phase_probs)
    
    # Save to parquet
    print("\n" + "="*80)
    print("SAVING RESULTS")
    print("="*80)
    
    metrics_file = Path('data/sa20_metrics.parquet')
    
    # Create a combined metrics file with all three groupings
    combined_metrics = {
        'by_inning': inning_metrics,
        'by_over': over_metrics,
        'by_phase': phase_metrics,
    }
    
    # Save each to separate sheets (using parquet partitioning)
    for group_name, group_df in combined_metrics.items():
        group_df.to_parquet(f'data/sa20_metrics_{group_name}.parquet', index=False)
        print(f"✅ Saved: data/sa20_metrics_{group_name}.parquet")
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(inning_metrics.to_string(index=False))
    
    print("\n✅ Metrics calculation complete!")

if __name__ == "__main__":
    main()
