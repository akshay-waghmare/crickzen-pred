"""
Analyze SSM Female v1 Model Calibration Performance

Computes Brier, ECE, and Log Loss for:
1. Raw model output
2. Inning-specific isotonic calibrator
3. Resource-based probability
4. Per-over calibrators (if available)

Similar to SA20/WPL analysis for comparing calibration methods.
"""

import pandas as pd
import numpy as np
import joblib
from pathlib import Path
import json
from sklearn.metrics import brier_score_loss, log_loss
from scipy.special import logit, expit

# Paths
MODEL_DIR = Path("models/ssm_female_v1")
DATA_DIR = Path("data")
FEATURES_FILE = DATA_DIR / "ssm_female_features_v1" / "training.parquet"
OUTPUT_DIR = Path("data")
OUTPUT_FILE = OUTPUT_DIR / "ssm_female_calibration_metrics.parquet"

def calculate_ece(y_true, y_pred, n_bins=10):
    """Calculate Expected Calibration Error."""
    bin_edges = np.linspace(0, 1, n_bins + 1)
    bin_indices = np.digitize(y_pred, bin_edges) - 1
    bin_indices = np.clip(bin_indices, 0, n_bins - 1)
    
    ece = 0
    for i in range(n_bins):
        mask = bin_indices == i
        if mask.sum() == 0:
            continue
        
        bin_acc = np.abs(y_true[mask].mean() - y_pred[mask].mean())
        ece += mask.sum() / len(y_true) * bin_acc
    
    return ece

