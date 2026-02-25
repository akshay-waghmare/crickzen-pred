import os
import json
import glob
import random
import pandas as pd
import numpy as np
import time
from pathlib import Path
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, as_completed
from sklearn.metrics import log_loss, brier_score_loss

from bbl_pipeline.inference.predictor import Predictor
from bbl_pipeline.inference.schema import MatchState as MLMatchState
from bbl_pipeline.simulation.engine import simulate_one_over
from bbl_pipeline.simulation.state import MatchState as SimMatchState

# Setup
MODEL_DIR = os.path.abspath("models/t20_international_male_v1")
FS_DIR = "data/t20_international_male_feature_store_v1"
JSON_DIR = "t20_international_male"
LEAGUE = "t20i"
NUM_MATCHES = 500 # Increased for better stability
POINTS_PER_MATCH = 12
MAX_WORKERS = os.cpu_count() or 4

def calculate_ece(probs, labels, n_bins=10):
    """Calculate Expected Calibration Error."""
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    bin_lowers = bin_boundaries[:-1]
    bin_uppers = bin_boundaries[1:]
    ece = 0
    for bin_lower, bin_upper in zip(bin_lowers, bin_uppers):
        in_bin = (probs > bin_lower) & (probs <= bin_upper)
        if np.any(in_bin):
            prop_in_bin = np.mean(in_bin)
            actual_on_bin = np.mean(labels[in_bin])
            avg_prob_in_bin = np.mean(probs[in_bin])
            ece += prop_in_bin * np.abs(actual_on_bin - avg_prob_in_bin)
    return ece

# Global predictor for workers (lazy loaded)
_worker_predictor = None

def get_worker_predictor():
    global _worker_predictor
    if _worker_predictor is None:
        _worker_predictor = Predictor.load(MODEL_DIR, FS_DIR, league=LEAGUE)
    return _worker_predictor

