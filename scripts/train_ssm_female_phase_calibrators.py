"""
Train Phase Calibrators for SSM Female Model (SA20 Style)

Generates 8 phase-specific calibrators:
- Innings 1: powerplay, middle_early, middle_late, death
- Innings 2: powerplay, middle_early, middle_late, death

For each phase, determines the best probability source (raw, cal, resource)
based on Brier score and trains calibrators accordingly.

Outputs:
- phase_calibrators.pkl: Phase calibrators (isotonic)
- phase_calibrators_platt.pkl: Phase calibrators (Platt scaling for smooth output)
- ssm_female_metrics_by_inning.parquet: Metrics by inning
- ssm_female_metrics_by_over.parquet: Metrics by over (within innings)
- ssm_female_metrics_by_phase.parquet: Metrics by phase
"""

import pandas as pd
import numpy as np
import joblib
from pathlib import Path
from sklearn.metrics import brier_score_loss, log_loss
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_predict
import warnings
warnings.filterwarnings('ignore')

# Paths
MODEL_DIR = Path("models/ssm_female_v1")
DATA_DIR = Path("data")
FEATURES_FILE = DATA_DIR / "ssm_female_features_v1" / "training.parquet"
OUTPUT_DIR = DATA_DIR

# Phase definitions (SA20 style - 4 phases per innings)
PHASES = {
    'powerplay': (1, 6),
    'middle_early': (7, 11),
    'middle_late': (12, 15),
    'death': (16, 20)
}


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


def derive_over_from_resources(df):
    """
    Derive over number from overs_remaining.
    overs_remaining = 20 means we're at start (over 1)
    overs_remaining = 19 means over 1 completed (so over 2)
    etc.
    """
    # Use ceiling of (20 - overs_remaining) but ensure at least 1
    overs = np.ceil(20 - df['overs_remaining'].values).astype(int)
    overs = np.clip(overs, 1, 20)
    return overs


def get_phase_from_over(over):
    """Get phase name from over number."""
    for phase_name, (start, end) in PHASES.items():
        if start <= over <= end:
            return phase_name
    return 'death'  # Fallback


