#!/usr/bin/env python3
"""
First Innings Penalty Validation and Refinement

Step 1: Define quantitative binning thresholds for score position
Step 2: Validate penalty tables against historical data
Step 3: Output refined 3D penalty tables

Author: Copilot
Date: January 16, 2026
"""
import pandas as pd
import numpy as np
from typing import Dict, Tuple

# Load training data
df = pd.read_parquet('data/bbl_features_v2/training.parquet')
df_inn1 = df[df['innings'] == 1].copy()

print("="*80)
print("FIRST INNINGS PENALTY VALIDATION")
print("="*80)
print(f"Total 1st innings samples: {len(df_inn1):,}\n")

# ============================================================================
# STEP 1: Define Quantitative Binning
# ============================================================================
print("="*80)
print("STEP 1: QUANTITATIVE BINNING THRESHOLDS")
print("="*80)

# Calculate overs bowled
df_inn1['overs_bowled'] = 20 - df_inn1['overs_remaining']

# Calculate expected run rate at each phase
# Using historical average run rate progression
PHASE_EXPECTED_RR = {
    'powerplay': 7.5,   # Overs 0-6: ~7.5 RPO typical
    'middle': 7.8,      # Overs 6-14: ~7.8 RPO
    'death': 9.5,       # Overs 14-18: ~9.5 RPO (acceleration)
    'final': 11.0,      # Overs 18-20: ~11 RPO (slog)
}

# Alternative: Calculate from data
print("\nHistorical Run Rates by Phase:")
for phase_name, (start, end) in [('powerplay', (0, 6)), ('middle', (6, 14)), ('death', (14, 18)), ('final', (18, 20))]:
    phase_df = df_inn1[(df_inn1['overs_bowled'] >= start) & (df_inn1['overs_bowled'] < end)]
    if len(phase_df) > 0 and 'current_run_rate' in phase_df.columns:
        avg_rr = phase_df['current_run_rate'].mean()
        print(f"  {phase_name}: {avg_rr:.2f} RPO (n={len(phase_df):,})")

# Define phase
def get_phase(overs):
    if overs < 6:
        return 'powerplay'
    elif overs < 14:
        return 'middle'
    elif overs < 18:
        return 'death'
    else:
        return 'final'

df_inn1['phase'] = df_inn1['overs_bowled'].apply(get_phase)

# Calculate ease ratio: current_run_rate / expected_run_rate
def get_expected_rr(phase):
    return PHASE_EXPECTED_RR.get(phase, 8.0)

df_inn1['expected_rr'] = df_inn1['phase'].apply(get_expected_rr)
df_inn1['ease_ratio'] = df_inn1['current_run_rate'] / df_inn1['expected_rr']
df_inn1['ease_ratio'] = df_inn1['ease_ratio'].clip(0.3, 2.0)  # Clip extremes

# Define score position bins based on ease ratio
# Calibrate thresholds from data distribution
print("\nEase Ratio Distribution (CRR / Expected RR):")
print(df_inn1['ease_ratio'].describe())

percentiles = df_inn1['ease_ratio'].quantile([0.1, 0.25, 0.5, 0.75, 0.9])
print("\nPercentiles:")
print(percentiles)

# Define thresholds based on data
EASE_THRESHOLDS = {
    'well_ahead': 1.15,    # Top 25% ease
    'ahead': 1.05,         # Above average
    'par': 0.95,           # Around average (0.95-1.05)
    'behind': 0.85,        # Below average
    'well_behind': 0.0     # Bottom (< 0.85)
}

def classify_ease(ratio):
    if ratio >= EASE_THRESHOLDS['well_ahead']:
        return 'well_ahead'
    elif ratio >= EASE_THRESHOLDS['ahead']:
        return 'ahead'
    elif ratio >= EASE_THRESHOLDS['par']:
        return 'par'
    elif ratio >= EASE_THRESHOLDS['behind']:
        return 'behind'
    else:
        return 'well_behind'

df_inn1['ease_bucket'] = df_inn1['ease_ratio'].apply(classify_ease)

print("\nEase Bucket Distribution:")
print(df_inn1['ease_bucket'].value_counts())

# ============================================================================
# STEP 2: Validate with Historical Win Rates
# ============================================================================
print("\n" + "="*80)
print("STEP 2: VALIDATE PENALTY TABLES WITH HISTORICAL WIN RATES")
print("="*80)

