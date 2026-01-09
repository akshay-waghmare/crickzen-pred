"""
Analyze SA20 model calibration: Platt scaling vs Isotonic regression

Given the limited SA20 data (~21k rows), this script compares:
1. Current phase-wise isotonic calibration
2. Platt scaling (logistic regression)
3. Hybrid approaches

Metrics: Brier Score, ECE (Expected Calibration Error), reliability diagrams
"""

import pandas as pd
import numpy as np
import joblib
from pathlib import Path
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.linear_model import LogisticRegression
from sklearn.isotonic import IsotonicRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict
import warnings
warnings.filterwarnings('ignore')

# Paths
FEATURES_PATH = Path('data/sat_features_v1/training.parquet')
MODEL_PATH = Path('models/sat_v1')

def load_data():
    """Load SA20 training features."""
    df = pd.read_parquet(FEATURES_PATH)
    print(f"Loaded {len(df):,} rows from SA20 training data")
    return df

def get_phase(over):
    """Map over to phase (1-indexed over number)."""
    if over <= 6:
        return 'powerplay'
    elif over <= 11:
        return 'middle_early'
    elif over <= 15:
        return 'middle_late'
    else:
        return 'death'

def calculate_ece(y_true, y_pred, n_bins=10):
    """Calculate Expected Calibration Error."""
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        mask = (y_pred >= bin_boundaries[i]) & (y_pred < bin_boundaries[i + 1])
        if mask.sum() > 0:
            bin_accuracy = y_true[mask].mean()
            bin_confidence = y_pred[mask].mean()
            bin_weight = mask.sum() / len(y_true)
            ece += bin_weight * abs(bin_accuracy - bin_confidence)
    return ece

def calculate_brier(y_true, y_pred):
    """Calculate Brier score."""
    return np.mean((y_true - y_pred) ** 2)

def analyze_data_distribution(df):
    """Analyze data distribution by innings and phase."""
    print("\n" + "="*60)
    print("DATA DISTRIBUTION ANALYSIS")
    print("="*60)
    
    # Calculate over from overs_remaining
    df['over'] = (20 - df['overs_remaining']).clip(1, 20).astype(int)
    df['phase'] = df['over'].apply(get_phase)
    
    # By innings
    if 'innings' in df.columns:
        print("\nBy Innings:")
        innings_counts = df.groupby('innings').size()
        print(innings_counts)
    
    # By phase
    print("\nBy Phase:")
    phase_counts = df.groupby('phase').size()
    print(phase_counts)
    
    # By innings x phase
    if 'innings' in df.columns:
        print("\nBy Innings x Phase:")
        cross_counts = df.groupby(['innings', 'phase']).size().unstack(fill_value=0)
        print(cross_counts)
        
        print("\n⚠️ Minimum samples per cell:", cross_counts.min().min())
        print("   Recommended minimum for isotonic: ~200 samples")
        print("   Recommended minimum for Platt: ~50 samples")
    
    return df

