import pandas as pd
import numpy as np

def analyze_sample_sizes():
    print("Loading ILT20 training data...")
    df = pd.read_parquet('data/ilt_features_v2/training_sampled.parquet')
    
    # Infer columns if missing
    if 'overs_remaining' in df.columns:
        overs_rem = df['overs_remaining']
    else:
        # Fallback logic if needed, but it should be there
        overs_rem = (120 - (df['over'] * 6 + df['ball'])) / 6
        
    if 'required_run_rate' in df.columns:
        rrr = df['required_run_rate']
        innings = np.where(rrr > 0, 2, 1)
    else:
        innings = df['innings']

    # Calculate derived fields
    balls_rem = np.round(overs_rem * 6)
    runs_req = df['required_run_rate'] * overs_rem
    wickets_rem = 10 - df['wickets_lost']
    
    # Define Masks
    mask_inn2 = innings == 2
    
    # 1. Victory Lap Tier 1 (Runs <= 6, Wickets >= 3)
    mask_vl1 = mask_inn2 & (runs_req <= 6) & (wickets_rem >= 3) & (runs_req > 0)
    
    # 2. Victory Lap Tier 2 (Runs <= 12, Runs < Balls, Wickets >= 4)
    mask_vl2 = mask_inn2 & (runs_req <= 12) & (runs_req < balls_rem) & (wickets_rem >= 4) & (runs_req > 6)
    
    # 3. Extreme Resource (> 97%)
    resource_probs = df['resource_win_prob'] if 'resource_win_prob' in df.columns else np.zeros(len(df))
    mask_res_high = mask_inn2 & (resource_probs > 0.97)
    
    # 4. Extreme Resource (< 3%)
    mask_res_low = mask_inn2 & (resource_probs < 0.03)
    
    print("\n" + "="*60)
    print("SAMPLE SIZE ANALYSIS (2nd Innings Only)")
    print("="*60)
    print(f"Total 2nd Innings Samples: {mask_inn2.sum()}")
    print("-" * 60)
    print(f"Victory Lap Tier 1 (Need <= 6, Wkts >= 3):   {mask_vl1.sum()} samples")
    print(f"Victory Lap Tier 2 (Need <= 12, Safe):       {mask_vl2.sum()} samples")
    print(f"Resource Prob > 97%:                         {mask_res_high.sum()} samples")
    print(f"Resource Prob < 3%:                          {mask_res_low.sum()} samples")
    print("-" * 60)
    
    # Check outcomes for VL1
    if mask_vl1.sum() > 0:
        wins = df[mask_vl1]['is_winner'].sum()
        print(f"\nOutcomes for Victory Lap Tier 1:")
        print(f"Wins: {wins} / {mask_vl1.sum()} ({wins/mask_vl1.sum()*100:.1f}%)")
        if wins < mask_vl1.sum():
            print("⚠️ FOUND A CHOKE! A team lost from this position.")
            print(df[mask_vl1 & (df['is_winner'] == 0)][['match_id', 'innings', 'over', 'ball', 'current_score', 'wickets_lost', 'target_runs']])

if __name__ == "__main__":
    analyze_sample_sizes()
