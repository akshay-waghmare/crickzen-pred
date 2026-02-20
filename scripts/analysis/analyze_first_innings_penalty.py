#!/usr/bin/env python3
"""
First Innings Wicket Penalty Calibration Analysis

Analyze how wickets impact win probability in first innings based on:
1. Match phase (overs bowled)
2. Score vs expected par
3. Wickets lost

Goal: Determine data-driven penalty surface for first innings death overs.

Author: Copilot
Date: January 16, 2026
"""
import pandas as pd
import numpy as np

# Load training data
df = pd.read_parquet('data/bbl_features_v2/training.parquet')
df_inn1 = df[df['innings'] == 1].copy()

print("="*80)
print("FIRST INNINGS WICKET PENALTY CALIBRATION ANALYSIS")
print("="*80)
print(f"Total 1st innings samples: {len(df_inn1):,}\n")

# ============================================================================
# PART 1: Basic Win Rate by Wickets (All Phases)
# ============================================================================
print("="*80)
print("PART 1: WIN RATE BY WICKETS LOST (All Phases)")
print("="*80)

wicket_win_rates = df_inn1.groupby('wickets_lost')['is_winner'].agg(['mean', 'count'])
wicket_win_rates.columns = ['win_rate', 'count']
print("\nActual win rate by wickets lost (all situations):")
print(wicket_win_rates.to_string())

# ============================================================================
# PART 2: Calculate Overs Bowled from Available Features
# ============================================================================
# We need to derive overs from available columns
# Using overs_remaining if available

print("\n" + "="*80)
print("PART 2: PHASE CLASSIFICATION")
print("="*80)

# Check available columns
print("Available columns:", [c for c in df_inn1.columns if 'over' in c.lower() or 'ball' in c.lower() or 'remain' in c.lower()])

if 'overs_remaining' in df_inn1.columns:
    df_inn1['overs_bowled'] = 20 - df_inn1['overs_remaining']
else:
    # Estimate from resources_remaining
    df_inn1['overs_bowled'] = 20 * (1 - df_inn1['resources_remaining'])

# Define match phases
def classify_phase(overs):
    if overs < 6:
        return 'powerplay'
    elif overs < 14:
        return 'middle'
    elif overs < 18:
        return 'death'
    else:
        return 'final'

df_inn1['phase'] = df_inn1['overs_bowled'].apply(classify_phase)

print("\nPhase distribution:")
print(df_inn1['phase'].value_counts())

# ============================================================================
# PART 3: Win Rate by Wickets × Phase
# ============================================================================
print("\n" + "="*80)
print("PART 3: WIN RATE BY WICKETS × PHASE")
print("="*80)

pivot_phase = df_inn1.pivot_table(
    values='is_winner',
    index='wickets_lost',
    columns='phase',
    aggfunc='mean'
)

pivot_phase_count = df_inn1.pivot_table(
    values='is_winner',
    index='wickets_lost',
    columns='phase',
    aggfunc='count'
)

# Reorder columns
phase_order = ['powerplay', 'middle', 'death', 'final']
phase_order = [p for p in phase_order if p in pivot_phase.columns]

print("\nWin Rates by Wickets × Phase:")
print(pivot_phase[phase_order].round(3).to_string())
print("\nSample Counts:")
print(pivot_phase_count[phase_order].to_string())

# ============================================================================
# PART 4: Score vs Par Analysis
# ============================================================================
print("\n" + "="*80)
print("PART 4: WIN RATE BY WICKETS × SCORE VS PAR")
print("="*80)

# Use score_vs_par if available, otherwise calculate
if 'score_vs_par' in df_inn1.columns:
    df_inn1['score_position'] = df_inn1['score_vs_par']
else:
    # Estimate par score at each point (using projected_score or current_run_rate)
    if 'current_run_rate' in df_inn1.columns:
        # Expected score = CRR * 20 vs average (~165)
        df_inn1['score_position'] = (df_inn1['current_run_rate'] * 20) - 165
    else:
        df_inn1['score_position'] = 0

# Classify score position
def classify_score_position(score_diff):
    if score_diff >= 20:
        return 'well_ahead'  # 20+ runs above par
    elif score_diff >= 5:
        return 'ahead'       # 5-20 runs above par
    elif score_diff >= -5:
        return 'par'         # Within 5 runs of par
    elif score_diff >= -20:
        return 'behind'      # 5-20 runs below par
    else:
        return 'well_behind' # 20+ runs below par

