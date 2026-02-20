"""
Analyze calibration quality across probability bins for BBL v12 model.
Compares brier_optimized vs innings_phase calibrators.
"""
import pandas as pd
import numpy as np
import joblib
from pathlib import Path
from sklearn.model_selection import KFold

# Load data
features_path = Path("data/bbl_features_v4/training.parquet")
model_path = Path("models/bbl_v12")

print("Loading data...")
df = pd.read_parquet(features_path)
print(f"Loaded {len(df):,} samples")

# Load model
model = joblib.load(model_path / "champion_model.joblib")

# Get feature columns (exclude target and metadata)
exclude_cols = {'is_winner', 'match_id', 'innings', 'over', 'ball', 
                'batting_team', 'bowling_team', 'venue', 'date'}
feature_cols = [c for c in df.columns if c not in exclude_cols]

X = df[feature_cols]  # Keep as DataFrame
y = df['is_winner'].values

# Get innings and phase info from features
df['inn_num'] = df['innings'].apply(lambda x: 1 if x == 1 else 2)

# Calculate over from overs_remaining (20 - overs_remaining = current over approx)
# overs_remaining is float like 19.4, 18.2, etc.
df['over'] = (20 - df['overs_remaining']).apply(lambda x: max(1, min(20, int(x) + 1)))
df['phase'] = df['over'].apply(lambda o: 'powerplay' if o <= 6 else ('middle' if o <= 15 else 'death'))
df['inn_phase'] = df['inn_num'].astype(str) + '_' + df['phase']

print("\n" + "="*80)
print("OOF CALIBRATION ANALYSIS BY PROBABILITY BINS")
print("="*80)

# 5-fold CV to get OOF predictions
kf = KFold(n_splits=5, shuffle=True, random_state=42)
oof_raw = np.zeros(len(df))

print("\nGenerating OOF predictions...")
for fold, (train_idx, val_idx) in enumerate(kf.split(X)):
    X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
    y_train, y_val = y[train_idx], y[val_idx]
    
    # Clone and train model
    from sklearn.base import clone
    fold_model = clone(model)
    fold_model.fit(X_train, y_train)
    
    # Get raw predictions
    oof_raw[val_idx] = fold_model.predict_proba(X_val)[:, 1]
    print(f"  Fold {fold+1} done")

df['oof_raw'] = oof_raw

# Load calibrators
oof_calibrators = joblib.load(model_path / "oof_calibrators.pkl")
brier_cals = oof_calibrators.get('brier_optimized', {})
phase_cals = oof_calibrators.get('innings_phase', {})

print(f"\nBrier-optimized calibrators: {len(brier_cals)} (per-over)")
print(f"Innings×Phase calibrators: {len(phase_cals)}")

# Apply calibrations
def apply_brier_optimized(row):
    """Apply per-over brier-optimized calibrator."""
    inn = int(row['inn_num'])
    over = int(row['over'])
    key = f"inn{inn}_over{over}"
    if key in brier_cals:
        return brier_cals[key].predict([row['oof_raw']])[0]
    # Fallback to phase calibrator
    phase = row['phase']
    fallback_key = f"inn{inn}_{phase}"
    if fallback_key in phase_cals:
        return phase_cals[fallback_key].predict([row['oof_raw']])[0]
    return row['oof_raw']

def apply_innings_phase(row):
    """Apply innings×phase calibrator."""
    inn = int(row['inn_num'])
    phase = row['phase']
    key = f"inn{inn}_{phase}"
    if key in phase_cals:
        return phase_cals[key].predict([row['oof_raw']])[0]
    return row['oof_raw']

print("\nApplying calibrators...")
df['oof_brier_opt'] = df.apply(apply_brier_optimized, axis=1)
df['oof_inn_phase'] = df.apply(apply_innings_phase, axis=1)

# Analyze by probability bins
def analyze_calibration_bins(probs, actuals, method_name, n_bins=10):
    """Analyze calibration in probability bins."""
    bins = np.linspace(0, 1, n_bins + 1)
    bin_indices = np.digitize(probs, bins) - 1
    bin_indices = np.clip(bin_indices, 0, n_bins - 1)
    
    results = []
    for i in range(n_bins):
        mask = bin_indices == i
        n = mask.sum()
        if n > 0:
            mean_pred = probs[mask].mean()
            mean_actual = actuals[mask].mean()
            calibration_error = abs(mean_pred - mean_actual)
            brier = ((probs[mask] - actuals[mask]) ** 2).mean()
            results.append({
                'bin': f"{bins[i]:.1f}-{bins[i+1]:.1f}",
                'bin_center': (bins[i] + bins[i+1]) / 2,
                'n_samples': n,
                'mean_predicted': mean_pred,
                'mean_actual': mean_actual,
                'calibration_error': calibration_error,
                'brier': brier,
                'method': method_name
            })
    return pd.DataFrame(results)

# Overall calibration
print("\n" + "="*80)
print("OVERALL CALIBRATION BY PROBABILITY BINS")
print("="*80)

raw_bins = analyze_calibration_bins(df['oof_raw'].values, y, 'Raw')
brier_bins = analyze_calibration_bins(df['oof_brier_opt'].values, y, 'Brier-Optimized')
phase_bins = analyze_calibration_bins(df['oof_inn_phase'].values, y, 'Innings×Phase')

all_bins = pd.concat([raw_bins, brier_bins, phase_bins])

