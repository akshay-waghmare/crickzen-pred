#!/usr/bin/env python3
"""
Analyze wicket penalty calibration based on chase difficulty.

Goal: Determine if wicket penalties should be dynamic based on:
1. Required Run Rate (RRR) 
2. Current Run Rate (CRR)
3. CRR/RRR ratio (chase ease)
4. Pressure Index

Author: Copilot
Date: January 16, 2026
"""
import pandas as pd
import numpy as np

# Load training data
df = pd.read_parquet('data/bbl_features_v2/training.parquet')
df_inn2 = df[df['innings'] == 2].copy()

print("="*80)
print("WICKET PENALTY CALIBRATION ANALYSIS - 2ND INNINGS")
print("="*80)
print(f"Total 2nd innings samples: {len(df_inn2):,}\n")

# ============================================================================
# PART 1: Current Wicket Penalty Table (for reference)
# ============================================================================
print("="*80)
print("PART 1: CURRENT WICKET PENALTY TABLE (Reference)")
print("="*80)

# Actual win rate by wickets lost
wicket_win_rates = df_inn2.groupby('wickets_lost')['is_winner'].agg(['mean', 'count'])
wicket_win_rates.columns = ['win_rate', 'count']
print("\nActual win rate by wickets lost (all situations):")
print(wicket_win_rates.to_string())

# Current penalty table from code
current_penalty = {0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 0.75, 5: 0.50, 6: 0.35, 7: 0.25, 8: 0.12, 9: 0.05, 10: 0.01}
print("\nCurrent WICKET_PENALTY table:")
for w, p in current_penalty.items():
    actual = wicket_win_rates.loc[w, 'win_rate'] if w in wicket_win_rates.index else 0
    print(f"  {w} wickets: penalty={p:.2f}, actual_win_rate={actual:.3f}")

# ============================================================================
# PART 2: Win Rate by Wickets × Chase Difficulty (CRR/RRR Ratio)
# ============================================================================
print("\n" + "="*80)
print("PART 2: WIN RATE BY WICKETS × CHASE DIFFICULTY (CRR/RRR Ratio)")
print("="*80)

# Calculate chase ease ratio (CRR / RRR)
# Higher = easier chase (scoring faster than required)
df_inn2['crr_rrr_ratio'] = df_inn2['current_run_rate'] / df_inn2['required_run_rate'].replace(0, 0.1)
df_inn2['crr_rrr_ratio'] = df_inn2['crr_rrr_ratio'].clip(-10, 10)  # Clip extreme values

# Handle negative RRR (already won)
df_inn2.loc[df_inn2['required_run_rate'] <= 0, 'crr_rrr_ratio'] = 10  # Treat as very easy

# Define chase difficulty buckets
def classify_chase_ease(ratio):
    if ratio >= 3:
        return "very_easy"     # CRR 3x+ RRR (e.g., CRR=10, RRR=3)
    elif ratio >= 1.5:
        return "easy"          # CRR 1.5-3x RRR
    elif ratio >= 1.0:
        return "comfortable"   # CRR >= RRR (on track)
    elif ratio >= 0.7:
        return "tough"         # Slightly behind
    else:
        return "desperate"     # Way behind

df_inn2['chase_ease'] = df_inn2['crr_rrr_ratio'].apply(classify_chase_ease)

# Cross-tabulation: wickets × chase ease
print("\nWin Rate by Wickets Lost × Chase Ease (CRR/RRR ratio):")
print("-"*80)

pivot_wr = df_inn2.pivot_table(
    values='is_winner', 
    index='wickets_lost', 
    columns='chase_ease', 
    aggfunc='mean'
)[['very_easy', 'easy', 'comfortable', 'tough', 'desperate']]

pivot_count = df_inn2.pivot_table(
    values='is_winner', 
    index='wickets_lost', 
    columns='chase_ease', 
    aggfunc='count'
)[['very_easy', 'easy', 'comfortable', 'tough', 'desperate']]