df_inn1['score_bucket'] = df_inn1['score_position'].apply(classify_score_position)

pivot_score = df_inn1.pivot_table(
    values='is_winner',
    index='wickets_lost',
    columns='score_bucket',
    aggfunc='mean'
)

pivot_score_count = df_inn1.pivot_table(
    values='is_winner',
    index='wickets_lost',
    columns='score_bucket',
    aggfunc='count'
)

score_order = ['well_ahead', 'ahead', 'par', 'behind', 'well_behind']
score_order = [s for s in score_order if s in pivot_score.columns]

print("\nWin Rates by Wickets × Score Position:")
print(pivot_score[score_order].round(3).to_string())
print("\nSample Counts:")
print(pivot_score_count[score_order].to_string())

# ============================================================================
# PART 5: CRITICAL - Death/Final Overs Analysis
# ============================================================================
print("\n" + "="*80)
print("PART 5: DEATH & FINAL OVERS DEEP DIVE (Overs 16+)")
print("="*80)

death_final = df_inn1[df_inn1['overs_bowled'] >= 16].copy()
print(f"\nSamples in death/final phase (16+ overs): {len(death_final):,}")

# Win rate by wickets in death overs
print("\nWin rate by wickets (death/final only):")
death_wr = death_final.groupby('wickets_lost')['is_winner'].agg(['mean', 'count'])
death_wr.columns = ['win_rate', 'count']
print(death_wr.to_string())

# 3D Analysis: Wickets × Score Position × Phase (death only)
print("\n\n=== 3D ANALYSIS: WICKETS × SCORE × PHASE (Death/Final) ===")
print("-"*60)

for phase in ['death', 'final']:
    phase_df = df_inn1[df_inn1['phase'] == phase]
    if len(phase_df) == 0:
        continue
    
    print(f"\n{phase.upper()} OVERS (14-18 or 18-20):")
    pivot_3d = phase_df.pivot_table(
        values='is_winner',
        index='wickets_lost',
        columns='score_bucket',
        aggfunc='mean'
    )
    pivot_3d_count = phase_df.pivot_table(
        values='is_winner',
        index='wickets_lost',
        columns='score_bucket',
        aggfunc='count'
    )
    
    avail_cols = [s for s in score_order if s in pivot_3d.columns]
    if avail_cols:
        print("\nWin Rates:")
        print(pivot_3d[avail_cols].round(3).to_string())
        print("\nCounts:")
        print(pivot_3d_count[avail_cols].fillna(0).astype(int).to_string())

# ============================================================================
# PART 6: Focus on Problem Scenarios (High Score + High Wickets in Death)
# ============================================================================
print("\n" + "="*80)
print("PART 6: PROBLEM SCENARIO - HIGH SCORE + HIGH WICKETS IN DEATH")
print("="*80)

# High score (well ahead) + 5+ wickets + death/final overs
problem_scenarios = df_inn1[
    (df_inn1['overs_bowled'] >= 16) & 
    (df_inn1['wickets_lost'] >= 5) &
    (df_inn1['score_bucket'].isin(['well_ahead', 'ahead']))
]

print(f"\nSamples: Death overs + 5+ wickets + ahead/well_ahead: {len(problem_scenarios):,}")

if len(problem_scenarios) > 0:
    print("\nBreakdown by wickets:")
    for wkts in sorted(problem_scenarios['wickets_lost'].unique()):
        subset = problem_scenarios[problem_scenarios['wickets_lost'] == wkts]
        print(f"  {int(wkts)} wickets: {subset['is_winner'].mean():.3f} win rate (n={len(subset)})")
    
    print("\nCompare to low-wicket scenarios:")
    low_wkt_ahead = df_inn1[
        (df_inn1['overs_bowled'] >= 16) & 
        (df_inn1['wickets_lost'] <= 2) &
        (df_inn1['score_bucket'].isin(['well_ahead', 'ahead']))
    ]
    print(f"  0-2 wickets, ahead: {low_wkt_ahead['is_winner'].mean():.3f} (n={len(low_wkt_ahead)})")

# ============================================================================
# PART 7: Very Final Overs (18-20) Analysis
# ============================================================================
print("\n" + "="*80)
print("PART 7: VERY FINAL OVERS (18-20) - WICKETS SHOULD BARELY MATTER")
print("="*80)