def main():
    print("[INFO] Loading SSM Female training data...")
    df = pd.read_parquet(FEATURES_FILE)
    print(f"[OK] Loaded {len(df):,} samples")
    
    # Load model
    print("[INFO] Loading SSM Female v1 model and calibrators...")
    model = joblib.load(MODEL_DIR / "champion_model.joblib")
    iso_cal = joblib.load(MODEL_DIR / "isotonic_calibrator.pkl")
    
    # Check for per-over calibrators
    per_over_cals = None
    if (MODEL_DIR / "per_over_calibrators.pkl").exists():
        per_over_cals = joblib.load(MODEL_DIR / "per_over_calibrators.pkl")
        print(f"[OK] Loaded per-over calibrators: {len(per_over_cals)} keys")
    else:
        print("[WARN] Per-over calibrators not found")
    
    # Get features for prediction
    feature_cols = list(model.selected_features_)
    print(f"[INFO] Using {len(feature_cols)} features for prediction")
    print(f"[INFO] Features: {feature_cols}")
    
    # Get target and predictions
    y_true = df['is_winner'].values
    
    # Raw model predictions
    X = df[feature_cols]  # Keep as DataFrame for the model
    raw_probs = model.predict_proba(X)[:, 1]
    
    # Innings and other info
    innings = df['innings'].values if 'innings' in df.columns else np.ones(len(df))
    overs = df['overs'].values if 'overs' in df.columns else np.zeros(len(df))
    runs_scored = df['runs_scored'].values if 'runs_scored' in df.columns else np.zeros(len(df))
    
    # Resource probability (if available)
    resource_probs = df['resource_win_prob'].values if 'resource_win_prob' in df.columns else np.full(len(df), 0.5)
    
    # Inn-specific calibration
    inn_cals = {}
    cal_probs = np.zeros(len(df))
    for i, inn in enumerate(innings):
        inn_key = int(inn)
        if inn_key not in inn_cals and inn_key in iso_cal:
            inn_cals[inn_key] = iso_cal[inn_key]
        
        if inn_key in inn_cals:
            cal_probs[i] = inn_cals[inn_key].predict([[raw_probs[i]]])[0]
    
    cal_probs = np.clip(cal_probs, 0.001, 0.999)
    
    # Per-over calibration (if available)
    per_over_probs = np.full(len(df), np.nan)
    per_over_sources = np.full(len(df), '', dtype=object)
    if per_over_cals is not None:
        for i, (inn, over) in enumerate(zip(innings, overs)):
            over_key = f"inn{int(inn)}_over{int(np.ceil(over))}"
            if over_key in per_over_cals:
                cal_info = per_over_cals[over_key]
                source = cal_info.get('source', 'raw')
                method = cal_info.get('method', 'isotonic')
                
                # Get input based on source
                if source == 'raw':
                    input_prob = raw_probs[i]
                elif source == 'cal':
                    input_prob = cal_probs[i]
                else:  # 'res'
                    input_prob = resource_probs[i]
                
                # Apply calibrator
                if method == 'platt':
                    input_clipped = np.clip(input_prob, 0.001, 0.999)
                    logit_val = logit(input_clipped)
                    per_over_probs[i] = expit(cal_info['calibrator'].predict([[logit_val]])[0])
                else:
                    per_over_probs[i] = cal_info['calibrator'].predict([[input_prob]])[0]
                
                per_over_sources[i] = source
    
    per_over_probs = np.clip(per_over_probs, 0.001, 0.999)
    
    # Calculate metrics by inning
    print("\n[INFO] Computing metrics by inning...")
    inning_metrics = []
    for inn in sorted(np.unique(innings)):
        mask = innings == inn
        inning_metrics.append({
            'Innings': int(inn),
            'N': mask.sum(),
            'Brier_Raw': brier_score_loss(y_true[mask], raw_probs[mask]),
            'Brier_Cal': brier_score_loss(y_true[mask], cal_probs[mask]),
            'Brier_Resource': brier_score_loss(y_true[mask], resource_probs[mask]),
            'ECE_Raw': calculate_ece(y_true[mask], raw_probs[mask]),
            'ECE_Cal': calculate_ece(y_true[mask], cal_probs[mask]),
            'ECE_Resource': calculate_ece(y_true[mask], resource_probs[mask]),
            'LogLoss_Raw': log_loss(y_true[mask], raw_probs[mask]),
            'LogLoss_Cal': log_loss(y_true[mask], cal_probs[mask]),
            'LogLoss_Resource': log_loss(y_true[mask], resource_probs[mask]),
        })
        
        # Add per-over metrics if available
        if per_over_cals is not None:
            per_over_mask = mask & ~np.isnan(per_over_probs)
            if per_over_mask.sum() > 0:
                inning_metrics[-1]['Brier_PerOver'] = brier_score_loss(y_true[per_over_mask], per_over_probs[per_over_mask])
                inning_metrics[-1]['ECE_PerOver'] = calculate_ece(y_true[per_over_mask], per_over_probs[per_over_mask])
                inning_metrics[-1]['LogLoss_PerOver'] = log_loss(y_true[per_over_mask], per_over_probs[per_over_mask])
            else:
                inning_metrics[-1]['Brier_PerOver'] = np.nan
                inning_metrics[-1]['ECE_PerOver'] = np.nan
                inning_metrics[-1]['LogLoss_PerOver'] = np.nan
    
    inning_df = pd.DataFrame(inning_metrics)
    print("\n[OK] Inning Metrics:")
    print(inning_df.to_string())
    
    # Calculate metrics by over (overs 2, 5, 10, 15, 20)
    print("\n[INFO] Computing metrics by over...")
    over_metrics = []
    target_overs = [2, 5, 10, 15, 20]
    
    for inn in sorted(np.unique(innings)):
        for target_over in target_overs:
            mask = (innings == inn) & (overs >= target_over - 0.5) & (overs < target_over + 0.5)
            if mask.sum() == 0:
                continue
            
            metric = {
                'Innings': int(inn),
                'Over': target_over,
                'N': mask.sum(),
                'Brier_Raw': brier_score_loss(y_true[mask], raw_probs[mask]),
                'Brier_Cal': brier_score_loss(y_true[mask], cal_probs[mask]),
                'Brier_Resource': brier_score_loss(y_true[mask], resource_probs[mask]),
                'ECE_Raw': calculate_ece(y_true[mask], raw_probs[mask]),
                'ECE_Cal': calculate_ece(y_true[mask], cal_probs[mask]),
                'ECE_Resource': calculate_ece(y_true[mask], resource_probs[mask]),
                'LogLoss_Raw': log_loss(y_true[mask], raw_probs[mask]),
                'LogLoss_Cal': log_loss(y_true[mask], cal_probs[mask]),
                'LogLoss_Resource': log_loss(y_true[mask], resource_probs[mask]),
            }
            
            # Add per-over metrics
            if per_over_cals is not None:
                per_over_mask = mask & ~np.isnan(per_over_probs)
                if per_over_mask.sum() > 0:
                    metric['Brier_PerOver'] = brier_score_loss(y_true[per_over_mask], per_over_probs[per_over_mask])
                    metric['ECE_PerOver'] = calculate_ece(y_true[per_over_mask], per_over_probs[per_over_mask])
                    metric['LogLoss_PerOver'] = log_loss(y_true[per_over_mask], per_over_probs[per_over_mask])
                else:
                    metric['Brier_PerOver'] = np.nan
                    metric['ECE_PerOver'] = np.nan
                    metric['LogLoss_PerOver'] = np.nan
            
            over_metrics.append(metric)
    
    over_df = pd.DataFrame(over_metrics)
    print("\n[OK] Per-Over Metrics (Sample Overs):")
    print(over_df.to_string())
    
    # Calculate metrics by phase
    print("\n[INFO] Computing metrics by phase...")
    phase_metrics = []
    
    for inn in sorted(np.unique(innings)):
        # Define phases: PP (1-6), Middle (7-12), Death (13-20)
        phases = [
            ('Powerplay', 1, 6),
            ('Middle', 7, 12),
            ('Death', 13, 20)
        ]
        
        for phase_name, start_over, end_over in phases:
            mask = (innings == inn) & (overs >= start_over) & (overs <= end_over)
            if mask.sum() == 0:
                continue
            
            metric = {
                'Innings': int(inn),
                'Phase': phase_name,
                'N': mask.sum(),
                'Brier_Raw': brier_score_loss(y_true[mask], raw_probs[mask]),
                'Brier_Cal': brier_score_loss(y_true[mask], cal_probs[mask]),
                'Brier_Resource': brier_score_loss(y_true[mask], resource_probs[mask]),
                'ECE_Raw': calculate_ece(y_true[mask], raw_probs[mask]),
                'ECE_Cal': calculate_ece(y_true[mask], cal_probs[mask]),
                'ECE_Resource': calculate_ece(y_true[mask], resource_probs[mask]),
                'LogLoss_Raw': log_loss(y_true[mask], raw_probs[mask]),
                'LogLoss_Cal': log_loss(y_true[mask], cal_probs[mask]),
                'LogLoss_Resource': log_loss(y_true[mask], resource_probs[mask]),
            }
            
            # Add per-over metrics
            if per_over_cals is not None:
                per_over_mask = mask & ~np.isnan(per_over_probs)
                if per_over_mask.sum() > 0:
                    metric['Brier_PerOver'] = brier_score_loss(y_true[per_over_mask], per_over_probs[per_over_mask])
                    metric['ECE_PerOver'] = calculate_ece(y_true[per_over_mask], per_over_probs[per_over_mask])
                    metric['LogLoss_PerOver'] = log_loss(y_true[per_over_mask], per_over_probs[per_over_mask])
                else:
                    metric['Brier_PerOver'] = np.nan
                    metric['ECE_PerOver'] = np.nan
                    metric['LogLoss_PerOver'] = np.nan
            
            phase_metrics.append(metric)
    
    phase_df = pd.DataFrame(phase_metrics)
    print("\n[OK] Phase Metrics:")
    print(phase_df.to_string())
    
    # Print winners
    print("\n" + "="*80)
    print("WINNERS BY METRIC")
    print("="*80)
    
    for metric_type in ['Brier', 'ECE', 'LogLoss']:
        print(f"\n### {metric_type.upper()} ###")
        
        # By inning
        for idx, row in inning_df.iterrows():
            cols = [f'{metric_type}_Raw', f'{metric_type}_Cal', f'{metric_type}_Resource']
            if f'{metric_type}_PerOver' in inning_df.columns:
                cols.append(f'{metric_type}_PerOver')
            
            valid_cols = [c for c in cols if c in inning_df.columns]
            winner = valid_cols[np.argmin([row[c] for c in valid_cols])]
            print(f"Inn {int(row['Innings'])}: {winner} = {row[winner]:.4f}")
    
    # Save metrics
    print(f"\n[INFO] Saving metrics to {OUTPUT_FILE}...")
    
    # Combine all metrics into single output file with multiple sheets
    metrics_dict = {
        'inning_metrics': inning_df,
        'over_metrics': over_df,
        'phase_metrics': phase_df,
    }
    
    # Save as parquet (multiple tables)
    inning_df.to_parquet(OUTPUT_DIR / "ssm_female_metrics_by_inning.parquet", index=False)
    over_df.to_parquet(OUTPUT_DIR / "ssm_female_metrics_by_over.parquet", index=False)
    phase_df.to_parquet(OUTPUT_DIR / "ssm_female_metrics_by_phase.parquet", index=False)
    
    print("[OK] Metrics saved successfully!")
    print(f"  - {OUTPUT_DIR / 'ssm_female_metrics_by_inning.parquet'}")
    print(f"  - {OUTPUT_DIR / 'ssm_female_metrics_by_over.parquet'}")
    print(f"  - {OUTPUT_DIR / 'ssm_female_metrics_by_phase.parquet'}")
    
    # Summary statistics
    print("\n" + "="*80)
    print("OVERALL SUMMARY")
    print("="*80)
    
    summary = {
        'Metric': ['Brier', 'ECE', 'LogLoss'],
        'Raw_Mean': [
            inning_df['Brier_Raw'].mean(),
            inning_df['ECE_Raw'].mean(),
            inning_df['LogLoss_Raw'].mean(),
        ],
        'Cal_Mean': [
            inning_df['Brier_Cal'].mean(),
            inning_df['ECE_Cal'].mean(),
            inning_df['LogLoss_Cal'].mean(),
        ],
        'Resource_Mean': [
            inning_df['Brier_Resource'].mean(),
            inning_df['ECE_Resource'].mean(),
            inning_df['LogLoss_Resource'].mean(),
        ]
    }
    
    if 'Brier_PerOver' in inning_df.columns:
        summary['PerOver_Mean'] = [
            inning_df['Brier_PerOver'].mean(),
            inning_df['ECE_PerOver'].mean(),
            inning_df['LogLoss_PerOver'].mean(),
        ]
    
    summary_df = pd.DataFrame(summary)
    print(summary_df.to_string(index=False))


if __name__ == "__main__":
    main()
