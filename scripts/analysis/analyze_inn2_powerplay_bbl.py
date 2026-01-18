"""
Analyze BBL second innings powerplay calibration performance.
Compare resource_win_prob, raw, innings+phase, and brier-optimized methods.
"""
import pandas as pd
import numpy as np
from pathlib import Path
import joblib
from sklearn.metrics import brier_score_loss, log_loss
from sklearn.isotonic import IsotonicRegression

def calculate_metrics(y_true, y_pred, name):
    """Calculate Brier and Log Loss."""
    brier = brier_score_loss(y_true, y_pred)
    logloss = log_loss(y_true, y_pred, labels=[0, 1])
    return {
        'Method': name,
        'Brier': brier,
        'LogLoss': logloss,
        'N': len(y_true)
    }

def main():
    # Load training data and model
    model_dir = Path('models/bbl_v12')
    features_file = Path('data/bbl_features_v4/training.parquet')
    
    print(f"📊 Loading training data from {features_file}")
    df = pd.read_parquet(features_file)
    
    print(f"📊 Loading training data from {features_file}")
    df = pd.read_parquet(features_file)
    
    # Load model and calibrators
    print(f"📊 Loading model from {model_dir}")
    model = joblib.load(model_dir / 'champion_model.joblib')
    calibrators = joblib.load(model_dir / 'isotonic_calibrator.pkl')
    
    print(f"\n📈 Total samples: {len(df):,}")
    
    # Filter for second innings powerplay
    df_inn2_pp = df[(df['innings'] == 2) & (df['is_powerplay'] == 1)].copy()
    
    print(f"\n🎯 Second Innings Powerplay samples: {len(df_inn2_pp):,}")
    
    if len(df_inn2_pp) == 0:
        print("❌ No second innings powerplay samples found!")
        return
    
    # Use all features that model was trained with
    # The model has selected_features_ already
    y_true = df_inn2_pp['is_winner'].values
    
    print(f"Predicting with model's selected features: {len(model.selected_features_)} features")
    
    # Generate raw predictions - model will select the features it needs
    raw_prob = model.predict_proba(df_inn2_pp)[:, 1]
    
    # Apply different calibration methods
    results = []
    
    # 1. Resource win probability (from features)
    if 'resource_win_prob' in df_inn2_pp.columns:
        results.append(calculate_metrics(
            y_true, 
            df_inn2_pp['resource_win_prob'].values,
            'Resource Win Prob (Feature)'
        ))
    
    # 2. Raw probability
    results.append(calculate_metrics(
        y_true,
        raw_prob,
        'Raw Model'
    ))
    
    # 3. Innings-specific calibrated
    if 'innings_calibrator' in calibrators:
        inn2_cal = calibrators['innings_calibrator'][1]  # Innings 2
        inn_spec_prob = inn2_cal.predict(raw_prob)
        results.append(calculate_metrics(
            y_true,
            inn_spec_prob,
            'Innings-Specific'
        ))
    
    # 4. Phase calibrated (innings×phase) - inn2_powerplay
    if 'phase_calibrators' in calibrators and 'inn2_powerplay' in calibrators['phase_calibrators']:
        phase_cal = calibrators['phase_calibrators']['inn2_powerplay']
        phase_prob = phase_cal.predict(raw_prob)
        results.append(calculate_metrics(
            y_true,
            phase_prob,
            'Innings×Phase (inn2_powerplay)'
        ))
    
    # 5. Brier-optimized (per-over) - calculate over from overs_remaining
    if 'per_over_calibrators' in calibrators and 'overs_remaining' in df_inn2_pp.columns:
        per_over_cals = calibrators['per_over_calibrators']
        brier_probs = []
        
        for idx, (_, row) in enumerate(df_inn2_pp.iterrows()):
            # Calculate current over (20 - overs_remaining)
            over_num = int(20 - row['overs_remaining']) + 1
            # Cap at 20 since powerplay is overs 1-6
            over_num = min(max(over_num, 1), 6)
            
            key = f'inn2_over{over_num}'
            
            if key in per_over_cals:
                cal_prob = per_over_cals[key].predict([raw_prob[idx]])[0]
            else:
                # Fallback to phase calibrator
                if 'phase_calibrators' in calibrators and 'inn2_powerplay' in calibrators['phase_calibrators']:
                    phase_cal = calibrators['phase_calibrators']['inn2_powerplay']
                    cal_prob = phase_cal.predict([raw_prob[idx]])[0]
                else:
                    cal_prob = raw_prob[idx]
            
            brier_probs.append(cal_prob)
        
        results.append(calculate_metrics(
            y_true,
            np.array(brier_probs),
            'Brier-Optimized (Per-Over)'
        ))
    
    # Convert to DataFrame
    results_df = pd.DataFrame(results)
    
    print("\n" + "="*70)
    print("📊 BBL SECOND INNINGS POWERPLAY CALIBRATION COMPARISON")
    print("="*70)
    print(f"\nSamples: {len(df_inn2_pp):,} balls")
    print(f"Actual win rate: {y_true.mean():.1%}")
    print("\n" + results_df.to_string(index=False))
    
    # Calculate improvements
    if len(results_df) > 1:
        raw_brier = results_df[results_df['Method'] == 'Raw Model']['Brier'].values[0]
        raw_logloss = results_df[results_df['Method'] == 'Raw Model']['LogLoss'].values[0]
        
        print("\n" + "="*70)
        print("📈 IMPROVEMENT vs RAW MODEL")
        print("="*70)
        
        for _, row in results_df.iterrows():
            if row['Method'] != 'Raw Model':
                brier_imp = ((raw_brier - row['Brier']) / raw_brier) * 100
                logloss_imp = ((raw_logloss - row['LogLoss']) / raw_logloss) * 100
                print(f"\n{row['Method']}:")
                print(f"  Brier:   {row['Brier']:.4f} ({brier_imp:+.1f}%)")
                print(f"  LogLoss: {row['LogLoss']:.4f} ({logloss_imp:+.1f}%)")
    
    # Save results
    output_file = model_dir / 'inn2_powerplay_analysis.csv'
    results_df.to_csv(output_file, index=False)
    print(f"\n💾 Results saved to {output_file}")
    
    # Additional analysis: over-by-over breakdown
    if 'overs_remaining' in df_inn2_pp.columns:
        print("\n" + "="*70)
        print("📊 OVER-BY-OVER BREAKDOWN (Second Innings Powerplay)")
        print("="*70)
        
        # Calculate over number from overs_remaining
        df_inn2_pp['over_num'] = (20 - df_inn2_pp['overs_remaining']).round().astype(int) + 1
        df_inn2_pp['over_num'] = df_inn2_pp['over_num'].clip(1, 6)  # Powerplay is overs 1-6
        
        over_results = []
        for over_num in sorted(df_inn2_pp['over_num'].unique()):
            df_over = df_inn2_pp[df_inn2_pp['over_num'] == over_num]
            y_over = df_over['is_winner'].values
            
            if len(y_over) < 10:  # Skip if too few samples
                continue
            
            # Get predictions for this over - model selects features
            raw_over = model.predict_proba(df_over)[:, 1]
            
            row_data = {
                'Over': over_num,
                'N': len(y_over),
                'Win_Rate': y_over.mean()
            }
            
            # Raw Brier
            row_data['Raw_Brier'] = brier_score_loss(y_over, raw_over)
            
            # Phase Brier
            if 'phase_calibrators' in calibrators and 'inn2_powerplay' in calibrators['phase_calibrators']:
                phase_cal = calibrators['phase_calibrators']['inn2_powerplay']
                phase_over = phase_cal.predict(raw_over)
                row_data['Phase_Brier'] = brier_score_loss(y_over, phase_over)
            
            # Per-over Brier
            if 'per_over_calibrators' in calibrators:
                key = f'inn2_over{int(over_num)}'
                if key in calibrators['per_over_calibrators']:
                    perover_cal = calibrators['per_over_calibrators'][key]
                    perover_over = perover_cal.predict(raw_over)
                    row_data['PerOver_Brier'] = brier_score_loss(y_over, perover_over)
            
            over_results.append(row_data)
        
        if over_results:
            over_df = pd.DataFrame(over_results)
            print("\n" + over_df.to_string(index=False))
            
            # Save over analysis
            over_file = model_dir / 'inn2_powerplay_over_analysis.csv'
            over_df.to_csv(over_file, index=False)
            print(f"\n💾 Over-by-over analysis saved to {over_file}")

if __name__ == '__main__':
    main()