final_overs = df_inn1[df_inn1['overs_bowled'] >= 18].copy()
print(f"\nSamples in final overs (18+): {len(final_overs):,}")

if len(final_overs) > 0:
    # Pivot by wickets and score
    pivot_final = final_overs.pivot_table(
        values='is_winner',
        index='wickets_lost',
        columns='score_bucket',
        aggfunc=['mean', 'count']
    )
    
    print("\nWin Rate in Final Overs (18-20) by Wickets × Score:")
    
    for score_b in score_order:
        if ('mean', score_b) in pivot_final.columns:
            print(f"\n{score_b.upper()}:")
            for wkts in range(10):
                if wkts in pivot_final.index:
                    wr = pivot_final.loc[wkts, ('mean', score_b)]
                    cnt = pivot_final.loc[wkts, ('count', score_b)]
                    if not pd.isna(wr):
                        print(f"  {wkts} wkts: {wr:.3f} (n={int(cnt)})")

# ============================================================================
# PART 8: Proposed Penalty Tables
# ============================================================================
print("\n" + "="*80)
print("PART 8: PROPOSED FIRST INNINGS WICKET PENALTY TABLES")
print("="*80)

# Calculate penalties for each phase × score_position combination
print("\nPenalty = Win_Rate / Base_Win_Rate (where base is 0 wickets in same condition)")
print("-"*80)

for phase in ['powerplay', 'middle', 'death', 'final']:
    phase_df = df_inn1[df_inn1['phase'] == phase]
    if len(phase_df) == 0:
        continue
        
    print(f"\n### {phase.upper()} Phase ###")
    
    for score_b in ['well_ahead', 'ahead', 'par', 'behind', 'well_behind']:
        subset = phase_df[phase_df['score_bucket'] == score_b]
        if len(subset) < 50:
            continue
            
        base_wr = subset[subset['wickets_lost'] == 0]['is_winner'].mean()
        if pd.isna(base_wr) or base_wr < 0.1:
            base_wr = subset[subset['wickets_lost'] <= 1]['is_winner'].mean()
        if pd.isna(base_wr):
            continue
            
        print(f"\n  {score_b} (base WR: {base_wr:.3f}):")
        for wkts in range(10):
            wkt_subset = subset[subset['wickets_lost'] == wkts]
            if len(wkt_subset) >= 10:
                wr = wkt_subset['is_winner'].mean()
                penalty = min(1.0, wr / base_wr) if base_wr > 0 else 0
                print(f"    {wkts} wkts: WR={wr:.3f}, penalty={penalty:.3f} (n={len(wkt_subset)})")

# ============================================================================
# PART 9: Key Insights Summary
# ============================================================================
print("\n" + "="*80)
print("PART 9: KEY INSIGHTS SUMMARY")
print("="*80)

print("""
Analysis Questions:
1. Do wickets matter less in death overs?
2. Does score position modify the wicket impact?
3. What should the penalty surface look like?
""")

# Calculate the effect of wickets by phase
print("\nWicket Effect by Phase (6 wickets vs 0 wickets):")
for phase in ['powerplay', 'middle', 'death', 'final']:
    phase_df = df_inn1[df_inn1['phase'] == phase]
    if len(phase_df) == 0:
        continue
    wr_0 = phase_df[phase_df['wickets_lost'] == 0]['is_winner'].mean()
    wr_6 = phase_df[phase_df['wickets_lost'] == 6]['is_winner'].mean()
    if not pd.isna(wr_0) and not pd.isna(wr_6):
        ratio = wr_6 / wr_0 if wr_0 > 0 else 0
        print(f"  {phase:12}: 0 wkts={wr_0:.3f}, 6 wkts={wr_6:.3f}, ratio={ratio:.3f}")

# Score effect in death overs
print("\nScore Effect in Death/Final Overs (well_ahead vs well_behind, 5 wickets):")
death_final = df_inn1[df_inn1['overs_bowled'] >= 16]
for score_b in ['well_ahead', 'ahead', 'par', 'behind', 'well_behind']:
    subset = death_final[(death_final['score_bucket'] == score_b) & (death_final['wickets_lost'] == 5)]
    if len(subset) >= 5:
        wr = subset['is_winner'].mean()
        print(f"  {score_b:12}: {wr:.3f} (n={len(subset)})")