def analyze_single_match(match_path):
    """Worker function to analyze a single match."""
    predictor = get_worker_predictor()
    
    with open(match_path) as f:
        data = json.load(f)
    
    info = data.get("info", {})
    outcome = info.get("outcome", {})
    winner = outcome.get("winner")
    teams = info.get("teams", [])
    if not winner or winner not in teams or len(data.get("innings", [])) < 2:
        return []
        
    innings_data = data["innings"]
    target_info = innings_data[1].get("target", {})
    target_runs = target_info.get("runs")
    if not target_runs: return []
    
    # Determine actual winner for each innings
    inn1_batting = innings_data[0]["team"]
    inn1_won = 1 if winner == inn1_batting else 0
    
    inn2_batting = innings_data[1]["team"]
    inn2_won = 1 if winner == inn2_batting else 0
    
    match_records = []
    
    # Sample points from both innings
    for inn_idx in [0, 1]:
        batting_team = innings_data[inn_idx]["team"]
        bowling_team = [t for t in teams if t != batting_team][0]
        actual_label = inn1_won if inn_idx == 0 else inn2_won
        
        # Replay innings to get states
        score, wickets, legal_balls = 0, 0, 0
        overs = innings_data[inn_idx].get("overs", [])
        
        states_in_inn = []
        for ov_idx, ov in enumerate(overs):
            for d in ov["deliveries"]:
                score += d["runs"]["total"]
                if d.get("wickets"): wickets += 1
                
                # Count legal balls
                extras = d.get("extras", {})
                if "wides" not in extras and "noballs" not in extras:
                    legal_balls += 1
            
            if legal_balls > 0 and legal_balls % 6 == 0:
                states_in_inn.append({
                    "score": score,
                    "wickets": wickets,
                    "overs": legal_balls / 6.0,
                    "balls_remaining": (20 * 6) - legal_balls if inn_idx == 1 else 120 - legal_balls
                })
        
        # Sample N states from this innings
        if not states_in_inn: continue
        sampled_states = random.sample(states_in_inn, min(POINTS_PER_MATCH // 2, len(states_in_inn)))
        
        for s in sampled_states:
            # 1. ML Prediction
            ml_state = MLMatchState(
                match_id="test",
                venue=info.get("venue", "Unknown"),
                batting_team=batting_team,
                bowling_team=bowling_team,
                innings=inn_idx + 1,
                over=int(s["overs"]),
                ball=0,
                current_score=s["score"],
                wickets_lost=s["wickets"],
                batsman_1="Unknown",
                batsman_2="Unknown",
                bowler="Unknown",
                target_runs=target_runs if inn_idx == 1 else None
            )
            ml_prob = predictor.predict(ml_state)
            
            # 2. MC Prediction (Calibrated)
            sim_state = SimMatchState(
                innings=inn_idx + 1,
                score=s["score"],
                wickets_lost=min(s["wickets"], 9),
                balls_remaining=max(1, s["balls_remaining"]),
                target_runs=target_runs if inn_idx == 1 else None,
                batting_team=batting_team,
                bowling_team=bowling_team,
                league=LEAGUE,
                total_balls=120
            )
            mc_res = simulate_one_over(sim_state, n_simulations=500, model_dir=MODEL_DIR)
            mc_prob = mc_res.mean_prob
            
            match_records.append({
                "innings": inn_idx + 1,
                "over": s["overs"],
                "ml_prob": ml_prob,
                "mc_prob": mc_prob,
                "divergence": mc_prob - ml_prob,
                "actual": actual_label,
                "phase": "powerplay" if s["overs"] <= 6 else "middle" if s["overs"] <= 15 else "death"
            })
            
    return match_records

def run_analysis():
    all_json = glob.glob(f"{JSON_DIR}/*.json")
    if not all_json:
        print(f"ERROR: No JSON files found in {JSON_DIR}")
        return
    
    selected_matches = random.sample(all_json, min(NUM_MATCHES, len(all_json)))
    print(f"Running Calibration Analysis (Log-Loss, Brier & ECE) across {len(selected_matches)} matches...")
    
    all_records = []
    
    start_time = time.time()
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(analyze_single_match, path): path for path in selected_matches}
        
        for future in tqdm(as_completed(futures), total=len(selected_matches)):
            match_records = future.result()
            all_records.extend(match_records)
    
    total_time = time.time() - start_time
    print(f"\nAnalysis complete in {total_time:.1f}s")
    
    if not all_records:
        print("No records collected.")
        return
        
    df = pd.DataFrame(all_records)
    
    def get_metrics(sub_df, title):
        if sub_df.empty: return None
        y_true = sub_df["actual"].values
        ml_probs = sub_df["ml_prob"].values
        mc_probs = sub_df["mc_prob"].values
        
        # Clip
        ml_probs_c = np.clip(ml_probs, 1e-15, 1 - 1e-15)
        mc_probs_c = np.clip(mc_probs, 1e-15, 1 - 1e-15)
        
        return {
            "Segment": title,
            "N": len(sub_df),
            "ML_LL": log_loss(y_true, ml_probs_c),
            "MC_LL": log_loss(y_true, mc_probs_c),
            "ML_Brier": brier_score_loss(y_true, ml_probs),
            "MC_Brier": brier_score_loss(y_true, mc_probs),
            "ML_ECE": calculate_ece(ml_probs, y_true),
            "MC_ECE": calculate_ece(mc_probs, y_true)
        }

    results = []
    # 1. Overall
    results.append(get_metrics(df, "OVERALL"))
    
    # 2. Inning + Phase Breakdown
    for inn in [1, 2]:
        for phase in ["powerplay", "middle", "death"]:
            sub = df[(df["innings"] == inn) & (df["phase"] == phase)]
            results.append(get_metrics(sub, f"Inn {inn} - {phase.capitalize()}"))

    report_df = pd.DataFrame([r for r in results if r])
    
    print("\n" + "="*120)
    print(f"{'SEGMENT':<20} | {'N':<5} | {'ML LL':<8} | {'MC LL':<8} | {'ML Brier':<8} | {'MC Brier':<8} | {'ML ECE':<8} | {'MC ECE':<8}")
    print("-" * 120)
    for _, row in report_df.iterrows():
        print(f"{row['Segment']:<20} | {row['N']:<5} | {row['ML_LL']:<8.4f} | {row['MC_LL']:<8.4f} | "
              f"{row['ML_Brier']:<8.4f} | {row['MC_Brier']:<8.4f} | {row['ML_ECE']:<8.4f} | {row['MC_ECE']:<8.4f}")
    print("="*120)
    
    # Gap Analysis (>10% difference)
    print("\n" + "="*120)
    print("GAP ANALYSIS (>10% difference between ML and MC)")
    print("="*120)
    
    df["abs_diff"] = np.abs(df["divergence"])
    gap_df = df[df["abs_diff"] > 0.10].copy()
    
    if gap_df.empty:
        print("No instances found with >10% difference.")
    else:
        print(f"Found {len(gap_df)} instances with >10% difference ({len(gap_df)/len(df)*100:.1f}% of total).")
        
        # Where does reality align?
        # We check which model was closer to the actual outcome
        gap_df["ml_error"] = np.abs(gap_df["actual"] - gap_df["ml_prob"])
        gap_df["mc_error"] = np.abs(gap_df["actual"] - gap_df["mc_prob"])
        
        gap_df["ml_closer"] = gap_df["ml_error"] < gap_df["mc_error"]
        gap_df["mc_closer"] = gap_df["mc_error"] < gap_df["ml_error"]
        
        ml_wins = gap_df["ml_closer"].sum()
        mc_wins = gap_df["mc_closer"].sum()
        ties = len(gap_df) - ml_wins - mc_wins
        
        print(f"\nWhen gap > 10%, reality aligns with:")
        print(f" - ML Model: {ml_wins} times ({ml_wins/len(gap_df)*100:.1f}%)")
        print(f" - MC Model: {mc_wins} times ({mc_wins/len(gap_df)*100:.1f}%)")
        print(f" - Tie: {ties} times ({ties/len(gap_df)*100:.1f}%)")
        
        # Breakdown by phase
        print("\nGap Analysis by Phase:")
        for inn in [1, 2]:
            for phase in ["powerplay", "middle", "death"]:
                sub = gap_df[(gap_df["innings"] == inn) & (gap_df["phase"] == phase)]
                if len(sub) > 0:
                    ml_w = sub["ml_closer"].sum()
                    mc_w = sub["mc_closer"].sum()
                    print(f" - Inn {inn} {phase.capitalize()}: N={len(sub)} | ML closer: {ml_w/len(sub)*100:.1f}% | MC closer: {mc_w/len(sub)*100:.1f}%")

if __name__ == "__main__":
    run_analysis()