print("\n📊 RAW MODEL (uncalibrated):")
print(raw_bins[['bin', 'n_samples', 'mean_predicted', 'mean_actual', 'calibration_error', 'brier']].to_string(index=False))

print("\n📊 BRIER-OPTIMIZED (per-over calibrators):")
print(brier_bins[['bin', 'n_samples', 'mean_predicted', 'mean_actual', 'calibration_error', 'brier']].to_string(index=False))

print("\n📊 INNINGS×PHASE (6 calibrators):")
print(phase_bins[['bin', 'n_samples', 'mean_predicted', 'mean_actual', 'calibration_error', 'brier']].to_string(index=False))

# Compare methods
print("\n" + "="*80)
print("COMPARISON: Calibration Error by Bin")
print("="*80)

comparison = raw_bins[['bin', 'n_samples']].copy()
comparison['Raw_CE'] = raw_bins['calibration_error'].values
comparison['Brier_CE'] = brier_bins['calibration_error'].values
comparison['Phase_CE'] = phase_bins['calibration_error'].values
comparison['Best'] = comparison[['Raw_CE', 'Brier_CE', 'Phase_CE']].idxmin(axis=1)
print(comparison.to_string(index=False))

# Analyze by innings × phase
print("\n" + "="*80)
print("CALIBRATION BY INNINGS × PHASE × PROBABILITY BIN")
print("="*80)

for inn in [1, 2]:
    for phase in ['powerplay', 'middle', 'death']:
        mask = (df['inn_num'] == inn) & (df['phase'] == phase)
        subset = df[mask]
        if len(subset) == 0:
            continue
        
        print(f"\n🏏 Innings {inn} - {phase.upper()} ({len(subset):,} samples)")
        print("-" * 60)
        
        raw_seg = analyze_calibration_bins(subset['oof_raw'].values, subset['is_winner'].values, 'Raw')
        brier_seg = analyze_calibration_bins(subset['oof_brier_opt'].values, subset['is_winner'].values, 'Brier')
        phase_seg = analyze_calibration_bins(subset['oof_inn_phase'].values, subset['is_winner'].values, 'Phase')
        
        # Show only bins with data
        for i, (_, row) in enumerate(raw_seg.iterrows()):
            if row['n_samples'] > 0:
                brier_ce = brier_seg.iloc[i]['calibration_error'] if i < len(brier_seg) else np.nan
                phase_ce = phase_seg.iloc[i]['calibration_error'] if i < len(phase_seg) else np.nan
                best = "🥇 Brier" if brier_ce < phase_ce else "🥇 Phase"
                print(f"  {row['bin']:>9}: n={row['n_samples']:>5,} | Raw CE={row['calibration_error']:.4f} | Brier CE={brier_ce:.4f} | Phase CE={phase_ce:.4f} | {best}")

# Summary statistics
print("\n" + "="*80)
print("SUMMARY: Overall Metrics")
print("="*80)

def calc_metrics(probs, actuals):
    brier = ((probs - actuals) ** 2).mean()
    # ECE
    bins = np.linspace(0, 1, 11)
    bin_indices = np.digitize(probs, bins) - 1
    bin_indices = np.clip(bin_indices, 0, 9)
    ece = 0
    for i in range(10):
        mask = bin_indices == i
        if mask.sum() > 0:
            ece += mask.sum() * abs(probs[mask].mean() - actuals[mask].mean())
    ece /= len(probs)
    # Log loss
    eps = 1e-15
    probs_clipped = np.clip(probs, eps, 1 - eps)
    logloss = -np.mean(actuals * np.log(probs_clipped) + (1 - actuals) * np.log(1 - probs_clipped))
    return brier, ece, logloss

raw_metrics = calc_metrics(df['oof_raw'].values, y)
brier_metrics = calc_metrics(df['oof_brier_opt'].values, y)
phase_metrics = calc_metrics(df['oof_inn_phase'].values, y)

print(f"\n{'Method':<20} {'Brier':>10} {'ECE':>10} {'LogLoss':>10}")
print("-" * 52)
print(f"{'Raw':<20} {raw_metrics[0]:>10.4f} {raw_metrics[1]:>10.4f} {raw_metrics[2]:>10.4f}")
print(f"{'Brier-Optimized':<20} {brier_metrics[0]:>10.4f} {brier_metrics[1]:>10.4f} {brier_metrics[2]:>10.4f}")
print(f"{'Innings×Phase':<20} {phase_metrics[0]:>10.4f} {phase_metrics[1]:>10.4f} {phase_metrics[2]:>10.4f}")

# Check for problematic bins (high calibration error)
print("\n" + "="*80)
print("⚠️  PROBLEMATIC BINS (CE > 0.05)")
print("="*80)

for method, bins_df in [('Brier-Optimized', brier_bins), ('Innings×Phase', phase_bins)]:
    problems = bins_df[bins_df['calibration_error'] > 0.05]
    if len(problems) > 0:
        print(f"\n{method}:")
        for _, row in problems.iterrows():
            print(f"  Bin {row['bin']}: CE={row['calibration_error']:.4f}, n={row['n_samples']:,}, pred={row['mean_predicted']:.3f}, actual={row['mean_actual']:.3f}")
    else:
        print(f"\n{method}: ✅ All bins have CE ≤ 0.05")

print("\n✅ Analysis complete!")
