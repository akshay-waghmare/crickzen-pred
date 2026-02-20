"""
Analyze Brier, ECE, and Log Loss for T20 Male (International) model.
Compare raw model probabilities vs innings-calibrated vs resource-based probabilities.

This is similar to analyze_bbl_log_loss.py but for the T20 international men's model.
"""
import joblib
import pandas as pd
import numpy as np
from pathlib import Path
import json

def log_loss(y_true: np.ndarray, y_prob: np.ndarray, clip: float = 0.01) -> float:
    """Calculate log loss (cross-entropy) with confidence clipping.
    
    Using clip=0.01 (betting/forecasting standard) instead of eps=1e-15
    to prevent extreme tail predictions from dominating the metric.
    """
    y_prob = np.clip(y_prob, clip, 1 - clip)
    loss = -(y_true * np.log(y_prob) + (1 - y_true) * np.log(1 - y_prob))
    return float(np.mean(loss))

def brier_score(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Calculate Brier score."""
    return float(np.mean((y_prob - y_true) ** 2))

def expected_calibration_error(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    """Calculate Expected Calibration Error (lower is better)."""
    ece = 0.0
    for i in range(n_bins):
        mask = (y_prob >= i / n_bins) & (y_prob < (i + 1) / n_bins)
        if mask.sum() > 0:
            ece += mask.mean() * abs(y_prob[mask].mean() - y_true[mask].mean())
    return ece

# Load model and data
print("Loading T20 Male v1 model and training data...")
model = joblib.load('models/t20_male_v1/champion_model.joblib')
isotonic_cal = joblib.load('models/t20_male_v1/isotonic_calibrator.pkl')
df = pd.read_parquet('data/t20_male_features_v1/training.parquet')

print(f"Total samples: {len(df):,}")
print(f"Model type: {type(model).__name__}")

# Count unique matches
if 'match_id' in df.columns:
    print(f"Unique matches: {df['match_id'].nunique()}")

# Use actual feature columns from T20 Male (all except target and metadata)
exclude_cols = ['is_winner', 'overs_completed', 'match_id', 'ball_id']
feature_cols = [col for col in df.columns if col not in exclude_cols and not col.startswith('_')]
print(f"Using {len(feature_cols)} features")

# Get predictions
print("\nGenerating predictions...")
X = df[feature_cols].fillna(0)
y_true = df['is_winner'].values

# Raw model probabilities
raw_probs = model.predict_proba(X)[:, 1]

# Innings-specific calibrated probabilities
innings_cal_probs = np.zeros_like(raw_probs)
for innings in [1, 2]:
    mask = df['innings'] == innings
    if mask.sum() > 0:
        calibrator = isotonic_cal[f'calibrator_innings{innings}']
        innings_cal_probs[mask] = calibrator.predict(raw_probs[mask].reshape(-1, 1)).ravel()

# Resource-based probabilities
resource_probs = df['resource_win_prob'].values
valid_resource_mask = df['resource_win_prob'].notna()
print(f"Resource prob coverage: {valid_resource_mask.sum():,}/{len(df):,} ({valid_resource_mask.mean()*100:.1f}%)")

print(f"Raw prob range: [{raw_probs.min():.3f}, {raw_probs.max():.3f}]")
print(f"Innings-cal prob range: [{innings_cal_probs.min():.3f}, {innings_cal_probs.max():.3f}]")
print(f"Resource prob range: [{resource_probs[valid_resource_mask].min():.3f}, {resource_probs[valid_resource_mask].max():.3f}]")

# Define phases using overs_remaining
def get_phase(overs_remaining):
    """Determine match phase from overs_remaining."""
    overs_completed = 20 - overs_remaining
    if overs_completed < 6:
        return 'powerplay'
    elif overs_completed >= 16:
        return 'death'
    else:
        return 'middle'

df['phase'] = df['overs_remaining'].apply(get_phase)

# Calculate metrics by innings and phase
print("\n" + "="*130)
print("T20 MALE v1 MODEL - BRIER, ECE, and LOG LOSS ANALYSIS")
print("="*130)
print(f"{'Innings':<8} {'Phase':<12} {'N':<8} {'Raw Br':<9} {'InnCal Br':<10} {'Res Br':<9} {'Raw ECE':<9} {'InnCal ECE':<11} {'Res ECE':<9} {'Winner (Brier)'}")
print("="*130)

results = []

for innings in [1, 2]:
    for phase in ['powerplay', 'middle', 'death']:
        mask = (df['innings'] == innings) & (df['phase'] == phase) & valid_resource_mask
        
        if mask.sum() < 100:  # Skip tiny buckets
            continue
            
        y_true_subset = y_true[mask]
        raw_subset = raw_probs[mask]
        innings_cal_subset = innings_cal_probs[mask]
        resource_subset = resource_probs[mask]
        
        # Calculate metrics
        raw_brier = brier_score(y_true_subset, raw_subset)
        innings_cal_brier = brier_score(y_true_subset, innings_cal_subset)
        resource_brier = brier_score(y_true_subset, resource_subset)
        
        raw_ece = expected_calibration_error(y_true_subset, raw_subset)
        innings_cal_ece = expected_calibration_error(y_true_subset, innings_cal_subset)
        resource_ece = expected_calibration_error(y_true_subset, resource_subset)
        
        raw_ll = log_loss(y_true_subset, raw_subset)
        innings_cal_ll = log_loss(y_true_subset, innings_cal_subset)
        resource_ll = log_loss(y_true_subset, resource_subset)
        
        # Determine winners
        brier_winner = min([('raw', raw_brier), ('inn-cal', innings_cal_brier), ('resource', resource_brier)], key=lambda x: x[1])[0]
        ece_winner = min([('raw', raw_ece), ('inn-cal', innings_cal_ece), ('resource', resource_ece)], key=lambda x: x[1])[0]
        ll_winner = min([('raw', raw_ll), ('inn-cal', innings_cal_ll), ('resource', resource_ll)], key=lambda x: x[1])[0]
        
        winner_text = {'raw': 'RAW*', 'inn-cal': 'INN-CAL*', 'resource': 'RES*'}[brier_winner]
        
        results.append({
            'innings': innings,
            'phase': phase,
            'n': mask.sum(),
            'raw_brier': raw_brier,
            'innings_cal_brier': innings_cal_brier,
            'resource_brier': resource_brier,
            'raw_ece': raw_ece,
            'innings_cal_ece': innings_cal_ece,
            'resource_ece': resource_ece,
            'raw_logloss': raw_ll,
            'innings_cal_logloss': innings_cal_ll,
            'resource_logloss': resource_ll,
            'brier_winner': brier_winner,
            'ece_winner': ece_winner,
            'll_winner': ll_winner
        })
        
        print(f"Inn {innings:<6} {phase:<12} {mask.sum():<8,} "
              f"{raw_brier:<9.4f} {innings_cal_brier:<10.4f} {resource_brier:<9.4f} "
              f"{raw_ece:<9.4f} {innings_cal_ece:<11.4f} {resource_ece:<9.4f} {winner_text}")

# Overall statistics
print("\n" + "="*130)
print("OVERALL STATISTICS")
print("="*130)
overall_mask = valid_resource_mask
overall_raw_brier = brier_score(y_true[overall_mask], raw_probs[overall_mask])
overall_innings_cal_brier = brier_score(y_true[overall_mask], innings_cal_probs[overall_mask])
overall_resource_brier = brier_score(y_true[overall_mask], resource_probs[overall_mask])
overall_raw_ece = expected_calibration_error(y_true[overall_mask], raw_probs[overall_mask])
overall_innings_cal_ece = expected_calibration_error(y_true[overall_mask], innings_cal_probs[overall_mask])
overall_resource_ece = expected_calibration_error(y_true[overall_mask], resource_probs[overall_mask])
overall_raw_ll = log_loss(y_true[overall_mask], raw_probs[overall_mask])
overall_innings_cal_ll = log_loss(y_true[overall_mask], innings_cal_probs[overall_mask])
overall_resource_ll = log_loss(y_true[overall_mask], resource_probs[overall_mask])

print("BRIER SCORE (accuracy):")
print(f"  Raw Model:              {overall_raw_brier:.4f}")
print(f"  Innings-Calibrated:     {overall_innings_cal_brier:.4f}")
print(f"  Resource:               {overall_resource_brier:.4f}")
brier_overall_winner = min([('Raw', overall_raw_brier), ('Inn-Cal', overall_innings_cal_brier), ('Resource', overall_resource_brier)], key=lambda x: x[1])
print(f"  Winner:                 🏆 {brier_overall_winner[0]}")
print()
print("ECE (calibration):")
print(f"  Raw Model:              {overall_raw_ece:.4f}")
print(f"  Innings-Calibrated:     {overall_innings_cal_ece:.4f}")
print(f"  Resource:               {overall_resource_ece:.4f}")
ece_overall_winner = min([('Raw', overall_raw_ece), ('Inn-Cal', overall_innings_cal_ece), ('Resource', overall_resource_ece)], key=lambda x: x[1])
print(f"  Winner:                 🏆 {ece_overall_winner[0]}")
print()
print("LOG LOSS:")
print(f"  Raw Model:              {overall_raw_ll:.4f}")
print(f"  Innings-Calibrated:     {overall_innings_cal_ll:.4f}")
print(f"  Resource:               {overall_resource_ll:.4f}")
ll_overall_winner = min([('Raw', overall_raw_ll), ('Inn-Cal', overall_innings_cal_ll), ('Resource', overall_resource_ll)], key=lambda x: x[1])
print(f"  Winner:                 🏆 {ll_overall_winner[0]}")

# Summary by innings
print("\n" + "="*130)
print("SUMMARY BY INNINGS")
print("="*130)
for innings in [1, 2]:
    mask = (df['innings'] == innings) & valid_resource_mask
    y_true_subset = y_true[mask]
    raw_subset = raw_probs[mask]
    innings_cal_subset = innings_cal_probs[mask]
    resource_subset = resource_probs[mask]
    
    raw_brier = brier_score(y_true_subset, raw_subset)
    innings_cal_brier = brier_score(y_true_subset, innings_cal_subset)
    resource_brier = brier_score(y_true_subset, resource_subset)
    
    raw_ece = expected_calibration_error(y_true_subset, raw_subset)
    innings_cal_ece = expected_calibration_error(y_true_subset, innings_cal_subset)
    resource_ece = expected_calibration_error(y_true_subset, resource_subset)
    
    raw_ll = log_loss(y_true_subset, raw_subset)
    innings_cal_ll = log_loss(y_true_subset, innings_cal_subset)
    resource_ll = log_loss(y_true_subset, resource_subset)
    
    brier_winner = min([('Raw', raw_brier), ('Inn-Cal', innings_cal_brier), ('Resource', resource_brier)], key=lambda x: x[1])
    ece_winner = min([('Raw', raw_ece), ('Inn-Cal', innings_cal_ece), ('Resource', resource_ece)], key=lambda x: x[1])
    ll_winner = min([('Raw', raw_ll), ('Inn-Cal', innings_cal_ll), ('Resource', resource_ll)], key=lambda x: x[1])
    
    print(f"\nInnings {innings} (n={mask.sum():,}):")
    print(f"  Brier:    Raw={raw_brier:.4f}, Inn-Cal={innings_cal_brier:.4f}, Resource={resource_brier:.4f} (🏆 {brier_winner[0]})")
    print(f"  ECE:      Raw={raw_ece:.4f}, Inn-Cal={innings_cal_ece:.4f}, Resource={resource_ece:.4f} (🏆 {ece_winner[0]})")
    print(f"  Log Loss: Raw={raw_ll:.4f}, Inn-Cal={innings_cal_ll:.4f}, Resource={resource_ll:.4f} (🏆 {ll_winner[0]})")

# Per-over analysis (for calibrator training guidance)
print("\n" + "="*130)
print("PER-OVER ANALYSIS (for calibrator training)")
print("="*130)
print(f"{'Innings':<8} {'Over':<6} {'N':<8} {'Raw Brier':<11} {'InnCal Brier':<13} {'Res Brier':<11} {'Best Source (Brier)':<20} {'Best Source (ECE)'}")
print("-"*120)

per_over_results = []
for innings in [1, 2]:
    for over in range(1, 21):
        over_start = 20 - over
        over_end = 21 - over
        mask = (df['innings'] == innings) & (df['overs_remaining'] >= over_start) & (df['overs_remaining'] < over_end) & valid_resource_mask
        
        if mask.sum() < 50:
            continue
            
        y_true_subset = y_true[mask]
        raw_subset = raw_probs[mask]
        innings_cal_subset = innings_cal_probs[mask]
        resource_subset = resource_probs[mask]
        
        raw_brier = brier_score(y_true_subset, raw_subset)
        innings_cal_brier = brier_score(y_true_subset, innings_cal_subset)
        resource_brier = brier_score(y_true_subset, resource_subset)
        
        raw_ece = expected_calibration_error(y_true_subset, raw_subset)
        innings_cal_ece = expected_calibration_error(y_true_subset, innings_cal_subset)
        resource_ece = expected_calibration_error(y_true_subset, resource_subset)
        
        brier_best = min([('raw', raw_brier), ('inn-cal', innings_cal_brier), ('resource', resource_brier)], key=lambda x: x[1])
        ece_best = min([('raw', raw_ece), ('inn-cal', innings_cal_ece), ('resource', resource_ece)], key=lambda x: x[1])
        
        per_over_results.append({
            'innings': innings,
            'over': over,
            'n': mask.sum(),
            'raw_brier': raw_brier,
            'innings_cal_brier': innings_cal_brier,
            'resource_brier': resource_brier,
            'raw_ece': raw_ece,
            'innings_cal_ece': innings_cal_ece,
            'resource_ece': resource_ece,
            'brier_best': brier_best[0],
            'ece_best': ece_best[0]
        })
        
        print(f"Inn {innings:<6} {over:<6} {mask.sum():<8,} "
              f"{raw_brier:<11.4f} {innings_cal_brier:<13.4f} {resource_brier:<11.4f} "
              f"{brier_best[0]:<20} {ece_best[0]}")

# Helper to convert numpy types to Python native types
def convert_to_native(obj):
    if isinstance(obj, dict):
        return {k: convert_to_native(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_native(v) for v in obj]
    elif isinstance(obj, (np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.float64, np.float32)):
        return float(obj)
    return obj

# Save analysis results
analysis_output = {
    'model': 't20_male_v1',
    'generated_date': pd.Timestamp.now().isoformat(),
    'total_samples': int(len(df)),
    'overall_metrics': {
        'brier': {
            'raw': float(overall_raw_brier),
            'innings_calibrated': float(overall_innings_cal_brier),
            'resource': float(overall_resource_brier),
            'winner': brier_overall_winner[0]
        },
        'ece': {
            'raw': float(overall_raw_ece),
            'innings_calibrated': float(overall_innings_cal_ece),
            'resource': float(overall_resource_ece),
            'winner': ece_overall_winner[0]
        },
        'log_loss': {
            'raw': float(overall_raw_ll),
            'innings_calibrated': float(overall_innings_cal_ll),
            'resource': float(overall_resource_ll),
            'winner': ll_overall_winner[0]
        }
    },
    'phase_results': convert_to_native(results),
    'per_over_results': convert_to_native(per_over_results)
}

output_path = Path('models/t20_male_v1/analysis_results.json')
with open(output_path, 'w') as f:
    json.dump(analysis_output, f, indent=2)
print(f"\n✅ Saved analysis to {output_path}")

print("\n" + "="*130)
print("CALIBRATOR TRAINING RECOMMENDATIONS")
print("="*130)
results_df = pd.DataFrame(per_over_results)
print("\nBrier-optimized source by innings:")
for innings in [1, 2]:
    inn_df = results_df[results_df['innings'] == innings]
    brier_counts = inn_df['brier_best'].value_counts()
    print(f"  Innings {innings}: {dict(brier_counts)}")

print("\nECE-optimized source by innings:")
for innings in [1, 2]:
    inn_df = results_df[results_df['innings'] == innings]
    ece_counts = inn_df['ece_best'].value_counts()
    print(f"  Innings {innings}: {dict(ece_counts)}")

print("\n" + "="*130)
print("NEXT STEPS:")
print("="*130)
print("1. Run scripts/train_t20_male_calibrators.py to generate per-over calibrators")
print("2. Add T20 Male model to live_streamlit_app.py")
print("3. Update model_registry.json with T20 Male model details")