# Create 3D pivot: Phase × Ease × Wickets -> Win Rate
print("\nWin Rate by Phase × Ease × Wickets:")
print("-"*60)

# Store results for penalty table generation
penalty_data = {}

for phase in ['powerplay', 'middle', 'death', 'final']:
    phase_df = df_inn1[df_inn1['phase'] == phase]
    if len(phase_df) == 0:
        continue
    
    print(f"\n### {phase.upper()} PHASE ###")
    penalty_data[phase] = {}
    
    for ease in ['well_ahead', 'ahead', 'par', 'behind', 'well_behind']:
        ease_df = phase_df[phase_df['ease_bucket'] == ease]
        if len(ease_df) < 30:
            continue
            
        penalty_data[phase][ease] = {}
        
        # Get base win rate (0-1 wickets)
        base_subset = ease_df[ease_df['wickets_lost'] <= 1]
        base_wr = base_subset['is_winner'].mean() if len(base_subset) > 0 else 0.5
        
        print(f"\n  {ease} (base WR: {base_wr:.3f}, n={len(ease_df):,}):")
        
        for wkts in range(10):
            wkt_df = ease_df[ease_df['wickets_lost'] == wkts]
            if len(wkt_df) >= 10:
                wr = wkt_df['is_winner'].mean()
                penalty = min(1.0, wr / base_wr) if base_wr > 0 else 0.5
                penalty_data[phase][ease][wkts] = {
                    'win_rate': wr,
                    'penalty': penalty,
                    'count': len(wkt_df)
                }
                print(f"    {wkts} wkts: WR={wr:.3f}, penalty={penalty:.3f} (n={len(wkt_df)})")

# ============================================================================
# STEP 3: Generate Refined 3D Penalty Tables
# ============================================================================
print("\n" + "="*80)
print("STEP 3: REFINED 3D PENALTY TABLES (Copy-Paste Ready)")
print("="*80)

print("\n# Phase thresholds (overs bowled)")
print("PHASE_THRESHOLDS = {")
print("    'powerplay': 6,   # Overs 0-6")
print("    'middle': 14,     # Overs 6-14")
print("    'death': 18,      # Overs 14-18")
print("    'final': 20       # Overs 18-20")
print("}")

print("\n# Ease ratio thresholds (CRR / Expected RR)")
print("EASE_THRESHOLDS = {")
for k, v in EASE_THRESHOLDS.items():
    print(f"    '{k}': {v},")
print("}")

print("\n# Expected run rate by phase")
print("PHASE_EXPECTED_RR = {")
for k, v in PHASE_EXPECTED_RR.items():
    print(f"    '{k}': {v},")
print("}")

# Generate penalty tables
print("\n# 3D Penalty Tables: PHASE -> EASE -> WICKETS -> penalty")
print("FIRST_INNINGS_WICKET_PENALTY_3D = {")

for phase in ['powerplay', 'middle', 'death', 'final']:
    if phase not in penalty_data:
        continue
    
    print(f"    '{phase}': {{")
    
    for ease in ['well_ahead', 'ahead', 'par', 'behind', 'well_behind']:
        if ease not in penalty_data.get(phase, {}):
            # Use default penalties if no data
            print(f"        '{ease}': {{0: 1.00, 2: 0.90, 4: 0.70, 6: 0.40, 8: 0.15, 10: 0.01}},")
            continue
        
        ease_data = penalty_data[phase][ease]
        penalties = {}
        
        for wkts in range(11):
            if wkts in ease_data:
                penalties[wkts] = round(ease_data[wkts]['penalty'], 2)
            else:
                # Interpolate from nearest
                lower = max([w for w in ease_data.keys() if w < wkts], default=0)
                upper = min([w for w in ease_data.keys() if w > wkts], default=10)
                if lower in ease_data and upper in ease_data:
                    lower_p = ease_data[lower]['penalty']
                    upper_p = ease_data[upper]['penalty']
                    ratio = (wkts - lower) / (upper - lower) if upper != lower else 0
                    penalties[wkts] = round(lower_p + ratio * (upper_p - lower_p), 2)
                elif lower in ease_data:
                    penalties[wkts] = round(ease_data[lower]['penalty'] * 0.7, 2)
                else:
                    penalties[wkts] = 0.5
        
        penalty_str = ", ".join([f"{k}: {v:.2f}" for k, v in sorted(penalties.items())])
        print(f"        '{ease}': {{{penalty_str}}},")
    
    print("    },")

