"""
Analyze log loss for SA20 model across all phases.
Compare raw model probabilities vs resource-based probabilities.
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

# Load model and data
print("Loading SA20 model and training data...")
model = joblib.load('models/sat_v1/champion_model.joblib')
phase_calibrators = joblib.load('models/sat_v1/phase_calibrators.pkl')
df = pd.read_parquet('data/sat_features_v1/training.parquet')

print(f"Total samples: {len(df):,}")
print(f"Columns: {df.columns.tolist()[:10]}...")

# Use actual feature columns from SA20 (all except target)
feature_cols = [col for col in df.columns if col not in ['is_winner', 'overs_completed']]
print(f"Using {len(feature_cols)} features")

# Get predictions
print("\nGenerating raw model predictions...")
X = df[feature_cols].fillna(0)
y_true = df['is_winner'].values

# Raw model probabilities
raw_probs = model.predict_proba(X)[:, 1]

# Phase-calibrated probabilities (will be filled in the loop)
phase_cal_probs = np.zeros_like(raw_probs)

# Don't artificially help resource with fillna(0.5) - drop missing instead
resource_probs = df['resource_win_prob'].values
valid_resource_mask = df['resource_win_prob'].notna()
print(f"Resource prob coverage: {valid_resource_mask.sum():,}/{len(df):,} ({valid_resource_mask.mean()*100:.1f}%)")

print(f"Raw prob range: [{raw_probs.min():.3f}, {raw_probs.max():.3f}]")
print(f"Resource prob range: [{resource_probs.min():.3f}, {resource_probs.max():.3f}]")

# Define phases using overs_remaining (matching SA20 calibrator structure)
def get_phase(overs_remaining):
    """Determine match phase from overs_remaining (with middle split)."""
    overs_completed = 20 - overs_remaining
    if overs_completed < 6:
        return 'powerplay'
    elif overs_completed < 11:
        return 'middle_early'
    elif overs_completed < 16:
        return 'middle_late'
    else:
        return 'death'

df['phase'] = df['overs_remaining'].apply(get_phase)

# Calculate log loss by innings and phase with baseline normalization
print("\n" + "="*120)
print("LOG LOSS ANALYSIS - SA20 MODEL (Normalized vs 0.5 Baseline)")
print("="*120)
print(f"{'Innings':<8} {'Phase':<12} {'N':<8} {'Raw LL':<9} {'Phase-Cal':<10} {'Res LL':<9} {'Raw Norm':<10} {'Δ Raw-Res':<12} {'Winner'}")
print("="*120)

results = []

for innings in [1, 2]:
    for phase in ['powerplay', 'middle_early', 'middle_late', 'death']:
        # Apply valid resource mask
        mask = (df['innings'] == innings) & (df['phase'] == phase) & valid_resource_mask
        
        if mask.sum() < 50:  # Skip tiny buckets
            continue
            
        y_true_subset = y_true[mask]
        raw_subset = raw_probs[mask]
        resource_subset = resource_probs[mask]
        
        # Apply phase-specific calibrator
        phase_key = f'inn{innings}_{phase}'
        if phase_key in phase_calibrators:
            phase_cal_subset = phase_calibrators[phase_key].predict(raw_subset.reshape(-1, 1)).ravel()
            phase_cal_probs[mask] = phase_cal_subset
        else:
            phase_cal_subset = raw_subset
            phase_cal_probs[mask] = raw_subset
            print(f"Warning: No calibrator for {phase_key}")
        
        # Calculate metrics
        raw_ll = log_loss(y_true_subset, raw_subset)
        phase_cal_ll = log_loss(y_true_subset, phase_cal_subset)
        resource_ll = log_loss(y_true_subset, resource_subset)
        
        # Baseline normalization (0.5 uniform predictor)
        baseline_probs = np.full_like(y_true_subset, 0.5, dtype=float)
        baseline_ll = log_loss(y_true_subset, baseline_probs)
        
        raw_ll_norm = raw_ll / baseline_ll
        phase_cal_ll_norm = phase_cal_ll / baseline_ll
        resource_ll_norm = resource_ll / baseline_ll
        delta_raw_res = raw_ll - resource_ll
        delta_cal_res = phase_cal_ll - resource_ll
        
        raw_brier = brier_score(y_true_subset, raw_subset)
        phase_cal_brier = brier_score(y_true_subset, phase_cal_subset)
        resource_brier = brier_score(y_true_subset, resource_subset)
        
        # Determine winner
        ll_winner = min([('raw', raw_ll), ('phase-cal', phase_cal_ll), ('resource', resource_ll)], key=lambda x: x[1])[0]
        winner_text = {'raw': 'RAW*', 'phase-cal': 'PHASE-CAL*', 'resource': 'RES*'}[ll_winner]
        
        results.append({
            'innings': innings,
            'phase': phase,
            'n': mask.sum(),
            'raw_logloss': raw_ll,
            'phase_cal_logloss': phase_cal_ll,
            'resource_logloss': resource_ll,
            'raw_ll_norm': raw_ll_norm,
            'phase_cal_ll_norm': phase_cal_ll_norm,
            'delta_raw_res': delta_raw_res,
            'delta_cal_res': delta_cal_res,
            'raw_brier': raw_brier,
            'phase_cal_brier': phase_cal_brier,
            'resource_brier': resource_brier,
            'logloss_winner': ll_winner,
            'brier_winner': min([('raw', raw_brier), ('phase-cal', phase_cal_brier), ('resource', resource_brier)], key=lambda x: x[1])[0]
        })
        
        print(f"Inn {innings:<6} {phase:<12} {mask.sum():<8,} "
              f"{raw_ll:<9.4f} {phase_cal_ll:<10.4f} {resource_ll:<9.4f} "
              f"{raw_ll_norm:<10.3f} {delta_raw_res:<+12.4f} {winner_text}")
        print()

# Overall statistics (only on valid resource rows)
print("="*120)
print("OVERALL STATISTICS")
print("="*120)
overall_mask = valid_resource_mask
overall_raw_ll = log_loss(y_true[overall_mask], raw_probs[overall_mask])
overall_phase_cal_ll = log_loss(y_true[overall_mask], phase_cal_probs[overall_mask])
overall_resource_ll = log_loss(y_true[overall_mask], resource_probs[overall_mask])
overall_raw_brier = brier_score(y_true[overall_mask], raw_probs[overall_mask])
overall_phase_cal_brier = brier_score(y_true[overall_mask], phase_cal_probs[overall_mask])
overall_resource_brier = brier_score(y_true[overall_mask], resource_probs[overall_mask])

# Baseline normalization
baseline_ll = log_loss(y_true[overall_mask], np.full(overall_mask.sum(), 0.5))
overall_raw_ll_norm = overall_raw_ll / baseline_ll
overall_phase_cal_ll_norm = overall_phase_cal_ll / baseline_ll
overall_resource_ll_norm = overall_resource_ll / baseline_ll
overall_delta_ll = overall_raw_ll - overall_resource_ll
overall_delta_cal = overall_phase_cal_ll - overall_resource_ll

print(f"Raw Model Log Loss:      {overall_raw_ll:.4f} (normalized: {overall_raw_ll_norm:.3f}x baseline)")
print(f"Phase-Cal Log Loss:      {overall_phase_cal_ll:.4f} (normalized: {overall_phase_cal_ll_norm:.3f}x baseline)")
print(f"Resource Log Loss:       {overall_resource_ll:.4f} (normalized: {overall_resource_ll_norm:.3f}x baseline)")
ll_overall_winner = min([('Raw', overall_raw_ll), ('Phase-Cal', overall_phase_cal_ll), ('Resource', overall_resource_ll)], key=lambda x: x[1])
print(f"Winner:                  🏆 {ll_overall_winner[0]}")
print()
print(f"Raw Model Brier:         {overall_raw_brier:.4f}")
print(f"Phase-Cal Brier:         {overall_phase_cal_brier:.4f}")
print(f"Resource Brier:          {overall_resource_brier:.4f}")
brier_overall_winner = min([('Raw', overall_raw_brier), ('Phase-Cal', overall_phase_cal_brier), ('Resource', overall_resource_brier)], key=lambda x: x[1])
print(f"Winner:                  🏆 {brier_overall_winner[0]}")
print("="*120)

# Summary by innings
print("\nSUMMARY BY INNINGS:")
print("="*100)
for innings in [1, 2]:
    mask = (df['innings'] == innings) & valid_resource_mask
    y_true_subset = y_true[mask]
    raw_subset = raw_probs[mask]
    resource_subset = resource_probs[mask]
    
    raw_ll = log_loss(y_true_subset, raw_subset)
    resource_ll = log_loss(y_true_subset, resource_subset)
    raw_brier = brier_score(y_true_subset, raw_subset)
    resource_brier = brier_score(y_true_subset, resource_subset)
    
    print(f"\nInnings {innings} (n={mask.sum():,}):")
    print(f"  Log Loss:  Raw={raw_ll:.4f}, Resource={resource_ll:.4f} "
          f"({'🏆 Raw wins' if raw_ll < resource_ll else '🏆 Resource wins'})")
    print(f"  Brier:     Raw={raw_brier:.4f}, Resource={resource_brier:.4f} "
          f"({'🏆 Raw wins' if raw_brier < resource_brier else '🏆 Resource wins'})")

print("\n" + "="*80)
print("KEY INSIGHTS:")
print("="*80)

# Count winners
logloss_winners = pd.DataFrame(results)
raw_wins_ll = (logloss_winners['logloss_winner'] == 'raw').sum()
phase_cal_wins_ll = (logloss_winners['logloss_winner'] == 'phase-cal').sum()
resource_wins_ll = (logloss_winners['logloss_winner'] == 'resource').sum()

raw_wins_brier = (logloss_winners['brier_winner'] == 'raw').sum()
phase_cal_wins_brier = (logloss_winners['brier_winner'] == 'phase-cal').sum()
resource_wins_brier = (logloss_winners['brier_winner'] == 'resource').sum()

print(f"Log Loss Winners:  Raw={raw_wins_ll}/8 phases, Phase-Cal={phase_cal_wins_ll}/8 phases, Resource={resource_wins_ll}/8 phases")
print(f"Brier Winners:     Raw={raw_wins_brier}/8 phases, Phase-Cal={phase_cal_wins_brier}/8 phases, Resource={resource_wins_brier}/8 phases")
print()

# Worst phases for each
worst_raw_ll = logloss_winners.nlargest(3, 'raw_logloss')[['innings', 'phase', 'raw_logloss']]
worst_resource_ll = logloss_winners.nlargest(3, 'resource_logloss')[['innings', 'phase', 'resource_logloss']]

print("Worst phases for Raw Model (by Log Loss):")
for _, row in worst_raw_ll.iterrows():
    print(f"  Inn{row['innings']} {row['phase']}: {row['raw_logloss']:.4f}")

print("\nWorst phases for Resource (by Log Loss):")
for _, row in worst_resource_ll.iterrows():
    print(f"  Inn{row['innings']} {row['phase']}: {row['resource_logloss']:.4f}")

print("="*80)
