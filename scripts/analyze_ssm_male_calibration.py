"""
SSM Male Calibration Analysis (Per-Over Style)

Generates comprehensive calibration metrics:
- By inning (innings 1 vs 2)
- By over (all 40 over-innings combinations)
- By phase (for reference comparison)

Analyzes: Brier Score, ECE, Log Loss for Raw, InnSpec Cal, Resource, Per-Over ECE, Per-Over Brier, LL-Opt

Outputs:
- ssm_male_metrics_by_inning.parquet
- ssm_male_metrics_by_over.parquet  
- ssm_male_metrics_by_phase.parquet
"""

import pandas as pd
import numpy as np
import joblib
from pathlib import Path
from sklearn.metrics import brier_score_loss, log_loss
import warnings
warnings.filterwarnings('ignore')

# Paths
MODEL_DIR = Path("models/ssm_v1")
DATA_DIR = Path("data")
FEATURES_FILE = DATA_DIR / "ssm_features_v1" / "training.parquet"
OUTPUT_DIR = DATA_DIR
BRIER_CALS_FILE = MODEL_DIR / "brier_calibrators.pkl"  # Brier-optimized calibrators
LOGLOSS_CALS_FILE = MODEL_DIR / "logloss_calibrators.pkl"  # Log loss-optimized calibrators

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
    """Derive over number from overs_remaining."""
    overs = np.ceil(20 - df['overs_remaining'].values).astype(int)
    overs = np.clip(overs, 1, 20)
    return overs


def get_phase_from_over(over):
    """Get phase name from over number."""
    for phase_name, (start, end) in PHASES.items():
        if start <= over <= end:
            return phase_name
    return 'death'


