"""
Analyze log loss for SSM (Super Smash) model across all phases.
Compare raw model probabilities vs innings-calibrated vs resource-based probabilities.
"""
import joblib
import pandas as pd
import numpy as np
from pathlib import Path

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

def ece_score(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    """Calculate Expected Calibration Error."""
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        in_bin = (y_prob >= bin_boundaries[i]) & (y_prob < bin_boundaries[i + 1])
        prop_in_bin = in_bin.mean()
        if prop_in_bin > 0:
            avg_confidence = y_prob[in_bin].mean()
            avg_accuracy = y_true[in_bin].mean()
            ece += prop_in_bin * abs(avg_accuracy - avg_confidence)
    return float(ece)

# Load model and data
print("Loading SSM v1 model and training data...")
model = joblib.load('models/ssm_v1/champion_model.joblib')
isotonic_cal = joblib.load('models/ssm_v1/isotonic_calibrator.pkl')
per_over_cal = joblib.load('models/ssm_v1/per_over_calibrators.pkl')
df = pd.read_parquet('data/ssm_features_v1/training.parquet')

print(f"Total samples: {len(df):,}")
print(f"Model type: {type(model).__name__}")

# Use actual feature columns from SSM (all except target and metadata)
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

# Per-over calibrated probabilities (will be filled in the loop)
per_over_cal_probs = np.zeros_like(raw_probs)

# Resource-based probabilities (don't artificially help with fillna(0.5))
resource_probs = df['resource_win_prob'].values
valid_resource_mask = df['resource_win_prob'].notna()
print(f"Resource prob coverage: {valid_resource_mask.sum():,}/{len(df):,} ({valid_resource_mask.mean()*100:.1f}%)")

print(f"Raw prob range: [{raw_probs.min():.3f}, {raw_probs.max():.3f}]")
print(f"Innings-cal prob range: [{innings_cal_probs.min():.3f}, {innings_cal_probs.max():.3f}]")
print(f"Resource prob range: [{resource_probs[valid_resource_mask].min():.3f}, {resource_probs[valid_resource_mask].max():.3f}]")

# Define phases using overs_remaining (more reliable)
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

# Calculate log loss by innings and phase with baseline normalization
print("\n" + "="*130)
print("LOG LOSS ANALYSIS - SSM v1 MODEL (Super Smash New Zealand)")
print("="*130)
print(f"{'Innings':<8} {'Phase':<12} {'N':<8} {'Raw LL':<9} {'Inn-Cal':<9} {'Per-Over':<10} {'Res LL':<9} {'Raw Norm':<10} {'Winner'}")
print("="*130)

results = []

for innings in [1, 2]:
    for phase in ['powerplay', 'middle', 'death']:
        # Apply valid resource mask
        mask = (df['innings'] == innings) & (df['phase'] == phase) & valid_resource_mask
        
        if mask.sum() < 100:  # Skip tiny buckets
            continue
            
        y_true_subset = y_true[mask]
        raw_subset = raw_probs[mask]
        innings_cal_subset = innings_cal_probs[mask]
        resource_subset = resource_probs[mask]
        
        # Apply per-over calibrator (aggregate across overs in phase)
        per_over_cal_subset = np.zeros_like(raw_subset)
        for i, (idx, row) in enumerate(df[mask].iterrows()):
            over = int(20 - row['overs_remaining'])
            over_key = f'inn{innings}_over{over}'
            if over_key in per_over_cal and 'calibrator' in per_over_cal[over_key]:
                cal = per_over_cal[over_key]['calibrator']
                per_over_cal_subset[i] = cal.predict([[raw_subset[i]]])[0]
            else:
                per_over_cal_subset[i] = raw_subset[i]
        per_over_cal_probs[mask] = per_over_cal_subset
        
        # Calculate metrics
        raw_ll = log_loss(y_true_subset, raw_subset)
        innings_cal_ll = log_loss(y_true_subset, innings_cal_subset)
        per_over_cal_ll = log_loss(y_true_subset, per_over_cal_subset)
        resource_ll = log_loss(y_true_subset, resource_subset)
        
        # Baseline normalization
        baseline_probs = np.full_like(y_true_subset, 0.5, dtype=float)
        baseline_ll = log_loss(y_true_subset, baseline_probs)
        
        raw_ll_norm = raw_ll / baseline_ll
        innings_cal_ll_norm = innings_cal_ll / baseline_ll
        per_over_cal_ll_norm = per_over_cal_ll / baseline_ll
        resource_ll_norm = resource_ll / baseline_ll
        
        delta_raw_resource = raw_ll - resource_ll
        
        raw_brier = brier_score(y_true_subset, raw_subset)
        innings_cal_brier = brier_score(y_true_subset, innings_cal_subset)
        per_over_cal_brier = brier_score(y_true_subset, per_over_cal_subset)
        resource_brier = brier_score(y_true_subset, resource_subset)
        
        raw_ece = ece_score(y_true_subset, raw_subset)
        innings_cal_ece = ece_score(y_true_subset, innings_cal_subset)
        per_over_cal_ece = ece_score(y_true_subset, per_over_cal_subset)
        resource_ece = ece_score(y_true_subset, resource_subset)
        
        # Determine winners
        ll_winner = min([('raw', raw_ll), ('inn-cal', innings_cal_ll), ('per-over', per_over_cal_ll), ('resource', resource_ll)], key=lambda x: x[1])[0]
        brier_winner = min([('raw', raw_brier), ('inn-cal', innings_cal_brier), ('per-over', per_over_cal_brier), ('resource', resource_brier)], key=lambda x: x[1])[0]
        
        winner_text = {'raw': 'RAW*', 'inn-cal': 'INN-CAL*', 'per-over': 'PER-OVER*', 'resource': 'RES*'}[ll_winner]
        
        results.append({
            'innings': innings,
            'phase': phase,
            'n': mask.sum(),
            'raw_logloss': raw_ll,
            'innings_cal_logloss': innings_cal_ll,
            'per_over_cal_logloss': per_over_cal_ll,
            'resource_logloss': resource_ll,
            'raw_ll_norm': raw_ll_norm,
            'delta_raw_resource': delta_raw_resource,
            'raw_brier': raw_brier,
            'innings_cal_brier': innings_cal_brier,
            'per_over_cal_brier': per_over_cal_brier,
            'resource_brier': resource_brier,
            'raw_ece': raw_ece,
            'innings_cal_ece': innings_cal_ece,
            'per_over_cal_ece': per_over_cal_ece,
            'resource_ece': resource_ece,
            'll_winner': ll_winner,
            'brier_winner': brier_winner
        })
        
        print(f"Inn {innings:<6} {phase:<12} {mask.sum():<8,} "
              f"{raw_ll:<9.4f} {innings_cal_ll:<9.4f} {per_over_cal_ll:<10.4f} {resource_ll:<9.4f} "
              f"{raw_ll_norm:<10.3f} {winner_text}")
        print()

# Overall statistics (only on valid resource rows)
print("="*115)
print("OVERALL STATISTICS")
print("="*115)
overall_mask = valid_resource_mask
overall_raw_ll = log_loss(y_true[overall_mask], raw_probs[overall_mask])
overall_innings_cal_ll = log_loss(y_true[overall_mask], innings_cal_probs[overall_mask])
overall_per_over_cal_ll = log_loss(y_true[overall_mask], per_over_cal_probs[overall_mask])
overall_resource_ll = log_loss(y_true[overall_mask], resource_probs[overall_mask])
overall_raw_brier = brier_score(y_true[overall_mask], raw_probs[overall_mask])
overall_innings_cal_brier = brier_score(y_true[overall_mask], innings_cal_probs[overall_mask])
overall_per_over_cal_brier = brier_score(y_true[overall_mask], per_over_cal_probs[overall_mask])
overall_resource_brier = brier_score(y_true[overall_mask], resource_probs[overall_mask])
overall_raw_ece = ece_score(y_true[overall_mask], raw_probs[overall_mask])
overall_innings_cal_ece = ece_score(y_true[overall_mask], innings_cal_probs[overall_mask])
overall_per_over_cal_ece = ece_score(y_true[overall_mask], per_over_cal_probs[overall_mask])
overall_resource_ece = ece_score(y_true[overall_mask], resource_probs[overall_mask])

# Baseline normalization
baseline_ll = log_loss(y_true[overall_mask], np.full(overall_mask.sum(), 0.5))
overall_raw_ll_norm = overall_raw_ll / baseline_ll
overall_innings_cal_ll_norm = overall_innings_cal_ll / baseline_ll
overall_per_over_cal_ll_norm = overall_per_over_cal_ll / baseline_ll
overall_resource_ll_norm = overall_resource_ll / baseline_ll

print("LOG LOSS:")
print(f"  Raw Model:              {overall_raw_ll:.4f} (norm: {overall_raw_ll_norm:.3f}x)")
print(f"  Innings-Calibrated:     {overall_innings_cal_ll:.4f} (norm: {overall_innings_cal_ll_norm:.3f}x)")
print(f"  Per-Over-Calibrated:    {overall_per_over_cal_ll:.4f} (norm: {overall_per_over_cal_ll_norm:.3f}x)")
print(f"  Resource:               {overall_resource_ll:.4f} (norm: {overall_resource_ll_norm:.3f}x)")
ll_overall_winner = min([('Raw', overall_raw_ll), ('Inn-Cal', overall_innings_cal_ll), ('Per-Over', overall_per_over_cal_ll), ('Resource', overall_resource_ll)], key=lambda x: x[1])
print(f"  Winner:                 🏆 {ll_overall_winner[0]}")
print()
print("BRIER SCORE:")
print(f"  Raw Model:              {overall_raw_brier:.4f}")
print(f"  Innings-Calibrated:     {overall_innings_cal_brier:.4f}")
print(f"  Per-Over-Calibrated:    {overall_per_over_cal_brier:.4f}")
print(f"  Resource:               {overall_resource_brier:.4f}")
brier_overall_winner = min([('Raw', overall_raw_brier), ('Inn-Cal', overall_innings_cal_brier), ('Per-Over', overall_per_over_cal_brier), ('Resource', overall_resource_brier)], key=lambda x: x[1])
print(f"  Winner:                 🏆 {brier_overall_winner[0]}")
print()
print("ECE (Expected Calibration Error):")
print(f"  Raw Model:              {overall_raw_ece:.4f}")
print(f"  Innings-Calibrated:     {overall_innings_cal_ece:.4f}")
print(f"  Per-Over-Calibrated:    {overall_per_over_cal_ece:.4f}")
print(f"  Resource:               {overall_resource_ece:.4f}")
ece_overall_winner = min([('Raw', overall_raw_ece), ('Inn-Cal', overall_innings_cal_ece), ('Per-Over', overall_per_over_cal_ece), ('Resource', overall_resource_ece)], key=lambda x: x[1])
print(f"  Winner:                 🏆 {ece_overall_winner[0]}")
print("="*130)

# Summary by innings
print("\nSUMMARY BY INNINGS:")
print("="*115)
for innings in [1, 2]:
    mask = (df['innings'] == innings) & valid_resource_mask
    y_true_subset = y_true[mask]
    raw_subset = raw_probs[mask]
    innings_cal_subset = innings_cal_probs[mask]
    per_over_cal_subset = per_over_cal_probs[mask]
    resource_subset = resource_probs[mask]
    
    raw_ll = log_loss(y_true_subset, raw_subset)
    innings_cal_ll = log_loss(y_true_subset, innings_cal_subset)
    per_over_cal_ll = log_loss(y_true_subset, per_over_cal_subset)
    resource_ll = log_loss(y_true_subset, resource_subset)
    raw_brier = brier_score(y_true_subset, raw_subset)
    innings_cal_brier = brier_score(y_true_subset, innings_cal_subset)
    per_over_cal_brier = brier_score(y_true_subset, per_over_cal_subset)
    resource_brier = brier_score(y_true_subset, resource_subset)
    raw_ece = ece_score(y_true_subset, raw_subset)
    innings_cal_ece = ece_score(y_true_subset, innings_cal_subset)
    per_over_cal_ece = ece_score(y_true_subset, per_over_cal_subset)
    resource_ece = ece_score(y_true_subset, resource_subset)
    
    ll_winner = min([('Raw', raw_ll), ('Inn-Cal', innings_cal_ll), ('Per-Over', per_over_cal_ll), ('Resource', resource_ll)], key=lambda x: x[1])
    brier_winner = min([('Raw', raw_brier), ('Inn-Cal', innings_cal_brier), ('Per-Over', per_over_cal_brier), ('Resource', resource_brier)], key=lambda x: x[1])
    ece_winner = min([('Raw', raw_ece), ('Inn-Cal', innings_cal_ece), ('Per-Over', per_over_cal_ece), ('Resource', resource_ece)], key=lambda x: x[1])
    
    print(f"\nInnings {innings} (n={mask.sum():,}):")
    print(f"  Log Loss:  Raw={raw_ll:.4f}, Inn-Cal={innings_cal_ll:.4f}, Per-Over={per_over_cal_ll:.4f}, Resource={resource_ll:.4f} (🏆 {ll_winner[0]})")
    print(f"  Brier:     Raw={raw_brier:.4f}, Inn-Cal={innings_cal_brier:.4f}, Per-Over={per_over_cal_brier:.4f}, Resource={resource_brier:.4f} (🏆 {brier_winner[0]})")
    print(f"  ECE:       Raw={raw_ece:.4f}, Inn-Cal={innings_cal_ece:.4f}, Per-Over={per_over_cal_ece:.4f}, Resource={resource_ece:.4f} (🏆 {ece_winner[0]})")

print("\n" + "="*100)
print("KEY INSIGHTS:")
print("="*100)

# Count winners
results_df = pd.DataFrame(results)
ll_counts = results_df['ll_winner'].value_counts()
brier_counts = results_df['brier_winner'].value_counts()

print("Log Loss Winners by phase:")
for winner in ['raw', 'inn-cal', 'per-over', 'resource']:
    count = ll_counts.get(winner, 0)
    print(f"  {winner.upper()}: {count}/6 phases")

print("\nBrier Winners by phase:")
for winner in ['raw', 'inn-cal', 'per-over', 'resource']:
    count = brier_counts.get(winner, 0)
    print(f"  {winner.upper()}: {count}/6 phases")

# Worst phases for each
print("\nWorst phases by Log Loss:")
print("  Raw Model:")
worst_raw = results_df.nlargest(3, 'raw_logloss')[['innings', 'phase', 'raw_logloss']]
for _, row in worst_raw.iterrows():
    print(f"    Inn{row['innings']} {row['phase']}: {row['raw_logloss']:.4f}")

print("  Innings-Calibrated:")
worst_cal = results_df.nlargest(3, 'innings_cal_logloss')[['innings', 'phase', 'innings_cal_logloss']]
for _, row in worst_cal.iterrows():
    print(f"    Inn{row['innings']} {row['phase']}: {row['innings_cal_logloss']:.4f}")

print("  Resource:")
worst_resource = results_df.nlargest(3, 'resource_logloss')[['innings', 'phase', 'resource_logloss']]
for _, row in worst_resource.iterrows():
    print(f"    Inn{row['innings']} {row['phase']}: {row['resource_logloss']:.4f}")

# Calculate improvement from calibration
print("\n" + "="*100)
print("CALIBRATION IMPACT:")
print("="*100)
for innings in [1, 2]:
    mask = df['innings'] == innings
    y_true_subset = y_true[mask]
    raw_subset = raw_probs[mask]
    cal_subset = innings_cal_probs[mask]
    
    raw_ll = log_loss(y_true_subset, raw_subset)
    cal_ll = log_loss(y_true_subset, cal_subset)
    improvement = ((raw_ll - cal_ll) / raw_ll) * 100
    
    raw_brier = brier_score(y_true_subset, raw_subset)
    cal_brier = brier_score(y_true_subset, cal_subset)
    brier_improvement = ((raw_brier - cal_brier) / raw_brier) * 100
    
    raw_ece = ece_score(y_true_subset, raw_subset)
    cal_ece = ece_score(y_true_subset, cal_subset)
    ece_improvement = ((raw_ece - cal_ece) / raw_ece) * 100 if raw_ece > 0 else 0
    
    print(f"Innings {innings}:")
    print(f"  Log Loss:  {raw_ll:.4f} → {cal_ll:.4f} ({improvement:+.1f}%)")
    print(f"  Brier:     {raw_brier:.4f} → {cal_brier:.4f} ({brier_improvement:+.1f}%)")
    print(f"  ECE:       {raw_ece:.4f} → {cal_ece:.4f} ({ece_improvement:+.1f}%)")
    print()

# Generate summary for model registry
print("="*100)
print("SSM MODEL SUMMARY (for model_registry.json):")
print("="*100)
print(f"""
"SSM": {{
    "path": "models/ssm_v1",
    "version": "v1",
    "description": "XGBLogRegEnsemble (25 features) + CV-OOF Innings-Specific Isotonic Calibration (Brier: {overall_innings_cal_brier:.4f}, ECE: {overall_innings_cal_ece:.4f})",
    "calibrator": {{
        "path": "models/ssm_v1/isotonic_calibrator.pkl",
        "type": "isotonic_regression",
        "oof_metrics": {{
            "brier_raw": {overall_raw_brier:.4f},
            "brier_calibrated": {overall_innings_cal_brier:.4f},
            "ece_raw": {overall_raw_ece:.4f},
            "ece_calibrated": {overall_innings_cal_ece:.4f}
        }}
    }},
    "feature_store": {{
        "path": "data/ssm_feature_store_v1",
        "version": "v1"
    }}
}}
""")

print("="*100)