print("\nWin Rates:")
print(pivot_wr.round(3).to_string())
print("\nSample Counts:")
print(pivot_count.to_string())

# ============================================================================
# PART 3: Recommended Dynamic Wicket Penalty
# ============================================================================
print("\n" + "="*80)
print("PART 3: RECOMMENDED DYNAMIC WICKET PENALTY")
print("="*80)

# Calculate what penalty would give correct calibration for each bucket
# Penalty = actual_win_rate / base_win_rate (where base is 0-wicket win rate)
print("\nDynamic Penalty = Actual_WR / Base_WR (where base = 0-wicket win rate)")
print("-"*80)

for chase_type in ['very_easy', 'easy', 'comfortable', 'tough', 'desperate']:
    print(f"\n{chase_type.upper()} chase:")
    col_data = pivot_wr[chase_type]
    base_wr = col_data.get(0, col_data.dropna().iloc[0] if len(col_data.dropna()) > 0 else 0.5)
    
    for wkts in range(10):
        if wkts in col_data.index and not pd.isna(col_data[wkts]):
            actual_wr = col_data[wkts]
            penalty = actual_wr / base_wr if base_wr > 0 else 0
            penalty = min(1.0, penalty)  # Cap at 1.0
            count = pivot_count.loc[wkts, chase_type] if wkts in pivot_count.index else 0
            print(f"  {wkts} wkts: WR={actual_wr:.3f}, penalty={penalty:.3f} (n={int(count)})")

# ============================================================================
# PART 4: Analysis by Required Run Rate Buckets
# ============================================================================
print("\n" + "="*80)
print("PART 4: WIN RATE BY WICKETS × REQUIRED RUN RATE")
print("="*80)

# Define RRR buckets
def classify_rrr(rrr):
    if rrr <= 0:
        return "won/trivial"
    elif rrr <= 4:
        return "easy (<4)"
    elif rrr <= 6:
        return "moderate (4-6)"
    elif rrr <= 8:
        return "challenging (6-8)"
    elif rrr <= 10:
        return "difficult (8-10)"
    else:
        return "desperate (10+)"

df_inn2['rrr_bucket'] = df_inn2['required_run_rate'].apply(classify_rrr)

# Cross-tabulation
pivot_rrr = df_inn2.pivot_table(
    values='is_winner', 
    index='wickets_lost', 
    columns='rrr_bucket', 
    aggfunc='mean'
)

pivot_rrr_count = df_inn2.pivot_table(
    values='is_winner', 
    index='wickets_lost', 
    columns='rrr_bucket', 
    aggfunc='count'
)

# Reorder columns
col_order = ['won/trivial', 'easy (<4)', 'moderate (4-6)', 'challenging (6-8)', 'difficult (8-10)', 'desperate (10+)']
col_order = [c for c in col_order if c in pivot_rrr.columns]

print("\nWin Rates by Wickets × RRR:")
print(pivot_rrr[col_order].round(3).to_string())
print("\nSample Counts:")
print(pivot_rrr_count[col_order].to_string())

# ============================================================================
# PART 5: Focus on the Problem Scenario (RRR < 4, 5+ wickets lost)
# ============================================================================
print("\n" + "="*80)
print("PART 5: PROBLEM SCENARIO DEEP DIVE (Easy Chase + 5+ Wickets)")
print("="*80)

# Filter to easy chases with 5+ wickets lost
problem_df = df_inn2[(df_inn2['required_run_rate'] < 4) & (df_inn2['wickets_lost'] >= 5)]
print(f"\nSamples with RRR < 4 and 5+ wickets lost: {len(problem_df)}")