def compare_calibration_methods(df, model_probs, y_true, method_name=""):
    """Compare Platt vs Isotonic calibration using cross-validation."""
    print(f"\n{'='*60}")
    print(f"CALIBRATION COMPARISON: {method_name}")
    print(f"{'='*60}")
    
    n_samples = len(df)
    print(f"Samples: {n_samples:,}")
    
    # Raw model performance
    raw_brier = calculate_brier(y_true, model_probs)
    raw_ece = calculate_ece(y_true, model_probs)
    print(f"\n📊 Raw Model:")
    print(f"   Brier: {raw_brier:.4f}")
    print(f"   ECE:   {raw_ece:.4f}")
    
    results = {
        'raw': {'brier': raw_brier, 'ece': raw_ece}
    }
    
    # Prepare for CV calibration
    n_splits = min(5, n_samples // 50)  # At least 50 samples per fold
    if n_splits < 2:
        print(f"⚠️ Not enough samples for CV (need at least 100, have {n_samples})")
        return results
    
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    
    # Platt Scaling (Logistic Regression on logits)
    try:
        platt_preds = np.zeros(n_samples)
        for train_idx, val_idx in skf.split(model_probs.reshape(-1, 1), y_true):
            # Convert to logits for Platt scaling
            train_probs = np.clip(model_probs[train_idx], 1e-6, 1-1e-6)
            train_logits = np.log(train_probs / (1 - train_probs))
            
            lr = LogisticRegression(solver='lbfgs', max_iter=1000)
            lr.fit(train_logits.reshape(-1, 1), y_true[train_idx])
            
            val_probs = np.clip(model_probs[val_idx], 1e-6, 1-1e-6)
            val_logits = np.log(val_probs / (1 - val_probs))
            platt_preds[val_idx] = lr.predict_proba(val_logits.reshape(-1, 1))[:, 1]
        
        platt_brier = calculate_brier(y_true, platt_preds)
        platt_ece = calculate_ece(y_true, platt_preds)
        print(f"\n🔵 Platt Scaling (Logistic):")
        print(f"   Brier: {platt_brier:.4f} ({'+' if platt_brier > raw_brier else ''}{(platt_brier - raw_brier)*100:.2f}%)")
        print(f"   ECE:   {platt_ece:.4f} ({'+' if platt_ece > raw_ece else ''}{(platt_ece - raw_ece)*100:.2f}%)")
        results['platt'] = {'brier': platt_brier, 'ece': platt_ece}
    except Exception as e:
        print(f"⚠️ Platt scaling failed: {e}")
    
    # Isotonic Regression
    try:
        iso_preds = np.zeros(n_samples)
        for train_idx, val_idx in skf.split(model_probs.reshape(-1, 1), y_true):
            ir = IsotonicRegression(out_of_bounds='clip')
            ir.fit(model_probs[train_idx], y_true[train_idx])
            iso_preds[val_idx] = ir.predict(model_probs[val_idx])
        
        iso_brier = calculate_brier(y_true, iso_preds)
        iso_ece = calculate_ece(y_true, iso_preds)
        print(f"\n🟢 Isotonic Regression:")
        print(f"   Brier: {iso_brier:.4f} ({'+' if iso_brier > raw_brier else ''}{(iso_brier - raw_brier)*100:.2f}%)")
        print(f"   ECE:   {iso_ece:.4f} ({'+' if iso_ece > raw_ece else ''}{(iso_ece - raw_ece)*100:.2f}%)")
        results['isotonic'] = {'brier': iso_brier, 'ece': iso_ece}
    except Exception as e:
        print(f"⚠️ Isotonic regression failed: {e}")
    
    # Beta Calibration (approximated with scaled sigmoid)
    try:
        beta_preds = np.zeros(n_samples)
        for train_idx, val_idx in skf.split(model_probs.reshape(-1, 1), y_true):
            # Use log-odds and squared log-odds as features
            train_probs = np.clip(model_probs[train_idx], 1e-6, 1-1e-6)
            train_logits = np.log(train_probs / (1 - train_probs))
            train_X = np.column_stack([train_logits, train_logits**2])
            
            lr = LogisticRegression(solver='lbfgs', max_iter=1000)
            lr.fit(train_X, y_true[train_idx])
            
            val_probs = np.clip(model_probs[val_idx], 1e-6, 1-1e-6)
            val_logits = np.log(val_probs / (1 - val_probs))
            val_X = np.column_stack([val_logits, val_logits**2])
            beta_preds[val_idx] = lr.predict_proba(val_X)[:, 1]
        
        beta_brier = calculate_brier(y_true, beta_preds)
        beta_ece = calculate_ece(y_true, beta_preds)
        print(f"\n🟣 Beta Calibration (Approx):")
        print(f"   Brier: {beta_brier:.4f} ({'+' if beta_brier > raw_brier else ''}{(beta_brier - raw_brier)*100:.2f}%)")
        print(f"   ECE:   {beta_ece:.4f} ({'+' if beta_ece > raw_ece else ''}{(beta_ece - raw_ece)*100:.2f}%)")
        results['beta'] = {'brier': beta_brier, 'ece': beta_ece}
    except Exception as e:
        print(f"⚠️ Beta calibration failed: {e}")
    
    return results

def analyze_by_phase(df, probs_col='raw_win_prob', target_col='batting_team_won'):
    """Analyze calibration by phase and innings."""
    print("\n" + "="*60)
    print("PHASE-WISE CALIBRATION ANALYSIS")
    print("="*60)
    
    df['over'] = (20 - df['overs_remaining']).clip(1, 20).astype(int)
    df['phase'] = df['over'].apply(get_phase)
    
    all_results = {}
    
    for innings in [1, 2]:
        print(f"\n{'='*50}")
        print(f"INNINGS {innings}")
        print(f"{'='*50}")
        
        for phase in ['powerplay', 'middle_early', 'middle_late', 'death']:
            mask = (df['innings'] == innings) & (df['phase'] == phase)
            subset = df[mask]
            
            if len(subset) < 50:
                print(f"\n⚠️ Inn{innings} {phase}: Only {len(subset)} samples - SKIPPING")
                continue
            
            model_probs = subset[probs_col].values
            y_true = subset[target_col].values
            
            results = compare_calibration_methods(
                subset, model_probs, y_true, 
                f"Inn{innings} - {phase}"
            )
            all_results[f'inn{innings}_{phase}'] = results
    
    return all_results

def generate_recommendations(all_results):
    """Generate recommendations based on analysis."""
    print("\n" + "="*60)
    print("📋 RECOMMENDATIONS")
    print("="*60)
    
    recommendations = []
    
    for key, results in all_results.items():
        if not results:
            continue
            
        raw_brier = results.get('raw', {}).get('brier', 999)
        raw_ece = results.get('raw', {}).get('ece', 999)
        
        best_brier_method = 'raw'
        best_brier = raw_brier
        best_ece_method = 'raw'
        best_ece = raw_ece
        
        for method in ['platt', 'isotonic', 'beta']:
            if method in results:
                if results[method]['brier'] < best_brier:
                    best_brier = results[method]['brier']
                    best_brier_method = method
                if results[method]['ece'] < best_ece:
                    best_ece = results[method]['ece']
                    best_ece_method = method
        
        recommendations.append({
            'segment': key,
            'best_brier': best_brier_method,
            'best_ece': best_ece_method,
            'brier_improvement': (raw_brier - best_brier) * 100,
            'ece_improvement': (raw_ece - best_ece) * 100
        })
    
    print("\n| Segment | Best for Brier | Best for ECE | Brier Δ | ECE Δ |")
    print("|---------|----------------|--------------|---------|-------|")
    
    platt_wins_brier = 0
    isotonic_wins_brier = 0
    platt_wins_ece = 0
    isotonic_wins_ece = 0
    
    for rec in recommendations:
        print(f"| {rec['segment']:<22} | {rec['best_brier']:<14} | {rec['best_ece']:<12} | {rec['brier_improvement']:+.2f}% | {rec['ece_improvement']:+.2f}% |")
        
        if rec['best_brier'] == 'platt':
            platt_wins_brier += 1
        elif rec['best_brier'] == 'isotonic':
            isotonic_wins_brier += 1
        
        if rec['best_ece'] == 'platt':
            platt_wins_ece += 1
        elif rec['best_ece'] == 'isotonic':
            isotonic_wins_ece += 1
    
    print(f"\n📊 SUMMARY:")
    print(f"   Platt wins (Brier): {platt_wins_brier} | Isotonic wins (Brier): {isotonic_wins_brier}")
    print(f"   Platt wins (ECE):   {platt_wins_ece} | Isotonic wins (ECE):   {isotonic_wins_ece}")
    
    if platt_wins_brier + platt_wins_ece > isotonic_wins_brier + isotonic_wins_ece:
        print("\n✅ RECOMMENDATION: Use PLATT SCALING for SA20")
        print("   Reason: Better performance with limited data (less overfitting)")
    else:
        print("\n✅ RECOMMENDATION: Use ISOTONIC REGRESSION for SA20")
        print("   Reason: Better calibration despite smaller dataset")
    
    return recommendations

def main():
    print("="*60)
    print("SA20 CALIBRATION ANALYSIS: Platt vs Isotonic")
    print("="*60)
    
    # Load data
    df = load_data()
    
    # Analyze distribution
    df = analyze_data_distribution(df)
    
    # Check required columns
    if 'resource_win_prob' not in df.columns:
        print("\n⚠️ 'resource_win_prob' not found. Using available probability column.")
        prob_cols = [c for c in df.columns if 'prob' in c.lower() or 'win' in c.lower()]
        print(f"   Available: {prob_cols}")
        if prob_cols:
            probs_col = prob_cols[0]
        else:
            print("   ERROR: No probability column found!")
            return
    else:
        probs_col = 'resource_win_prob'
    
    if 'batting_team_won' not in df.columns:
        print("\n⚠️ 'batting_team_won' not found. Looking for target column...")
        target_cols = [c for c in df.columns if 'won' in c.lower() or 'winner' in c.lower() or 'is_winner' in c.lower()]
        print(f"   Available: {target_cols}")
        if 'is_winner' in df.columns:
            target_col = 'is_winner'
        elif target_cols:
            target_col = target_cols[0]
        else:
            print("   ERROR: No target column found!")
            return
    else:
        target_col = 'batting_team_won'
    
    print(f"\n📌 Using probability column: {probs_col}")
    print(f"📌 Using target column: {target_col}")
    
    # Overall comparison
    model_probs = df[probs_col].values
    y_true = df[target_col].values
    
    print("\n" + "="*60)
    print("OVERALL CALIBRATION (All Data)")
    print("="*60)
    overall_results = compare_calibration_methods(df, model_probs, y_true, "All SA20 Data")
    
    # Per-innings comparison
    if 'innings' in df.columns:
        print("\n" + "="*60)
        print("BY INNINGS")
        print("="*60)
        
        innings_results = {}
        for inn in [1, 2]:
            mask = df['innings'] == inn
            subset = df[mask]
            results = compare_calibration_methods(
                subset, 
                subset[probs_col].values, 
                subset[target_col].values, 
                f"Innings {inn}"
            )
            innings_results[f'innings_{inn}'] = results
    
    # Phase-wise analysis
    if 'innings' in df.columns:
        all_results = analyze_by_phase(df, probs_col, target_col)
        
        # Generate recommendations
        generate_recommendations(all_results)
    
    print("\n" + "="*60)
    print("ANALYSIS COMPLETE")
    print("="*60)

if __name__ == "__main__":
    main()