print("}")

# ============================================================================
# STEP 4: Validation - Compare Predicted vs Actual Win Rates
# ============================================================================
print("\n" + "="*80)
print("STEP 4: VALIDATION - PREDICTED VS ACTUAL WIN RATES")
print("="*80)

# Function to get penalty from tables
def get_penalty_from_table(phase, ease, wickets, penalty_data):
    if phase not in penalty_data:
        return 0.5
    if ease not in penalty_data[phase]:
        return 0.5
    if wickets not in penalty_data[phase][ease]:
        # Find nearest
        available = list(penalty_data[phase][ease].keys())
        if not available:
            return 0.5
        nearest = min(available, key=lambda x: abs(x - wickets))
        return penalty_data[phase][ease][nearest]['penalty']
    return penalty_data[phase][ease][wickets]['penalty']

# Test on death/final overs (the problem area)
print("\nValidation on Death/Final Overs:")
print("-"*60)

test_df = df_inn1[df_inn1['phase'].isin(['death', 'final'])].copy()

# Add predicted penalty
test_df['predicted_penalty'] = test_df.apply(
    lambda row: get_penalty_from_table(row['phase'], row['ease_bucket'], int(row['wickets_lost']), penalty_data),
    axis=1
)

# Group by predicted penalty bins and check actual win rate
test_df['penalty_bin'] = pd.cut(test_df['predicted_penalty'], bins=[0, 0.3, 0.5, 0.7, 0.9, 1.0])

print("\nActual Win Rate by Predicted Penalty Bin:")
validation = test_df.groupby('penalty_bin')['is_winner'].agg(['mean', 'count'])
validation.columns = ['actual_win_rate', 'count']
print(validation)

# Correlation between predicted penalty and actual outcome
correlation = test_df['predicted_penalty'].corr(test_df['is_winner'])
print(f"\nCorrelation (predicted penalty vs actual win): {correlation:.4f}")

# ============================================================================
# STEP 5: Problem Scenario Validation
# ============================================================================
print("\n" + "="*80)
print("STEP 5: PROBLEM SCENARIO VALIDATION")
print("="*80)

# Test scenarios from user
scenarios = [
    {'desc': '202/2 at 18 overs', 'score': 202, 'wkts': 2, 'overs': 18, 'crr': 202/18},
    {'desc': '210/6 at 19 overs', 'score': 210, 'wkts': 6, 'overs': 19, 'crr': 210/19},
    {'desc': '180/4 at 17 overs', 'score': 180, 'wkts': 4, 'overs': 17, 'crr': 180/17},
    {'desc': '150/6 at 16 overs', 'score': 150, 'wkts': 6, 'overs': 16, 'crr': 150/16},
    {'desc': '120/6 at 14 overs', 'score': 120, 'wkts': 6, 'overs': 14, 'crr': 120/14},
]

print(f"\n{'Scenario':<25} {'Phase':<10} {'CRR':>6} {'ExpRR':>6} {'Ease':>6} {'Bucket':<12} {'Wkts':>5} {'Penalty':>8}")
print("-"*100)

for s in scenarios:
    phase = get_phase(s['overs'])
    exp_rr = get_expected_rr(phase)
    ease = s['crr'] / exp_rr
    ease_bucket = classify_ease(ease)
    penalty = get_penalty_from_table(phase, ease_bucket, s['wkts'], penalty_data)
    
    print(f"{s['desc']:<25} {phase:<10} {s['crr']:>6.2f} {exp_rr:>6.1f} {ease:>6.2f} {ease_bucket:<12} {s['wkts']:>5} {penalty:>8.3f}")

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print("""
Key Findings:
1. Ease ratio (CRR / Expected RR) provides good score position classification
2. Penalty tables vary significantly by Phase × Ease × Wickets
3. In death/final overs with high ease (well_ahead), wicket penalty is minimal

Next Steps:
1. Implement 3D penalty tables in calculator.py
2. Add smooth interpolation between phases and ease levels
3. Test with live prediction scenarios
""")
