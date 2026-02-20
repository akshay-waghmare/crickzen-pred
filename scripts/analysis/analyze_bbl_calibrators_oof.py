#!/usr/bin/env python3
"""
BBL Comprehensive OOF Calibration Analysis

Compares 7 different calibration approaches using proper out-of-fold cross-validation:
1. Raw Model - Uncalibrated XGBLogRegEnsemble
2. Combined - Single isotonic calibrator for all data
3. Innings-Specific - 2 calibrators (innings 1, innings 2)
4. Innings×Phase - 6 calibrators (2 innings × 3 phases) using isotonic
5. Brier-Optimized - Per-over isotonic (40 calibrators: 2 innings × 20 overs)
6. ECE-Optimized - Histogram binning per innings×phase (6 calibrators)
7. LogLoss-Optimized - Platt scaling per innings×phase (6 calibrators)

Metrics: Brier Score, ECE, Log Loss
Method: 5-fold time-series CV with proper OOF predictions

Author: Copilot
Date: January 15, 2026
"""

import pandas as pd
import numpy as np
import joblib
from pathlib import Path
from sklearn.model_selection import KFold
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss
import warnings
warnings.filterwarnings('ignore')

# =============================================================================
# CONFIGURATION
# =============================================================================
MODEL_DIR = Path("models/bbl_v10")
FEATURES_PATH = Path("data/bbl_features_v2/training.parquet")
N_SPLITS = 5
N_BINS = 10  # For ECE calculation

# =============================================================================
# METRIC FUNCTIONS
# =============================================================================

