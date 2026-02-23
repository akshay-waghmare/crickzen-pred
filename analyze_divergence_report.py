
import os
import json
import glob
import random
import pandas as pd
import numpy as np
import time
import datetime
from pathlib import Path
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, as_completed
from sklearn.metrics import log_loss, brier_score_loss

from bbl_pipeline.inference.predictor import Predictor
from bbl_pipeline.inference.schema import MatchState as MLMatchState
from bbl_pipeline.simulation.engine import simulate_one_over, _load_mc_calibrator
from bbl_pipeline.simulation.state import MatchState as SimMatchState
from bbl_pipeline.features.format_config import FormatConfig

# Setup
MODEL_DIR = "models/t20_international_male_v1"
import os
MODEL_DIR = os.path.abspath(MODEL_DIR)
FS_DIR = "data/t20_international_male_feature_store_v1"
JSON_DIR = "t20_international_male"
LEAGUE = "t20i"
NUM_MATCHES = 200 # Sufficient for ECE/LogLoss stability
POINTS_PER_MATCH = 8
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
        
        # We'll collect all over-end states
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
            # simulate_one_over applies MCCalibrator automatically
            mc_res = simulate_one_over(sim_state, n_simulations=500, model_dir=MODEL_DIR)
            mc_prob = mc_res.mean_prob
            
            # Extract raw mean if available
            raw_mc_prob = getattr(mc_res, "raw_mean", None)
            if raw_mc_prob is None:
                raw_mc_prob = mc_prob            # Note: SimulationResult stores raw_mean before Platt/Temperature adjustment
            
            match_records.append({
                "innings": inn_idx + 1,
                "over": s["overs"],
                "ml_prob": ml_prob,
                "mc_prob": mc_prob,
                "raw_mc_prob": raw_mc_prob,
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
    print(f"Running Calibration Analysis (Log-Loss & ECE) across {len(selected_matches)} matches...")
    print(f"MC Engine: Using CALIBRATED Innings-Specific Probabilities.")
    
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
        raw_mc_probs = sub_df["raw_mc_prob"].values
        
        # Clip
        ml_probs_c = np.clip(ml_probs, 1e-15, 1 - 1e-15)
        mc_probs_c = np.clip(mc_probs, 1e-15, 1 - 1e-15)
        raw_mc_probs_c = np.clip(raw_mc_probs, 1e-15, 1 - 1e-15)
        
        return {
            "Segment": title,
            "N": len(sub_df),
            "ML_LL": log_loss(y_true, ml_probs_c),
            "MC_CAL_LL": log_loss(y_true, mc_probs_c),
            "MC_RAW_LL": log_loss(y_true, raw_mc_probs_c),
            "ML_ECE": calculate_ece(ml_probs, y_true),
            "MC_CAL_ECE": calculate_ece(mc_probs, y_true),
            "MC_RAW_ECE": calculate_ece(raw_mc_probs, y_true)
        }

    results = []
    # 1. Overall
    results.append(get_metrics(df, "OVERALL"))
    
    # 2. Inning Breakdown
    for inn in [1, 2]:
        sub = df[df["innings"] == inn]
        results.append(get_metrics(sub, f"Innings {inn}"))

    report_df = pd.DataFrame([r for r in results if r])
    
    print("\n" + "="*110)
    print(f"{'SEGMENT':<15} | {'ML LL':<8} | {'MC CAL LL':<10} | {'MC RAW LL':<10} | {'ML ECE':<8} | {'MC CAL ECE':<10} | {'MC RAW ECE':<10}")
    print("-"*110)
    for _, row in report_df.iterrows():
        print(f"{row['Segment']:<15} | {row['ML_LL']:<8.4f} | {row['MC_CAL_LL']:<10.4f} | {row['MC_RAW_LL']:<10.4f} | "
              f"{row['ML_ECE']:<8.4f} | {row['MC_CAL_ECE']:<10.4f} | {row['MC_RAW_ECE']:<10.4f}")
    print("="*110)
    
    print("\n💡 INTERPRETATION:")
    print(" - Log-Loss (LL): Lower is better. Measures 'Sharpness' (how much the model rewarded correct confidence).")
    print(" - ECE (Expected Calibration Error): Lower is better. Measures 'Honesty' (if 70% means 70% win rate).")
    
    # Summary recommendation
    overall_trust = "ML" if report_df.iloc[0]["ML_LL"] < report_df.iloc[0]["MC_CAL_LL"] else "MC"
    print(f"\n🏆 OVERALL TRUSTED MODEL: {overall_trust}")
    
    # Check for specific segments where MC might be better (e.g. lower ECE)
    inn1 = report_df[report_df['Segment'] == 'Innings 1']
    if not inn1.empty and inn1.iloc[0]['MC_CAL_ECE'] < inn1.iloc[0]['ML_ECE']:
        print("💡 NOTE: Calibrated MC shows better 'Honesty' (Lower ECE) in Innings 1.")

if __name__ == "__main__":
    run_analysis()
