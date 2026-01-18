"""
Analyze BBL model confidence - check for systematic under/overconfidence.
Focus on second innings easy chase situations.
"""
import pandas as pd
import numpy as np
from pathlib import Path
import joblib
from sklearn.metrics import brier_score_loss
import matplotlib.pyplot as plt

def analyze_confidence_by_probability_bins(y_true, y_pred, n_bins=10):
    """Analyze calibration by probability bins."""
    bins = np.linspace(0, 1, n_bins + 1)
    bin_centers = (bins[:-1] + bins[1:]) / 2
    
    results = []
    for i in range(n_bins):
        bin_mask = (y_pred >= bins[i]) & (y_pred < bins[i + 1])
        if i == n_bins - 1:  # Include 1.0 in last bin
            bin_mask = (y_pred >= bins[i]) & (y_pred <= bins[i + 1])
        
        if bin_mask.sum() == 0:
            continue
        
        bin_true = y_true[bin_mask]
        bin_pred = y_pred[bin_mask]
        
        results.append({
            'Bin': f"{bins[i]:.1f}-{bins[i+1]:.1f}",
            'Bin_Center': bin_centers[i],
            'N': len(bin_true),
            'Mean_Predicted': bin_pred.mean(),
            'Mean_Actual': bin_true.mean(),
            'Difference': bin_true.mean() - bin_pred.mean(),
            'Brier': brier_score_loss(bin_true, bin_pred)
        })
    
    return pd.DataFrame(results)

def main():
    # Load training data and model
    model_dir = Path('models/bbl_v12')
    features_file = Path('data/bbl_features_v4/training.parquet')
    
    print(f"📊 Loading training data from {features_file}")
    df = pd.read_parquet(features_file)
    
    print(f"📊 Loading model from {model_dir}")
    model = joblib.load(model_dir / 'champion_model.joblib')
    calibrators = joblib.load(model_dir / 'isotonic_calibrator.pkl')
    
    print(f"\n📈 Total samples: {len(df):,}")
    
    # Focus on second innings
    df_inn2 = df[df['innings'] == 2].copy()
    print(f"📊 Second innings samples: {len(df_inn2):,}")
    
    # Get raw predictions
    raw_prob = model.predict_proba(df_inn2)[:, 1]
    y_true = df_inn2['is_winner'].values
    
    # Apply phase calibration
    phase_probs = []
    for idx, row in df_inn2.iterrows():
        if row['is_powerplay'] == 1:
            phase_key = 'inn2_powerplay'
        elif row['is_death_overs'] == 1:
            phase_key = 'inn2_death'
        else:
            phase_key = 'inn2_middle'
        
        if phase_key in calibrators['phase_calibrators']:
            cal = calibrators['phase_calibrators'][phase_key]
            phase_probs.append(cal.predict([raw_prob[len(phase_probs)]])[0])
        else:
            phase_probs.append(raw_prob[len(phase_probs)])
    
    phase_probs = np.array(phase_probs)
    
    print("\n" + "="*70)
    print("📊 OVERALL SECOND INNINGS CALIBRATION")
    print("="*70)
    
    print(f"\nActual win rate: {y_true.mean():.1%}")
    print(f"Mean raw prediction: {raw_prob.mean():.1%}")
    print(f"Mean phase calibrated: {phase_probs.mean():.1%}")
    print(f"\nRaw Brier: {brier_score_loss(y_true, raw_prob):.4f}")
    print(f"Phase Brier: {brier_score_loss(y_true, phase_probs):.4f}")
    
    # Analyze by probability bins
    print("\n" + "="*70)
    print("📊 RAW MODEL CALIBRATION BY PROBABILITY BIN")
    print("="*70)
    
    raw_bins = analyze_confidence_by_probability_bins(y_true, raw_prob, n_bins=10)
    print("\n" + raw_bins.to_string(index=False))
    
    print("\n" + "="*70)
    print("📊 PHASE CALIBRATED BY PROBABILITY BIN")
    print("="*70)
    
    phase_bins = analyze_confidence_by_probability_bins(y_true, phase_probs, n_bins=10)
    print("\n" + phase_bins.to_string(index=False))
    
    # Focus on high-probability predictions (>80%)
    print("\n" + "="*70)
    print("🎯 HIGH CONFIDENCE PREDICTIONS (>80%)")
    print("="*70)
    
    high_conf_mask = raw_prob > 0.8
    print(f"\nSamples with raw prob > 80%: {high_conf_mask.sum():,} ({high_conf_mask.sum()/len(raw_prob):.1%})")
    
    if high_conf_mask.sum() > 0:
        high_y = y_true[high_conf_mask]
        high_raw = raw_prob[high_conf_mask]
        high_phase = phase_probs[high_conf_mask]
        
        print(f"Actual win rate: {high_y.mean():.1%}")
        print(f"Mean raw prediction: {high_raw.mean():.1%}")
        print(f"Mean phase calibrated: {high_phase.mean():.1%}")
        print(f"\n{'UNDERCONFIDENT' if high_y.mean() > high_raw.mean() else 'OVERCONFIDENT'} by {abs(high_y.mean() - high_raw.mean()):.1%}")
        print(f"Phase calibration {'INCREASES' if high_phase.mean() > high_raw.mean() else 'DECREASES'} confidence by {abs(high_phase.mean() - high_raw.mean()):.1%}")
    
    # Analyze easy chase situations (RRR < 6, wickets <= 2)
    print("\n" + "="*70)
    print("🏏 EASY CHASE SITUATIONS (RRR < 6, Wickets <= 2)")
    print("="*70)
    
    easy_chase_mask = (df_inn2['required_run_rate'] < 6) & (df_inn2['required_run_rate'] > 0) & (df_inn2['overs_remaining'] > 5)
    
    if 'wickets_lost' in df_inn2.columns:
        easy_chase_mask = easy_chase_mask & (df_inn2['wickets_lost'] <= 2)
    
    print(f"\nEasy chase samples: {easy_chase_mask.sum():,}")
    
    if easy_chase_mask.sum() > 0:
        easy_y = y_true[easy_chase_mask]
        easy_raw = raw_prob[easy_chase_mask]
        easy_phase = phase_probs[easy_chase_mask]
        easy_resource = df_inn2.loc[easy_chase_mask, 'resource_win_prob'].values
        
        print(f"Actual win rate: {easy_y.mean():.1%}")
        print(f"Mean raw prediction: {easy_raw.mean():.1%}")
        print(f"Mean phase calibrated: {easy_phase.mean():.1%}")
        print(f"Mean resource_win_prob: {easy_resource.mean():.1%}")
        print(f"\nRaw Brier: {brier_score_loss(easy_y, easy_raw):.4f}")
        print(f"Phase Brier: {brier_score_loss(easy_y, easy_phase):.4f}")
        print(f"Resource Brier: {brier_score_loss(easy_y, easy_resource):.4f}")
        
        # Save for further analysis
        easy_df = pd.DataFrame({
            'actual': easy_y,
            'raw_prob': easy_raw,
            'phase_prob': easy_phase,
            'resource_prob': easy_resource,
            'rrr': df_inn2.loc[easy_chase_mask, 'required_run_rate'].values,
            'overs_remaining': df_inn2.loc[easy_chase_mask, 'overs_remaining'].values,
        })
        
        output_file = model_dir / 'easy_chase_analysis.csv'
        easy_df.to_csv(output_file, index=False)
        print(f"\n💾 Easy chase analysis saved to {output_file}")

if __name__ == '__main__':
    main()