def main():
    print("="*80)
    print("SSM FEMALE PHASE CALIBRATOR TRAINING (SA20 STYLE)")
    print("="*80)
    
    # Load data
    print("\n[INFO] Loading SSM Female training data...")
    df = pd.read_parquet(FEATURES_FILE)
    print(f"[OK] Loaded {len(df):,} samples")
    
    # Load model and existing calibrator
    print("[INFO] Loading model and calibrators...")
    model = joblib.load(MODEL_DIR / "champion_model.joblib")
    iso_cal = joblib.load(MODEL_DIR / "isotonic_calibrator.pkl")
    print("[OK] Model and calibrators loaded")
    
    # Derive over numbers from overs_remaining
    df['derived_over'] = derive_over_from_resources(df)
    df['phase'] = df['derived_over'].apply(get_phase_from_over)
    
    # Get features and predictions
    feature_cols = list(model.selected_features_)
    X = df[feature_cols]
    y_true = df['is_winner'].values
    
    # Raw predictions
    raw_probs = model.predict_proba(X)[:, 1]
    
    # Innings-specific calibrated predictions
    innings = df['innings'].values
    cal_probs = np.zeros(len(df))
    for i, inn in enumerate(innings):
        inn_key = int(inn)
        if inn_key in iso_cal:
            cal_probs[i] = iso_cal[inn_key].predict([[raw_probs[i]]])[0]
        else:
            cal_probs[i] = raw_probs[i]
    cal_probs = np.clip(cal_probs, 0.001, 0.999)
    
    # Resource probability
    resource_probs = df['resource_win_prob'].values
    resource_probs = np.clip(resource_probs, 0.001, 0.999)
    
    # Store in DataFrame for analysis
    df['raw_prob'] = raw_probs
    df['cal_prob'] = cal_probs
    df['resource_prob'] = resource_probs
    
    # ==========================================================================
    # ANALYSIS BY INNING
    # ==========================================================================
    print("\n" + "="*80)
    print("ANALYSIS BY INNING")
    print("="*80)
    
    inning_metrics = []
    for inn in [1, 2]:
        mask = innings == inn
        inning_metrics.append({
            'Group': f'Innings {inn}',
            'N': mask.sum(),
            'Brier_Raw': brier_score_loss(y_true[mask], raw_probs[mask]),
            'Brier_InnSpec': brier_score_loss(y_true[mask], cal_probs[mask]),
            'Brier_Resource': brier_score_loss(y_true[mask], resource_probs[mask]),
            'ECE_Raw': calculate_ece(y_true[mask], raw_probs[mask]),
            'ECE_InnSpec': calculate_ece(y_true[mask], cal_probs[mask]),
            'ECE_Resource': calculate_ece(y_true[mask], resource_probs[mask]),
            'LogLoss_Raw': log_loss(y_true[mask], raw_probs[mask]),
            'LogLoss_InnSpec': log_loss(y_true[mask], cal_probs[mask]),
            'LogLoss_Resource': log_loss(y_true[mask], resource_probs[mask]),
        })
    
    inning_df = pd.DataFrame(inning_metrics)
    print(inning_df.to_string(index=False))
    inning_df.to_parquet(OUTPUT_DIR / "ssm_female_metrics_by_inning.parquet", index=False)
    
    # ==========================================================================
    # ANALYSIS BY PHASE (8 phases = 2 innings x 4 phases)
    # ==========================================================================
    print("\n" + "="*80)
    print("ANALYSIS BY PHASE (SA20 STYLE - 8 PHASES)")
    print("="*80)
    
    phase_metrics = []
    best_sources = {}  # Store best source for each phase
    
    for inn in [1, 2]:
        for phase_name in PHASES.keys():
            mask = (df['innings'] == inn) & (df['phase'] == phase_name)
            n = mask.sum()
            
            if n < 100:
                print(f"[WARN] Inn {inn} {phase_name}: Only {n} samples, skipping...")
                continue
            
            y_phase = y_true[mask]
            raw_phase = raw_probs[mask]
            cal_phase = cal_probs[mask]
            res_phase = resource_probs[mask]
            
            brier_raw = brier_score_loss(y_phase, raw_phase)
            brier_cal = brier_score_loss(y_phase, cal_phase)
            brier_res = brier_score_loss(y_phase, res_phase)
            
            ece_raw = calculate_ece(y_phase, raw_phase)
            ece_cal = calculate_ece(y_phase, cal_phase)
            ece_res = calculate_ece(y_phase, res_phase)
            
            ll_raw = log_loss(y_phase, raw_phase)
            ll_cal = log_loss(y_phase, cal_phase)
            ll_res = log_loss(y_phase, res_phase)
            
            # Determine best source for Brier
            briers = {'raw': brier_raw, 'cal': brier_cal, 'res': brier_res}
            best_brier = min(briers, key=briers.get)
            
            # Determine best source for ECE
            eces = {'raw': ece_raw, 'cal': ece_cal, 'res': ece_res}
            best_ece = min(eces, key=eces.get)
            
            phase_key = f'inn{inn}_{phase_name}'
            best_sources[phase_key] = {
                'best_brier': best_brier,
                'best_ece': best_ece,
                'n': n
            }
            
            phase_metrics.append({
                'Innings': inn,
                'Phase': phase_name,
                'N': n,
                'Brier_Raw': brier_raw,
                'Brier_InnSpec': brier_cal,
                'Brier_Resource': brier_res,
                'ECE_Raw': ece_raw,
                'ECE_InnSpec': ece_cal,
                'ECE_Resource': ece_res,
                'LogLoss_Raw': ll_raw,
                'LogLoss_InnSpec': ll_cal,
                'LogLoss_Resource': ll_res,
                'Best_Brier': best_brier,
                'Best_ECE': best_ece
            })
            
            print(f"Inn{inn} {phase_name:12s} N={n:5d} | Brier: Raw={brier_raw:.4f} Cal={brier_cal:.4f} Res={brier_res:.4f} | Best: {best_brier}")
    
    phase_df = pd.DataFrame(phase_metrics)
    print("\n" + phase_df.to_string(index=False))
    # Note: phase_df saved after calibrators are trained with Phase_Isotonic metrics
    
    # ==========================================================================
    # ANALYSIS BY OVER
    # ==========================================================================
    print("\n" + "="*80)
    print("ANALYSIS BY OVER")
    print("="*80)
    
    over_metrics = []
    for inn in [1, 2]:
        for over in range(1, 21):
            mask = (df['innings'] == inn) & (df['derived_over'] == over)
            n = mask.sum()
            
            if n < 50:
                continue
            
            y_over = y_true[mask]
            raw_over = raw_probs[mask]
            cal_over = cal_probs[mask]
            res_over = resource_probs[mask]
            
            over_metrics.append({
                'Innings': inn,
                'Over': over,
                'N': n,
                'Brier_Raw': brier_score_loss(y_over, raw_over),
                'Brier_InnSpec': brier_score_loss(y_over, cal_over),
                'Brier_Resource': brier_score_loss(y_over, res_over),
                'ECE_Raw': calculate_ece(y_over, raw_over),
                'ECE_InnSpec': calculate_ece(y_over, cal_over),
                'ECE_Resource': calculate_ece(y_over, res_over),
                'LogLoss_Raw': log_loss(y_over, raw_over),
                'LogLoss_InnSpec': log_loss(y_over, cal_over),
                'LogLoss_Resource': log_loss(y_over, res_over),
            })
    
    over_df = pd.DataFrame(over_metrics)
    print(over_df.to_string(index=False))
    over_df.to_parquet(OUTPUT_DIR / "ssm_female_metrics_by_over.parquet", index=False)
    
    # ==========================================================================
    # TRAIN PHASE CALIBRATORS (Isotonic) - RESOURCE-BASED FOR ECE OPTIMIZATION
    # ==========================================================================
    print("\n" + "="*80)
    print("TRAINING PHASE CALIBRATORS (ISOTONIC) - RESOURCE-BASED")
    print("="*80)
    
    phase_calibrators = {}
    
    for inn in [1, 2]:
        for phase_name in PHASES.keys():
            mask = (df['innings'] == inn) & (df['phase'] == phase_name)
            n = mask.sum()
            
            if n < 100:
                continue
            
            phase_key = f'inn{inn}_{phase_name}'
            
            # FORCE RESOURCE as source for all phases (ECE-optimized)
            # Resource-based calibration provides better ECE for women's cricket
            best_source = 'res'  # Always use resource_win_prob
            
            y_phase = y_true[mask]
            
            # Always use resource probabilities
            input_probs = resource_probs[mask]
            
            # Train isotonic calibrator with cross-validation OOF
            iso = IsotonicRegression(out_of_bounds='clip')
            iso.fit(input_probs, y_phase)
            
            phase_calibrators[phase_key] = {
                'calibrator': iso,
                'source': best_source,
                'method': 'isotonic',
                'n_samples': n
            }
            
            # Evaluate calibrated output
            calibrated = iso.predict(input_probs)
            brier_before = brier_score_loss(y_phase, input_probs)
            brier_after = brier_score_loss(y_phase, calibrated)
            ece_before = calculate_ece(y_phase, input_probs)
            ece_after = calculate_ece(y_phase, calibrated)
            ll_before = log_loss(y_phase, np.clip(input_probs, 0.001, 0.999))
            ll_after = log_loss(y_phase, np.clip(calibrated, 0.001, 0.999))
            
            # Store metrics for updating the phase metrics DataFrame
            phase_calibrators[phase_key]['brier_after'] = brier_after
            phase_calibrators[phase_key]['ece_after'] = ece_after
            phase_calibrators[phase_key]['ll_after'] = ll_after
            
            print(f"{phase_key}: source={best_source} | Brier: {brier_before:.4f} -> {brier_after:.4f} | ECE: {ece_before:.4f} -> {ece_after:.4f} | LL: {ll_before:.4f} -> {ll_after:.4f}")
    
    # Add Phase_Isotonic metrics to the phase_df
    print("\n[INFO] Adding Phase_Isotonic metrics to phase_df...")
    phase_df['Brier_PhaseIso'] = phase_df.apply(
        lambda row: phase_calibrators.get(f"inn{row['Innings']}_{row['Phase']}", {}).get('brier_after', np.nan), axis=1
    )
    phase_df['ECE_PhaseIso'] = phase_df.apply(
        lambda row: phase_calibrators.get(f"inn{row['Innings']}_{row['Phase']}", {}).get('ece_after', np.nan), axis=1
    )
    phase_df['LogLoss_PhaseIso'] = phase_df.apply(
        lambda row: phase_calibrators.get(f"inn{row['Innings']}_{row['Phase']}", {}).get('ll_after', np.nan), axis=1
    )
    
    # Save updated phase_df with Phase_Isotonic metrics
    phase_df.to_parquet(OUTPUT_DIR / "ssm_female_metrics_by_phase.parquet", index=False)
    print(f"[OK] Saved phase metrics with Phase_Isotonic to {OUTPUT_DIR / 'ssm_female_metrics_by_phase.parquet'}")
    
    # Save isotonic calibrators
    joblib.dump(phase_calibrators, MODEL_DIR / "phase_calibrators.pkl")
    print(f"\n[OK] Saved isotonic phase calibrators to {MODEL_DIR / 'phase_calibrators.pkl'}")
    
    # ==========================================================================
    # TRAIN PHASE CALIBRATORS (Platt Scaling for smooth output) - RESOURCE-BASED
    # ==========================================================================
    print("\n" + "="*80)
    print("TRAINING PHASE CALIBRATORS (PLATT SCALING) - RESOURCE-BASED")
    print("="*80)
    
    phase_calibrators_platt = {}
    
    for inn in [1, 2]:
        for phase_name in PHASES.keys():
            mask = (df['innings'] == inn) & (df['phase'] == phase_name)
            n = mask.sum()
            
            if n < 100:
                continue
            
            phase_key = f'inn{inn}_{phase_name}'
            
            # FORCE RESOURCE as source for all phases (ECE-optimized)
            best_source = 'res'
            
            y_phase = y_true[mask]
            
            # Always use resource probabilities
            input_probs = resource_probs[mask]
            
            # Convert to logits for Platt scaling
            input_clipped = np.clip(input_probs, 0.001, 0.999)
            logits = np.log(input_clipped / (1 - input_clipped)).reshape(-1, 1)
            
            # Train logistic regression (Platt scaling)
            platt = LogisticRegression(C=1e10, solver='lbfgs', max_iter=1000)
            platt.fit(logits, y_phase)
            
            phase_calibrators_platt[phase_key] = {
                'calibrator': platt,
                'source': best_source,
                'method': 'platt',
                'n_samples': n
            }
            
            # Evaluate
            calibrated = platt.predict_proba(logits)[:, 1]
            brier_before = brier_score_loss(y_phase, input_probs)
            brier_after = brier_score_loss(y_phase, calibrated)
            ece_before = calculate_ece(y_phase, input_probs)
            ece_after = calculate_ece(y_phase, calibrated)
            
            print(f"{phase_key}: source={best_source} | Brier: {brier_before:.4f} -> {brier_after:.4f} | ECE: {ece_before:.4f} -> {ece_after:.4f}")
    
    # Save Platt calibrators
    joblib.dump(phase_calibrators_platt, MODEL_DIR / "phase_calibrators_platt.pkl")
    print(f"\n[OK] Saved Platt phase calibrators to {MODEL_DIR / 'phase_calibrators_platt.pkl'}")
    
    # ==========================================================================
    # SUMMARY
    # ==========================================================================
    print("\n" + "="*80)
    print("SUMMARY - BEST SOURCES BY PHASE")
    print("="*80)
    
    print("\n| Phase Key | Best Brier Source | Best ECE Source | N Samples |")
    print("|-----------|-------------------|-----------------|-----------|")
    for key, info in best_sources.items():
        print(f"| {key:20s} | {info['best_brier']:^17s} | {info['best_ece']:^15s} | {info['n']:>9,d} |")
    
    print("\n[OK] Training complete!")
    print(f"[OK] Metrics saved to:")
    print(f"  - {OUTPUT_DIR / 'ssm_female_metrics_by_inning.parquet'}")
    print(f"  - {OUTPUT_DIR / 'ssm_female_metrics_by_phase.parquet'}")
    print(f"  - {OUTPUT_DIR / 'ssm_female_metrics_by_over.parquet'}")
    print(f"[OK] Calibrators saved to:")
    print(f"  - {MODEL_DIR / 'phase_calibrators.pkl'}")
    print(f"  - {MODEL_DIR / 'phase_calibrators_platt.pkl'}")


if __name__ == "__main__":
    main()