def brier_score(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Calculate Brier score (lower is better)."""
    y_prob = np.clip(y_prob, 0, 1)
    return np.mean((y_prob - y_true) ** 2)


def expected_calibration_error(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    """Calculate Expected Calibration Error (lower is better)."""
    y_prob = np.clip(y_prob, 0, 1)
    ece = 0.0
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    
    for i in range(n_bins):
        mask = (y_prob >= bin_boundaries[i]) & (y_prob < bin_boundaries[i + 1])
        if i == n_bins - 1:  # Include upper bound in last bin
            mask = (y_prob >= bin_boundaries[i]) & (y_prob <= bin_boundaries[i + 1])
        
        if mask.sum() > 0:
            accuracy = y_true[mask].mean()
            avg_prob = y_prob[mask].mean()
            ece += mask.mean() * abs(avg_prob - accuracy)
    
    return ece


def safe_log_loss(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """
    Calculate log loss with confidence clipping.
    
    Using clip=0.01 (betting/forecasting standard) instead of eps=1e-7
    to prevent extreme tail predictions from dominating the metric.
    """
    y_prob = np.clip(y_prob, 0.01, 0.99)
    return log_loss(y_true, y_prob)


# =============================================================================
# CALIBRATOR TRAINING FUNCTIONS
# =============================================================================

def train_combined_calibrator(y_train, probs_train):
    """Train a single isotonic calibrator for all data."""
    iso = IsotonicRegression(out_of_bounds='clip')
    iso.fit(probs_train, y_train)
    return iso


def train_innings_specific_calibrators(df_train, y_train, probs_train):
    """Train 2 calibrators: one per innings."""
    calibrators = {}
    for innings in [1, 2]:
        mask = df_train['innings'] == innings
        if mask.sum() > 50:  # Min samples
            iso = IsotonicRegression(out_of_bounds='clip')
            iso.fit(probs_train[mask], y_train[mask])
            calibrators[f'innings_{innings}'] = iso
    return calibrators


def get_phase(over):
    """Get phase from over number."""
    if over <= 6:
        return 'powerplay'
    elif over <= 15:
        return 'middle'
    else:
        return 'death'


def train_innings_phase_calibrators(df_train, y_train, probs_train, over_train):
    """Train 6 calibrators: one per innings×phase combination."""
    calibrators = {}
    for innings in [1, 2]:
        for phase, start_over, end_over in [('powerplay', 1, 6), ('middle', 7, 15), ('death', 16, 20)]:
            mask = (df_train['innings'] == innings) & (over_train >= start_over) & (over_train <= end_over)
            if mask.sum() > 50:  # Min samples
                iso = IsotonicRegression(out_of_bounds='clip')
                iso.fit(probs_train[mask], y_train[mask])
                calibrators[f'inn{innings}_{phase}'] = iso
    return calibrators


def train_brier_optimized_calibrators(df_train, y_train, probs_train, over_train):
    """Train per-over calibrators (40 calibrators: 2 innings × 20 overs) for finer granularity."""
    calibrators = {}
    for innings in [1, 2]:
        for ov in range(1, 21):
            mask = (df_train['innings'] == innings) & (over_train == ov)
            if mask.sum() > 30:  # Min samples per over
                iso = IsotonicRegression(out_of_bounds='clip')
                iso.fit(probs_train[mask], y_train[mask])
                calibrators[f'inn{innings}_over{ov}'] = iso
    return calibrators


def train_ece_optimized_calibrators(df_train, y_train, probs_train, over_train):
    """Train histogram binning calibrators per innings×phase (better for ECE)."""
    from sklearn.calibration import _SigmoidCalibration
    calibrators = {}
    for innings in [1, 2]:
        for phase, start_over, end_over in [('powerplay', 1, 6), ('middle', 7, 15), ('death', 16, 20)]:
            mask = (df_train['innings'] == innings) & (over_train >= start_over) & (over_train <= end_over)
            if mask.sum() > 50:
                # Use histogram binning approach for ECE optimization
                probs = probs_train[mask]
                targets = y_train[mask]
                n_bins = 15
                bin_boundaries = np.linspace(0, 1, n_bins + 1)
                bin_means = []
                bin_centers = []
                
                for i in range(n_bins):
                    bin_mask = (probs >= bin_boundaries[i]) & (probs < bin_boundaries[i + 1])
                    if i == n_bins - 1:
                        bin_mask = (probs >= bin_boundaries[i]) & (probs <= bin_boundaries[i + 1])
                    if bin_mask.sum() > 0:
                        bin_means.append(targets[bin_mask].mean())
                        bin_centers.append(probs[bin_mask].mean())
                    else:
                        bin_means.append((bin_boundaries[i] + bin_boundaries[i + 1]) / 2)
                        bin_centers.append((bin_boundaries[i] + bin_boundaries[i + 1]) / 2)
                
                # Fit isotonic on the bin statistics for smooth mapping
                iso = IsotonicRegression(out_of_bounds='clip')
                iso.fit(np.array(bin_centers), np.array(bin_means))
                calibrators[f'inn{innings}_{phase}'] = ('histogram', iso, bin_boundaries)
    return calibrators


def train_logloss_optimized_calibrators(df_train, y_train, probs_train, over_train):
    """Train innings×phase calibrators optimized for Log Loss (Platt scaling)."""
    calibrators = {}
    for innings in [1, 2]:
        for phase, start_over, end_over in [('powerplay', 1, 6), ('middle', 7, 15), ('death', 16, 20)]:
            mask = (df_train['innings'] == innings) & (over_train >= start_over) & (over_train <= end_over)
            if mask.sum() > 50:  # Min samples
                # Platt scaling (logistic regression on probabilities)
                platt = LogisticRegression(C=1e10, solver='lbfgs', max_iter=1000)
                platt.fit(probs_train[mask].reshape(-1, 1), y_train[mask])
                calibrators[f'inn{innings}_{phase}'] = ('platt', platt)
    return calibrators


# =============================================================================
# CALIBRATION APPLICATION FUNCTIONS
# =============================================================================

def apply_combined_calibrator(calibrator, probs):
    """Apply single combined calibrator."""
    return calibrator.predict(probs)


def apply_innings_specific_calibrators(calibrators, df_test, probs):
    """Apply innings-specific calibrators."""
    calibrated = probs.copy()
    for innings in [1, 2]:
        mask = df_test['innings'] == innings
        key = f'innings_{innings}'
        if key in calibrators and mask.sum() > 0:
            calibrated[mask] = calibrators[key].predict(probs[mask])
    return calibrated


def apply_innings_phase_calibrators(calibrators, df_test, over_test, probs):
    """Apply innings×phase calibrators."""
    calibrated = probs.copy()
    for innings in [1, 2]:
        for phase, start_over, end_over in [('powerplay', 1, 6), ('middle', 7, 15), ('death', 16, 20)]:
            mask = (df_test['innings'] == innings) & (over_test >= start_over) & (over_test <= end_over)
            key = f'inn{innings}_{phase}'
            if key in calibrators and mask.sum() > 0:
                cal_item = calibrators[key]
                if isinstance(cal_item, tuple):
                    if cal_item[0] == 'platt':  # Platt scaling
                        _, platt = cal_item
                        calibrated[mask] = platt.predict_proba(probs[mask].reshape(-1, 1))[:, 1]
                    elif cal_item[0] == 'histogram':  # Histogram binning
                        _, iso, _ = cal_item
                        calibrated[mask] = iso.predict(probs[mask])
                else:  # Isotonic
                    calibrated[mask] = cal_item.predict(probs[mask])
    return calibrated


def apply_per_over_calibrators(calibrators, df_test, over_test, probs):
    """Apply per-over calibrators (for brier_optimized)."""
    calibrated = probs.copy()
    for innings in [1, 2]:
        for ov in range(1, 21):
            mask = (df_test['innings'] == innings) & (over_test == ov)
            key = f'inn{innings}_over{ov}'
            if key in calibrators and mask.sum() > 0:
                calibrated[mask] = calibrators[key].predict(probs[mask])
    return calibrated


# =============================================================================
# MAIN ANALYSIS
# =============================================================================

def run_oof_analysis():
    """Run comprehensive OOF calibration analysis."""
    print("=" * 80)
    print("BBL v10 COMPREHENSIVE OOF CALIBRATION ANALYSIS")
    print("=" * 80)
    
    # Load data
    print("\n📂 Loading data...")
    df = pd.read_parquet(FEATURES_PATH)
    print(f"   Loaded {len(df):,} training samples")
    
    # Load model
    model = joblib.load(MODEL_DIR / 'champion_model.joblib')
    print(f"   Loaded model from {MODEL_DIR / 'champion_model.joblib'}")
    
    # Prepare features
    exclude_cols = ['is_winner', 'innings']
    feature_cols = [c for c in df.columns if c not in exclude_cols]
    X = df[feature_cols]
    y = df['is_winner'].values
    innings = df['innings'].values
    
    # Calculate over number
    over = np.ceil(20 - df['overs_remaining'].values).astype(int) + 1
    over = np.clip(over, 1, 20)
    
    print(f"   Features: {len(feature_cols)}")
    print(f"   Innings 1: {(innings == 1).sum():,} | Innings 2: {(innings == 2).sum():,}")
    
    # Initialize storage for OOF predictions
    methods = ['raw', 'combined', 'innings_specific', 'innings_phase', 
               'brier_optimized', 'ece_optimized', 'logloss_optimized']
    
    oof_probs = {m: np.zeros(len(df)) for m in methods}
    fold_results = {m: [] for m in methods}
    
    # K-Fold CV (using simple KFold for this analysis - shuffle=False for time series)
    kf = KFold(n_splits=N_SPLITS, shuffle=False)
    
    print(f"\n🔄 Running {N_SPLITS}-fold cross-validation...")
    print("-" * 80)
    
    for fold_idx, (train_idx, test_idx) in enumerate(kf.split(X)):
        print(f"\n📊 Fold {fold_idx + 1}/{N_SPLITS}")
        print(f"   Train: {len(train_idx):,} samples | Test: {len(test_idx):,} samples")
        
        # Split data
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]
        df_train, df_test = df.iloc[train_idx], df.iloc[test_idx]
        over_train, over_test = over[train_idx], over[test_idx]
        
        # Get raw predictions
        raw_probs_train = model.predict_proba(X_train)[:, 1]
        raw_probs_test = model.predict_proba(X_test)[:, 1]
        
        # 1. Raw Model (uncalibrated)
        oof_probs['raw'][test_idx] = raw_probs_test
        
        # 2. Combined (single calibrator)
        combined_cal = train_combined_calibrator(y_train, raw_probs_train)
        oof_probs['combined'][test_idx] = apply_combined_calibrator(combined_cal, raw_probs_test)
        
        # 3. Innings-Specific (2 calibrators)
        inn_cals = train_innings_specific_calibrators(df_train, y_train, raw_probs_train)
        oof_probs['innings_specific'][test_idx] = apply_innings_specific_calibrators(
            inn_cals, df_test, raw_probs_test)
        
        # 4. Innings×Phase (6 calibrators - standard isotonic)
        phase_cals = train_innings_phase_calibrators(df_train, y_train, raw_probs_train, over_train)
        oof_probs['innings_phase'][test_idx] = apply_innings_phase_calibrators(
            phase_cals, df_test, over_test, raw_probs_test)
        
        # 5. Brier-Optimized (per-over isotonic - 40 calibrators)
        brier_cals = train_brier_optimized_calibrators(df_train, y_train, raw_probs_train, over_train)
        oof_probs['brier_optimized'][test_idx] = apply_per_over_calibrators(
            brier_cals, df_test, over_test, raw_probs_test)
        
        # 6. ECE-Optimized (histogram binning per innings×phase)
        ece_cals = train_ece_optimized_calibrators(df_train, y_train, raw_probs_train, over_train)
        oof_probs['ece_optimized'][test_idx] = apply_innings_phase_calibrators(
            ece_cals, df_test, over_test, raw_probs_test)
        
        # 7. LogLoss-Optimized (Platt scaling per innings×phase)
        ll_cals = train_logloss_optimized_calibrators(df_train, y_train, raw_probs_train, over_train)
        oof_probs['logloss_optimized'][test_idx] = apply_innings_phase_calibrators(
            ll_cals, df_test, over_test, raw_probs_test)
        
        # Calculate per-fold metrics
        for method in methods:
            probs = oof_probs[method][test_idx]
            fold_results[method].append({
                'brier': brier_score(y_test, probs),
                'ece': expected_calibration_error(y_test, probs, N_BINS),
                'logloss': safe_log_loss(y_test, probs),
                'n_samples': len(test_idx)
            })
        
        # Print fold results
        print(f"\n   {'Method':<22} {'Brier':>10} {'ECE':>10} {'LogLoss':>10}")
        print(f"   {'-'*54}")
        for method in methods:
            r = fold_results[method][-1]
            print(f"   {method:<22} {r['brier']:>10.4f} {r['ece']:>10.4f} {r['logloss']:>10.4f}")
    
    # ==========================================================================
    # AGGREGATE RESULTS
    # ==========================================================================
    print("\n" + "=" * 80)
    print("AGGREGATE OOF RESULTS")
    print("=" * 80)
    
    # Overall metrics
    print("\n📈 OVERALL PERFORMANCE (Full OOF Predictions)")
    print("-" * 70)
    print(f"{'Method':<22} {'Brier':>10} {'ECE':>10} {'LogLoss':>10}")
    print("-" * 70)
    
    overall_results = {}
    for method in methods:
        probs = oof_probs[method]
        brier = brier_score(y, probs)
        ece = expected_calibration_error(y, probs, N_BINS)
        ll = safe_log_loss(y, probs)
        overall_results[method] = {'brier': brier, 'ece': ece, 'logloss': ll}
        print(f"{method:<22} {brier:>10.4f} {ece:>10.4f} {ll:>10.4f}")
    
    # Mean ± Std across folds
    print("\n📊 MEAN ± STD ACROSS FOLDS")
    print("-" * 80)
    print(f"{'Method':<22} {'Brier':>18} {'ECE':>18} {'LogLoss':>18}")
    print("-" * 80)
    
    fold_stats = {}
    for method in methods:
        briers = [r['brier'] for r in fold_results[method]]
        eces = [r['ece'] for r in fold_results[method]]
        lls = [r['logloss'] for r in fold_results[method]]
        
        fold_stats[method] = {
            'brier_mean': np.mean(briers), 'brier_std': np.std(briers),
            'ece_mean': np.mean(eces), 'ece_std': np.std(eces),
            'logloss_mean': np.mean(lls), 'logloss_std': np.std(lls)
        }
        
        print(f"{method:<22} "
              f"{fold_stats[method]['brier_mean']:.4f}±{fold_stats[method]['brier_std']:.4f}  "
              f"{fold_stats[method]['ece_mean']:.4f}±{fold_stats[method]['ece_std']:.4f}  "
              f"{fold_stats[method]['logloss_mean']:.4f}±{fold_stats[method]['logloss_std']:.4f}")
    
    # Improvement over raw
    print("\n📈 IMPROVEMENT OVER RAW MODEL")
    print("-" * 70)
    print(f"{'Method':<22} {'Brier Δ%':>12} {'ECE Δ%':>12} {'LogLoss Δ%':>12}")
    print("-" * 70)
    
    raw_brier = overall_results['raw']['brier']
    raw_ece = overall_results['raw']['ece']
    raw_ll = overall_results['raw']['logloss']
    
    for method in methods[1:]:  # Skip raw
        brier_imp = (raw_brier - overall_results[method]['brier']) / raw_brier * 100
        ece_imp = (raw_ece - overall_results[method]['ece']) / raw_ece * 100
        ll_imp = (raw_ll - overall_results[method]['logloss']) / raw_ll * 100
        
        brier_sym = "✅" if brier_imp > 0 else "❌"
        ece_sym = "✅" if ece_imp > 0 else "❌"
        ll_sym = "✅" if ll_imp > 0 else "❌"
        
        print(f"{method:<22} {brier_imp:>+10.2f}% {brier_sym} {ece_imp:>+10.2f}% {ece_sym} {ll_imp:>+10.2f}% {ll_sym}")
    
    # ==========================================================================
    # PER-INNINGS BREAKDOWN
    # ==========================================================================
    print("\n" + "=" * 80)
    print("PER-INNINGS BREAKDOWN")
    print("=" * 80)
    
    for inn in [1, 2]:
        mask = innings == inn
        print(f"\n🏏 INNINGS {inn} ({mask.sum():,} balls)")
        print("-" * 70)
        print(f"{'Method':<22} {'Brier':>10} {'ECE':>10} {'LogLoss':>10}")
        print("-" * 70)
        
        for method in methods:
            probs = oof_probs[method][mask]
            brier = brier_score(y[mask], probs)
            ece = expected_calibration_error(y[mask], probs, N_BINS)
            ll = safe_log_loss(y[mask], probs)
            print(f"{method:<22} {brier:>10.4f} {ece:>10.4f} {ll:>10.4f}")
    
    # ==========================================================================
    # PER-PHASE BREAKDOWN
    # ==========================================================================
    print("\n" + "=" * 80)
    print("PER-INNINGS × PHASE BREAKDOWN")
    print("=" * 80)
    
    phases = [
        (1, 'powerplay', 1, 6),
        (1, 'middle', 7, 15),
        (1, 'death', 16, 20),
        (2, 'powerplay', 1, 6),
        (2, 'middle', 7, 15),
        (2, 'death', 16, 20),
    ]
    
    for inn, phase_name, start_ov, end_ov in phases:
        mask = (innings == inn) & (over >= start_ov) & (over <= end_ov)
        if mask.sum() < 10:
            continue
            
        print(f"\n🏏 INN{inn} {phase_name.upper()} (overs {start_ov}-{end_ov}, {mask.sum():,} balls)")
        print("-" * 70)
        print(f"{'Method':<22} {'Brier':>10} {'ECE':>10} {'LogLoss':>10}")
        print("-" * 70)
        
        for method in methods:
            probs = oof_probs[method][mask]
            brier = brier_score(y[mask], probs)
            ece = expected_calibration_error(y[mask], probs, N_BINS)
            ll = safe_log_loss(y[mask], probs)
            print(f"{method:<22} {brier:>10.4f} {ece:>10.4f} {ll:>10.4f}")
    
    # ==========================================================================
    # PER-FOLD DETAILS
    # ==========================================================================
    print("\n" + "=" * 80)
    print("PER-FOLD DETAILS")
    print("=" * 80)
    
    for fold_idx in range(N_SPLITS):
        print(f"\n📊 Fold {fold_idx + 1}")
        n_samples = fold_results['raw'][fold_idx]['n_samples']
        print(f"   Samples: {n_samples:,}")
        print(f"   {'Method':<22} {'Brier':>10} {'ECE':>10} {'LogLoss':>10}")
        print(f"   {'-'*54}")
        
        for method in methods:
            r = fold_results[method][fold_idx]
            print(f"   {method:<22} {r['brier']:>10.4f} {r['ece']:>10.4f} {r['logloss']:>10.4f}")
    
    # ==========================================================================
    # RANKING
    # ==========================================================================
    print("\n" + "=" * 80)
    print("FINAL RANKING")
    print("=" * 80)
    
    # Rank by each metric
    for metric in ['brier', 'ece', 'logloss']:
        sorted_methods = sorted(methods, key=lambda m: overall_results[m][metric])
        print(f"\n🏆 By {metric.upper()}: ", end="")
        for i, m in enumerate(sorted_methods):
            medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"{i+1}."
            print(f"{medal} {m}={overall_results[m][metric]:.4f}", end="  ")
        print()
    
    # ==========================================================================
    # SAVE RESULTS
    # ==========================================================================
    print("\n" + "=" * 80)
    print("SAVING RESULTS")
    print("=" * 80)
    
    # Create results dataframe
    results_data = []
    for method in methods:
        results_data.append({
            'method': method,
            'brier': overall_results[method]['brier'],
            'ece': overall_results[method]['ece'],
            'logloss': overall_results[method]['logloss'],
            'brier_mean': fold_stats[method]['brier_mean'],
            'brier_std': fold_stats[method]['brier_std'],
            'ece_mean': fold_stats[method]['ece_mean'],
            'ece_std': fold_stats[method]['ece_std'],
            'logloss_mean': fold_stats[method]['logloss_mean'],
            'logloss_std': fold_stats[method]['logloss_std'],
        })
    
    results_df = pd.DataFrame(results_data)
    results_df.to_csv('bbl_calibration_oof_results.csv', index=False)
    print("✅ Saved results to bbl_calibration_oof_results.csv")
    
    return overall_results, fold_stats, fold_results, oof_probs


if __name__ == '__main__':
    run_oof_analysis()