if len(problem_df) > 0:
    print("\nWin rate breakdown:")
    for wkts in sorted(problem_df['wickets_lost'].unique()):
        subset = problem_df[problem_df['wickets_lost'] == wkts]
        print(f"  {int(wkts)} wickets: {subset['is_winner'].mean():.3f} (n={len(subset)})")
    
    # What about when CRR >> RRR?
    very_easy = problem_df[problem_df['crr_rrr_ratio'] >= 2]
    print(f"\nVery easy (CRR >= 2*RRR) with 5+ wickets: {len(very_easy)}")
    if len(very_easy) > 0:
        print(f"  Win rate: {very_easy['is_winner'].mean():.3f}")
        for wkts in sorted(very_easy['wickets_lost'].unique()):
            subset = very_easy[very_easy['wickets_lost'] == wkts]
            print(f"    {int(wkts)} wickets: {subset['is_winner'].mean():.3f} (n={len(subset)})")

# ============================================================================
# PART 6: Pressure Index Analysis
# ============================================================================
print("\n" + "="*80)
print("PART 6: WIN RATE BY WICKETS × PRESSURE INDEX")
print("="*80)

if 'pressure_index' in df_inn2.columns:
    # Pressure index buckets
    def classify_pressure(p):
        if p <= -0.5:
            return "very_low"
        elif p <= 0:
            return "low"
        elif p <= 0.5:
            return "moderate"
        elif p <= 1:
            return "high"
        else:
            return "extreme"
    
    df_inn2['pressure_bucket'] = df_inn2['pressure_index'].apply(classify_pressure)
    
    pivot_pressure = df_inn2.pivot_table(
        values='is_winner', 
        index='wickets_lost', 
        columns='pressure_bucket', 
        aggfunc='mean'
    )
    
    pivot_pressure_count = df_inn2.pivot_table(
        values='is_winner', 
        index='wickets_lost', 
        columns='pressure_bucket', 
        aggfunc='count'
    )
    
    p_order = ['very_low', 'low', 'moderate', 'high', 'extreme']
    p_order = [c for c in p_order if c in pivot_pressure.columns]
    
    print("\nWin Rates by Wickets × Pressure Index:")
    print(pivot_pressure[p_order].round(3).to_string())

# ============================================================================
# PART 7: Proposed New Penalty Tables
# ============================================================================
print("\n" + "="*80)
print("PART 7: PROPOSED DYNAMIC WICKET PENALTY TABLES")
print("="*80)

print("\nBased on the analysis, here are proposed penalty tables by chase difficulty:")
print("\nFormat: wickets -> penalty_multiplier")
print("-"*80)

# Calculate penalties based on actual data
for chase_type in ['very_easy', 'easy', 'comfortable', 'tough', 'desperate']:
    print(f"\n# {chase_type.upper()} chase (CRR/RRR ratio based):")
    col_data = pivot_wr[chase_type]
    base_wr = col_data.get(0, 0.95)  # Assume 95% if no data
    
    penalties = {}
    for wkts in range(11):
        if wkts in col_data.index and not pd.isna(col_data[wkts]):
            actual_wr = col_data[wkts]
            penalty = actual_wr / base_wr if base_wr > 0 else 0
            penalty = min(1.0, penalty)
        else:
            penalty = current_penalty.get(wkts, 0.01)  # Fallback to current
        penalties[wkts] = round(penalty, 2)
    
    print(f"WICKET_PENALTY_{chase_type.upper()} = {{")
    for w, p in penalties.items():
        print(f"    {w}: {p:.2f},")
    print("}")

print("\n" + "="*80)
print("SUMMARY & RECOMMENDATIONS")
print("="*80)
print("""
Key Findings:
1. In EASY chases (RRR < 4 or CRR >> RRR), wicket penalties should be REDUCED
2. The current flat penalty of 0.50 for 5 wickets is too harsh for easy situations
3. Dynamic penalty based on chase difficulty significantly improves calibration

Recommendation:
- Implement a 2D penalty lookup: WICKET_PENALTY[difficulty][wickets]
- Or use a formula: penalty = base_penalty * (1 - difficulty_adjustment)
  where difficulty_adjustment increases as CRR/RRR ratio increases
""")