def main():
    print("="*80)
    print("SSM MALE CALIBRATION ANALYSIS (PER-OVER STYLE)")
    print("="*80)
    
    # Load data
    print("\n[INFO] Loading SSM Male training data...")
    df = pd.read_parquet(FEATURES_FILE)
    print(f"[OK] Loaded {len(df):,} samples")
    
    # Load model and calibrators
    print("[INFO] Loading model and calibrators...")
    model = joblib.load(MODEL_DIR / "champion_model.joblib")
    iso_cal = joblib.load(MODEL_DIR / "isotonic_calibrator.pkl")
    per_over_cals = joblib.load(MODEL_DIR / "per_over_calibrators.pkl")
    brier_cals = joblib.load(BRIER_CALS_FILE)  # Brier-optimized calibrators
    logloss_cals = joblib.load(LOGLOSS_CALS_FILE)  # Log loss-optimized calibrators
    print(f"[OK] Model loaded, {len(per_over_cals)} per-over ECE cals, {len(brier_cals)} brier cals, {len(logloss_cals)} LL cals")
    
    # Derive over numbers
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
    
    # Per-over calibrated predictions
    per_over_probs = np.zeros(len(df))
    overs = df['derived_over'].values
    for i in range(len(df)):
        inn = int(innings[i])
        over = int(overs[i])
        cal_key = f'inn{inn}_over{over}'
        
        if cal_key in per_over_cals:
            cal_info = per_over_cals[cal_key]
            source = cal_info.get('source', 'raw')
            calibrator = cal_info['calibrator']
            
            if source == 'raw':
                input_prob = raw_probs[i]
            elif source == 'cal':
                input_prob = cal_probs[i]
            else:  # 'res'
                input_prob = resource_probs[i]
            
            per_over_probs[i] = calibrator.predict([[input_prob]])[0]
        else:
            per_over_probs[i] = raw_probs[i]
    per_over_probs = np.clip(per_over_probs, 0.001, 0.999)
    
    # Brier-optimized per-over calibrated predictions
    brier_probs = np.zeros(len(df))
    for i in range(len(df)):
        inn = int(innings[i])
        over = int(overs[i])
        cal_key = f'inn{inn}_over{over}'
        
        if cal_key in brier_cals:
            cal_info = brier_cals[cal_key]
            source = cal_info.get('source', 'raw')
            calibrator = cal_info['calibrator']
            
            if source == 'raw':
                input_prob = raw_probs[i]
            elif source == 'cal':
                input_prob = cal_probs[i]
            elif source == 'per':  # Use ECE-calibrated per-over
                input_prob = per_over_probs[i]
            else:  # 'res'
                input_prob = resource_probs[i]
            
            brier_probs[i] = calibrator.predict([[input_prob]])[0]
        else:
            brier_probs[i] = raw_probs[i]
    brier_probs = np.clip(brier_probs, 0.001, 0.999)
    
    # Log loss-optimized per-over calibrated predictions
    logloss_probs = np.zeros(len(df))
    for i in range(len(df)):
        inn = int(innings[i])
        over = int(overs[i])
        cal_key = f'inn{inn}_over{over}'
        
        if cal_key in logloss_cals:
            cal_info = logloss_cals[cal_key]
            source = cal_info.get('source', 'raw')
            calibrator = cal_info['calibrator']
            
            if source == 'raw':
                input_prob = raw_probs[i]
            elif source == 'cal':
                input_prob = cal_probs[i]
            elif source == 'per':  # Use ECE-calibrated per-over
                input_prob = per_over_probs[i]
            elif source == 'bri':  # Use Brier-calibrated per-over
                input_prob = brier_probs[i]
            else:  # 'res'
                input_prob = resource_probs[i]
            
            logloss_probs[i] = calibrator.predict([[input_prob]])[0]
        else:
            logloss_probs[i] = raw_probs[i]
    logloss_probs = np.clip(logloss_probs, 0.001, 0.999)
    
    # Store in DataFrame
    df['raw_prob'] = raw_probs
    df['cal_prob'] = cal_probs
    df['resource_prob'] = resource_probs
    df['per_over_prob'] = per_over_probs
    df['brier_prob'] = brier_probs
    df['logloss_prob'] = logloss_probs
    
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
            'Brier_POC_ECE': brier_score_loss(y_true[mask], per_over_probs[mask]),
            'Brier_POC_Brier': brier_score_loss(y_true[mask], brier_probs[mask]),
            'Brier_LL_Opt': brier_score_loss(y_true[mask], logloss_probs[mask]),
            'ECE_Raw': calculate_ece(y_true[mask], raw_probs[mask]),
            'ECE_InnSpec': calculate_ece(y_true[mask], cal_probs[mask]),
            'ECE_Resource': calculate_ece(y_true[mask], resource_probs[mask]),
            'ECE_POC_ECE': calculate_ece(y_true[mask], per_over_probs[mask]),
            'ECE_POC_Brier': calculate_ece(y_true[mask], brier_probs[mask]),
            'ECE_LL_Opt': calculate_ece(y_true[mask], logloss_probs[mask]),
            'LogLoss_Raw': log_loss(y_true[mask], raw_probs[mask]),
            'LogLoss_InnSpec': log_loss(y_true[mask], cal_probs[mask]),
            'LogLoss_Resource': log_loss(y_true[mask], resource_probs[mask]),
            'LogLoss_POC_ECE': log_loss(y_true[mask], per_over_probs[mask]),
            'LogLoss_POC_Brier': log_loss(y_true[mask], brier_probs[mask]),
            'LogLoss_LL_Opt': log_loss(y_true[mask], logloss_probs[mask]),
        })
    
    inning_df = pd.DataFrame(inning_metrics)
    print(inning_df.to_string(index=False))
    inning_df.to_parquet(OUTPUT_DIR / "ssm_male_metrics_by_inning.parquet", index=False)
    
    # ==========================================================================
    # ANALYSIS BY OVER (40 overs = 2 innings x 20 overs)
    # ==========================================================================
    print("\n" + "="*80)
    print("ANALYSIS BY OVER")
    print("="*80)
    
    over_metrics = []
    print(f"\n{'Inn':>3} {'Over':>4} {'N':>6} | {'B_Raw':>8} {'B_POC_E':>8} {'B_POC_B':>8} | {'E_Raw':>6} {'E_POC_E':>6} {'E_POC_B':>6} | Best_Brier Best_ECE")
    print("-" * 110)
    
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
            poc_over = per_over_probs[mask]
            brier_over = brier_probs[mask]
            ll_over = logloss_probs[mask]
            
            brier_raw = brier_score_loss(y_over, raw_over)
            brier_cal = brier_score_loss(y_over, cal_over)
            brier_res = brier_score_loss(y_over, res_over)
            brier_poc = brier_score_loss(y_over, poc_over)
            brier_bri = brier_score_loss(y_over, brier_over)
            brier_ll = brier_score_loss(y_over, ll_over)
            
            ece_raw = calculate_ece(y_over, raw_over)
            ece_cal = calculate_ece(y_over, cal_over)
            ece_res = calculate_ece(y_over, res_over)
            ece_poc = calculate_ece(y_over, poc_over)
            ece_bri = calculate_ece(y_over, brier_over)
            ece_ll = calculate_ece(y_over, ll_over)
            
            ll_raw = log_loss(y_over, raw_over)
            ll_cal = log_loss(y_over, cal_over)
            ll_res = log_loss(y_over, res_over)
            ll_poc = log_loss(y_over, poc_over)
            ll_bri = log_loss(y_over, brier_over)
            ll_ll = log_loss(y_over, ll_over)
            
            # Determine best sources
            briers = {'raw': brier_raw, 'cal': brier_cal, 'res': brier_res, 'poc_ece': brier_poc, 'poc_brier': brier_bri, 'll_opt': brier_ll}
            eces = {'raw': ece_raw, 'cal': ece_cal, 'res': ece_res, 'poc_ece': ece_poc, 'poc_brier': ece_bri, 'll_opt': ece_ll}
            logloss_scores = {'raw': ll_raw, 'cal': ll_cal, 'res': ll_res, 'poc_ece': ll_poc, 'poc_brier': ll_bri, 'll_opt': ll_ll}
            best_brier = min(briers, key=briers.get)
            best_ece = min(eces, key=eces.get)
            best_logloss = min(logloss_scores, key=logloss_scores.get)
            
            # Get source used by per-over calibrators
            cal_key = f'inn{inn}_over{over}'
            poc_source = per_over_cals.get(cal_key, {}).get('source', 'N/A')
            brier_source = brier_cals.get(cal_key, {}).get('source', 'N/A')
            ll_source = logloss_cals.get(cal_key, {}).get('source', 'N/A')
            
            over_metrics.append({
                'Innings': inn,
                'Over': over,
                'N': n,
                'Brier_Raw': brier_raw,
                'Brier_InnSpec': brier_cal,
                'Brier_Resource': brier_res,
                'Brier_POC_ECE': brier_poc,
                'Brier_POC_Brier': brier_bri,
                'Brier_LL_Opt': brier_ll,
                'ECE_Raw': ece_raw,
                'ECE_InnSpec': ece_cal,
                'ECE_Resource': ece_res,
                'ECE_POC_ECE': ece_poc,
                'ECE_POC_Brier': ece_bri,
                'ECE_LL_Opt': ece_ll,
                'LogLoss_Raw': ll_raw,
                'LogLoss_InnSpec': ll_cal,
                'LogLoss_Resource': ll_res,
                'LogLoss_POC_ECE': ll_poc,
                'LogLoss_POC_Brier': ll_bri,
                'LogLoss_LL_Opt': ll_ll,
                'Best_Brier': best_brier,
                'Best_ECE': best_ece,
                'Best_LogLoss': best_logloss,
                'POC_ECE_Source': poc_source,
                'POC_Brier_Source': brier_source,
                'LL_Opt_Source': ll_source,
            })
            
            print(f"{inn:>3} {over:>4} {n:>6} | {brier_raw:>8.4f} {brier_poc:>8.4f} {brier_bri:>8.4f} | {ece_raw:>6.4f} {ece_poc:>6.4f} {ece_bri:>6.4f} | {best_brier:>10} {best_ece:>10}")
    
    over_df = pd.DataFrame(over_metrics)
    over_df.to_parquet(OUTPUT_DIR / "ssm_male_metrics_by_over.parquet", index=False)
    print(f"\n[OK] Saved per-over metrics to {OUTPUT_DIR / 'ssm_male_metrics_by_over.parquet'}")
    
    # ==========================================================================
    # ANALYSIS BY PHASE (for comparison)
    # ==========================================================================
    print("\n" + "="*80)
    print("ANALYSIS BY PHASE (SA20 STYLE - 8 PHASES)")
    print("="*80)
    
    phase_metrics = []
    
    for inn in [1, 2]:
        for phase_name in PHASES.keys():
            mask = (df['innings'] == inn) & (df['phase'] == phase_name)
            n = mask.sum()
            
            if n < 100:
                continue
            
            y_phase = y_true[mask]
            raw_phase = raw_probs[mask]
            cal_phase = cal_probs[mask]
            res_phase = resource_probs[mask]
            poc_phase = per_over_probs[mask]
            brier_phase = brier_probs[mask]
            ll_phase = logloss_probs[mask]
            
            brier_raw = brier_score_loss(y_phase, raw_phase)
            brier_cal = brier_score_loss(y_phase, cal_phase)
            brier_res = brier_score_loss(y_phase, res_phase)
            brier_poc = brier_score_loss(y_phase, poc_phase)
            brier_bri = brier_score_loss(y_phase, brier_phase)
            brier_ll = brier_score_loss(y_phase, ll_phase)
            
            ece_raw = calculate_ece(y_phase, raw_phase)
            ece_cal = calculate_ece(y_phase, cal_phase)
            ece_res = calculate_ece(y_phase, res_phase)
            ece_poc = calculate_ece(y_phase, poc_phase)
            ece_bri = calculate_ece(y_phase, brier_phase)
            ece_ll = calculate_ece(y_phase, ll_phase)
            
            ll_raw = log_loss(y_phase, raw_phase)
            ll_cal = log_loss(y_phase, cal_phase)
            ll_res = log_loss(y_phase, res_phase)
            ll_poc = log_loss(y_phase, poc_phase)
            ll_bri = log_loss(y_phase, brier_phase)
            ll_ll = log_loss(y_phase, ll_phase)
            
            # Determine best sources
            briers = {'raw': brier_raw, 'cal': brier_cal, 'res': brier_res, 'poc_ece': brier_poc, 'poc_brier': brier_bri, 'll_opt': brier_ll}
            eces = {'raw': ece_raw, 'cal': ece_cal, 'res': ece_res, 'poc_ece': ece_poc, 'poc_brier': ece_bri, 'll_opt': ece_ll}
            logloss_scores = {'raw': ll_raw, 'cal': ll_cal, 'res': ll_res, 'poc_ece': ll_poc, 'poc_brier': ll_bri, 'll_opt': ll_ll}
            best_brier = min(briers, key=briers.get)
            best_ece = min(eces, key=eces.get)
            best_logloss = min(logloss_scores, key=logloss_scores.get)
            
            phase_metrics.append({
                'Innings': inn,
                'Phase': phase_name,
                'N': n,
                'Brier_Raw': brier_raw,
                'Brier_InnSpec': brier_cal,
                'Brier_Resource': brier_res,
                'Brier_POC_ECE': brier_poc,
                'Brier_POC_Brier': brier_bri,
                'Brier_LL_Opt': brier_ll,
                'ECE_Raw': ece_raw,
                'ECE_InnSpec': ece_cal,
                'ECE_Resource': ece_res,
                'ECE_POC_ECE': ece_poc,
                'ECE_POC_Brier': ece_bri,
                'ECE_LL_Opt': ece_ll,
                'LogLoss_Raw': ll_raw,
                'LogLoss_InnSpec': ll_cal,
                'LogLoss_Resource': ll_res,
                'LogLoss_POC_ECE': ll_poc,
                'LogLoss_POC_Brier': ll_bri,
                'LogLoss_LL_Opt': ll_ll,
                'Best_Brier': best_brier,
                'Best_ECE': best_ece,
                'Best_LogLoss': best_logloss
            })
            
            print(f"Inn{inn} {phase_name:12s} N={n:5d} | Brier: Raw={brier_raw:.4f} ECE={brier_poc:.4f} Bri={brier_bri:.4f} | Best: {best_brier} | ECE Best: {best_ece}")
    
    phase_df = pd.DataFrame(phase_metrics)
    phase_df.to_parquet(OUTPUT_DIR / "ssm_male_metrics_by_phase.parquet", index=False)
    
    # ==========================================================================
    # SUMMARY
    # ==========================================================================
    print("\n" + "="*80)
    print("SUMMARY - PER-OVER CALIBRATOR SOURCES")
    print("="*80)
    
    print("\n| Inn | Over | ECE_Src | Brier_Src | ECE After |")
    print("|-----|------|---------|-----------|-----------|")
    for inn in [1, 2]:
        for over in range(1, 21):
            cal_key = f'inn{inn}_over{over}'
            ece_source = per_over_cals.get(cal_key, {}).get('source', 'N/A')
            brier_source = brier_cals.get(cal_key, {}).get('source', 'N/A')
            # Find ECE from over_df
            row = over_df[(over_df['Innings'] == inn) & (over_df['Over'] == over)]
            ece_poc = row['ECE_POC_ECE'].values[0] if len(row) > 0 else 'N/A'
            if isinstance(ece_poc, float):
                print(f"| {inn:>3} | {over:>4} | {ece_source:>7} | {brier_source:>9} | {ece_poc:>9.4f} |")
            else:
                print(f"| {inn:>3} | {over:>4} | {ece_source:>7} | {brier_source:>9} | {ece_poc:>9} |")
    
    # Overall statistics
    print("\n" + "="*80)
    print("OVERALL METRICS COMPARISON")
    print("="*80)
    
    print(f"\n{'Metric':<15} {'Raw':>12} {'InnSpec':>12} {'Resource':>12} {'POC_ECE':>12} {'POC_Brier':>12}")
    print("-" * 80)
    print(f"{'Brier':<15} {brier_score_loss(y_true, raw_probs):>12.4f} {brier_score_loss(y_true, cal_probs):>12.4f} {brier_score_loss(y_true, resource_probs):>12.4f} {brier_score_loss(y_true, per_over_probs):>12.4f} {brier_score_loss(y_true, brier_probs):>12.4f}")
    print(f"{'ECE':<15} {calculate_ece(y_true, raw_probs):>12.4f} {calculate_ece(y_true, cal_probs):>12.4f} {calculate_ece(y_true, resource_probs):>12.4f} {calculate_ece(y_true, per_over_probs):>12.4f} {calculate_ece(y_true, brier_probs):>12.4f}")
    print(f"{'Log Loss':<15} {log_loss(y_true, raw_probs):>12.4f} {log_loss(y_true, cal_probs):>12.4f} {log_loss(y_true, resource_probs):>12.4f} {log_loss(y_true, per_over_probs):>12.4f} {log_loss(y_true, brier_probs):>12.4f}")
    
    print("\n[OK] Analysis complete!")
    print(f"[OK] Metrics saved to:")
    print(f"  - {OUTPUT_DIR / 'ssm_male_metrics_by_inning.parquet'}")
    print(f"  - {OUTPUT_DIR / 'ssm_male_metrics_by_over.parquet'}")
    print(f"  - {OUTPUT_DIR / 'ssm_male_metrics_by_phase.parquet'}")


if __name__ == "__main__":
    main()
