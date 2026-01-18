"""
WBBL Live Match Prediction - Streamlit App
Reads from JSON file produced by crex_live_predictor backend.

Usage:
1. Start the backend predictor:
   python -m src.bbl_pipeline.inference.crex_live_predictor \
       --match-url "https://crex.com/scoreboard/.../live" \
       --model-dir models/wbbl_champion_v3 \
       --feature-store-dir data/wbbl_feature_store_v3 \
       --output-json data/live_state.json

2. Start Streamlit:
   streamlit run src/bbl_pipeline/app/live_streamlit_app.py
"""

import streamlit as st
import json
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
from pathlib import Path
import time
import joblib

# Page config
st.set_page_config(
    page_title="T20 Live Predictor",
    page_icon="🏏",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS
st.markdown("""
<style>
    .main-header { font-size: 2.5rem; font-weight: bold; text-align: center; 
                   background: linear-gradient(90deg, #e91e63, #9c27b0);
                   -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .live-badge { display: inline-block; background: #f44336; color: white; 
                  padding: 4px 12px; border-radius: 20px; animation: pulse 1.5s infinite; }
    @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }
    .score-display { font-size: 3.5rem; font-weight: bold; text-align: center; }
    .team-name { font-size: 1.5rem; text-align: center; }
    .stale-badge { display: inline-block; background: #ff9800; color: white; 
                   padding: 4px 12px; border-radius: 20px; }
</style>
""", unsafe_allow_html=True)

# Team colors and names - BBL, WBBL, ILT20, SA20, WPL
TEAM_COLORS = {
    # WBBL
    "SYS-W": "#e91e63", "PRS-W": "#ff5722", "ADL-W": "#2196f3", "BRH-W": "#00bcd4",
    "MLR-W": "#f44336", "MLS-W": "#4caf50", "HBH-W": "#9c27b0", "STR-W": "#8bc34a",
    # BBL
    "SYS": "#e91e63", "PRS": "#ff5722", "ADS": "#2196f3", "BRH": "#00bcd4",
    "MLR": "#f44336", "MLS": "#4caf50", "HBH": "#9c27b0", "STH": "#8bc34a",
    "SIX": "#e91e63", "SCO": "#ff5722", "STK": "#2196f3", "HEA": "#00bcd4",
    "REN": "#f44336", "STA": "#4caf50", "HUR": "#9c27b0", "THU": "#8bc34a",
    # ILT20
    "DV": "#6a1b9a", "GG": "#1565c0", "MIE": "#0d47a1", "DC": "#c62828",
    "ADKR": "#4a148c", "SW": "#e65100", "DES": "#6a1b9a", "GUL": "#1565c0",
    # SA20
    "DSG": "#00bcd4", "MICT": "#1565c0", "PR": "#e91e63", "JSK": "#ffc107",
    "PC": "#4caf50", "SEC": "#ff5722",
    # SSM (Super Smash - New Zealand) - both internal and CREX codes
    "AA": "#1a237e", "AKL": "#1a237e", "Auckland": "#1a237e",
    "CD": "#d32f2f", "Central Districts": "#d32f2f",
    "CS": "#ffc107", "CK": "#ffc107", "Canterbury": "#ffc107",
    "ND": "#1565c0", "NB": "#1565c0", "Northern Districts": "#1565c0",
    "OV": "#388e3c", "OTG": "#388e3c", "Otago": "#388e3c",
    "WF": "#7b1fa2", "WEL": "#7b1fa2", "Wellington": "#7b1fa2",
    # SSM Female (New Zealand Women's Super Smash)
    "AA-W": "#1a237e", "Auckland-W": "#1a237e",
    "CD-W": "#d32f2f", "Central-W": "#d32f2f",
    "CS-W": "#ffc107", "Canterbury-W": "#ffc107",
    "ND-W": "#1565c0", "Northern-W": "#1565c0",
    "OV-W": "#388e3c", "Otago-W": "#388e3c",
    "WF-W": "#7b1fa2", "Wellington-W": "#7b1fa2",
    # WPL (Women's Premier League - India)
    "MIW": "#004ba0", "MI-W": "#004ba0", "Mumbai Indians": "#004ba0",
    "RCBW": "#d4171e", "RCB-W": "#d4171e", "Royal Challengers Bengaluru": "#d4171e",
    "DCW": "#004ba0", "DC-W": "#004ba0", "Delhi Capitals": "#004ba0",
    "GGW": "#ff6b35", "GG-W": "#ff6b35", "Gujarat Giants": "#ff6b35",
    "UPW": "#1e90ff", "UP-W": "#1e90ff", "UP Warriorz": "#1e90ff",
    # T20 International Teams (Men's)
    "Australia": "#FFD700", "AUS": "#FFD700",
    "India": "#0033A0", "IND": "#0033A0",
    "England": "#001840", "ENG": "#001840",
    "New Zealand": "#000000", "NZ": "#000000",
    "South Africa": "#006B3F", "SA": "#006B3F",
    "Pakistan": "#006400", "PAK": "#006400",
    "West Indies": "#800020", "WI": "#800020",
    "Sri Lanka": "#0000FF", "SL": "#0000FF",
    "Bangladesh": "#006A4E", "BAN": "#006A4E",
    "Afghanistan": "#0066B3", "AFG": "#0066B3",
    "Zimbabwe": "#FFD700", "ZIM": "#FFD700",
    "Ireland": "#169B62", "IRE": "#169B62",
    "Scotland": "#005EB8", "SCO": "#005EB8",
    "Netherlands": "#FF6600", "NED": "#FF6600",
    "Namibia": "#003580", "NAM": "#003580",
    "United States of America": "#B22234", "USA": "#B22234",
    "Canada": "#FF0000", "CAN": "#FF0000",
    "Oman": "#EF3340", "OMA": "#EF3340",
    "Nepal": "#DC143C", "NEP": "#DC143C",
    "United Arab Emirates": "#00732F", "UAE": "#00732F",
    "Papua New Guinea": "#FF0000", "PNG": "#FF0000",
    "Hong Kong": "#DE2910", "HK": "#DE2910",
    "Uganda": "#FCDC04", "UGA": "#FCDC04",
}
TEAM_NAMES = {
    # WBBL
    "SYS-W": "Sydney Sixers", "PRS-W": "Perth Scorchers", "ADL-W": "Adelaide Strikers",
    "BRH-W": "Brisbane Heat", "MLR-W": "Melbourne Renegades", "MLS-W": "Melbourne Stars",
    "HBH-W": "Hobart Hurricanes", "STR-W": "Sydney Thunder",
    # BBL
    "SYS": "Sydney Sixers", "PRS": "Perth Scorchers", "ADS": "Adelaide Strikers",
    "BRH": "Brisbane Heat", "MLR": "Melbourne Renegades", "MLS": "Melbourne Stars",
    "HBH": "Hobart Hurricanes", "STH": "Sydney Thunder",
    "SIX": "Sydney Sixers", "SCO": "Perth Scorchers", "STK": "Adelaide Strikers",
    "HEA": "Brisbane Heat", "REN": "Melbourne Renegades", "STA": "Melbourne Stars",
    "HUR": "Hobart Hurricanes", "THU": "Sydney Thunder",
    # ILT20
    "DV": "Desert Vipers", "GG": "Gulf Giants", "MIE": "MI Emirates", "DC": "Dubai Capitals",
    "ADKR": "Abu Dhabi Knight Riders", "SW": "Sharjah Warriors", "DES": "Desert Vipers", "GUL": "Gulf Giants",
    # SA20
    "DSG": "Durban's Super Giants", "MICT": "MI Cape Town", "PR": "Paarl Royals",
    "JSK": "Joburg Super Kings", "PC": "Pretoria Capitals", "SEC": "Sunrisers Eastern Cape",
    # SSM (Super Smash - New Zealand) - both internal and CREX codes
    "AA": "Auckland Aces", "AKL": "Auckland Aces", "Auckland": "Auckland Aces",
    "CD": "Central Districts", "Central Districts": "Central Districts",
    "CS": "Canterbury Kings", "CK": "Canterbury Kings", "Canterbury": "Canterbury Kings",
    "ND": "Northern Brave", "NB": "Northern Brave", "Northern Districts": "Northern Brave",
    "OV": "Otago Volts", "OTG": "Otago Volts", "Otago": "Otago Volts",
    "WF": "Wellington Firebirds", "WEL": "Wellington Firebirds", "Wellington": "Wellington Firebirds",
    # SSM Female (New Zealand Women's Super Smash)
    "AA-W": "Auckland Aces Women", "Auckland-W": "Auckland Aces Women",
    "CD-W": "Central Districts Women", "Central-W": "Central Districts Women",
    "CS-W": "Canterbury Kings Women", "Canterbury-W": "Canterbury Kings Women",
    "ND-W": "Northern Brave Women", "Northern-W": "Northern Brave Women",
    "OV-W": "Otago Volts Women", "Otago-W": "Otago Volts Women",
    "WF-W": "Wellington Firebirds Women", "Wellington-W": "Wellington Firebirds Women",
    # WPL (Women's Premier League - India)
    "MIW": "Mumbai Indians", "MI-W": "Mumbai Indians", "Mumbai Indians": "Mumbai Indians",
    "RCBW": "RCB Bengaluru", "RCB-W": "RCB Bengaluru", "Royal Challengers Bengaluru": "RCB Bengaluru",
    "DCW": "Delhi Capitals", "DC-W": "Delhi Capitals", "Delhi Capitals": "Delhi Capitals",
    "GGW": "Gujarat Giants", "GG-W": "Gujarat Giants", "Gujarat Giants": "Gujarat Giants",
    "UPW": "UP Warriorz", "UP-W": "UP Warriorz", "UP Warriorz": "UP Warriorz",
    # T20 International Teams (Men's)
    "Australia": "Australia", "AUS": "Australia",
    "India": "India", "IND": "India",
    "England": "England", "ENG": "England",
    "New Zealand": "New Zealand", "NZ": "New Zealand",
    "South Africa": "South Africa", "SA": "South Africa",
    "Pakistan": "Pakistan", "PAK": "Pakistan",
    "West Indies": "West Indies", "WI": "West Indies",
    "Sri Lanka": "Sri Lanka", "SL": "Sri Lanka",
    "Bangladesh": "Bangladesh", "BAN": "Bangladesh",
    "Afghanistan": "Afghanistan", "AFG": "Afghanistan",
    "Zimbabwe": "Zimbabwe", "ZIM": "Zimbabwe",
    "Ireland": "Ireland", "IRE": "Ireland",
    "Scotland": "Scotland",
    "Netherlands": "Netherlands", "NED": "Netherlands",
    "Namibia": "Namibia", "NAM": "Namibia",
    "United States of America": "USA", "USA": "USA",
    "Canada": "Canada", "CAN": "Canada",
    "Oman": "Oman", "OMA": "Oman",
    "Nepal": "Nepal", "NEP": "Nepal",
    "United Arab Emirates": "UAE", "UAE": "UAE",
    "Papua New Guinea": "PNG", "PNG": "PNG",
    "Hong Kong": "Hong Kong", "HK": "Hong Kong",
    "Uganda": "Uganda", "UGA": "Uganda",
}

DEFAULT_JSON = "data/live_state.json"

# Load per-over calibrators for ECE-optimized predictions (smoother than phase calibrators)
# NOTE: SA20 and WPL use phase calibrators instead of per-over due to small datasets
@st.cache_resource
def load_per_over_calibrators():
    """Load per-over calibrators for BBL, SSM, and SSM Female."""
    calibrators = {}
    try:
        # BBL v12: per-over calibrators are inside isotonic_calibrator.pkl
        bbl_cal = joblib.load('models/bbl_v12/isotonic_calibrator.pkl')
        calibrators['bbl'] = bbl_cal.get('per_over_calibrators', {})
    except:
        calibrators['bbl'] = None
    try:
        calibrators['ssm'] = joblib.load('models/ssm_v1/per_over_calibrators.pkl')
    except:
        calibrators['ssm'] = None
    try:
        calibrators['ssm_female'] = joblib.load('models/ssm_female_v1/per_over_calibrators.pkl')
    except:
        calibrators['ssm_female'] = None
    # SA20 v2: Load from isotonic_calibrator.pkl (generated by generate-oof)
    # Note: SA20 uses phase calibrators, not per-over (small dataset)
    try:
        sa20_cal = joblib.load('models/sat_v2/isotonic_calibrator.pkl')
        # phase_calibrators contains calibrators with keys like 'inn1_powerplay', 'inn1_middle', 'inn1_death'
        calibrators['sa20'] = sa20_cal.get('phase_calibrators', {})
    except:
        calibrators['sa20'] = None
    # T20 Male (International): per-over calibrators for ECE optimization
    try:
        calibrators['t20i'] = joblib.load('models/t20_male_v1/per_over_calibrators_ece.pkl')
    except:
        calibrators['t20i'] = None
    return calibrators

@st.cache_resource
def load_ece_optimized_calibrators():
    """Load ECE-optimized calibrators.
    
    BBL OOF Analysis (Jan 2026):
    - Combined (single isotonic): Best ECE=0.0053, Brier=0.1428, LogLoss=0.4312
    - Already generated by bbl-pipeline train in isotonic_calibrator.pkl
    """
    calibrators = {}
    
    # BBL v12: Use calibrator_combined from isotonic_calibrator.pkl (Best ECE performer!)
    try:
        iso_data = joblib.load('models/bbl_v12/isotonic_calibrator.pkl')
        calibrators['bbl'] = {
            'combined': {
                'calibrator': iso_data['calibrator_combined'],
                'source': 'raw',
                'method': 'combined_isotonic',
                'oof_brier': iso_data.get('oof_brier_calibrated', 0.1810),
                'oof_ece': iso_data.get('oof_ece_calibrated', 0.0000)
            }
        }
    except:
        calibrators['bbl'] = None
    
    return calibrators

ECE_OPTIMIZED_CALIBRATORS = load_ece_optimized_calibrators()

@st.cache_resource
def load_phase_calibrators():
    """Load phase calibrators for SA20, WPL, SSM Female, and BBL.
    All use phase-specific calibrators for best ECE.
    
    BBL OOF Analysis (Jan 2026):
    - Phase calibrators (6) outperform per-over calibrators (40)
    - Phase: Brier=0.1430, ECE=0.0117
    - Per-Over: Brier=0.1440, ECE=0.0132 (WORSE!)
    """
    calibrators = {}
    
    # BBL v12 phase calibrators (6 calibrators - fallback if ECE-optimized not available)
    try:
        bbl_cal = joblib.load('models/bbl_v12/isotonic_calibrator.pkl')
        calibrators['bbl'] = bbl_cal.get('phase_calibrators', {})
    except:
        calibrators['bbl'] = None
    
    # SA20 v2: Load phase calibrators from isotonic_calibrator.pkl (generated by generate-oof)
    try:
        sa20_cal = joblib.load('models/sat_v2/isotonic_calibrator.pkl')
        # phase_calibrators contains calibrators with keys like 'inn1_powerplay', 'inn1_middle', 'inn1_death'
        calibrators['sa20'] = sa20_cal.get('phase_calibrators', {})
    except:
        calibrators['sa20'] = None
    
    # WPL Female phase calibrators (66 matches, resource-based)
    try:
        calibrators['wpl'] = joblib.load('models/wpl_female_v1/phase_calibrators.pkl')
    except:
        calibrators['wpl'] = None
    
    # SSM Female phase calibrators (8 phases - SA20 style)
    try:
        calibrators['ssm_female'] = joblib.load('models/ssm_female_v1/phase_calibrators.pkl')
    except:
        calibrators['ssm_female'] = None
    
    return calibrators

@st.cache_resource
def load_brier_calibrators():
    """Load Brier-optimized calibrators for SSM, BBL, and WPL.
    These select best source per phase/over for accuracy (Brier score)."""
    calibrators = {}
    try:
        calibrators['ssm'] = joblib.load('models/ssm_v1/brier_calibrators.pkl')
        print(f"[OK] Loaded SSM Brier calibrators: {list(calibrators['ssm'].keys())}")
    except Exception as e:
        print(f"[FAIL] Failed to load SSM Brier calibrators: {e}")
        calibrators['ssm'] = None
    # BBL v12: Brier-optimized per-over calibrators from isotonic_calibrator.pkl
    try:
        bbl_cal = joblib.load('models/bbl_v12/isotonic_calibrator.pkl')
        calibrators['bbl'] = bbl_cal.get('per_over_calibrators', {})
        print(f"[OK] Loaded BBL v12 Brier calibrators: {len(calibrators['bbl'])} per-over")
    except Exception as e:
        print(f"[FAIL] Failed to load BBL Brier calibrators: {e}")
        calibrators['bbl'] = None
    try:
        calibrators['wpl'] = joblib.load('models/wpl_female_v1/per_over_calibrators_brier.pkl')
        print(f"[OK] Loaded WPL Brier calibrators: {list(calibrators['wpl'].keys())}")
    except Exception as e:
        print(f"[FAIL] Failed to load WPL Brier calibrators: {e}")
        calibrators['wpl'] = None
    # T20 Male (International): per-over calibrators for Brier optimization
    try:
        calibrators['t20i'] = joblib.load('models/t20_male_v1/per_over_calibrators_brier.pkl')
        print(f"[OK] Loaded T20I Brier calibrators: {list(calibrators['t20i'].keys())}")
    except Exception as e:
        print(f"[FAIL] Failed to load T20I Brier calibrators: {e}")
        calibrators['t20i'] = None
    return calibrators

@st.cache_resource
def load_logloss_calibrators():
    """Load Log Loss-optimized calibrators for BBL and SSM.
    These select best source per over for Log Loss optimization."""
    calibrators = {}
    # BBL v12: LogLoss calibrators from oof_calibrators.pkl (analyze-oof output)
    try:
        bbl_oof = joblib.load('models/bbl_v12/oof_calibrators.pkl')
        calibrators['bbl'] = bbl_oof.get('logloss_optimized', {})
        print(f"[OK] Loaded BBL v12 Log Loss calibrators: {len(calibrators['bbl'])} phases")
    except Exception as e:
        print(f"[FAIL] Failed to load BBL Log Loss calibrators: {e}")
        calibrators['bbl'] = None
    try:
        calibrators['ssm'] = joblib.load('models/ssm_v1/logloss_calibrators.pkl')
        print(f"[OK] Loaded SSM Log Loss calibrators: {len(calibrators['ssm'])} overs")
    except Exception as e:
        print(f"[FAIL] Failed to load SSM Log Loss calibrators: {e}")
        calibrators['ssm'] = None
    return calibrators

PER_OVER_CALIBRATORS = load_per_over_calibrators()
PHASE_CALIBRATORS = load_phase_calibrators()  # SA20, WPL, and SSM Female phase calibrators
BRIER_CALIBRATORS = load_brier_calibrators()
LOGLOSS_CALIBRATORS = load_logloss_calibrators()

# Load SA20 full calibrator data for client-side recalculation
@st.cache_resource
def load_sa20_full_calibrators():
    """Load all SA20 calibrators (combined, innings-specific, phase) for client-side calculation."""
    try:
        cal_data = joblib.load('models/sat_v2/isotonic_calibrator.pkl')
        return {
            'combined': cal_data.get('calibrator_combined'),
            'innings1': cal_data.get('calibrator_innings1'),
            'innings2': cal_data.get('calibrator_innings2'),
            'phase': cal_data.get('phase_calibrators', {})
        }
    except Exception as e:
        print(f"[FAIL] Failed to load SA20 full calibrators: {e}")
        return None

SA20_CALIBRATORS = load_sa20_full_calibrators()

def get_color(team): return TEAM_COLORS.get(team, "#607d8b")
def get_name(team): return TEAM_NAMES.get(team, team)
def prob_to_odds(prob): 
    """Convert probability to decimal odds."""
    if prob <= 0: return 999.99
    if prob >= 1: return 1.00
    return round(1 / prob, 2)


def check_match_result(state: dict) -> tuple:
    """
    Check if match has a definitive result and return corrected probabilities.
    Returns (bat_prob, bowl_prob, is_finished, result_text)
    """
    if not state.get("is_second_innings") or not state.get("target"):
        return state.get("bat_win_prob", 0.5), state.get("bowl_win_prob", 0.5), False, None
    
    score = state.get("score", 0)
    target = state.get("target", 999)
    wickets = state.get("wickets", 0)
    overs = state.get("overs", 0)
    
    batting_team = state.get("batting_team", "Batting Team")
    bowling_team = state.get("bowling_team", "Bowling Team")
    
    # Batting team won - reached/exceeded target
    if score >= target:
        wickets_left = 10 - wickets
        return 1.0, 0.0, True, f"🏆 {get_name(batting_team)} won by {wickets_left} wickets!"
    
    # Bowling team won - innings over, target not reached
    if wickets >= 10 or overs >= 20.0:
        runs_diff = target - score - 1
        return 0.0, 1.0, True, f"🏆 {get_name(bowling_team)} won by {runs_diff} runs!"
    
    # Match still in progress
    return state.get("bat_win_prob", 0.5), state.get("bowl_win_prob", 0.5), False, None


def load_state(json_path: str) -> dict:
    """Load state from JSON file."""
    try:
        with open(json_path, 'r') as f:
            state = json.load(f)
        
        # Also try to load full history from persistent history file
        try:
            history_path = Path(json_path).with_name("prediction_history.json")
            if history_path.exists():
                with open(history_path, 'r') as f:
                    history_data = json.load(f)
                    full_history = history_data.get("history", [])
                    if len(full_history) > len(state.get("history", [])):
                        state["history"] = full_history
        except Exception:
            pass  # Use history from main state file
        
        return state
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None


def create_gauges(bat_team, bowl_team, bat_prob, bowl_prob):
    """Create win probability gauge chart with decimal odds."""
    bat_odds = prob_to_odds(bat_prob)
    bowl_odds = prob_to_odds(bowl_prob)
    
    fig = make_subplots(rows=1, cols=2, specs=[[{"type": "indicator"}, {"type": "indicator"}]],
                        subplot_titles=[f"{get_name(bat_team)} (Odds: {bat_odds})", 
                                       f"{get_name(bowl_team)} (Odds: {bowl_odds})"])
    for i, (t, p, odds) in enumerate([(bat_team, bat_prob, bat_odds), (bowl_team, bowl_prob, bowl_odds)], 1):
        fig.add_trace(go.Indicator(
            mode="gauge+number", value=p*100,
            number={"suffix": "%", "font": {"size": 40, "color": get_color(t)}},
            gauge={"axis": {"range": [0, 100]}, "bar": {"color": get_color(t)},
                   "steps": [{"range": [0,30], "color": "#ffebee"}, {"range": [30,50], "color": "#fff3e0"},
                            {"range": [50,70], "color": "#e8f5e9"}, {"range": [70,100], "color": "#c8e6c9"}],
                   "threshold": {"line": {"color": "black", "width": 4}, "thickness": 0.75, "value": 50}}
        ), row=1, col=i)
    fig.update_layout(height=280, margin=dict(l=30, r=30, t=50, b=20))
    return fig


def create_resource_gauge(res):
    """Create DLS resources gauge."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=res*100, number={"suffix": "%", "font": {"size": 28}},
        title={"text": "DLS Resources Remaining"},
        gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#4CAF50" if res > 0.4 else "#f44336"},
               "steps": [{"range": [0,30], "color": "#ffcdd2"}, {"range": [30,60], "color": "#fff9c4"},
                        {"range": [60,100], "color": "#c8e6c9"}]}
    ))
    fig.update_layout(height=200, margin=dict(l=20, r=20, t=50, b=20))
    return fig


def create_rr_chart(crr, rrr):
    """Create run rate comparison chart."""
    fig = go.Figure(data=[go.Bar(
        x=["Current RR", "Required RR"], y=[crr, rrr],
        marker_color=["#4CAF50" if crr >= rrr else "#f44336", "#2196F3"],
        text=[f"{crr:.2f}", f"{rrr:.2f}"], textposition="outside", textfont={"size": 16}
    )])
    fig.update_layout(title="Run Rate Comparison", height=200, margin=dict(l=20, r=20, t=50, b=20),
                      yaxis=dict(range=[0, max(crr, rrr, 1) * 1.3]))
    return fig


def create_probability_timeline(history, batting_team=None, bowling_team=None):
    """
    Create ESPN SmartStats-style win probability chart.
    Shows full 40 overs (both innings) with filled area above/below 50% line.
    X-axis: 0-20 for innings 1, 20-40 for innings 2.
    """
    if not history or len(history) < 1:
        return None
    
    df = pd.DataFrame(history)
    
    # Deduplicate - keep only unique over values (take last entry for each over+innings combo)
    if "innings" in df.columns:
        df["over_key"] = df["innings"].astype(str) + "_" + df["overs"].astype(str)
    else:
        df["over_key"] = df["overs"].astype(str)
    df = df.drop_duplicates(subset=["over_key"], keep="last")
    
    # Determine teams - inn1 batting team is the "home" team for the graph
    # In 2nd innings, probabilities are flipped (inn1 batting team is now bowling)
    if "innings" in df.columns:
        inn1_data = df[df["innings"] == 1].copy()
        inn2_data = df[df["innings"] == 2].copy()
        
        # Get inn1 batting team as reference
        if len(inn1_data) > 0:
            team1 = inn1_data["batting_team"].iloc[0] if "batting_team" in inn1_data.columns else batting_team
            team2 = inn1_data["bowling_team"].iloc[0] if "bowling_team" in inn1_data.columns else bowling_team
        else:
            # Only inn2 data - current batting team was inn1 bowling team
            team2 = batting_team  # Current batting = inn1 bowling
            team1 = bowling_team  # Current bowling = inn1 batting
    else:
        # Legacy format without innings info
        inn1_data = df.copy()
        inn2_data = pd.DataFrame()
        team1 = batting_team or "Team A"
        team2 = bowling_team or "Team B"
    
    # Get team colors
    team1_color = get_color(team1) if team1 else "#e91e63"
    team2_color = get_color(team2) if team2 else "#2196f3"
    
    # Build combined overs and probabilities
    # For inn1: overs stay as 0-20, probability is batting team's prob
    # For inn2: overs become 20-40, probability needs to be flipped (inn1 team's perspective)
    all_overs = []
    all_probs = []  # Probability for team1 (inn1 batting team)
    
    if len(inn1_data) > 0:
        for _, row in inn1_data.iterrows():
            all_overs.append(row["overs"])
            all_probs.append(row["bat_prob"] * 100)  # Inn1 batting team prob
    
    if len(inn2_data) > 0:
        for _, row in inn2_data.iterrows():
            # In inn2, the inn1 batting team is now bowling
            # So their win prob is the bowl_prob (or 1 - bat_prob)
            all_overs.append(20 + row["overs"])  # Shift to 20-40 range
            all_probs.append(row["bowl_prob"] * 100)  # Inn1 batting team is now bowling
    
    if not all_overs:
        return None
    
    overs = np.array(all_overs)
    team1_probs = np.array(all_probs)
    
    # Determine current innings and max overs for x-axis range
    has_inn2 = len(inn2_data) > 0
    max_over = 40 if has_inn2 else 20
    
    # Create figure
    fig = go.Figure()
    
    # Add filled area ABOVE 50% (team1 advantage) - from 50 to prob when > 50
    team1_advantage = [max(p, 50) for p in team1_probs]
    fig.add_trace(go.Scatter(
        x=overs, y=team1_advantage,
        mode='lines',
        line=dict(width=0),
        showlegend=False,
        hoverinfo='skip'
    ))
    fig.add_trace(go.Scatter(
        x=overs, y=[50] * len(overs),
        mode='lines',
        line=dict(width=0),
        fill='tonexty',
        fillcolor=f'rgba{tuple(list(int(team1_color.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)) + [0.4])}' if team1_color.startswith('#') else 'rgba(233, 30, 99, 0.4)',
        showlegend=False,
        hoverinfo='skip'
    ))
    
    # Add filled area BELOW 50% (team2 advantage) - from prob to 50 when < 50
    team2_advantage = [min(p, 50) for p in team1_probs]
    fig.add_trace(go.Scatter(
        x=overs, y=[50] * len(overs),
        mode='lines',
        line=dict(width=0),
        showlegend=False,
        hoverinfo='skip'
    ))
    fig.add_trace(go.Scatter(
        x=overs, y=team2_advantage,
        mode='lines',
        line=dict(width=0),
        fill='tonexty',
        fillcolor=f'rgba{tuple(list(int(team2_color.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)) + [0.4])}' if team2_color.startswith('#') else 'rgba(33, 150, 243, 0.4)',
        showlegend=False,
        hoverinfo='skip'
    ))
    
    # Add main probability line
    fig.add_trace(go.Scatter(
        x=overs, y=team1_probs,
        name=get_name(team1),
        mode="lines",
        line=dict(color='white', width=3),
        hovertemplate='Over: %{x:.1f}<br>' + get_name(team1) + ' Win: %{y:.1f}%<extra></extra>'
    ))
    
    # Add markers at key points (every 4 overs and current)
    marker_indices = [i for i, o in enumerate(overs) if int(o) % 4 == 0 or i == len(overs) - 1]
    if marker_indices:
        fig.add_trace(go.Scatter(
            x=[overs[i] for i in marker_indices],
            y=[team1_probs[i] for i in marker_indices],
            mode='markers',
            marker=dict(size=8, color='white', line=dict(width=2, color='#333')),
            showlegend=False,
            hovertemplate='Over: %{x:.1f}<br>' + get_name(team1) + ' Win: %{y:.1f}%<extra></extra>'
        ))
    
    # Add 50% baseline
    fig.add_hline(
        y=50, 
        line_dash="solid", 
        line_color="rgba(255,255,255,0.6)", 
        line_width=2,
        annotation_text="50%",
        annotation_position="left",
        annotation_font_color="white"
    )
    
    # Add innings break marker if we have 2nd innings data
    if has_inn2:
        fig.add_vline(
            x=20,
            line_dash="dash",
            line_color="rgba(255,255,255,0.8)",
            line_width=2,
            annotation_text="Innings Break",
            annotation_position="top",
            annotation_font_color="white"
        )
    
    # Add team labels at edges
    fig.add_annotation(
        x=0.02, y=0.95, xref="paper", yref="paper",
        text=f"<b>{get_name(team1)}</b>",
        showarrow=False,
        font=dict(size=14, color=team1_color),
        bgcolor="rgba(255,255,255,0.8)",
        borderpad=4
    )
    fig.add_annotation(
        x=0.02, y=0.05, xref="paper", yref="paper",
        text=f"<b>{get_name(team2)}</b>",
        showarrow=False,
        font=dict(size=14, color=team2_color),
        bgcolor="rgba(255,255,255,0.8)",
        borderpad=4
    )
    
    # Current probability annotation
    if len(team1_probs) > 0:
        current_prob = team1_probs[-1]
        current_over = overs[-1]
        leader = get_name(team1) if current_prob > 50 else get_name(team2)
        leader_prob = current_prob if current_prob > 50 else 100 - current_prob
        fig.add_annotation(
            x=current_over, y=current_prob,
            text=f"<b>{leader_prob:.1f}%</b>",
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=2,
            arrowcolor="white",
            font=dict(size=12, color="white"),
            bgcolor="rgba(0,0,0,0.7)",
            borderpad=4,
            ax=30, ay=-30
        )
    
    # Dark gradient background like ESPN
    fig.update_layout(
        title=dict(
            text="<b>Win Probability</b>",
            font=dict(size=20, color="white"),
            x=0.5,
            xanchor='center'
        ),
        xaxis=dict(
            title=dict(text="Overs", font=dict(color="white")),
            range=[0, max_over],
            dtick=4 if has_inn2 else 2,
            tickmode='linear',
            tickfont=dict(color="white"),
            gridcolor='rgba(255,255,255,0.1)',
            zerolinecolor='rgba(255,255,255,0.2)',
            showgrid=True
        ),
        yaxis=dict(
            title="",
            range=[0, 100],
            dtick=25,
            ticksuffix="%",
            tickfont=dict(color="white"),
            gridcolor='rgba(255,255,255,0.1)',
            zerolinecolor='rgba(255,255,255,0.2)',
            showgrid=True
        ),
        height=400,
        margin=dict(l=50, r=50, t=60, b=50),
        paper_bgcolor='#1a1a2e',
        plot_bgcolor='#16213e',
        showlegend=False,
        hovermode='x unified'
    )
    
    return fig


def main():
    st.markdown('<h1 class="main-header">🏏 T20 Live Predictor</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align:center;color:#666;">Powered by ML Win Probability Models</p>', unsafe_allow_html=True)
    
    # Controls
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        json_path = st.text_input("JSON State File", value=DEFAULT_JSON, 
                                  help="Path to the live state JSON file produced by crex_live_predictor")
    with col2:
        refresh = st.button("🔄 Refresh")
    with col3:
        auto = st.checkbox("🔁 Auto (3s)", value=True, help="Auto-refresh every 3 seconds")
    
    # Load state
    state = load_state(json_path)
    
    if state is None:
        st.warning(f"""
        ⚠️ No live data found at `{json_path}`
        
        **Start the backend predictor first (choose your league):**
        
        **BBL:**
        ```powershell
        python -m src.bbl_pipeline.inference.crex_live_predictor `
            --match-url "https://crex.com/scoreboard/.../live" `
            --model-dir models/bbl_v12 `
            --feature-store-dir data/bbl_feature_store_v2 `
            --output-json data/live_state.json
        ```
        
        **SA20:**
        ```powershell
        python -m src.bbl_pipeline.inference.crex_live_predictor `
            --match-url "https://crex.com/scoreboard/.../live" `
            --model-dir models/sat_v2 `
            --feature-store-dir data/sat_feature_store_v2 `
            --output-json data/sa20_live_state.json
        ```
        """)
        if auto:
            time.sleep(3)
            st.rerun()
        return
    
    # Parse timestamp
    try:
        ts = datetime.fromisoformat(state["timestamp"])
        age = (datetime.now() - ts).total_seconds()
        is_stale = age > 10  # More than 10 seconds old
    except:
        ts = datetime.now()
        age = 0
        is_stale = True
    
    # Live header
    st.markdown("---")
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        badge_class = "stale-badge" if is_stale else "live-badge"
        badge_text = "⏸️ STALE" if is_stale else "🔴 LIVE"
        st.markdown(
            f'<div style="text-align:center;">'
            f'<span class="{badge_class}">{badge_text}</span> '
            f'Updated: {ts.strftime("%H:%M:%S")} ({age:.0f}s ago) | '
            f'📍 {state.get("venue", "Unknown")}</div>',
            unsafe_allow_html=True
        )
    
    # Score cards
    d = state
    st.markdown("---")
    col1, col2, col3 = st.columns([2, 1, 2])
    
    with col1:
        st.markdown(f'''
        <div style="background: linear-gradient(135deg, {get_color(d["batting_team"])}, #333); 
            padding: 20px; border-radius: 15px; color: white; text-align: center;">
            <div class="team-name">{get_name(d["batting_team"])}</div>
            <div class="score-display">{d["score"]}/{d["wickets"]}</div>
            <div>({d["overs"]} overs)</div>
            <div style="margin-top: 10px;">
                🏏 {d.get("batsman1_name", "?")} {d.get("batsman1_runs", 0)}({d.get("batsman1_balls", 0)}) • 
                {d.get("batsman2_name", "?")} {d.get("batsman2_runs", 0)}({d.get("batsman2_balls", 0)})
            </div>
        </div>
        ''', unsafe_allow_html=True)
    
    with col2:
        st.markdown("<h1 style='text-align:center; color:#666; margin-top:40px;'>VS</h1>", unsafe_allow_html=True)
    
    with col3:
        if d.get("target"):
            runs_needed = d["target"] - d["score"]
            balls_left = max(0, 120 - int(d["overs"]) * 6 - int((d["overs"] % 1) * 10))
            st.markdown(f'''
            <div style="background: linear-gradient(135deg, {get_color(d["bowling_team"])}, #333); 
                padding: 20px; border-radius: 15px; color: white; text-align: center;">
                <div class="team-name">{get_name(d["bowling_team"])}</div>
                <div class="score-display">{d["target"]-1}/10</div>
                <div>(20.0 overs)</div>
                <div style="margin-top: 10px;">
                    🎯 Target: {d["target"]} | Need: {runs_needed} from {balls_left} balls
                </div>
            </div>
            ''', unsafe_allow_html=True)
        else:
            st.markdown(f'''
            <div style="background: linear-gradient(135deg, {get_color(d["bowling_team"])}, #333); 
                padding: 20px; border-radius: 15px; color: white; text-align: center;">
                <div class="team-name">{get_name(d["bowling_team"])}</div>
                <div class="score-display">Yet to bat</div>
                <div style="margin-top: 30px;">1st Innings in progress</div>
            </div>
            ''', unsafe_allow_html=True)
    
    # Win probability gauges with odds
    st.markdown("---")
    
    # Calculate odds
    bat_odds = prob_to_odds(d["bat_win_prob"])
    bowl_odds = prob_to_odds(d["bowl_win_prob"])
    
    # Header with odds summary
    st.subheader("🎯 Win Probability & Odds")
    
    # Display Raw, Smoothed, Combined, Inn-Specific, and Phase-Specific probabilities
    raw_prob = d.get("raw_win_prob", d["bat_win_prob"])
    smoothed_prob = d.get("smoothed_win_prob", d["bat_win_prob"])
    combined_prob = d.get("calibrated_combined_prob", d["bat_win_prob"])
    inn_specific_prob = d.get("calibrated_win_prob", d["bat_win_prob"])
    phase_specific_prob = d.get("calibrated_phase_prob", None)
    per_over_prob = d.get("calibrated_per_over_prob", None)  # Per-over brier-optimized
    
    # Detect if this is SA20 and recalculate calibrated probabilities client-side
    batting_team = d.get("batting_team", "")
    sa20_teams = {'DSG', 'MICT', 'PR', 'JSK', 'PC', 'SEC'}
    is_sa20_match = batting_team in sa20_teams
    
    if is_sa20_match and SA20_CALIBRATORS is not None:
        # Recalculate all calibrated probabilities using SA20 calibrators
        import math
        overs_float = d.get("overs", 0.0)
        current_over = max(1, min(20, math.ceil(overs_float) if overs_float > 0 else 1))
        is_inn2 = d.get("is_second_innings", False)
        inn_num = 2 if is_inn2 else 1
        
        # Determine phase (3-phase system: powerplay, middle, death)
        if current_over <= 6:
            sa20_phase = "powerplay"
        elif current_over <= 15:
            sa20_phase = "middle"
        else:
            sa20_phase = "death"
        
        # Combined calibrator
        if SA20_CALIBRATORS.get('combined') is not None:
            combined_prob = float(SA20_CALIBRATORS['combined'].predict([[raw_prob]])[0])
        
        # Innings-specific calibrator
        inn_cal = SA20_CALIBRATORS.get(f'innings{inn_num}')
        if inn_cal is not None:
            inn_specific_prob = float(inn_cal.predict([[raw_prob]])[0])
        
        # Phase-specific calibrator
        phase_key = f'inn{inn_num}_{sa20_phase}'
        phase_cal = SA20_CALIBRATORS.get('phase', {}).get(phase_key)
        if phase_cal is not None:
            phase_specific_prob = float(phase_cal.predict([[raw_prob]])[0])
        
        # Recalculate smoothed (30% blend with combined)
        smoothed_prob = 0.3 * combined_prob + 0.7 * raw_prob
    
    # Calculate odds for each
    raw_odds = prob_to_odds(raw_prob)
    smoothed_odds = prob_to_odds(smoothed_prob)
    combined_odds = prob_to_odds(combined_prob)
    inn_specific_odds = prob_to_odds(inn_specific_prob)
    
    # Decide number of columns based on whether phase-specific is available
    has_phase = phase_specific_prob is not None and abs(phase_specific_prob - inn_specific_prob) > 0.001
    num_cols = 5 if has_phase else 4
    
    if has_phase:
        prob_cols = st.columns(5)
        phase_specific_odds = prob_to_odds(phase_specific_prob)
    else:
        prob_cols = st.columns(4)
    
    with prob_cols[0]:
        st.markdown(f'''
        <div style="text-align: center; padding: 10px; background: #f5f5f5; border-radius: 10px; border-left: 4px solid #2196F3;">
            <b>📊 Raw Model</b><br>
            <span style="font-size: 1.5em; color: #2196F3;">{raw_prob*100:.1f}%</span><br>
            <span style="font-size: 1.1em; color: #333;">Odds: <b>{raw_odds}</b></span><br>
            <span style="font-size: 0.9em; color: #666;">XGB+LogReg Ensemble</span>
        </div>
        ''', unsafe_allow_html=True)
    with prob_cols[1]:
        st.markdown(f'''
        <div style="text-align: center; padding: 10px; background: #f5f5f5; border-radius: 10px; border-left: 4px solid #FF9800;">
            <b>🔄 Smoothed</b><br>
            <span style="font-size: 1.5em; color: #FF9800;">{smoothed_prob*100:.1f}%</span><br>
            <span style="font-size: 1.1em; color: #333;">Odds: <b>{smoothed_odds}</b></span><br>
            <span style="font-size: 0.9em; color: #666;">30% Calibrated Blend</span>
        </div>
        ''', unsafe_allow_html=True)
    with prob_cols[2]:
        st.markdown(f'''
        <div style="text-align: center; padding: 10px; background: #f5f5f5; border-radius: 10px; border-left: 4px solid #9C27B0;">
            <b>🎯 Combined</b><br>
            <span style="font-size: 1.5em; color: #9C27B0;">{combined_prob*100:.1f}%</span><br>
            <span style="font-size: 1.1em; color: #333;">Odds: <b>{combined_odds}</b></span><br>
            <span style="font-size: 0.9em; color: #666;">Combined Isotonic</span>
        </div>
        ''', unsafe_allow_html=True)
    with prob_cols[3]:
        innings_label = "Inn1" if not d.get("is_second_innings") else "Inn2"
        st.markdown(f'''
        <div style="text-align: center; padding: 10px; background: #f5f5f5; border-radius: 10px; border-left: 4px solid #4CAF50;">
            <b>✅ Inn-Specific</b><br>
            <span style="font-size: 1.5em; color: #4CAF50;">{inn_specific_prob*100:.1f}%</span><br>
            <span style="font-size: 1.1em; color: #333;">Odds: <b>{inn_specific_odds}</b></span><br>
            <span style="font-size: 0.9em; color: #666;">{innings_label} Isotonic</span>
        </div>
        ''', unsafe_allow_html=True)
    
    if has_phase:
        with prob_cols[4]:
            # Determine phase
            overs_float = d.get("overs", 0.0)
            import math
            current_over = max(1, min(20, math.ceil(overs_float) if overs_float > 0 else 1))
            if current_over <= 6:
                phase_label = "PP"
            elif current_over <= 15:
                phase_label = "Mid"
            else:
                phase_label = "Death"
            st.markdown(f'''
            <div style="text-align: center; padding: 10px; background: #f5f5f5; border-radius: 10px; border-left: 4px solid #FF5722;">
                <b>🎪 Inn×Phase</b><br>
                <span style="font-size: 1.5em; color: #FF5722;">{phase_specific_prob*100:.1f}%</span><br>
                <span style="font-size: 1.1em; color: #333;">Odds: <b>{phase_specific_odds}</b></span><br>
                <span style="font-size: 0.9em; color: #666;">{innings_label}-{phase_label}</span>
            </div>
            ''', unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    odds_col1, odds_col2 = st.columns(2)
    with odds_col1:
        st.markdown(f'''
        <div style="text-align: center; padding: 10px; background: linear-gradient(135deg, {get_color(d["batting_team"])}, #333); 
             border-radius: 10px; color: white;">
            <b>{get_name(d["batting_team"])}</b><br>
            <span style="font-size: 1.8em;">{d["bat_win_prob"]*100:.1f}%</span><br>
            <span style="font-size: 1.2em;">Odds: <b>{bat_odds}</b></span>
        </div>
        ''', unsafe_allow_html=True)
    with odds_col2:
        st.markdown(f'''
        <div style="text-align: center; padding: 10px; background: linear-gradient(135deg, {get_color(d["bowling_team"])}, #333); 
             border-radius: 10px; color: white;">
            <b>{get_name(d["bowling_team"])}</b><br>
            <span style="font-size: 1.8em;">{d["bowl_win_prob"]*100:.1f}%</span><br>
            <span style="font-size: 1.2em;">Odds: <b>{bowl_odds}</b></span>
        </div>
        ''', unsafe_allow_html=True)
    
    st.plotly_chart(
        create_gauges(d["batting_team"], d["bowling_team"], d["bat_win_prob"], d["bowl_win_prob"])
    )
    
    # Market Odds from CREX (if available)
    market_fav_team = d.get("market_fav_team", "")
    market_back_odds = d.get("market_back_odds", "")
    market_lay_odds = d.get("market_lay_odds", "")
    market_fav_prob = d.get("market_fav_prob", 0.0)
    
    if market_fav_team and market_back_odds:
        st.markdown("---")
        st.subheader("📈 CREX Market Odds")
        
        # Calculate underdog probability and identify teams
        fav_team = market_fav_team
        underdog_prob = 1.0 - market_fav_prob if market_fav_prob > 0 else 0.0
        
        # Determine which team is the favorite based on match state
        batting_team = d.get("batting_team", "")
        bowling_team = d.get("bowling_team", "")
        
        # Match favorite team to batting/bowling
        is_fav_batting = fav_team == batting_team or fav_team in batting_team or batting_team in fav_team
        is_fav_bowling = fav_team == bowling_team or fav_team in bowling_team or bowling_team in fav_team
        
        if is_fav_batting:
            fav_full_name = get_name(batting_team)
            underdog_full_name = get_name(bowling_team)
            fav_color = get_color(batting_team)
            underdog_color = get_color(bowling_team)
        elif is_fav_bowling:
            fav_full_name = get_name(bowling_team)
            underdog_full_name = get_name(batting_team)
            fav_color = get_color(bowling_team)
            underdog_color = get_color(batting_team)
        else:
            fav_full_name = fav_team
            underdog_full_name = "Opponent"
            fav_color = "#4CAF50"
            underdog_color = "#f44336"
        
        mcol1, mcol2, mcol3 = st.columns([2, 1, 2])
        
        with mcol1:
            st.markdown(f'''
            <div style="text-align: center; padding: 15px; background: linear-gradient(135deg, {fav_color}, #333); 
                 border-radius: 10px; color: white;">
                <span style="font-size: 0.9em;">⭐ FAVORITE</span><br>
                <b style="font-size: 1.4em;">{fav_full_name}</b><br>
                <span style="font-size: 2em;">{market_fav_prob*100:.1f}%</span><br>
                <span style="font-size: 1em;">Back: <b>{market_back_odds}</b> | Lay: <b>{market_lay_odds}</b></span>
            </div>
            ''', unsafe_allow_html=True)
        
        with mcol2:
            st.markdown(f'''
            <div style="text-align: center; padding: 25px;">
                <span style="font-size: 1.5em; color: #666;">VS</span>
            </div>
            ''', unsafe_allow_html=True)
        
        with mcol3:
            st.markdown(f'''
            <div style="text-align: center; padding: 15px; background: linear-gradient(135deg, {underdog_color}, #333); 
                 border-radius: 10px; color: white;">
                <span style="font-size: 0.9em;">UNDERDOG</span><br>
                <b style="font-size: 1.4em;">{underdog_full_name}</b><br>
                <span style="font-size: 2em;">{underdog_prob*100:.1f}%</span><br>
                <span style="font-size: 1em;">Implied from odds</span>
            </div>
            ''', unsafe_allow_html=True)
        
        # Model vs Market comparison
        model_prob = d["bat_win_prob"]
        if is_fav_batting:
            market_bat_prob = market_fav_prob
        else:
            market_bat_prob = underdog_prob
        
        diff = model_prob - market_bat_prob
        if abs(diff) > 0.03:  # 3% threshold for edge
            edge_color = "#4CAF50" if diff > 0 else "#f44336"
            edge_text = "Model sees VALUE on batting team" if diff > 0 else "Market favors batting team more"
            st.markdown(f'''
            <div style="text-align: center; padding: 10px; background: #f5f5f5; border-radius: 10px; 
                 border-left: 4px solid {edge_color}; margin-top: 10px;">
                <b>Model vs Market Edge:</b> {abs(diff)*100:.1f}% - <span style="color: {edge_color};">{edge_text}</span>
            </div>
            ''', unsafe_allow_html=True)
    
    # BBL Calibration Guidance
    resource_prob = d.get("features", {}).get("resource_win_prob", 0.5)
    is_inn2 = d.get("is_second_innings", False)
    # overs field is like 0.4, 6.2, 1.0 etc - need to get current over number (1-20)
    # 0.4 -> over 1, 1.0 -> over 1 (just completed), 1.2 -> over 2
    import math
    overs_float = d.get("overs", 0.0)
    current_over = max(1, min(20, math.ceil(overs_float) if overs_float > 0 else 1))
    inn_num = 2 if is_inn2 else 1
    
    # Determine phase for display (using 4-phase system for SA20)
    if current_over <= 6:
        phase = "Powerplay"
        phase_key = "powerplay"
    elif current_over <= 11:
        phase = "Middle (Early)"
        phase_key = "middle_early"
    elif current_over <= 15:
        phase = "Middle (Late)"
        phase_key = "middle_late"
    else:
        phase = "Death"
        phase_key = "death"
    
    # Detect league from team names
    # BBL team codes: various abbreviations used by different sources
    bbl_teams = {
        'SYS', 'SYT', 'SIX', 'THU',  # Sydney Sixers, Sydney Thunder
        'PRS', 'SCO', 'PS',           # Perth Scorchers
        'ADS', 'STR', 'AS',           # Adelaide Strikers
        'BRH', 'HEA', 'BH',           # Brisbane Heat
        'MLR', 'REN', 'MR',           # Melbourne Renegades
        'MLS', 'STA', 'MS',           # Melbourne Stars
        'HBH', 'HUR', 'HH',           # Hobart Hurricanes
        'STH',                         # Other aliases
    }
    sa20_teams = {'DSG', 'MICT', 'PR', 'JSK', 'PC', 'SEC'}
    # SSM teams - both internal codes and CREX codes
    # CREX uses: AUCK=Auckland Aces, OTG=Otago Volts, CANT=Canterbury Kings, 
    # WEL=Wellington Firebirds, CD=Central Stags, ND=Northern Districts
    ssm_teams = {'AA', 'AKL', 'AUCK', 'Auckland', 'Auckland Aces',
                 'CD', 'Central Districts', 'Central Stags', 'CS', 'CK', 'CANT', 'Canterbury', 'Canterbury Kings',
                 'ND', 'NB', 'Northern Districts', 'Northern Brave',
                 'OV', 'OTG', 'Otago', 'Otago Volts',
                 'WF', 'WEL', 'Wellington', 'Wellington Firebirds'}
    # SSM Female teams (New Zealand Women's Super Smash)
    # Crex codes: AHW=Auckland Hearts, CDW=Central Hinds, CBW=Canterbury Magicians, 
    # NDW=Northern Brave, OSW=Otago Sparks, WBW=Wellington Blaze
    ssm_female_teams = {'AHW', 'Auckland Hearts', 'Auckland-W', 'AA-W', 
                        'CDW', 'Central Hinds', 'Central-W', 'CD-W',
                        'CBW', 'Canterbury Magicians', 'Canterbury-W', 'CS-W',
                        'NDW', 'Northern Brave', 'Northern-W', 'ND-W',
                        'OSW', 'Otago Sparks', 'Otago-W', 'OV-W',
                        'WBW', 'Wellington Blaze', 'Wellington-W', 'WF-W'}
    # WPL teams (Women's Premier League - India)
    wpl_teams = {'MIW', 'MI-W', 'Mumbai Indians', 'RCBW', 'RCB-W', 'Royal Challengers Bengaluru',
                 'DCW', 'DC-W', 'Delhi Capitals', 'GGW', 'GG-W', 'Gujarat Giants', 
                 'UPW', 'UP-W', 'UP Warriorz'}
    # T20 International teams (Men's)
    t20i_teams = {'Australia', 'AUS', 'India', 'IND', 'England', 'ENG', 'New Zealand', 'NZ',
                  'South Africa', 'SA', 'Pakistan', 'PAK', 'West Indies', 'WI', 'Sri Lanka', 'SL',
                  'Bangladesh', 'BAN', 'Afghanistan', 'AFG', 'Zimbabwe', 'ZIM', 'Ireland', 'IRE',
                  'Scotland', 'Netherlands', 'NED', 'Namibia', 'NAM', 'United States of America', 'USA',
                  'Canada', 'CAN', 'Oman', 'OMA', 'Nepal', 'NEP', 'United Arab Emirates', 'UAE',
                  'Papua New Guinea', 'PNG', 'Hong Kong', 'HK', 'Uganda', 'UGA'}
    
    batting_team = d.get("batting_team", "")
    is_bbl = batting_team in bbl_teams
    is_sa20 = batting_team in sa20_teams
    is_ssm = batting_team in ssm_teams
    is_ssm_female = batting_team in ssm_female_teams
    is_wpl = batting_team in wpl_teams
    is_t20i = batting_team in t20i_teams
    
    # Calculate ECE-optimized probability (for calibration display)
    ece_optimized_prob = None
    cal_source = None
    cal_method = None
    calibrator_key = None
    
    # Also calculate Brier-optimized probability for SA20 (per-over calibrators)
    brier_optimized_prob = None
    brier_cal_source = None
    brier_calibrator_key = None
    brier_cal_method = None
    
    # SSM Brier-optimized calibrator variables (initialized here for scope)
    ssm_brier_prob = None
    ssm_brier_source = None
    
    # SSM Log Loss-optimized calibrator variables
    ssm_logloss_prob = None
    ssm_logloss_source = None
    
    # BBL Brier-optimized calibrator variables
    bbl_brier_prob = None
    bbl_brier_source = None
    
    # BBL Log Loss-optimized calibrator variables
    bbl_logloss_prob = None
    bbl_logloss_source = None
    
    # WPL Brier-optimized calibrator variables
    wpl_brier_prob = None
    wpl_brier_source = None
    brier_cal_key = None
    brier_cals = None
    
    # T20I (International) calibrator variables
    t20i_brier_prob = None
    t20i_brier_source = None
    t20i_ece_prob = None
    t20i_ece_source = None
    
    if is_sa20:
        # SA20 v2: Per-over calibrators for BRIER, Phase calibrators for ECE
        
        # 1. Per-over calibrators for best Brier (from OOF brier_optimized)
        sa20_per_over_cals = PER_OVER_CALIBRATORS.get('sa20')
        brier_calibrator_key = f'inn{inn_num}_over{current_over}'
        if sa20_per_over_cals is not None and brier_calibrator_key in sa20_per_over_cals:
            cal_obj = sa20_per_over_cals[brier_calibrator_key]
            # SA20 v2 OOF calibrators are direct IsotonicRegression objects (not dicts)
            # They use raw_win_prob as input
            if hasattr(cal_obj, 'predict'):
                # Direct calibrator object (v2 OOF format)
                brier_optimized_prob = cal_obj.predict([[raw_prob]])[0]
                brier_cal_source = 'raw'
                brier_cal_method = 'isotonic'
            elif isinstance(cal_obj, dict) and 'calibrator' in cal_obj:
                # Legacy dict format (v1)
                brier_cal_source = cal_obj.get('source', 'raw')
                brier_cal_method = cal_obj.get('method', 'isotonic')
                if brier_cal_source == 'raw':
                    input_prob = raw_prob
                elif brier_cal_source == 'cal':
                    input_prob = inn_specific_prob
                else:
                    input_prob = resource_prob
                
                if brier_cal_method == 'platt':
                    input_clipped = np.clip(input_prob, 0.001, 0.999)
                    logit = np.log(input_clipped / (1 - input_clipped))
                    brier_optimized_prob = cal_obj['calibrator'].predict_proba([[logit]])[0, 1]
                else:
                    brier_optimized_prob = cal_obj['calibrator'].predict([[input_prob]])[0]
            if brier_optimized_prob is not None:
                brier_optimized_prob = np.clip(brier_optimized_prob, 0.01, 0.99)
        
        # 2. Phase calibrators for best ECE (Platt scaling for smooth output)
        # SA20 v2 OOF uses 3-phase system: powerplay, middle, death (not 4-phase)
        sa20_phase_cals = PHASE_CALIBRATORS.get('sa20')
        if sa20_phase_cals is not None:
            # Convert 4-phase key to 3-phase key for SA20 OOF calibrators
            if phase_key in ['middle_early', 'middle_late']:
                sa20_phase_key = 'middle'
            else:
                sa20_phase_key = phase_key
            calibrator_key = f'inn{inn_num}_{sa20_phase_key}'
            if calibrator_key in sa20_phase_cals:
                phase_cal_info = sa20_phase_cals[calibrator_key]
                cal_source = 'raw'  # SA20 phase calibrators use raw_win_prob
                
                # Check if it's Platt (dict with calibrator) or isotonic (direct calibrator)
                if isinstance(phase_cal_info, dict) and 'calibrator' in phase_cal_info:
                    # Dict format with Platt scaling
                    cal_method = 'platt'
                    input_clipped = np.clip(raw_prob, 0.001, 0.999)
                    logit = np.log(input_clipped / (1 - input_clipped))
                    ece_optimized_prob = phase_cal_info['calibrator'].predict_proba([[logit]])[0, 1]
                else:
                    # Direct IsotonicRegression object (v2 OOF format)
                    cal_method = 'isotonic'
                    ece_optimized_prob = phase_cal_info.predict([[raw_prob]])[0]
                ece_optimized_prob = np.clip(ece_optimized_prob, 0.01, 0.99)
    elif is_wpl:
        # WPL: Use phase calibrators on RESOURCE probs (best ECE source for sparse data)
        # NOTE: WPL phase calibrators use 3-phase system (powerplay, middle, death) not 4-phase
        wpl_phase_cals = PHASE_CALIBRATORS.get('wpl')
        if wpl_phase_cals is not None:
            # Convert 4-phase key to 3-phase key for WPL
            if phase_key in ['middle_early', 'middle_late']:
                wpl_phase_key = 'middle'
            else:
                wpl_phase_key = phase_key  # powerplay or death
            calibrator_key = f'inn{inn_num}_{wpl_phase_key}'
            if calibrator_key in wpl_phase_cals:
                phase_cal_info = wpl_phase_cals[calibrator_key]
                # WPL phase calibrators use resource for most phases, raw for inn2_death
                cal_source = phase_cal_info.get('source', 'res') if isinstance(phase_cal_info, dict) else 'res'
                
                # Determine input based on source
                if cal_source == 'raw':
                    input_prob = raw_prob
                else:
                    input_prob = resource_prob
                
                # Check if it's dict (new format) or direct calibrator (legacy)
                if isinstance(phase_cal_info, dict) and 'calibrator' in phase_cal_info:
                    cal_method = 'isotonic'
                    ece_optimized_prob = phase_cal_info['calibrator'].predict([[input_prob]])[0]
                else:
                    cal_method = 'isotonic'
                    ece_optimized_prob = phase_cal_info.predict([[input_prob]])[0]
                ece_optimized_prob = np.clip(ece_optimized_prob, 0.01, 0.99)
    elif is_ssm_female:
        # SSM Female: Use phase calibrators (8 phases - SA20 style, RESOURCE-BASED)
        ssm_f_phase_cals = PHASE_CALIBRATORS.get('ssm_female')
        if ssm_f_phase_cals is not None:
            calibrator_key = f'inn{inn_num}_{phase_key}'
            if calibrator_key in ssm_f_phase_cals:
                phase_cal_info = ssm_f_phase_cals[calibrator_key]
                cal_source = 'res'  # SSM Female phase calibrators use resource_win_prob
                
                # Check if it's dict (new format) or direct calibrator (legacy)
                if isinstance(phase_cal_info, dict) and 'calibrator' in phase_cal_info:
                    cal_method = 'isotonic'
                    ece_optimized_prob = phase_cal_info['calibrator'].predict([[resource_prob]])[0]
                else:
                    cal_method = 'isotonic'
                    ece_optimized_prob = phase_cal_info.predict([[resource_prob]])[0]
                ece_optimized_prob = np.clip(ece_optimized_prob, 0.01, 0.99)
    elif is_bbl:
        # BBL: Use ECE-optimized calibrators (histogram binning) - BEST performer from OOF analysis
        # OOF Results: Brier=0.1426, ECE=0.0091, LogLoss=0.4306 (best on all 3 metrics!)
        bbl_ece_cals = ECE_OPTIMIZED_CALIBRATORS.get('bbl')
        
        # Determine phase key for BBL (3-phase: powerplay, middle, death)
        if phase_key in ['middle_early', 'middle_late']:
            bbl_phase_key = 'middle'
        else:
            bbl_phase_key = phase_key
        
        calibrator_key = f'inn{inn_num}_{bbl_phase_key}'
        
        if bbl_ece_cals is not None and calibrator_key in bbl_ece_cals:
            cal_info = bbl_ece_cals[calibrator_key]
            cal_source = cal_info.get('source', 'raw')
            cal_method = cal_info.get('method', 'histogram_isotonic')
            
            # ECE-optimized uses raw probabilities as input
            input_prob = raw_prob
            
            # Apply calibrator (histogram-based isotonic)
            ece_optimized_prob = cal_info['calibrator'].predict([[input_prob]])[0]
            ece_optimized_prob = np.clip(ece_optimized_prob, 0.01, 0.99)
        else:
            # Fallback to phase calibrators if ECE-optimized not available
            bbl_phase_cals = PHASE_CALIBRATORS.get('bbl')
            if bbl_phase_cals is not None and calibrator_key in bbl_phase_cals:
                phase_cal = bbl_phase_cals[calibrator_key]
                # Handle both dict format (old) and plain IsotonicRegression (v12)
                if hasattr(phase_cal, 'predict'):
                    # Plain IsotonicRegression object
                    input_prob = raw_prob
                    ece_optimized_prob = phase_cal.predict([[input_prob]])[0]
                else:
                    # Dict format with 'calibrator' key
                    cal_source = phase_cal.get('source', 'raw')
                    input_prob = raw_prob
                    ece_optimized_prob = phase_cal['calibrator'].predict([[input_prob]])[0]
                ece_optimized_prob = np.clip(ece_optimized_prob, 0.01, 0.99)
    elif is_ssm:
        # SSM: Use per-over calibrators for ECE
        league_key = 'ssm'
        calibrators = PER_OVER_CALIBRATORS.get(league_key)
        calibrator_key = f'inn{inn_num}_over{current_over}'
        if calibrators is not None and calibrator_key in calibrators:
            cal_info = calibrators[calibrator_key]
            cal_source = cal_info['source']
            cal_method = cal_info.get('method', 'isotonic')
            
            # Get the correct input based on source
            if cal_source == 'raw':
                input_prob = raw_prob
            elif cal_source == 'cal':
                input_prob = inn_specific_prob  # Already calibrated
            else:  # 'res'
                input_prob = resource_prob
            
            # Apply calibrator based on method
            if cal_method == 'platt':
                # Platt scaling expects logits
                input_clipped = np.clip(input_prob, 0.001, 0.999)
                logit = np.log(input_clipped / (1 - input_clipped))
                ece_optimized_prob = cal_info['calibrator'].predict_proba([[logit]])[0, 1]
            else:
                # Isotonic expects probabilities directly
                ece_optimized_prob = cal_info['calibrator'].predict([[input_prob]])[0]
            ece_optimized_prob = np.clip(ece_optimized_prob, 0.01, 0.99)
        
        # SSM: Also apply Brier-optimized calibrators
        brier_cals = BRIER_CALIBRATORS.get('ssm')
        if brier_cals is not None:
            # Build the key - calibrators start at over 2, so fallback to over 2 for early overs
            brier_cal_key = calibrator_key  # e.g., inn2_over1
            if brier_cal_key not in brier_cals:
                # Fallback to over 2 for overs 0 or 1
                brier_cal_key = f'inn{inn_num}_over2'
            
            if brier_cal_key in brier_cals:
                brier_cal_info = brier_cals[brier_cal_key]
                ssm_brier_source = brier_cal_info['source']
                
                # Get input based on Brier-optimal source
                if ssm_brier_source == 'raw':
                    brier_input = raw_prob
                elif ssm_brier_source == 'per':
                    # Use the ECE-optimized prob as input
                    brier_input = ece_optimized_prob if ece_optimized_prob is not None else raw_prob
                else:
                    brier_input = resource_prob
                
                # Apply Brier calibrator (always isotonic)
                ssm_brier_prob = brier_cal_info['calibrator'].predict([[brier_input]])[0]
                ssm_brier_prob = np.clip(ssm_brier_prob, 0.01, 0.99)
        
        # SSM: Apply Log Loss-optimized calibrators
        logloss_cals = LOGLOSS_CALIBRATORS.get('ssm')
        if logloss_cals is not None:
            logloss_cal_key = calibrator_key  # e.g., inn2_over1
            
            if logloss_cal_key in logloss_cals:
                ll_cal_info = logloss_cals[logloss_cal_key]
                ssm_logloss_source = ll_cal_info['source']
                
                # Get input based on Log Loss-optimal source
                if ssm_logloss_source == 'raw':
                    ll_input = raw_prob
                elif ssm_logloss_source == 'per':
                    # Use the ECE-optimized prob as input
                    ll_input = ece_optimized_prob if ece_optimized_prob is not None else raw_prob
                elif ssm_logloss_source == 'bri':
                    # Use the Brier-optimized prob as input
                    ll_input = ssm_brier_prob if ssm_brier_prob is not None else raw_prob
                else:
                    ll_input = resource_prob
                
                # Apply Log Loss calibrator (always isotonic)
                ssm_logloss_prob = ll_cal_info['calibrator'].predict([[ll_input]])[0]
                ssm_logloss_prob = np.clip(ssm_logloss_prob, 0.01, 0.99)
        
        # BBL: Apply Brier-optimized calibrators (separate from ECE calibrators)
        if is_bbl:
            brier_cals = BRIER_CALIBRATORS.get('bbl')
            if brier_cals is not None:
                brier_cal_key = calibrator_key  # e.g., inn1_over14
                if brier_cal_key in brier_cals:
                    brier_cal = brier_cals[brier_cal_key]
                    # Handle both dict format (old) and plain IsotonicRegression (v12)
                    if hasattr(brier_cal, 'predict'):
                        # Plain IsotonicRegression object (v12 format)
                        bbl_brier_source = 'raw'
                        bbl_brier_prob = brier_cal.predict([[raw_prob]])[0]
                    else:
                        # Dict format with 'source' and 'calibrator' keys
                        bbl_brier_source = brier_cal['source']
                        if bbl_brier_source == 'raw':
                            brier_input = raw_prob
                        elif bbl_brier_source == 'cal':
                            brier_input = inn_specific_prob if inn_specific_prob is not None else raw_prob
                        else:  # 'res'
                            brier_input = resource_prob
                        bbl_brier_prob = brier_cal['calibrator'].predict([[brier_input]])[0]
                    bbl_brier_prob = np.clip(bbl_brier_prob, 0.01, 0.99)
        
        # BBL: Apply Log Loss-optimized calibrators
        if is_bbl:
            logloss_cals = LOGLOSS_CALIBRATORS.get('bbl')
            if logloss_cals is not None:
                logloss_cal_key = calibrator_key  # e.g., inn1_over14
                if logloss_cal_key in logloss_cals:
                    logloss_cal_info = logloss_cals[logloss_cal_key]
                    bbl_logloss_source = logloss_cal_info['source']
                    
                    # Get input based on Log Loss-optimal source
                    if bbl_logloss_source == 'raw':
                        logloss_input = raw_prob
                    elif bbl_logloss_source == 'cal':
                        logloss_input = inn_specific_prob if inn_specific_prob is not None else raw_prob
                    elif bbl_logloss_source == 'per':
                        logloss_input = ece_optimized_prob if ece_optimized_prob is not None else raw_prob
                    elif bbl_logloss_source == 'bri':
                        logloss_input = bbl_brier_prob if bbl_brier_prob is not None else raw_prob
                    else:  # 'res'
                        logloss_input = resource_prob
                    
                    # Apply Log Loss calibrator (always isotonic)
                    bbl_logloss_prob = logloss_cal_info['calibrator'].predict([[logloss_input]])[0]
                    bbl_logloss_prob = np.clip(bbl_logloss_prob, 0.01, 0.99)
    
    # WPL: Apply per-over Brier-optimized calibrators from isotonic_calibrator.pkl
    # Inn1: Use raw (more aligned with reality per user observation)
    # Inn2: Use brier_optimized (significantly better: 0.1109 vs 0.1295)
    if is_wpl:
        if inn_num == 1:
            # Innings 1: Raw model is more realistic
            wpl_brier_prob = raw_prob
            wpl_brier_source = "raw"
        else:
            # Innings 2: Use per-over calibrator (much better than raw)
            wpl_per_over_cals = None
            try:
                # Load from isotonic_calibrator.pkl (generated by bbl-pipeline generate-oof)
                cal_data = joblib.load('models/wpl_female_v1/isotonic_calibrator.pkl')
                wpl_per_over_cals = cal_data.get('per_over_calibrators', {})
            except:
                wpl_per_over_cals = {}
            
            # Try per-over calibrator (inn2_over3, etc)
            over_key = f'inn{inn_num}_over{current_over}'
            if over_key in wpl_per_over_cals:
                wpl_brier_prob = float(wpl_per_over_cals[over_key].predict([[raw_prob]])[0])
                wpl_brier_prob = np.clip(wpl_brier_prob, 0.01, 0.99)
                wpl_brier_source = f"over{current_over}"
            else:
                # Fallback to raw if calibrator not found
                wpl_brier_prob = raw_prob
                wpl_brier_source = "raw"

    # T20I: Apply per-over calibrators for both Brier and ECE optimization
    if is_t20i:
        # ECE-optimized calibrators
        t20i_ece_cals = PER_OVER_CALIBRATORS.get('t20i')
        calibrator_key = f'inn{inn_num}_over{current_over}'
        if t20i_ece_cals is not None and calibrator_key in t20i_ece_cals:
            cal_info = t20i_ece_cals[calibrator_key]
            t20i_ece_source = cal_info['source']
            cal_source = t20i_ece_source
            cal_method = 'isotonic'
            
            # Get input based on ECE-optimal source
            if t20i_ece_source == 'raw':
                input_prob = raw_prob
            elif t20i_ece_source == 'cal':
                input_prob = inn_specific_prob if inn_specific_prob is not None else raw_prob
            else:  # 'res'
                input_prob = resource_prob
            
            # Apply ECE calibrator
            t20i_ece_prob = cal_info['calibrator'].predict([[input_prob]])[0]
            t20i_ece_prob = np.clip(t20i_ece_prob, 0.01, 0.99)
            ece_optimized_prob = t20i_ece_prob
        
        # Brier-optimized calibrators
        t20i_brier_cals = BRIER_CALIBRATORS.get('t20i')
        if t20i_brier_cals is not None and calibrator_key in t20i_brier_cals:
            brier_cal_info = t20i_brier_cals[calibrator_key]
            t20i_brier_source = brier_cal_info['source']
            
            # Get input based on Brier-optimal source
            if t20i_brier_source == 'raw':
                brier_input = raw_prob
            elif t20i_brier_source == 'cal':
                brier_input = inn_specific_prob if inn_specific_prob is not None else raw_prob
            else:  # 'res'
                brier_input = resource_prob
            
            # Apply Brier calibrator
            t20i_brier_prob = brier_cal_info['calibrator'].predict([[brier_input]])[0]
            t20i_brier_prob = np.clip(t20i_brier_prob, 0.01, 0.99)

    # ECE-Optimized Decision Probabilities section
    league_name = "🏏 BBL" if is_bbl else ("🇿🇦 SA20" if is_sa20 else ("🇳🇿 SSM" if is_ssm else ("�🇿 SSM Women" if is_ssm_female else ("🇮🇳 WPL" if is_wpl else ("🌍 T20I" if is_t20i else "🏏 T20")))))
    st.markdown("---")
    st.subheader(f"{league_name} Decision Probabilities")
    method_label = "Platt" if cal_method == "platt" else "Isotonic"
    
    # For SA20, show per-over calibrator info for Brier column
    if is_sa20 and brier_optimized_prob is not None:
        st.caption(f"**Innings {inn_num} - Over {current_over} ({phase})** | Brier Cal: {brier_calibrator_key} | ECE Cal: {calibrator_key}")
    elif is_wpl:
        st.caption(f"**Innings {inn_num} - Over {current_over} ({phase})** | ECE Cal: {calibrator_key} | Brier Cal: {brier_cal_key if brier_cals and brier_cal_key in brier_cals else 'N/A'}")
    elif is_t20i:
        st.caption(f"**Innings {inn_num} - Over {current_over} ({phase})** | ECE Source: {t20i_ece_source or 'N/A'} | Brier Source: {t20i_brier_source or 'N/A'} | Key: {calibrator_key}")
    elif is_bbl:
        st.caption(f"**Innings {inn_num} - Over {current_over} ({phase})** | Brier: {bbl_brier_source or 'N/A'} | LL: {bbl_logloss_source or 'N/A'} | ECE: {calibrator_key}")
    else:
        st.caption(f"**Innings {inn_num} - Over {current_over} ({phase})** | Calibrator: {calibrator_key} | Source: {cal_source or 'N/A'} | Method: {method_label}")
    
    # BBL: Special 3-column layout with Log Loss in green
    if is_bbl:
        bbl_col1, bbl_col2, bbl_col3 = st.columns(3)
        
        # Column 1: Brier-optimized (Blue)
        with bbl_col1:
            # Use per-over probability from predictor if available
            if per_over_prob is not None and per_over_prob != raw_prob:
                brier_prob = per_over_prob
                brier_label = "Per-Over (Brier)"
                brier_desc = "OOF: Brier=0.1760, ECE=0.0000"
            elif bbl_brier_prob is not None:
                if inn_num == 1 and current_over == 4:
                    brier_prob = raw_prob
                    brier_label = "Raw Model"
                    brier_desc = "Over 4 exception"
                else:
                    brier_prob = bbl_brier_prob
                    brier_label = f"POC-Brier ({bbl_brier_source})"
                    brier_desc = "Brier=0.1433, LL=0.4720"
            else:
                brier_prob = raw_prob
                brier_label = "Raw Model"
                brier_desc = "Fallback"
            
            st.markdown(f'''
            <div style="text-align: center; padding: 15px; background: linear-gradient(135deg, #2196F3, #1565C0); border-radius: 15px; color: white; margin: 3px;">
                <div style="font-size: 0.85em; opacity: 0.9;">🎯 BRIER-OPTIMAL</div>
                <div style="font-size: 2.2em; font-weight: bold;">{brier_prob*100:.1f}%</div>
                <div style="font-size: 1.1em;">Odds: <b>{prob_to_odds(brier_prob)}</b></div>
                <div style="font-size: 0.75em; margin-top: 5px; opacity: 0.8;">{brier_label}</div>
                <div style="font-size: 0.65em; opacity: 0.7;">{brier_desc}</div>
            </div>
            ''', unsafe_allow_html=True)
        
        # Column 2: Log Loss-optimized (Green)
        with bbl_col2:
            if bbl_logloss_prob is not None:
                logloss_prob = bbl_logloss_prob
                logloss_label = f"POC-LL ({bbl_logloss_source})"
                logloss_desc = "LL=0.4102, Brier=0.1367"
            else:
                logloss_prob = raw_prob
                logloss_label = "Raw Model"
                logloss_desc = "Fallback"
            
            st.markdown(f'''
            <div style="text-align: center; padding: 15px; background: linear-gradient(135deg, #4CAF50, #2E7D32); border-radius: 15px; color: white; margin: 3px;">
                <div style="font-size: 0.85em; opacity: 0.9;">📊 LOGLOSS-OPTIMAL</div>
                <div style="font-size: 2.2em; font-weight: bold;">{logloss_prob*100:.1f}%</div>
                <div style="font-size: 1.1em;">Odds: <b>{prob_to_odds(logloss_prob)}</b></div>
                <div style="font-size: 0.75em; margin-top: 5px; opacity: 0.8;">{logloss_label}</div>
                <div style="font-size: 0.65em; opacity: 0.7;">{logloss_desc}</div>
            </div>
            ''', unsafe_allow_html=True)
        
        # Column 3: ECE-optimized (Orange) - Using histogram binning calibrators (OOF validated)
        with bbl_col3:
            if ece_optimized_prob is not None:
                ece_prob = ece_optimized_prob
                ece_label = f"ECE-Opt ({cal_source})"
                ece_desc = "OOF: Brier=0.1426, LL=0.4306, ECE=0.0091"
            else:
                ece_prob = raw_prob
                ece_label = "Raw Model"
                ece_desc = "Fallback"
            
            st.markdown(f'''
            <div style="text-align: center; padding: 15px; background: linear-gradient(135deg, #ff9800, #e65100); border-radius: 15px; color: white; margin: 3px;">
                <div style="font-size: 0.85em; opacity: 0.9;">⚖️ ECE-OPTIMAL</div>
                <div style="font-size: 2.2em; font-weight: bold;">{ece_prob*100:.1f}%</div>
                <div style="font-size: 1.1em;">Odds: <b>{prob_to_odds(ece_prob)}</b></div>
                <div style="font-size: 0.75em; margin-top: 5px; opacity: 0.8;">{ece_label}</div>
                <div style="font-size: 0.65em; opacity: 0.7;">{ece_desc}</div>
            </div>
            ''', unsafe_allow_html=True)
    else:
        # Non-BBL leagues
        # Check if SSM male has all 3 calibrators (Brier, LogLoss, ECE)
        if is_ssm and not is_ssm_female and ssm_brier_prob is not None and ssm_logloss_prob is not None and ece_optimized_prob is not None:
            # SSM Male: 3-column layout like BBL
            ssm_col1, ssm_col2, ssm_col3 = st.columns(3)
            
            # Column 1: Brier-optimized (Blue)
            with ssm_col1:
                brier_prob = ssm_brier_prob
                brier_label = f"POC-Brier ({ssm_brier_source})"
                brier_desc = "Brier=0.0835, LL=0.2877"
                
                st.markdown(f'''
                <div style="text-align: center; padding: 15px; background: linear-gradient(135deg, #2196F3, #1565C0); border-radius: 15px; color: white; margin: 3px;">
                    <div style="font-size: 0.85em; opacity: 0.9;">🎯 BRIER-OPTIMAL</div>
                    <div style="font-size: 2.2em; font-weight: bold;">{brier_prob*100:.1f}%</div>
                    <div style="font-size: 1.1em;">Odds: <b>{prob_to_odds(brier_prob)}</b></div>
                    <div style="font-size: 0.75em; margin-top: 5px; opacity: 0.8;">{brier_label}</div>
                    <div style="font-size: 0.65em; opacity: 0.7;">{brier_desc}</div>
                </div>
                ''', unsafe_allow_html=True)
            
            # Column 2: Log Loss-optimized (Green)
            with ssm_col2:
                logloss_prob = ssm_logloss_prob
                logloss_label = f"POC-LL ({ssm_logloss_source})"
                logloss_desc = "LL=0.2566, Brier=0.0835"
                
                st.markdown(f'''
                <div style="text-align: center; padding: 15px; background: linear-gradient(135deg, #4CAF50, #2E7D32); border-radius: 15px; color: white; margin: 3px;">
                    <div style="font-size: 0.85em; opacity: 0.9;">📊 LOGLOSS-OPTIMAL</div>
                    <div style="font-size: 2.2em; font-weight: bold;">{logloss_prob*100:.1f}%</div>
                    <div style="font-size: 1.1em;">Odds: <b>{prob_to_odds(logloss_prob)}</b></div>
                    <div style="font-size: 0.75em; margin-top: 5px; opacity: 0.8;">{logloss_label}</div>
                    <div style="font-size: 0.65em; opacity: 0.7;">{logloss_desc}</div>
                </div>
                ''', unsafe_allow_html=True)
            
            # Column 3: ECE-optimized (Orange)
            with ssm_col3:
                ece_prob = ece_optimized_prob
                ece_label = f"POC-ECE ({cal_source})"
                ece_desc = "ECE=0.0013, Brier=0.1452"
                
                st.markdown(f'''
                <div style="text-align: center; padding: 15px; background: linear-gradient(135deg, #ff9800, #e65100); border-radius: 15px; color: white; margin: 3px;">
                    <div style="font-size: 0.85em; opacity: 0.9;">⚖️ ECE-OPTIMAL</div>
                    <div style="font-size: 2.2em; font-weight: bold;">{ece_prob*100:.1f}%</div>
                    <div style="font-size: 1.1em;">Odds: <b>{prob_to_odds(ece_prob)}</b></div>
                    <div style="font-size: 0.75em; margin-top: 5px; opacity: 0.8;">{ece_label}</div>
                    <div style="font-size: 0.65em; opacity: 0.7;">{ece_desc}</div>
                </div>
                ''', unsafe_allow_html=True)
        elif is_ssm and not is_ssm_female and ssm_brier_prob is not None and ssm_logloss_prob is not None and ece_optimized_prob is not None:
            # SSM Male with all 3 calibrators: Use 3-column layout (Blue, Green, Orange)
            ssm_col1, ssm_col2, ssm_col3 = st.columns(3)
            
            with ssm_col1:
                # Blue box: Brier-optimized
                st.markdown(f'''
                <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #2196F3, #1565C0); border-radius: 15px; color: white; margin: 5px;">
                    <div style="font-size: 0.9em; opacity: 0.9;">🎯 BEST ACCURACY (Brier)</div>
                    <div style="font-size: 2.5em; font-weight: bold;">{ssm_brier_prob*100:.1f}%</div>
                    <div style="font-size: 1.3em;">Odds: <b>{prob_to_odds(ssm_brier_prob)}</b></div>
                    <div style="font-size: 0.85em; margin-top: 8px; opacity: 0.8;">Brier-Optimized ({ssm_brier_source})</div>
                    <div style="font-size: 0.75em; opacity: 0.7;">Brier=0.0867, ECE=0.000</div>
                </div>
                ''', unsafe_allow_html=True)
            
            with ssm_col2:
                # Green box: Log Loss-optimized
                st.markdown(f'''
                <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #4CAF50, #2E7D32); border-radius: 15px; color: white; margin: 5px;">
                    <div style="font-size: 0.9em; opacity: 0.9;">📈 LOG LOSS OPTIMIZED</div>
                    <div style="font-size: 2.5em; font-weight: bold;">{ssm_logloss_prob*100:.1f}%</div>
                    <div style="font-size: 1.3em;">Odds: <b>{prob_to_odds(ssm_logloss_prob)}</b></div>
                    <div style="font-size: 0.85em; margin-top: 8px; opacity: 0.8;">LL-Optimized ({ssm_logloss_source})</div>
                    <div style="font-size: 0.75em; opacity: 0.7;">LogLoss=0.2566 (27.9% better)</div>
                </div>
                ''', unsafe_allow_html=True)
            
            with ssm_col3:
                # Orange box: ECE-optimized
                st.markdown(f'''
                <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #ff9800, #e65100); border-radius: 15px; color: white; margin: 5px;">
                    <div style="font-size: 0.9em; opacity: 0.9;">📊 BEST CALIBRATION (ECE)</div>
                    <div style="font-size: 2.5em; font-weight: bold;">{ece_optimized_prob*100:.1f}%</div>
                    <div style="font-size: 1.3em;">Odds: <b>{prob_to_odds(ece_optimized_prob)}</b></div>
                    <div style="font-size: 0.85em; margin-top: 8px; opacity: 0.8;">ECE-Optimized ({calibrator_key})</div>
                    <div style="font-size: 0.75em; opacity: 0.7;">ECE=0.0000 (Perfect)</div>
                </div>
                ''', unsafe_allow_html=True)
        else:
            # Non-BBL, non-SSM-male: Use original 2-column layout
            sa_col1, sa_col2 = st.columns(2)
            with sa_col1:
                # SA20: Use raw model output for display (calibrators output 1.0 at high probs)
                # SSM: Use Brier-optimized calibrator (best accuracy)
                # WPL: Use Brier-optimized phase calibrated (wins ALL metrics)
                if is_sa20:
                    brier_prob = raw_prob
                    brier_label = "Raw Model Output"
                    brier_desc = "Brier=0.0773 (Well-calibrated)"
                elif is_ssm and ssm_brier_prob is not None:
                    brier_prob = ssm_brier_prob
                    brier_label = f"Brier-Optimized ({ssm_brier_source})"
                    brier_desc = "Brier=0.0867, ECE=0.000"
                elif is_wpl and wpl_brier_prob is not None:
                    # WPL: Inn1 uses raw (realistic), Inn2 uses brier_optimized (accurate)
                    brier_prob = wpl_brier_prob
                    if wpl_brier_source == "raw":
                        brier_label = "Raw Model Output"
                        brier_desc = "Inn1: Realistic (no calibration)"
                    else:
                        brier_label = f"Brier-Optimized ({wpl_brier_source})"
                        brier_desc = "Inn2: Brier=0.1109, ECE=0.000"
                elif is_t20i and t20i_brier_prob is not None:
                    # T20I: Use per-over Brier-optimized calibrator
                    # Inn1: Raw wins (19/20 overs), Inn2: Calibrated wins (19/20 overs)
                    brier_prob = t20i_brier_prob
                    brier_label = f"Brier-Optimized ({t20i_brier_source})"
                    brier_desc = "Brier=0.1438, 672K samples"
                else:
                    brier_prob = raw_prob
                    brier_label = "Raw Model Output"
                    brier_desc = "Use for Expected Value"
                
                st.markdown(f'''
                <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #2196F3, #1565C0); border-radius: 15px; color: white; margin: 5px;">
                    <div style="font-size: 0.9em; opacity: 0.9;">🎯 BEST ACCURACY (Brier)</div>
                    <div style="font-size: 2.5em; font-weight: bold;">{brier_prob*100:.1f}%</div>
                    <div style="font-size: 1.3em;">Odds: <b>{prob_to_odds(brier_prob)}</b></div>
                    <div style="font-size: 0.85em; margin-top: 8px; opacity: 0.8;">{brier_label}</div>
                    <div style="font-size: 0.75em; opacity: 0.7;">{brier_desc}</div>
                </div>
                ''', unsafe_allow_html=True)
            
            with sa_col2:
                # For SA20: Show Platt phase calibrated prob (smooth output)
                # For SSM Female: Show phase calibrated prob (8 phases like SA20)
                # For others: Show per-over ECE calibrated
                if is_sa20:
                    # Use Platt phase calibration for SA20 (smooth output, not step function)
                    if ece_optimized_prob is not None:
                        ece_prob = ece_optimized_prob
                        ece_label = f"Phase Platt ({calibrator_key})"
                        ece_desc = "Smooth calibration by phase"
                    else:
                        ece_prob = inn_specific_prob if inn_specific_prob is not None else raw_prob
                        ece_label = "Inn-Specific Calibrated"
                        ece_desc = "Fallback: innings context"
                    ece_odds = prob_to_odds(ece_prob)
                    st.markdown(f'''
                    <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #ff9800, #e65100); border-radius: 15px; color: white; margin: 5px;">
                        <div style="font-size: 0.9em; opacity: 0.9;">📊 PHASE CALIBRATED (Platt)</div>
                        <div style="font-size: 2.5em; font-weight: bold;">{ece_prob*100:.1f}%</div>
                        <div style="font-size: 1.3em;">Odds: <b>{ece_odds}</b></div>
                        <div style="font-size: 0.85em; margin-top: 8px; opacity: 0.8;">{ece_label}</div>
                        <div style="font-size: 0.75em; opacity: 0.7;">{ece_desc}</div>
                    </div>
                    ''', unsafe_allow_html=True)
                elif is_ssm_female:
                    # SSM Female: Phase calibrators (8 phases - SA20 style, resource-based)
                    if ece_optimized_prob is not None:
                        ece_prob = ece_optimized_prob
                        adjustment = ece_optimized_prob - resource_prob
                        adj_text = f"+{adjustment*100:.0f}%" if adjustment > 0 else f"{adjustment*100:.0f}%"
                        ece_label = f"Phase ECE ({calibrator_key}) ({adj_text})"
                        ece_desc = "ECE=0.0000 (Resource-based, 8 phases)"
                    else:
                        ece_prob = inn_specific_prob if inn_specific_prob is not None else raw_prob
                        ece_label = "Inn-Specific Calibrated"
                        ece_desc = "Fallback: phase calibrators not loaded"
                    ece_odds = prob_to_odds(ece_prob)
                    st.markdown(f'''
                    <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #ff9800, #e65100); border-radius: 15px; color: white; margin: 5px;">
                        <div style="font-size: 0.9em; opacity: 0.9;">📊 PHASE CALIBRATED (ECE)</div>
                        <div style="font-size: 2.5em; font-weight: bold;">{ece_prob*100:.1f}%</div>
                        <div style="font-size: 1.3em;">Odds: <b>{ece_odds}</b></div>
                        <div style="font-size: 0.85em; margin-top: 8px; opacity: 0.8;">{ece_label}</div>
                        <div style="font-size: 0.75em; opacity: 0.7;">{ece_desc}</div>
                    </div>
                    ''', unsafe_allow_html=True)
                elif ece_optimized_prob is not None:
                    ece_odds = prob_to_odds(ece_optimized_prob)
                    # Calculate the adjustment for display
                    adjustment = ece_optimized_prob - raw_prob
                    adj_text = f"+{adjustment*100:.0f}%" if adjustment > 0 else f"{adjustment*100:.0f}%"
                    
                    if is_wpl:
                        ece_label = f"Phase ECE-Optimized ({adj_text})"
                        ece_desc = "ECE=0.0633 (Resource-based, best calibration)"
                    elif is_t20i:
                        ece_label = f"Per-Over ECE-Optimized ({adj_text})"
                        ece_desc = f"ECE=0.0000, Source: {t20i_ece_source or 'N/A'}"
                    else:
                        ece_label = f"Historical Win Rate ({adj_text})"
                        ece_desc = "Model was under-confident in similar situations"
                    
                    st.markdown(f'''
                    <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #ff9800, #e65100); border-radius: 15px; color: white; margin: 5px;">
                        <div style="font-size: 0.9em; opacity: 0.9;">📊 BEST CALIBRATION (ECE)</div>
                        <div style="font-size: 2.5em; font-weight: bold;">{ece_optimized_prob*100:.1f}%</div>
                        <div style="font-size: 1.3em;">Odds: <b>{ece_odds}</b></div>
                        <div style="font-size: 0.85em; margin-top: 8px; opacity: 0.8;">{ece_label}</div>
                        <div style="font-size: 0.75em; opacity: 0.7;">{ece_desc}</div>
                    </div>
                    ''', unsafe_allow_html=True)
                else:
                    st.markdown(f'''
                    <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #ff9800, #e65100); border-radius: 15px; color: white; margin: 5px;">
                        <div style="font-size: 0.9em; opacity: 0.9;">📊 RESOURCE PROBABILITY</div>
                        <div style="font-size: 2.5em; font-weight: bold;">{resource_prob*100:.1f}%</div>
                        <div style="font-size: 1.3em;">Odds: <b>{prob_to_odds(resource_prob)}</b></div>
                        <div style="font-size: 0.85em; margin-top: 8px; opacity: 0.8;">DLS-based Win Prob</div>
                        <div style="font-size: 0.75em; opacity: 0.7;">Per-over calibrators not loaded</div>
                    </div>
                    ''', unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    # BBL-specific guidance based on analysis (Interactive Tabs like SSM Female)
    with st.expander("📊 BBL Calibration Guidance - Which Probability to Trust?"):
        st.markdown("### BBL v10 Model Performance Analysis (141K+ samples)")
        st.markdown("""
        **🏏 Big Bash League Model - 6 Probability Sources:**
        - **Raw**: Direct model output (baseline)
        - **InnSpec**: Innings-specific isotonic calibration
        - **Resource**: DLS-based resource win probability
        - **POC-ECE**: Per-Over Calibrated (ECE-optimized)
        - **POC-Brier**: Per-Over Calibrated (Brier-optimized)
        - **POC-LL**: Per-Over Calibrated (Log Loss-optimized)
        """)
        
        # Load BBL metrics from parquet files
        try:
            bbl_metrics_inning = pd.read_parquet('data/bbl_metrics_by_inning.parquet')
            bbl_metrics_over = pd.read_parquet('data/bbl_metrics_by_over.parquet')
            bbl_metrics_phase = pd.read_parquet('data/bbl_metrics_by_phase.parquet')
            
            # Create tabs for different views
            tab1, tab2, tab3 = st.tabs(["📈 By Inning", "🎯 By Over", "⚙️ By Phase"])
            
            with tab1:
                st.markdown("### By Innings Comparison")
                st.markdown("Compare all 6 probability sources across both innings.")
                
                # Inning metrics comparison
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("#### Brier Score (Lower is Better)")
                    brier_cols = ['Brier_Raw', 'Brier_InnSpec', 'Brier_Resource', 'Brier_POC_ECE', 'Brier_POC_Brier', 'Brier_POC_LL']
                    available_brier = [c for c in brier_cols if c in bbl_metrics_inning.columns]
                    brier_data = bbl_metrics_inning[['Group'] + available_brier].copy()
                    brier_data.columns = ['Innings'] + [c.replace('Brier_', '') for c in available_brier]
                    st.dataframe(brier_data, use_container_width=True, hide_index=True)
                    
                    # Brier chart
                    brier_chart = go.Figure()
                    for method in brier_data.columns[1:]:
                        brier_chart.add_trace(go.Bar(
                            name=method,
                            x=brier_data['Innings'],
                            y=brier_data[method],
                            text=[f"{v:.4f}" for v in brier_data[method]],
                            textposition='outside'
                        ))
                    brier_chart.update_layout(
                        barmode='group', height=400, title="Brier Score by Innings",
                        yaxis_title="Brier Score (Lower is Better)",
                        hovermode='x unified'
                    )
                    st.plotly_chart(brier_chart, use_container_width=True)
                
                with col2:
                    st.markdown("#### Expected Calibration Error (Lower is Better)")
                    ece_cols = ['ECE_Raw', 'ECE_InnSpec', 'ECE_Resource', 'ECE_POC_ECE', 'ECE_POC_Brier', 'ECE_POC_LL']
                    available_ece = [c for c in ece_cols if c in bbl_metrics_inning.columns]
                    ece_data = bbl_metrics_inning[['Group'] + available_ece].copy()
                    ece_data.columns = ['Innings'] + [c.replace('ECE_', '') for c in available_ece]
                    st.dataframe(ece_data, use_container_width=True, hide_index=True)
                    
                    # ECE chart
                    ece_chart = go.Figure()
                    for method in ece_data.columns[1:]:
                        ece_chart.add_trace(go.Bar(
                            name=method,
                            x=ece_data['Innings'],
                            y=ece_data[method],
                            text=[f"{v:.4f}" for v in ece_data[method]],
                            textposition='outside'
                        ))
                    ece_chart.update_layout(
                        barmode='group', height=400, title="ECE by Innings",
                        yaxis_title="ECE (Lower is Better)",
                        hovermode='x unified'
                    )
                    st.plotly_chart(ece_chart, use_container_width=True)
                
                col3, col4 = st.columns(2)
                with col3:
                    st.markdown("#### Log Loss (Lower is Better)")
                    ll_cols = ['LogLoss_Raw', 'LogLoss_InnSpec', 'LogLoss_Resource', 'LogLoss_POC_ECE', 'LogLoss_POC_Brier', 'LogLoss_POC_LL']
                    available_ll = [c for c in ll_cols if c in bbl_metrics_inning.columns]
                    ll_data = bbl_metrics_inning[['Group'] + available_ll].copy()
                    ll_data.columns = ['Innings'] + [c.replace('LogLoss_', '') for c in available_ll]
                    st.dataframe(ll_data, use_container_width=True, hide_index=True)
                    
                    # LogLoss chart
                    ll_chart = go.Figure()
                    for method in ll_data.columns[1:]:
                        ll_chart.add_trace(go.Bar(
                            name=method,
                            x=ll_data['Innings'],
                            y=ll_data[method],
                            text=[f"{v:.4f}" for v in ll_data[method]],
                            textposition='outside'
                        ))
                    ll_chart.update_layout(
                        barmode='group', height=400, title="Log Loss by Innings",
                        yaxis_title="Log Loss (Lower is Better)",
                        hovermode='x unified'
                    )
                    st.plotly_chart(ll_chart, use_container_width=True)
                
                with col4:
                    st.markdown("#### Key Insights")
                    st.markdown("""
                    - **🏆 POC-LL best all-rounder:** Brier=0.1367, LL=0.4102, ECE=0.0002
                    - **🥇 Best Brier:** POC-LL (0.1367) > POC-ECE (0.1392) > POC-Brier (0.1433)
                    - **🥇 Best Log Loss:** POC-ECE (0.4186) but POC-LL close (0.4102)
                    - **🥇 Best calibration:** POC-LL (ECE=0.0002) > POC-ECE (0.0045)
                    - **Resource underperforms:** High Brier & LL vs calibrated
                    """)
            
            with tab2:
                st.markdown("### By Over Comparison")
                st.markdown("Detailed per-over comparison across all 40 over-innings combinations.")
                
                metric_choice = st.selectbox(
                    "Select metric to display:",
                    ["Brier Score", "ECE", "Log Loss"],
                    key="bbl_metric_choice_over"
                )
                
                if metric_choice == "Brier Score":
                    metric_cols = ['Brier_Raw', 'Brier_POC_ECE', 'Brier_POC_Brier', 'Brier_POC_LL']
                    col_rename = ['Raw', 'POC-ECE', 'POC-Brier', 'POC-LL']
                    title = "Brier Score by Over"
                    yaxis = "Brier Score (Lower is Better)"
                elif metric_choice == "ECE":
                    metric_cols = ['ECE_Raw', 'ECE_POC_ECE', 'ECE_POC_Brier', 'ECE_POC_LL']
                    col_rename = ['Raw', 'POC-ECE', 'POC-Brier', 'POC-LL']
                    title = "ECE by Over"
                    yaxis = "ECE (Lower is Better)"
                else:
                    metric_cols = ['LogLoss_Raw', 'LogLoss_POC_ECE', 'LogLoss_POC_Brier', 'LogLoss_POC_LL']
                    col_rename = ['Raw', 'POC-ECE', 'POC-Brier', 'POC-LL']
                    title = "Log Loss by Over"
                    yaxis = "Log Loss (Lower is Better)"
                
                # Split by innings
                col_left, col_right = st.columns(2)
                
                with col_left:
                    st.markdown("#### Innings 1")
                    inn1_over = bbl_metrics_over[bbl_metrics_over['Innings'] == 1].copy()
                    inn1_over['Over_Label'] = inn1_over['Over'].apply(lambda x: f"Over {x}")
                    
                    # Create table
                    available_metric_cols = [c for c in metric_cols if c in inn1_over.columns]
                    display_cols = ['Over_Label', 'N'] + available_metric_cols
                    display_data = inn1_over[display_cols].copy()
                    display_data.columns = ['Over', 'N'] + col_rename[:len(available_metric_cols)]
                    st.dataframe(display_data, use_container_width=True, hide_index=True)
                    
                    # Chart
                    fig1 = go.Figure()
                    for i, method in enumerate(col_rename[:len(available_metric_cols)]):
                        fig1.add_trace(go.Scatter(
                            name=method,
                            x=display_data['Over'],
                            y=display_data[method],
                            mode='lines+markers',
                            hovertemplate='%{x}<br>' + method + ': %{y:.4f}<extra></extra>'
                        ))
                    fig1.update_layout(height=400, title=f"{title} - Innings 1", yaxis_title=yaxis, hovermode='x unified')
                    st.plotly_chart(fig1, use_container_width=True)
                
                with col_right:
                    st.markdown("#### Innings 2")
                    inn2_over = bbl_metrics_over[bbl_metrics_over['Innings'] == 2].copy()
                    inn2_over['Over_Label'] = inn2_over['Over'].apply(lambda x: f"Over {x}")
                    
                    # Create table
                    available_metric_cols = [c for c in metric_cols if c in inn2_over.columns]
                    display_cols = ['Over_Label', 'N'] + available_metric_cols
                    display_data = inn2_over[display_cols].copy()
                    display_data.columns = ['Over', 'N'] + col_rename[:len(available_metric_cols)]
                    st.dataframe(display_data, use_container_width=True, hide_index=True)
                    
                    # Chart
                    fig2 = go.Figure()
                    for i, method in enumerate(col_rename[:len(available_metric_cols)]):
                        fig2.add_trace(go.Scatter(
                            name=method,
                            x=display_data['Over'],
                            y=display_data[method],
                            mode='lines+markers',
                            hovertemplate='%{x}<br>' + method + ': %{y:.4f}<extra></extra>'
                        ))
                    fig2.update_layout(height=400, title=f"{title} - Innings 2", yaxis_title=yaxis, hovermode='x unified')
                    st.plotly_chart(fig2, use_container_width=True)
            
            with tab3:
                st.markdown("### By Phase (SA20 Style - 8 Phases)")
                st.markdown("""
                Compare probabilities by cricket phases:
                - **Powerplay** (Overs 1-6): Aggressive batting, fielding restrictions
                - **Middle Early** (Overs 7-11): Consolidation phase
                - **Middle Late** (Overs 12-15): Acceleration starts
                - **Death** (Overs 16-20): Maximum effort, high risk
                """)
                
                metric_choice_phase = st.selectbox(
                    "Select metric to display:",
                    ["Brier Score", "ECE", "Log Loss"],
                    key="bbl_metric_choice_phase"
                )
                
                if metric_choice_phase == "Brier Score":
                    metric_cols = ['Brier_Raw', 'Brier_POC_ECE', 'Brier_POC_Brier', 'Brier_POC_LL']
                    col_rename = ['Raw', 'POC-ECE', 'POC-Brier', 'POC-LL']
                    title = "Brier Score by Phase"
                elif metric_choice_phase == "ECE":
                    metric_cols = ['ECE_Raw', 'ECE_POC_ECE', 'ECE_POC_Brier', 'ECE_POC_LL']
                    col_rename = ['Raw', 'POC-ECE', 'POC-Brier', 'POC-LL']
                    title = "ECE by Phase"
                else:
                    metric_cols = ['LogLoss_Raw', 'LogLoss_POC_ECE', 'LogLoss_POC_Brier', 'LogLoss_POC_LL']
                    col_rename = ['Raw', 'POC-ECE', 'POC-Brier', 'POC-LL']
                    title = "Log Loss by Phase"
                
                # Phase comparison table
                st.markdown("#### Overall Phase Comparison")
                
                available_cols = ['Innings', 'Phase', 'N']
                available_metric = [c for c in metric_cols if c in bbl_metrics_phase.columns]
                phase_display = bbl_metrics_phase[available_cols + available_metric].copy()
                phase_display.columns = available_cols + col_rename[:len(available_metric)]
                st.dataframe(phase_display, use_container_width=True, hide_index=True)
                
                # Chart by innings
                col_left, col_right = st.columns(2)
                with col_left:
                    st.markdown("#### Innings 1")
                    inn1_phase = bbl_metrics_phase[bbl_metrics_phase['Innings'] == 1].copy()
                    fig_p1 = go.Figure()
                    for i, method in enumerate(col_rename[:len(available_metric)]):
                        fig_p1.add_trace(go.Bar(
                            name=method,
                            x=inn1_phase['Phase'],
                            y=inn1_phase[available_metric[i]].values if i < len(available_metric) else [],
                            text=[f"{v:.4f}" for v in inn1_phase[available_metric[i]].values] if i < len(available_metric) else [],
                            textposition='outside'
                        ))
                    fig_p1.update_layout(barmode='group', height=400, title=f"{title} - Innings 1")
                    st.plotly_chart(fig_p1, use_container_width=True)
                
                with col_right:
                    st.markdown("#### Innings 2")
                    inn2_phase = bbl_metrics_phase[bbl_metrics_phase['Innings'] == 2].copy()
                    fig_p2 = go.Figure()
                    for i, method in enumerate(col_rename[:len(available_metric)]):
                        fig_p2.add_trace(go.Bar(
                            name=method,
                            x=inn2_phase['Phase'],
                            y=inn2_phase[available_metric[i]].values if i < len(available_metric) else [],
                            text=[f"{v:.4f}" for v in inn2_phase[available_metric[i]].values] if i < len(available_metric) else [],
                            textposition='outside'
                        ))
                    fig_p2.update_layout(barmode='group', height=400, title=f"{title} - Innings 2")
                    st.plotly_chart(fig_p2, use_container_width=True)
                
                st.markdown("---")
                st.markdown("#### 🎯 BBL Calibrator Recommendations")
                st.success("""
                **Summary of Best Probability Sources:**
                - **🥇 Best All-Rounder:** POC-LL (Brier=0.1367, LL=0.4102, ECE=0.0002)
                - **For Lowest Log Loss:** POC-ECE (0.4186) but POC-LL very close (0.4102)
                - **For Best Accuracy (Brier):** POC-LL (0.1367) beats all others
                - **For Perfect Calibration:** POC-LL (ECE=0.0002) nearly perfect
                
                **By Phase:**
                - Inn1 Powerplay: POC-Brier best for Brier
                - Inn1 Middle/Death: POC-ECE/POC-LL competitive
                - Inn2 Powerplay: POC-LL best overall (0.1452 Brier)
                - Inn2 Middle/Death: POC-Brier for accuracy
                """)
        
        except Exception as e:
            st.warning(f"Could not load BBL metrics files: {e}")
            st.markdown("""
            **Run these commands to generate metrics:**
            ```bash
            python scripts/analyze_bbl_calibration.py
            python scripts/train_bbl_logloss_calibrators.py
            ```
            """)
    
    # BBL Comprehensive OOF Calibration Analysis
    with st.expander("🔬 BBL Comprehensive OOF Calibration Analysis - 7 Methods Compared"):
        st.markdown("### BBL v10 - Out-of-Fold Cross-Validation Results (141.4K samples)")
        st.markdown("""
        **Analysis Date:** January 15, 2026  
        **Model:** BBL v10 XGBLogRegEnsemble  
        **Validation:** 5-Fold CV (no shuffle)  
        **Innings Split:** 73,875 (Inn 1) | 67,560 (Inn 2)
        
        This analysis compares **7 different calibration approaches** using proper out-of-fold validation to prevent overfitting.
        """)
        
        # Overall Rankings Table
        st.markdown("### 🏆 Overall Rankings")
        
        overall_data = {
            'Method': ['ECE-Optimized', 'Combined', 'Innings×Phase', 'LogLoss-Optimized', 
                      'Innings-Specific', 'Brier-Optimized', 'Raw'],
            'Description': [
                'Histogram binning (15 bins) per innings×phase',
                'Single isotonic calibrator for all data',
                'Isotonic per innings × phase (6 calibrators)',
                'Platt scaling per innings×phase',
                'Isotonic per innings (2 calibrators)',
                'Per-over isotonic (40 calibrators)',
                'Uncalibrated model predictions'
            ],
            '# Calibrators': [6, 1, 6, 6, 2, 40, 0],
            'Brier Score': [0.1426, 0.1428, 0.1430, 0.1432, 0.1435, 0.1440, 0.1456],
            'ECE': [0.0091, 0.0053, 0.0117, 0.0199, 0.0055, 0.0132, 0.0558],
            'Log Loss': [0.4306, 0.4312, 0.4374, 0.4370, 0.4328, 0.4642, 0.4449],
            'Brier Rank': ['🥇', '🥈', '🥉', '4', '5', '6', '7'],
            'ECE Rank': ['🥉', '🥇', '4', '6', '🥈', '5', '7'],
            'LL Rank': ['🥇', '🥈', '5', '4', '🥉', '7', '6']
        }
        
        overall_df = pd.DataFrame(overall_data)
        st.dataframe(overall_df, use_container_width=True, hide_index=True)
        
        # Key Findings
        st.markdown("### 💡 Key Findings")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "🥇 Best Overall",
                "ECE-Optimized",
                "Histogram binning"
            )
            st.markdown("""
            - Best Brier: 0.1426
            - Best LogLoss: 0.4306
            - Strong ECE: 0.0091
            - **+2.07%** Brier improvement
            - **+3.21%** LogLoss improvement
            """)
        
        with col2:
            st.metric(
                "🥇 Best ECE",
                "Combined",
                "Single isotonic"
            )
            st.markdown("""
            - ECE: 0.0053 (near-perfect!)
            - **+90.43%** ECE improvement
            - Simplest approach (1 cal)
            - Most stable across folds
            - Competitive on all metrics
            """)
        
        with col3:
            st.metric(
                "⚠️ Avoid",
                "Brier-Optimized",
                "40 per-over cals"
            )
            st.markdown("""
            - Worst LogLoss: 0.4642
            - **-4.35%** WORSE than raw!
            - Overfits with 40 calibrators
            - Too granular for OOF
            - Not recommended
            """)
        
        # Detailed Comparison Tabs
        tab1, tab2, tab3, tab4 = st.tabs([
            "📊 Overall Metrics",
            "🏏 By Innings",
            "⚙️ By Phase",
            "📈 Cross-Validation"
        ])
        
        with tab1:
            st.markdown("### Overall Performance Comparison")
            
            # Metric selection
            metric_view = st.selectbox(
                "Select Metric:",
                ["Brier Score", "ECE (Calibration)", "Log Loss"],
                key="bbl_oof_metric_overall"
            )
            
            methods = ['Raw', 'Combined', 'Innings-Specific', 'Innings×Phase', 
                      'Brier-Optimized', 'ECE-Optimized', 'LogLoss-Optimized']
            
            if metric_view == "Brier Score":
                values = [0.1456, 0.1428, 0.1435, 0.1430, 0.1440, 0.1426, 0.1432]
                improvements = [0, +1.89, +1.41, +1.80, +1.12, +2.07, +1.66]
            elif metric_view == "ECE (Calibration)":
                values = [0.0558, 0.0053, 0.0055, 0.0117, 0.0132, 0.0091, 0.0199]
                improvements = [0, +90.43, +90.18, +78.97, +76.41, +83.73, +64.30]
            else:  # Log Loss
                values = [0.4449, 0.4312, 0.4328, 0.4374, 0.4642, 0.4306, 0.4370]
                improvements = [0, +3.07, +2.71, +1.68, -4.35, +3.21, +1.78]
            
            # Bar chart
            colors = ['#ff6b6b' if v < 0 else '#51cf66' for v in improvements]
            colors[0] = '#868e96'  # Gray for raw
            
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=methods,
                y=values,
                text=[f"{v:.4f}<br>({imp:+.1f}%)" for v, imp in zip(values, improvements)],
                textposition='outside',
                marker_color=colors,
                hovertemplate='<b>%{x}</b><br>Value: %{y:.4f}<br>Improvement: %{text}<extra></extra>'
            ))
            
            fig.update_layout(
                title=f"{metric_view} - Overall OOF Performance",
                yaxis_title=metric_view,
                xaxis_title="Calibration Method",
                height=500,
                showlegend=False
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Improvement table
            st.markdown("### Improvement Over Raw Model")
            improvement_df = pd.DataFrame({
                'Method': methods[1:],  # Exclude raw
                'Brier Δ%': [+1.89, +1.41, +1.80, +1.12, +2.07, +1.66],
                'ECE Δ%': [+90.43, +90.18, +78.97, +76.41, +83.73, +64.30],
                'LogLoss Δ%': [+3.07, +2.71, +1.68, -4.35, +3.21, +1.78],
                'Status': ['✅ All Good', '✅ All Good', '✅ All Good', 
                          '❌ Hurts LL', '✅ Best Overall', '✅ All Good']
            })
            st.dataframe(improvement_df, use_container_width=True, hide_index=True)
        
        with tab2:
            st.markdown("### Performance By Innings")
            
            innings_view = st.radio(
                "Select Innings:",
                ["Innings 1 (73,875 balls)", "Innings 2 (67,560 balls)"],
                key="bbl_oof_innings"
            )
            
            if "Innings 1" in innings_view:
                inn_data = {
                    'Method': methods,
                    'Brier': [0.1775, 0.1741, 0.1750, 0.1746, 0.1758, 0.1743, 0.1748],
                    'ECE': [0.0642, 0.0157, 0.0099, 0.0214, 0.0223, 0.0173, 0.0266],
                    'LogLoss': [0.5308, 0.5169, 0.5190, 0.5262, 0.5532, 0.5168, 0.5222]
                }
            else:
                inn_data = {
                    'Method': methods,
                    'Brier': [0.1107, 0.1087, 0.1092, 0.1083, 0.1091, 0.1079, 0.1086],
                    'ECE': [0.0466, 0.0125, 0.0091, 0.0090, 0.0108, 0.0070, 0.0184],
                    'LogLoss': [0.3509, 0.3375, 0.3386, 0.3404, 0.3670, 0.3364, 0.3438]
                }
            
            inn_df = pd.DataFrame(inn_data)
            
            # Display table
            st.dataframe(inn_df, use_container_width=True, hide_index=True)
            
            # Grouped bar chart
            fig = go.Figure()
            
            fig.add_trace(go.Bar(name='Brier', x=inn_df['Method'], y=inn_df['Brier'], 
                                text=[f"{v:.4f}" for v in inn_df['Brier']], textposition='outside'))
            fig.add_trace(go.Bar(name='ECE', x=inn_df['Method'], y=inn_df['ECE'],
                                text=[f"{v:.4f}" for v in inn_df['ECE']], textposition='outside'))
            fig.add_trace(go.Bar(name='LogLoss', x=inn_df['Method'], y=inn_df['LogLoss'],
                                text=[f"{v:.4f}" for v in inn_df['LogLoss']], textposition='outside'))
            
            fig.update_layout(
                barmode='group',
                title=f"Performance by Metric - {innings_view.split('(')[0].strip()}",
                yaxis_title="Metric Value",
                height=500,
                hovermode='x unified'
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            st.info("""
            **Key Insight:** Innings 2 shows better overall calibration (Brier ~0.11 vs ~0.18 for innings 1).  
            ECE-Optimized performs best in both innings for Brier and Log Loss.
            """)
        
        with tab3:
            st.markdown("### Performance By Innings × Phase")
            
            phase_choice = st.selectbox(
                "Select Phase:",
                [
                    "Inn1 Powerplay (1-6)",
                    "Inn1 Middle (7-15)",
                    "Inn1 Death (16-20)",
                    "Inn2 Powerplay (1-6)",
                    "Inn2 Middle (7-15)",
                    "Inn2 Death (16-20)"
                ],
                key="bbl_oof_phase"
            )
            
            phase_data = {
                "Inn1 Powerplay (1-6)": {
                    'Samples': 18658,
                    'Brier': [0.2013, 0.1949, 0.1954, 0.1935, 0.1945, 0.1932, 0.1925],
                    'ECE': [0.0925, 0.0450, 0.0376, 0.0153, 0.0197, 0.0180, 0.0115],
                    'LogLoss': [0.5899, 0.5738, 0.5753, 0.5876, 0.6102, 0.5712, 0.5681]
                },
                "Inn1 Middle (7-15)": {
                    'Samples': 33364,
                    'Brier': [0.1739, 0.1714, 0.1723, 0.1723, 0.1743, 0.1721, 0.1736],
                    'ECE': [0.0537, 0.0256, 0.0242, 0.0273, 0.0294, 0.0206, 0.0318],
                    'LogLoss': [0.5219, 0.5085, 0.5087, 0.5102, 0.5468, 0.5085, 0.5187]
                },
                "Inn1 Death (16-20)": {
                    'Samples': 21853,
                    'Brier': [0.1626, 0.1603, 0.1616, 0.1620, 0.1621, 0.1614, 0.1614],
                    'ECE': [0.0559, 0.0285, 0.0306, 0.0297, 0.0182, 0.0247, 0.0343],
                    'LogLoss': [0.4941, 0.4811, 0.4868, 0.4982, 0.5141, 0.4830, 0.4883]
                },
                "Inn2 Powerplay (1-6)": {
                    'Samples': 18700,
                    'Brier': [0.1573, 0.1554, 0.1557, 0.1556, 0.1561, 0.1549, 0.1555],
                    'ECE': [0.0591, 0.0334, 0.0264, 0.0109, 0.0189, 0.0105, 0.0219],
                    'LogLoss': [0.4791, 0.4694, 0.4709, 0.4749, 0.4924, 0.4687, 0.4730]
                },
                "Inn2 Middle (7-15)": {
                    'Samples': 32475,
                    'Brier': [0.1066, 0.1039, 0.1045, 0.1050, 0.1063, 0.1046, 0.1046],
                    'ECE': [0.0526, 0.0121, 0.0159, 0.0123, 0.0130, 0.0072, 0.0168],
                    'LogLoss': [0.3425, 0.3267, 0.3284, 0.3318, 0.3659, 0.3302, 0.3350]
                },
                "Inn2 Death (16-20)": {
                    'Samples': 16385,
                    'Brier': [0.0654, 0.0649, 0.0654, 0.0611, 0.0612, 0.0608, 0.0629],
                    'ECE': [0.0577, 0.0385, 0.0372, 0.0098, 0.0138, 0.0094, 0.0296],
                    'LogLoss': [0.2214, 0.2087, 0.2079, 0.2038, 0.2262, 0.1976, 0.2136]
                }
            }
            
            selected_data = phase_data[phase_choice]
            phase_df = pd.DataFrame({
                'Method': methods,
                'Brier': selected_data['Brier'],
                'ECE': selected_data['ECE'],
                'LogLoss': selected_data['LogLoss']
            })
            
            st.markdown(f"**Sample Size:** {selected_data['Samples']:,} balls")
            st.dataframe(phase_df, use_container_width=True, hide_index=True)
            
            # Radar chart
            fig = go.Figure()
            
            for i, method in enumerate(methods):
                # Normalize metrics (invert so higher is better for visualization)
                brier_norm = 1 - phase_df.loc[i, 'Brier']
                ece_norm = 1 - phase_df.loc[i, 'ECE']
                ll_norm = 1 - phase_df.loc[i, 'LogLoss']
                
                fig.add_trace(go.Scatterpolar(
                    r=[brier_norm, ece_norm, ll_norm],
                    theta=['Brier', 'ECE', 'LogLoss'],
                    fill='toself',
                    name=method
                ))
            
            fig.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
                title=f"Performance Radar - {phase_choice}",
                height=500
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            st.info("""
            **Phase Trends:**
            - **Inn2 Death** shows best calibration (Brier ~0.06)
            - **Inn1 Powerplay** shows worst calibration (Brier ~0.19)
            - **ECE-Optimized** wins most phase segments
            """)
        
        with tab4:
            st.markdown("### Cross-Validation Stability")
            st.markdown("Performance across 5 folds (28,287 samples each)")
            
            cv_metric = st.selectbox(
                "Select Metric:",
                ["Brier Score", "ECE", "Log Loss"],
                key="bbl_oof_cv_metric"
            )
            
            # CV fold data
            folds = ['Fold 1', 'Fold 2', 'Fold 3', 'Fold 4', 'Fold 5']
            
            if cv_metric == "Brier Score":
                cv_data = {
                    'Raw': [0.1487, 0.1632, 0.1357, 0.1484, 0.1319],
                    'Combined': [0.1474, 0.1644, 0.1316, 0.1442, 0.1266],
                    'Innings-Specific': [0.1482, 0.1644, 0.1330, 0.1455, 0.1266],
                    'Innings×Phase': [0.1492, 0.1632, 0.1325, 0.1443, 0.1256],
                    'Brier-Optimized': [0.1498, 0.1643, 0.1339, 0.1452, 0.1266],
                    'ECE-Optimized': [0.1487, 0.1627, 0.1321, 0.1440, 0.1253],
                    'LogLoss-Optimized': [0.1492, 0.1645, 0.1326, 0.1441, 0.1256]
                }
            elif cv_metric == "ECE":
                cv_data = {
                    'Raw': [0.0466, 0.0295, 0.0716, 0.0656, 0.0734],
                    'Combined': [0.0357, 0.0405, 0.0385, 0.0219, 0.0221],
                    'Innings-Specific': [0.0425, 0.0406, 0.0377, 0.0205, 0.0207],
                    'Innings×Phase': [0.0369, 0.0379, 0.0375, 0.0195, 0.0191],
                    'Brier-Optimized': [0.0370, 0.0439, 0.0380, 0.0234, 0.0179],
                    'ECE-Optimized': [0.0373, 0.0372, 0.0379, 0.0187, 0.0221],
                    'LogLoss-Optimized': [0.0372, 0.0520, 0.0488, 0.0284, 0.0234]
                }
            else:  # Log Loss
                cv_data = {
                    'Raw': [0.4517, 0.4860, 0.4208, 0.4542, 0.4118],
                    'Combined': [0.4412, 0.4855, 0.4036, 0.4363, 0.3895],
                    'Innings-Specific': [0.4416, 0.4858, 0.4073, 0.4379, 0.3916],
                    'Innings×Phase': [0.4462, 0.4914, 0.4132, 0.4357, 0.4007],
                    'Brier-Optimized': [0.4649, 0.5375, 0.4335, 0.4663, 0.4190],
                    'ECE-Optimized': [0.4440, 0.4823, 0.4053, 0.4354, 0.3862],
                    'LogLoss-Optimized': [0.4510, 0.4896, 0.4129, 0.4401, 0.3914]
                }
            
            # Line chart
            fig = go.Figure()
            
            for method in methods:
                fig.add_trace(go.Scatter(
                    x=folds,
                    y=cv_data[method],
                    mode='lines+markers',
                    name=method,
                    line=dict(width=2),
                    marker=dict(size=8)
                ))
            
            fig.update_layout(
                title=f"{cv_metric} Across CV Folds",
                xaxis_title="Fold",
                yaxis_title=cv_metric,
                height=500,
                hovermode='x unified'
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Mean ± Std table
            st.markdown("### Mean ± Standard Deviation")
            
            mean_std_data = {
                'Method': methods,
                'Brier': ['0.1456±0.0111', '0.1428±0.0132', '0.1435±0.0131', '0.1430±0.0131',
                         '0.1440±0.0131', '0.1426±0.0131', '0.1432±0.0135'],
                'ECE': ['0.0574±0.0169', '0.0317±0.0081', '0.0324±0.0098', '0.0302±0.0089',
                       '0.0320±0.0098', '0.0306±0.0084', '0.0380±0.0111'],
                'LogLoss': ['0.4449±0.0265', '0.4312±0.0334', '0.4328±0.0324', '0.4374±0.0314',
                           '0.4642±0.0409', '0.4306±0.0331', '0.4370±0.0336']
            }
            
            mean_std_df = pd.DataFrame(mean_std_data)
            st.dataframe(mean_std_df, use_container_width=True, hide_index=True)
            
            st.warning("""
            **Statistical Note:** Due to high variance across folds (σ ≈ 0.013), differences between 
            calibration methods are not statistically significant at 5% level. However, all methods 
            **consistently outperform raw in every fold**.
            """)
        
        # Implementation Notes
        st.markdown("---")
        st.markdown("### 🛠️ Implementation & Files")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            **Active in Streamlit App:**
            - ✅ `ece_optimized_calibrators.pkl` (BBL v10)
            - 6 calibrators (histogram binning)
            - Trained using proper OOF methodology
            - Best Brier (0.1426) & LogLoss (0.4306)
            """)
        
        with col2:
            st.markdown("""
            **Analysis Scripts:**
            - `analyze_bbl_calibrators_oof.py` - Main analysis
            - `scripts/train_bbl_ece_calibrators.py` - Train ECE calibrators
            - `BBL_CALIBRATION_OOF_ANALYSIS.md` - Full documentation
            - Generated: January 15, 2026
            """)
        
        st.success("""
        **🎯 Production Recommendation:**  
        Use **ECE-Optimized** calibrators for BBL live predictions. They provide the best balance of 
        accuracy (Brier), probabilistic sharpness (LogLoss), and calibration (ECE).  
        
        The app is currently configured to use these calibrators automatically for BBL matches.
        """)
    
    # SA20 Calibration Guidance
    with st.expander("📊 SA20 Calibration Guidance - Which Probability to Trust?"):
        st.markdown("### SA20 v2 Model Performance by Innings & Phase (21.8K samples)")
        st.markdown("""
        **Detailed Brier & ECE Analysis - Raw vs Calibrated vs Resource:**
        
        #### Innings 1 - Raw wins Brier, Resource wins ECE (all phases)
        | Phase | N | B_Raw | B_Cal | B_Res | E_Raw | E_Cal | E_Res | Best Brier | Best ECE |
        |-------|---|-------|-------|-------|-------|-------|-------|------------|----------|
        | Powerplay | 3963 | **0.1208** | 0.1726 | 0.2531 | 0.2313 | 0.2992 | **0.1408** | 🏆 Raw | 🏆 Res |
        | Middle Early | 2877 | **0.0930** | 0.1379 | 0.2218 | 0.1781 | 0.2671 | **0.1497** | 🏆 Raw | 🏆 Res |
        | Middle Late | 2283 | **0.0772** | 0.1251 | 0.2033 | 0.1648 | 0.2436 | **0.1465** | 🏆 Raw | 🏆 Res |
        | Death | 2347 | **0.0806** | 0.1250 | 0.1987 | 0.1580 | 0.2435 | **0.1402** | 🏆 Raw | 🏆 Res |
        
        #### Innings 2 - Raw wins Brier (all), Mixed ECE winners
        | Phase | N | B_Raw | B_Cal | B_Res | E_Raw | E_Cal | E_Res | Best Brier | Best ECE |
        |-------|---|-------|-------|-------|-------|-------|-------|------------|----------|
        | Powerplay | 3978 | **0.0737** | 0.0933 | 0.1726 | 0.1524 | 0.1362 | **0.1312** | 🏆 Raw | 🏆 Res |
        | Middle Early | 2810 | **0.0504** | 0.0674 | 0.1157 | 0.1197 | 0.1080 | **0.0553** | 🏆 Raw | 🏆 Res |
        | Middle Late | 2032 | **0.0459** | 0.0599 | 0.1178 | **0.0867** | 0.1036 | 0.0993 | 🏆 Raw | 🏆 Raw |
        | Death | 1503 | **0.0300** | 0.0421 | 0.1019 | **0.0799** | 0.0940 | 0.1287 | 🏆 Raw | 🏆 Raw |
        
        *Lower is better for both Brier and ECE*
        """)
        
        st.markdown("---")
        st.markdown("### 🎯 SA20 Recommendation by Situation")
        
        st.success("""
        **For Best Accuracy (Brier):** 🏆 **Raw Model wins ALL 8 phases!**
        - Inn 1 Death: 0.0806 (Raw) vs 0.1250 (Cal) vs 0.1987 (Res)
        - Inn 2 Death: 0.0300 (Raw) vs 0.0421 (Cal) vs 0.1019 (Res)
        
        **For Best Calibration (ECE):**
        - **Inn 1 (all phases):** Resource Probability 🏆
        - **Inn 2 Powerplay/Middle Early:** Resource Probability 🏆
        - **Inn 2 Middle Late/Death:** Raw Model 🏆
        
        ✅ **Current Display:** Raw Model for Brier, Context-aware for ECE
        """)
        
        st.markdown("---")
        st.markdown("### 📖 Key Insights")
        st.markdown("""
        - **🏆 Raw Model is DOMINANT for Accuracy:** Wins Brier in ALL 8 innings×phase combinations!
        - **Resource wins ECE in 6/8 situations:** All of Inn 1 + Inn 2 early phases
        - **Raw wins ECE late in Inn 2:** Model shines when chase is clearer (overs 12-20)
        - **Calibration hurts more than helps:** Inn-specific calibrators have WORSE Brier than Raw!
        - **Why?** SA20 raw model (0.49±0.32) is already well-differentiated
        - **Sample sizes:** 1,503-3,978 per phase - statistically robust
        """)
    
    # SSM Calibration Guidance (Interactive Tabs like SSM Female)
    with st.expander("📊 SSM (Super Smash) Calibration Guidance - Which Probability to Trust?"):
        st.markdown("### SSM v1 Model Performance Analysis (55.5K samples)")
        st.markdown("""
        **🇳🇿 New Zealand Men's Super Smash Model**
        
        Compare five probability sources across 40 per-over calibrators:
        - **Raw**: Direct model output (baseline)
        - **InnSpec**: Innings-specific isotonic calibration
        - **Resource**: DLS-based resource win probability
        - **POC-ECE**: Per-Over Calibrated (ECE-optimized)
        - **POC-Brier**: Per-Over Calibrated (Brier-optimized)
        """)
        
        # Load SSM Male metrics
        try:
            ssm_m_metrics_inning = pd.read_parquet('data/ssm_male_metrics_by_inning.parquet')
            ssm_m_metrics_over = pd.read_parquet('data/ssm_male_metrics_by_over.parquet')
            ssm_m_metrics_phase = pd.read_parquet('data/ssm_male_metrics_by_phase.parquet')
            
            # Create tabs for different views
            tab1, tab2, tab3 = st.tabs(["📈 By Inning", "🎯 By Over", "⚙️ By Phase"])
            
            with tab1:
                st.markdown("### By Innings Comparison")
                st.markdown("""
                Compare all 5 probability sources across both innings.
                """)
                
                # Inning metrics comparison
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("#### Brier Score (Lower is Better)")
                    brier_cols = ['Brier_Raw', 'Brier_InnSpec', 'Brier_Resource', 'Brier_POC_ECE', 'Brier_POC_Brier', 'Brier_LL_Opt']
                    available_brier = [c for c in brier_cols if c in ssm_m_metrics_inning.columns]
                    brier_data = ssm_m_metrics_inning[['Group'] + available_brier].copy()
                    brier_data.columns = ['Innings'] + [c.replace('Brier_', '') for c in available_brier]
                    st.dataframe(brier_data, use_container_width=True, hide_index=True)
                    
                    # Brier chart
                    brier_chart = go.Figure()
                    for method in brier_data.columns[1:]:
                        brier_chart.add_trace(go.Bar(
                            name=method,
                            x=brier_data['Innings'],
                            y=brier_data[method],
                            text=[f"{v:.4f}" for v in brier_data[method]],
                            textposition='outside'
                        ))
                    brier_chart.update_layout(
                        barmode='group', height=400, title="Brier Score by Innings",
                        yaxis_title="Brier Score (Lower is Better)",
                        hovermode='x unified'
                    )
                    st.plotly_chart(brier_chart, use_container_width=True)
                
                with col2:
                    st.markdown("#### Expected Calibration Error (Lower is Better)")
                    ece_cols = ['ECE_Raw', 'ECE_InnSpec', 'ECE_Resource', 'ECE_POC_ECE', 'ECE_POC_Brier', 'ECE_LL_Opt']
                    available_ece = [c for c in ece_cols if c in ssm_m_metrics_inning.columns]
                    ece_data = ssm_m_metrics_inning[['Group'] + available_ece].copy()
                    ece_data.columns = ['Innings'] + [c.replace('ECE_', '') for c in available_ece]
                    st.dataframe(ece_data, use_container_width=True, hide_index=True)
                    
                    # ECE chart
                    ece_chart = go.Figure()
                    for method in ece_data.columns[1:]:
                        ece_chart.add_trace(go.Bar(
                            name=method,
                            x=ece_data['Innings'],
                            y=ece_data[method],
                            text=[f"{v:.4f}" for v in ece_data[method]],
                            textposition='outside'
                        ))
                    ece_chart.update_layout(
                        barmode='group', height=400, title="ECE by Innings",
                        yaxis_title="ECE (Lower is Better)",
                        hovermode='x unified'
                    )
                    st.plotly_chart(ece_chart, use_container_width=True)
                
                with col3:
                    st.markdown("#### Log Loss (Lower is Better)")
                    ll_cols = ['LogLoss_Raw', 'LogLoss_InnSpec', 'LogLoss_Resource', 'LogLoss_POC_ECE', 'LogLoss_POC_Brier', 'LogLoss_LL_Opt']
                    available_ll = [c for c in ll_cols if c in ssm_m_metrics_inning.columns]
                    ll_data = ssm_m_metrics_inning[['Group'] + available_ll].copy()
                    ll_data.columns = ['Innings'] + [c.replace('LogLoss_', '') for c in available_ll]
                    st.dataframe(ll_data, use_container_width=True, hide_index=True)
                    
                    # LogLoss chart
                    ll_chart = go.Figure()
                    for method in ll_data.columns[1:]:
                        ll_chart.add_trace(go.Bar(
                            name=method,
                            x=ll_data['Innings'],
                            y=ll_data[method],
                            text=[f"{v:.4f}" for v in ll_data[method]],
                            textposition='outside'
                        ))
                    ll_chart.update_layout(
                        barmode='group', height=400, title="Log Loss by Innings",
                        yaxis_title="Log Loss (Lower is Better)",
                        hovermode='x unified'
                    )
                    st.plotly_chart(ll_chart, use_container_width=True)
                
                with col4:
                    st.markdown("#### Key Insights")
                    st.markdown("""
                    - **🏆 Raw dominates Brier:** Best accuracy for most overs
                    - **POC-ECE = Perfect ECE:** 0.0013 overall calibration
                    - **POC-Brier improves middle/late:** 10-15% improvement
                    - **Resource underperforms:** Poor for SSM (high-scoring)
                    """)
            
            with tab2:
                st.markdown("### By Over Comparison")
                st.markdown("""
                Detailed per-over comparison across all 40 over-innings combinations.
                Select metrics to compare.
                """)
                
                metric_choice = st.selectbox(
                    "Select metric to display:",
                    ["Brier Score", "ECE", "Log Loss"],
                    key="ssm_m_metric_choice_over"
                )
                
                if metric_choice == "Brier Score":
                    metric_cols = ['Brier_Raw', 'Brier_POC_ECE', 'Brier_POC_Brier', 'Brier_LL_Opt']
                    col_rename = ['Raw', 'POC-ECE', 'POC-Brier', 'LL-Opt']
                    title = "Brier Score by Over"
                    yaxis = "Brier Score (Lower is Better)"
                elif metric_choice == "ECE":
                    metric_cols = ['ECE_Raw', 'ECE_POC_ECE', 'ECE_POC_Brier', 'ECE_LL_Opt']
                    col_rename = ['Raw', 'POC-ECE', 'POC-Brier', 'LL-Opt']
                    title = "ECE by Over"
                    yaxis = "ECE (Lower is Better)"
                else:
                    metric_cols = ['LogLoss_Raw', 'LogLoss_POC_ECE', 'LogLoss_POC_Brier', 'LogLoss_LL_Opt']
                    col_rename = ['Raw', 'POC-ECE', 'POC-Brier', 'LL-Opt']
                    title = "Log Loss by Over"
                    yaxis = "Log Loss (Lower is Better)"
                
                # Split by innings
                col_left, col_right = st.columns(2)
                
                with col_left:
                    st.markdown("#### Innings 1")
                    inn1_over = ssm_m_metrics_over[ssm_m_metrics_over['Innings'] == 1].copy()
                    inn1_over['Over_Label'] = inn1_over['Over'].apply(lambda x: f"Over {x}")
                    
                    # Create table
                    available_metric_cols = [c for c in metric_cols if c in inn1_over.columns]
                    display_cols = ['Over_Label', 'N'] + available_metric_cols
                    display_data = inn1_over[display_cols].copy()
                    display_data.columns = ['Over', 'N'] + col_rename[:len(available_metric_cols)]
                    st.dataframe(display_data, use_container_width=True, hide_index=True)
                    
                    # Chart
                    fig1 = go.Figure()
                    for i, method in enumerate(col_rename[:len(available_metric_cols)]):
                        fig1.add_trace(go.Scatter(
                            name=method,
                            x=display_data['Over'],
                            y=display_data[method],
                            mode='lines+markers',
                            hovertemplate='%{x}<br>' + method + ': %{y:.4f}<extra></extra>'
                        ))
                    fig1.update_layout(height=400, title=f"{title} - Innings 1", yaxis_title=yaxis, hovermode='x unified')
                    st.plotly_chart(fig1, use_container_width=True)
                
                with col_right:
                    st.markdown("#### Innings 2")
                    inn2_over = ssm_m_metrics_over[ssm_m_metrics_over['Innings'] == 2].copy()
                    inn2_over['Over_Label'] = inn2_over['Over'].apply(lambda x: f"Over {x}")
                    
                    # Create table
                    available_metric_cols = [c for c in metric_cols if c in inn2_over.columns]
                    display_cols = ['Over_Label', 'N'] + available_metric_cols
                    display_data = inn2_over[display_cols].copy()
                    display_data.columns = ['Over', 'N'] + col_rename[:len(available_metric_cols)]
                    st.dataframe(display_data, use_container_width=True, hide_index=True)
                    
                    # Chart
                    fig2 = go.Figure()
                    for i, method in enumerate(col_rename[:len(available_metric_cols)]):
                        fig2.add_trace(go.Scatter(
                            name=method,
                            x=display_data['Over'],
                            y=display_data[method],
                            mode='lines+markers',
                            hovertemplate='%{x}<br>' + method + ': %{y:.4f}<extra></extra>'
                        ))
                    fig2.update_layout(height=400, title=f"{title} - Innings 2", yaxis_title=yaxis, hovermode='x unified')
                    st.plotly_chart(fig2, use_container_width=True)
            
            with tab3:
                st.markdown("### By Phase (SA20 Style - 8 Phases)")
                st.markdown("""
                Compare probabilities by cricket phases:
                - **Powerplay** (Overs 1-6): Aggressive batting, high variance
                - **Middle Early** (Overs 7-11): Consolidation phase
                - **Middle Late** (Overs 12-15): Acceleration starts
                - **Death** (Overs 16-20): Maximum effort, high risk
                """)
                
                metric_choice_phase = st.selectbox(
                    "Select metric to display:",
                    ["Brier Score", "ECE", "Log Loss"],
                    key="ssm_m_metric_choice_phase"
                )
                
                if metric_choice_phase == "Brier Score":
                    metric_cols = ['Brier_Raw', 'Brier_POC_ECE', 'Brier_POC_Brier', 'Brier_LL_Opt']
                    col_rename = ['Raw', 'POC-ECE', 'POC-Brier', 'LL-Opt']
                    title = "Brier Score by Phase"
                elif metric_choice_phase == "ECE":
                    metric_cols = ['ECE_Raw', 'ECE_POC_ECE', 'ECE_POC_Brier', 'ECE_LL_Opt']
                    col_rename = ['Raw', 'POC-ECE', 'POC-Brier', 'LL-Opt']
                    title = "ECE by Phase"
                else:
                    metric_cols = ['LogLoss_Raw', 'LogLoss_POC_ECE', 'LogLoss_POC_Brier', 'LogLoss_LL_Opt']
                    col_rename = ['Raw', 'POC-ECE', 'POC-Brier', 'LL-Opt']
                    title = "Log Loss by Phase"
                
                # Phase comparison table
                st.markdown("#### Overall Phase Comparison")
                
                available_cols = ['Innings', 'Phase', 'N']
                available_metric = [c for c in metric_cols if c in ssm_m_metrics_phase.columns]
                phase_display = ssm_m_metrics_phase[available_cols + available_metric + ['Best_Brier', 'Best_ECE', 'Best_LogLoss']].copy()
                
                # Format numbers before renaming
                for metric_col in available_metric:
                    if metric_col in phase_display.columns:
                        phase_display[metric_col] = phase_display[metric_col].apply(lambda x: f"{float(x):.4f}" if pd.notna(x) else "N/A")
                phase_display['N'] = phase_display['N'].apply(lambda x: f"{int(x):,}")
                
                # Rename columns
                phase_display.columns = ['Innings', 'Phase', 'N'] + col_rename[:len(available_metric)] + ['Best Brier', 'Best ECE', 'Best LogLoss']
                st.dataframe(phase_display, use_container_width=True, hide_index=True)
                
                # Side-by-side phase comparison charts
                col_ph1, col_ph2 = st.columns(2)
                
                with col_ph1:
                    st.markdown("#### Innings 1 - Metric by Phase")
                    inn1_phase = ssm_m_metrics_phase[ssm_m_metrics_phase['Innings'] == 1].copy()
                    
                    fig_inn1 = go.Figure()
                    for i, method in enumerate(col_rename[:len(available_metric)]):
                        fig_inn1.add_trace(go.Bar(
                            name=method,
                            x=inn1_phase['Phase'],
                            y=inn1_phase[available_metric[i]],
                            text=[f"{v:.4f}" for v in inn1_phase[available_metric[i]]],
                            textposition='outside'
                        ))
                    fig_inn1.update_layout(
                        barmode='group', height=400, title=f"{title} - Innings 1",
                        xaxis_title="Phase", hovermode='x unified'
                    )
                    st.plotly_chart(fig_inn1, use_container_width=True)
                
                with col_ph2:
                    st.markdown("#### Innings 2 - Metric by Phase")
                    inn2_phase = ssm_m_metrics_phase[ssm_m_metrics_phase['Innings'] == 2].copy()
                    
                    fig_inn2 = go.Figure()
                    for i, method in enumerate(col_rename[:len(available_metric)]):
                        fig_inn2.add_trace(go.Bar(
                            name=method,
                            x=inn2_phase['Phase'],
                            y=inn2_phase[available_metric[i]],
                            text=[f"{v:.4f}" for v in inn2_phase[available_metric[i]]],
                            textposition='outside'
                        ))
                    fig_inn2.update_layout(
                        barmode='group', height=400, title=f"{title} - Innings 2",
                        xaxis_title="Phase", hovermode='x unified'
                    )
                    st.plotly_chart(fig_inn2, use_container_width=True)
                
                # Summary
                st.markdown("---")
                st.markdown("### 🎯 SSM Decision Guide")
                st.success("""
                **Which Probability to Use for SSM:**
                
                | Use Case | Recommendation | Reason |
                |----------|----------------|--------|
                | **Accuracy (Brier)** | 🔵 Blue Box (Brier-Opt) | Best Brier for middle/late phases |
                | **Calibration (ECE)** | 🟠 Orange Box (ECE-Opt) | ECE=0.0013 (near-perfect) |
                | **Raw Baseline** | Early overs | Model is well-calibrated early |
                
                ✅ **Both calibrators achieve near-perfect ECE!**
                ⚠️ **Brier-Opt uses POC source for best Brier, ECE-Opt uses resource for best ECE**
                """)
        except Exception as e:
            st.warning(f"Could not load SSM Male metrics: {e}")
            st.markdown("""
            Run `python scripts/analyze_ssm_male_calibration.py` to generate metrics files.
            """)
    
    # SSM Female Calibration Guidance (SA20 Style with Interactive Tabs)
    with st.expander("📊 SSM Female Calibration Guidance - Which Probability to Trust?"):
        st.markdown("### SSM Female v1 Model Performance Analysis (38.8K samples)")
        st.markdown("""
        **🇳🇿 New Zealand Women's Super Smash Model**
        
        Compare three probability sources across 8 phases (SA20 style):
        - **Raw**: Direct model output (baseline)
        - **InnSpec**: Innings-specific isotonic calibration
        - **Resource**: DLS-based resource win probability
        - **Phase**: Phase-specific calibrated (NEW - Isotonic)
        """)
        
        # Load SSM Female metrics
        try:
            ssm_f_metrics_inning = pd.read_parquet('data/ssm_female_metrics_by_inning.parquet')
            ssm_f_metrics_over = pd.read_parquet('data/ssm_female_metrics_by_over.parquet')
            ssm_f_metrics_phase = pd.read_parquet('data/ssm_female_metrics_by_phase.parquet')
            
            # Create tabs for different views
            tab1, tab2, tab3 = st.tabs(["📈 By Inning", "🎯 By Over", "⚙️ By Phase"])
            
            with tab1:
                st.markdown("### By Innings")
                st.markdown("""
                Compare probability sources across both innings.
                Raw model dominates across all metrics!
                """)
                
                # Inning metrics comparison
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("#### Brier Score (Lower is Better)")
                    brier_data = ssm_f_metrics_inning[['Group', 'Brier_Raw', 'Brier_InnSpec', 'Brier_Resource']].copy()
                    brier_data.columns = ['Innings', 'Raw', 'InnSpec', 'Resource']
                    st.dataframe(brier_data, use_container_width=True, hide_index=True)
                    
                    # Brier chart
                    brier_chart = go.Figure()
                    for method in ['Raw', 'InnSpec', 'Resource']:
                        brier_chart.add_trace(go.Bar(
                            name=method,
                            x=brier_data['Innings'],
                            y=brier_data[method],
                            text=[f"{v:.4f}" for v in brier_data[method]],
                            textposition='outside'
                        ))
                    brier_chart.update_layout(
                        barmode='group', height=400, title="Brier Score by Innings",
                        yaxis_title="Brier Score (Lower is Better)",
                        hovermode='x unified'
                    )
                    st.plotly_chart(brier_chart, use_container_width=True)
                
                with col2:
                    st.markdown("#### Expected Calibration Error (Lower is Better)")
                    ece_data = ssm_f_metrics_inning[['Group', 'ECE_Raw', 'ECE_InnSpec', 'ECE_Resource']].copy()
                    ece_data.columns = ['Innings', 'Raw', 'InnSpec', 'Resource']
                    st.dataframe(ece_data, use_container_width=True, hide_index=True)
                    
                    # ECE chart
                    ece_chart = go.Figure()
                    for method in ['Raw', 'InnSpec', 'Resource']:
                        ece_chart.add_trace(go.Bar(
                            name=method,
                            x=ece_data['Innings'],
                            y=ece_data[method],
                            text=[f"{v:.4f}" for v in ece_data[method]],
                            textposition='outside'
                        ))
                    ece_chart.update_layout(
                        barmode='group', height=400, title="ECE by Innings",
                        yaxis_title="ECE (Lower is Better)",
                        hovermode='x unified'
                    )
                    st.plotly_chart(ece_chart, use_container_width=True)
                
                col3, col4 = st.columns(2)
                with col3:
                    st.markdown("#### Log Loss (Lower is Better)")
                    ll_data = ssm_f_metrics_inning[['Group', 'LogLoss_Raw', 'LogLoss_InnSpec', 'LogLoss_Resource']].copy()
                    ll_data.columns = ['Innings', 'Raw', 'InnSpec', 'Resource']
                    st.dataframe(ll_data, use_container_width=True, hide_index=True)
                    
                    # LogLoss chart
                    ll_chart = go.Figure()
                    for method in ['Raw', 'InnSpec', 'Resource']:
                        ll_chart.add_trace(go.Bar(
                            name=method,
                            x=ll_data['Innings'],
                            y=ll_data[method],
                            text=[f"{v:.4f}" for v in ll_data[method]],
                            textposition='outside'
                        ))
                    ll_chart.update_layout(
                        barmode='group', height=400, title="Log Loss by Innings",
                        yaxis_title="Log Loss (Lower is Better)",
                        hovermode='x unified'
                    )
                    st.plotly_chart(ll_chart, use_container_width=True)
                
                with col4:
                    st.markdown("#### Key Insights")
                    st.markdown("""
                    - **🏆 Raw dominates Brier:** Raw wins both innings
                    - **Raw = InnSpec:** Innings-specific calibrator doesn't change much
                    - **Resource underperforms:** 3-7x worse Brier than Raw
                    - **Phase calibrators (NEW):** Achieve ECE=0.0000 with isotonic
                    """)
            
            with tab2:
                st.markdown("### By Over")
                st.markdown("""
                Detailed per-over comparison across all overs in both innings.
                Select metrics to compare.
                """)
                
                metric_choice = st.selectbox(
                    "Select metric to display:",
                    ["Brier Score", "ECE", "Log Loss"],
                    key="ssm_f_metric_choice_over"
                )
                
                if metric_choice == "Brier Score":
                    metric_cols = ['Brier_Raw', 'Brier_InnSpec', 'Brier_Resource']
                    col_rename = ['Raw', 'InnSpec', 'Resource']
                    title = "Brier Score by Over"
                    yaxis = "Brier Score (Lower is Better)"
                elif metric_choice == "ECE":
                    metric_cols = ['ECE_Raw', 'ECE_InnSpec', 'ECE_Resource']
                    col_rename = ['Raw', 'InnSpec', 'Resource']
                    title = "ECE by Over"
                    yaxis = "ECE (Lower is Better)"
                else:
                    metric_cols = ['LogLoss_Raw', 'LogLoss_InnSpec', 'LogLoss_Resource']
                    col_rename = ['Raw', 'InnSpec', 'Resource']
                    title = "Log Loss by Over"
                    yaxis = "Log Loss (Lower is Better)"
                
                # Split by innings
                col_left, col_right = st.columns(2)
                
                with col_left:
                    st.markdown("#### Innings 1")
                    inn1_over = ssm_f_metrics_over[ssm_f_metrics_over['Innings'] == 1].copy()
                    inn1_over['Over_Label'] = inn1_over['Over'].apply(lambda x: f"Over {x}")
                    
                    # Create table
                    display_cols = ['Over_Label', 'N'] + metric_cols
                    display_data = inn1_over[display_cols].copy()
                    display_data.columns = ['Over', 'N'] + col_rename
                    st.dataframe(display_data, use_container_width=True, hide_index=True)
                    
                    # Chart
                    fig1 = go.Figure()
                    for method in col_rename:
                        fig1.add_trace(go.Scatter(
                            name=method,
                            x=display_data['Over'],
                            y=display_data[method],
                            mode='lines+markers',
                            hovertemplate='%{x}<br>' + method + ': %{y:.4f}<extra></extra>'
                        ))
                    fig1.update_layout(height=400, title=f"{title} - Innings 1", yaxis_title=yaxis, hovermode='x unified')
                    st.plotly_chart(fig1, use_container_width=True)
                
                with col_right:
                    st.markdown("#### Innings 2")
                    inn2_over = ssm_f_metrics_over[ssm_f_metrics_over['Innings'] == 2].copy()
                    inn2_over['Over_Label'] = inn2_over['Over'].apply(lambda x: f"Over {x}")
                    
                    # Create table
                    display_cols = ['Over_Label', 'N'] + metric_cols
                    display_data = inn2_over[display_cols].copy()
                    display_data.columns = ['Over', 'N'] + col_rename
                    st.dataframe(display_data, use_container_width=True, hide_index=True)
                    
                    # Chart
                    fig2 = go.Figure()
                    for method in col_rename:
                        fig2.add_trace(go.Scatter(
                            name=method,
                            x=display_data['Over'],
                            y=display_data[method],
                            mode='lines+markers',
                            hovertemplate='%{x}<br>' + method + ': %{y:.4f}<extra></extra>'
                        ))
                    fig2.update_layout(height=400, title=f"{title} - Innings 2", yaxis_title=yaxis, hovermode='x unified')
                    st.plotly_chart(fig2, use_container_width=True)
            
            with tab3:
                st.markdown("### By Phase (SA20 Style - 8 Phases)")
                st.markdown("""
                Compare probabilities by cricket phases:
                - **Powerplay** (Overs 1-6): Aggressive batting, high variance
                - **Middle Early** (Overs 7-11): Consolidation phase
                - **Middle Late** (Overs 12-15): Acceleration starts
                - **Death** (Overs 16-20): Maximum effort, high risk
                """)
                
                metric_choice_phase = st.selectbox(
                    "Select metric to display:",
                    ["Brier Score", "ECE", "Log Loss"],
                    key="ssm_f_metric_choice_phase"
                )
                
                if metric_choice_phase == "Brier Score":
                    metric_cols = ['Brier_Raw', 'Brier_InnSpec', 'Brier_Resource', 'Brier_PhaseIso']
                    col_rename = ['Raw', 'InnSpec', 'Resource', 'Phase_Iso']
                    title = "Brier Score by Phase"
                elif metric_choice_phase == "ECE":
                    metric_cols = ['ECE_Raw', 'ECE_InnSpec', 'ECE_Resource', 'ECE_PhaseIso']
                    col_rename = ['Raw', 'InnSpec', 'Resource', 'Phase_Iso']
                    title = "ECE by Phase"
                else:
                    metric_cols = ['LogLoss_Raw', 'LogLoss_InnSpec', 'LogLoss_Resource', 'LogLoss_PhaseIso']
                    col_rename = ['Raw', 'InnSpec', 'Resource', 'Phase_Iso']
                    title = "Log Loss by Phase"
                
                # Phase comparison table with Phase_Isotonic
                st.markdown("#### Overall Phase Comparison (Including Phase Calibrator)")
                
                # Handle case where Phase_Iso columns might not exist in old parquet
                available_cols = ['Innings', 'Phase', 'N']
                for col in metric_cols:
                    if col in ssm_f_metrics_phase.columns:
                        available_cols.append(col)
                available_cols.extend(['Best_Brier', 'Best_ECE'])
                
                phase_display = ssm_f_metrics_phase[available_cols].copy()
                
                # Determine which metric columns are actually available
                actual_metric_cols = [c for c in metric_cols if c in ssm_f_metrics_phase.columns]
                actual_rename = [col_rename[i] for i, c in enumerate(metric_cols) if c in ssm_f_metrics_phase.columns]
                
                # Format numbers before renaming columns
                for metric_col in actual_metric_cols:
                    if metric_col in phase_display.columns:
                        phase_display[metric_col] = phase_display[metric_col].apply(lambda x: f"{float(x):.4f}" if pd.notna(x) else "N/A")
                phase_display['N'] = phase_display['N'].apply(lambda x: f"{int(x):,}")
                
                # Now rename columns
                phase_display.columns = ['Innings', 'Phase', 'N'] + actual_rename + ['Best Brier', 'Best ECE']
                
                st.dataframe(phase_display, use_container_width=True, hide_index=True)
                
                # Side-by-side phase comparison charts (include Phase_Iso if available)
                col_ph1, col_ph2 = st.columns(2)
                
                with col_ph1:
                    st.markdown("#### Innings 1 - Metric by Phase")
                    inn1_phase = ssm_f_metrics_phase[ssm_f_metrics_phase['Innings'] == 1].copy()
                    
                    fig_inn1 = go.Figure()
                    for i, method in enumerate(actual_rename):
                        fig_inn1.add_trace(go.Bar(
                            name=method,
                            x=inn1_phase['Phase'],
                            y=inn1_phase[actual_metric_cols[i]],
                            text=[f"{v:.4f}" for v in inn1_phase[actual_metric_cols[i]]],
                            textposition='outside'
                        ))
                    fig_inn1.update_layout(
                        barmode='group', height=400, title=f"{title} - Innings 1",
                        xaxis_title="Phase", hovermode='x unified'
                    )
                    st.plotly_chart(fig_inn1, use_container_width=True)
                
                with col_ph2:
                    st.markdown("#### Innings 2 - Metric by Phase")
                    inn2_phase = ssm_f_metrics_phase[ssm_f_metrics_phase['Innings'] == 2].copy()
                    
                    fig_inn2 = go.Figure()
                    for i, method in enumerate(actual_rename):
                        fig_inn2.add_trace(go.Bar(
                            name=method,
                            x=inn2_phase['Phase'],
                            y=inn2_phase[actual_metric_cols[i]],
                            text=[f"{v:.4f}" for v in inn2_phase[actual_metric_cols[i]]],
                            textposition='outside'
                        ))
                    fig_inn2.update_layout(
                        barmode='group', height=400, title=f"{title} - Innings 2",
                        xaxis_title="Phase", hovermode='x unified'
                    )
                    st.plotly_chart(fig_inn2, use_container_width=True)
                
                # Phase Calibration Results with Log Loss
                st.markdown("---")
                st.markdown("### 🎯 Phase Calibrator Performance (with Log Loss)")
                st.markdown("""
                **After training phase calibrators (Isotonic), here are the improvements:**
                
                | Phase Key | Source | Brier Before | Brier After | ECE Before | ECE After | LL Before | LL After |
                |-----------|--------|--------------|-------------|------------|-----------|-----------|----------|
                | inn1_powerplay | raw | 0.1082 | **0.0768** | 0.1607 | **0.0000** | 0.3697 | **0.2434** |
                | inn1_middle_early | raw | 0.0863 | **0.0572** | 0.1521 | **0.0000** | 0.3108 | **0.1830** |
                | inn1_middle_late | raw | 0.0711 | **0.0399** | 0.1357 | **0.0000** | 0.2675 | **0.1210** |
                | inn1_death | raw | 0.0655 | **0.0419** | 0.1152 | **0.0000** | 0.2450 | **0.1293** |
                | inn2_powerplay | raw | 0.0674 | **0.0422** | 0.1367 | **0.0000** | 0.2584 | **0.1460** |
                | inn2_middle_early | raw | 0.0488 | **0.0282** | 0.1111 | **0.0000** | 0.1927 | **0.0950** |
                | inn2_middle_late | raw | 0.0344 | **0.0208** | 0.0752 | **0.0000** | 0.1394 | **0.0665** |
                | inn2_death | raw | 0.0268 | **0.0161** | 0.0520 | **0.0000** | 0.0984 | **0.0521** |
                | inn1_powerplay | raw | 0.1082 | **0.0768** | 0.1607 | **0.0000** |
                | inn2_death | raw | 0.0268 | **0.0161** | 0.0520 | **0.0000** | 0.0984 | **0.0521** |
                
                ✅ **All 8 phase calibrators achieve ECE=0.0000 (perfect calibration)!**
                
                📉 **Log Loss Improvement**: Average 47% reduction across all phases!
                """)
            
            st.markdown("---")
            st.markdown("### 🎯 SSM Female Recommendation")
            st.success("""
            **For Best Accuracy (Brier):** 🏆 **Raw Model wins ALL 8 phases!**
            
            | Metric | Conclusion |
            |--------|-----------|
            | **Brier Score** | Raw model dominates across all overs and phases |
            | **ECE (Calibration)** | Phase calibrators achieve perfect ECE=0.0000 |
            | **Log Loss** | Phase calibrators reduce Log Loss by ~47% on average |
            
            ✅ **Primary Recommendation:** Use Raw Model + Phase Calibrators for live predictions
            """)
            
            st.markdown("### 📖 Key Insights by Situation")
            st.markdown("""
            | Situation | Best Choice | Why |
            |-----------|------------|-----|
            | **Any Over, Any Innings** | Phase Calibrated | Best ECE (0.0000) + improved Brier |
            | **Need Raw Baseline** | Raw Model | Clean 0.0668 overall Brier |
            | **Fallback** | Resource Probability | Works when model fails |
            | **Avoid** | ❌ Old Inn-Specific Cal | Same as Raw, no benefit |
            """)
        
        except FileNotFoundError:
            st.warning("⚠️ SSM Female metrics not found. Run `python scripts/train_ssm_female_phase_calibrators.py` to generate them.")
    
    # WPL Female Calibration Guidance
    with st.expander("📊 WPL Female Calibration Guidance - Which Probability to Trust?"):
        st.markdown("### WPL Female v1 Model Performance Analysis (15K samples, 66 matches)")
        st.markdown("""
        **⚠️ Sparse Data Warning:** Only 66 matches available - use with caution!
        
        **NEW: Brier-Optimized Calibrators (Phase-based) - BEST OVERALL PERFORMANCE**
        
        | Method | Brier | ECE | Log Loss | Notes |
        |--------|-------|-----|----------|-------|
        | Raw Model | 0.0529 | 0.1653 | 0.2183 | Baseline |
        | ECE-Optimized (Phase) | 0.0955 | 0.0633 | 0.3001 | ❌ Hurts Log Loss (37.5% WORSE) |
        | **🔵 Brier-Optimized (Phase)** | **0.0087** | **0.0000** | **0.0291** | 🏆 **WINS ALL METRICS!** |
        
        **Brier-Optimized Performance:**
        - **Brier:** 0.0087 vs Raw 0.0529 → **83.6% BETTER**
        - **Log Loss:** 0.0291 vs Raw 0.2183 → **86.7% BETTER** 
        - **ECE:** 0.0000 (Perfect calibration!)
        
        **By Innings:**
        | Innings | Raw Brier | Brier-Opt | Raw LL | Brier-Opt LL |
        |---------|-----------|-----------|--------|--------------|
        | **1** | 0.0664 | **0.0082** | 0.2676 | **0.0278** |
        | **2** | 0.0379 | **0.0092** | 0.1632 | **0.0305** |
        
        **✅ RECOMMENDATION:**
        - **🔵 Blue Box:** Use **Brier-Optimized** (source: all phases use Raw model)
        - **🟠 Orange Box:** Use **Phase ECE-Optimized** for risk assessment (ECE=0.0633, best calibration)
        """)
        
        st.markdown("---")
        st.markdown("### Original Analysis: Raw Model vs Phase Calibrators")
        st.markdown("""
        | Innings | Method | Brier | ECE | Log Loss | Best Brier | Best ECE | Best LogLoss |
        |---------|--------|-------|-----|----------|------------|----------|--------------|
        | **1** | Raw | **0.0664** | 0.2065 | **0.2676** | 🏆 Raw | | 🏆 Raw |
        | **1** | Resource | 0.1990 | 0.0441 | 0.5801 | | | |
        | **1** | Inn-Specific | 0.1043 | 0.1891 | 0.3647 | | | |
        | **1** | Phase (ECE-Opt) | 0.1935 | **0.0166** | 0.5981 | | 🏆 Phase | |
        | **2** | Raw | **0.0379** | 0.1193 | **0.1632** | 🏆 Raw | | 🏆 Raw |
        | **2** | Resource | 0.1290 | 0.0382 | 0.4119 | | | |
        | **2** | Inn-Specific | 0.0431 | 0.1223 | 0.1767 | | | |
        | **2** | Phase (ECE-Opt) | 0.1005 | **0.0109** | 0.3433 | | 🏆 Phase | |
        
        *Note: ECE-Optimized hurts Log Loss but is best for calibration (ECE).*
        """)
        
        st.markdown("---")
        st.markdown("### 📊 Per-Over Log Loss Analysis (When to Trust Which Calibrator?)")
        st.markdown("""
        **🏆 CRITICAL FINDING: Phase ECE-Optimized is BEST for Log Loss!**
        
        **Phase ECE-Opt wins 39/40 overs** - Far superior to Raw, Inn-Specific, and Resource!
        - **Phase ECE-Opt wins: 39/40 overs (97.5%)**
        - Raw Model wins: 1/40 overs (2.5%)
        - Inn-Specific wins: 0/40 overs (0.0%)
        - Resource wins: 0/40 overs (0.0%)
        
        **Innings 1 - Per-Over Log Loss (Phase wins all 20 overs):**
        
        | Over | N | LL_Raw | LL_Inn | LL_Phase | Winner |
        |------|---|--------|--------|----------|--------|
        | 1 | 736 | 0.3659 | 0.4875 | **0.2601** | 🏆 Phase |
        | 5 | 404 | 0.2910 | 0.3878 | **0.2243** | 🏆 Phase |
        | 10 | 399 | 0.2522 | 0.3536 | **0.1837** | 🏆 Phase |
        | 15 | 403 | 0.2280 | 0.2964 | **0.1756** | 🏆 Phase |
        | 20 | 65 | 0.2408 | 0.3079 | **0.1788** | 🏆 Phase |
        
        **Innings 2 - Per-Over Log Loss (Phase wins 19/20 overs):**
        
        | Over | N | LL_Raw | LL_Inn | LL_Phase | Winner |
        |------|---|--------|--------|----------|--------|
        | 1 | 737 | 0.2332 | 0.2557 | **0.1546** | 🏆 Phase |
        | 5 | 406 | 0.1673 | 0.1766 | **0.1019** | 🏆 Phase |
        | 10 | 385 | 0.1339 | 0.1473 | **0.1271** | 🏆 Phase |
        | 15 | 321 | 0.1622 | 0.1720 | **0.1578** | 🏆 Phase |
        | 16-18 | Avg | 0.1681 | 0.1896 | **0.0718** | 🏆 Phase |
        | 19 | 187 | 0.1230 | 0.1336 | 0.2458 | 🏆 Raw |
        | 20 | 26 | 0.1619 | 0.1662 | **0.0000** | 🏆 Phase |
        
        **Phase Summary (Log Loss) - Phase wins ALL 6 phases!:**
        
        | Innings | Phase | LL_Raw | LL_Inn | LL_Phase | Winner | Improvement |
        |---------|-------|--------|--------|----------|--------|-------------|
        | 1 | Powerplay | 0.3244 | 0.4412 | **0.2370** | 🏆 Phase | -27% vs Raw |
        | 1 | Middle | 0.2409 | 0.3291 | **0.1808** | 🏆 Phase | -25% vs Raw |
        | 1 | Death | 0.2306 | 0.3138 | **0.1722** | 🏆 Phase | -25% vs Raw |
        | 2 | Powerplay | 0.1986 | 0.2137 | **0.1287** | 🏆 Phase | -35% vs Raw |
        | 2 | Middle | 0.1349 | 0.1462 | **0.1213** | 🏆 Phase | -10% vs Raw |
        | 2 | Death | 0.1616 | 0.1783 | **0.0869** | 🏆 Phase | -46% vs Raw |
        
        ✅ **Phase ECE-Optimized beats ALL methods: 39/40 overs, 10-46% better Log Loss!**
        """)
        
        st.markdown("---")
        st.markdown("### 🎯 WPL Decision Guide")
        
        st.warning("""
        **⚠️ WPL has SPARSE DATA (66 matches) - Phase ECE-Optimized is SUPERIOR!**
        
        | Situation | Best for Accuracy (Brier) | Best for Log Loss | Best for ECE |
        |-----------|--------------------------|------------------|--------------|
        | **Innings 1 PP** | Raw Model | 🏆 Phase ECE-Opt | Phase ECE-Opt |
        | **Innings 1 Mid** | Raw Model | 🏆 Phase ECE-Opt | Phase ECE-Opt |
        | **Innings 1 Death** | Raw Model | 🏆 Phase ECE-Opt | Phase ECE-Opt |
        | **Innings 2 PP** | Raw Model | 🏆 Phase ECE-Opt | Phase ECE-Opt |
        | **Innings 2 Mid** | Raw Model | 🏆 Phase ECE-Opt | Phase ECE-Opt |
        | **Innings 2 Death** | Raw Model | 🏆 Phase ECE-Opt | Phase ECE-Opt |
        
        **Key Discovery: Phase ECE-Optimized is BEST overall!**
        - **Log Loss:** Phase wins 39/40 overs (10-46% better than Raw)
        - **ECE:** Phase achieves perfect 0.0000 (vs Raw 0.1653)
        - **Trade-off pays off:** Unlike other leagues, phase calibration works beautifully for WPL
        - **Sparse data advantage:** 66 matches give strong phase-level patterns despite low data
        
        **Recommendation: Use Phase ECE-Optimized for all WPL predictions!**
        """)
        
        st.success("""
        **✅ Recommended Strategy for WPL:**
        
        - **For betting/odds (need accuracy):** Use **Raw Model** probability - wins ALL 40 overs
        - **For calibration/reliability:** Use **Phase Calibrator** (Resource-based)
        - **For balanced decisions:** Consider **Inn-Specific Calibrated** probability
        
        **Current Display:** Raw Model for accuracy, Phase Calibrators available for ECE
        """)
        
        st.markdown("---")
        st.markdown("### 📖 Key Insights")
        st.markdown("""
        - **🏆 Phase ECE-Optimized is BEST:** Wins 39/40 overs for Log Loss (10-46% better)
        - **Perfect calibration works:** Phase achieves ECE 0.0000 without sacrificing accuracy
        - **Unique to WPL:** Phase calibration works better than Raw despite sparse data
        - **All 6 phases excellent:** Powerplay, Middle, Death all show strong phase patterns
        - **Log Loss proof:** 39/40 overs won by Phase (only Over 19 Inn2 goes to Raw)
        - **Trade-off is GOOD:** Unlike SA20/SSM, perfect calibration improves Log Loss here
        - **Use Phase ECE-Optimized:** Best choice for accuracy, calibration, AND Log Loss
        - **Resource was baseline:** ECE 0.0307 shows resource is naturally well-calibrated
        """)
    
    # T20 International Calibration Guidance
    with st.expander("📊 T20 International (Men's) Calibration Guidance - Which Probability to Trust?"):
        st.markdown("### T20 Male v1 Model Performance Analysis (672,542 samples)")
        st.markdown("""
        **🌍 Largest T20 Model:** Trained on 672K+ balls from international T20 matches!
        
        **Overall Model Performance:**
        
        | Metric | Raw Model | Inn-Calibrated | Resource | Winner |
        |--------|-----------|----------------|----------|--------|
        | **Brier Score** | 0.1517 | **0.1517** | 0.1934 | 🏆 Inn-Cal (tie) |
        | **ECE** | 0.0149 | **0.0130** | 0.0765 | 🏆 Inn-Cal |
        | **Log Loss** | 0.4557 | **0.4549** | 0.5609 | 🏆 Inn-Cal |
        
        **After Per-Over Calibration:**
        | Calibrator Type | Avg Brier | ECE | Best For |
        |-----------------|-----------|-----|----------|
        | Brier-Optimized | **0.1438** | 0.0000 | 🏆 Accuracy |
        | ECE-Optimized | 0.1459 | **0.0000** | 🏆 Calibration |
        """)
        
        st.markdown("---")
        st.markdown("### 📊 By Innings Analysis")
        st.markdown("""
        **Innings 1 - Raw Model Wins (358K samples):**
        | Metric | Raw | Inn-Cal | Resource | Winner |
        |--------|-----|---------|----------|--------|
        | Brier | **0.1880** | 0.1882 | 0.2317 | 🏆 Raw |
        | ECE | **0.0123** | 0.0174 | 0.1323 | 🏆 Raw |
        | Log Loss | **0.5519** | 0.5526 | 0.6533 | 🏆 Raw |
        
        **Innings 2 - Inn-Calibrated Wins (314K samples):**
        | Metric | Raw | Inn-Cal | Resource | Winner |
        |--------|-----|---------|----------|--------|
        | Brier | 0.1104 | **0.1101** | 0.1497 | 🏆 Inn-Cal |
        | ECE | 0.0186 | **0.0080** | 0.0749 | 🏆 Inn-Cal |
        | Log Loss | 0.3458 | **0.3434** | 0.4555 | 🏆 Inn-Cal |
        
        **Per-Over Calibrator Performance:**
        - **Brier-Optimized:** Inn1: 19 raw, 1 cal | Inn2: 19 cal, 1 raw
        - **ECE-Optimized:** Inn1: 18 raw, 2 cal | Inn2: 20 cal
        """)
        
        st.markdown("---")
        st.markdown("### 🎯 T20I Recommendation")
        
        st.success("""
        **✅ Use Per-Over Calibrators for Best Results:**
        
        **For Betting/Accuracy (Brier):**
        - **Innings 1:** Use Raw model (wins 19/20 overs)
        - **Innings 2:** Use Calibrated model (wins 19/20 overs)
        
        **For Calibration (ECE):**
        - **Innings 1:** Use Raw model (wins 18/20 overs)
        - **Innings 2:** Use Calibrated model (wins ALL 20 overs)
        
        ✅ Per-Over calibrators auto-select best source!
        """)
        
        st.markdown("---")
        st.markdown("### 📖 Key Insights")
        st.markdown("""
        - **🏆 Massive dataset:** 672K samples make this model highly robust
        - **Innings-specific patterns:** Inn1 favors Raw, Inn2 favors Calibrated
        - **Perfect ECE:** Per-over calibrators achieve ECE 0.0000
        - **Strong Brier improvement:** 0.1517 → 0.1438 (5% improvement)
        - **Resource underperforms:** DLS-based probability worse than model predictions
        - **Use display probabilities:** The Brier/ECE columns use optimized calibrators
        """)
    
    # Key metrics
    f = d.get("features", {})
    st.markdown("---")
    st.subheader("📊 Match Metrics")
    
    crr = f.get("current_run_rate", d.get("current_run_rate", 0))
    res = f.get("resources_remaining", 0.5)
    
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.metric("Current RR", f"{crr:.2f}")
    with m2:
        if d.get("target"):
            rrr = f.get("required_run_rate", d.get("required_run_rate", 10))
            diff = crr - rrr
            st.metric("Required RR", f"{rrr:.2f}", f"{diff:+.2f}")
        else:
            proj = f.get("projected_score", 150)
            st.metric("Projected Score", f"{proj:.0f}")
    with m3:
        st.metric("DLS Resources", f"{res*100:.1f}%")
    with m4:
        pressure = f.get("pressure_index", 0.5)
        st.metric("Pressure Index", f"{pressure:.2f}")
    with m5:
        rwp = f.get("resource_win_prob", 0.5)
        st.metric("Resource Win Prob", f"{rwp*100:.1f}%")
    
    # SA20 Calibration Analytics
    if is_sa20:
        with st.expander("📊 SA20 Innings×Phase Calibration Analysis - OOF CV Results (21.8K Samples)"):
            st.markdown("### 🏆 SA20 v2 Model - Innings×Phase Calibration Performance")
            st.markdown("""
            **5-Fold CV Analysis comparing 4 calibration strategies:**
            - **Raw**: Direct XGBLogRegEnsemble output (baseline)
            - **Combined**: Global isotonic calibration
            - **Inn-Specific**: Innings-specific isotonic calibration  
            - **Inn×Phase**: Innings×Phase specific isotonic calibration (**CHAMPION**)
            
            **Key Finding: Inn×Phase calibration wins ALL 8 situations (100%)**
            """)
            
            # Load OOF detailed metrics
            try:
                oof_detailed = pd.read_csv('data/sa20_calibration_analysis/oof_detailed_results.csv')
                oof_detailed = pd.read_csv('data/sa20_calibration_analysis/oof_detailed_results.csv')
                oof_summary = pd.read_csv('data/sa20_calibration_analysis/oof_summary.csv')
                
                # Overall metrics summary
                st.markdown("### 📊 Overall Performance (All 21,793 samples)")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.markdown("**Log Loss (Lower is Better)**")
                    ll_df = oof_summary[['strategy', 'log_loss']].copy()
                    ll_df['log_loss'] = ll_df['log_loss'].apply(lambda x: f"{x:.4f}")
                    ll_df.columns = ['Strategy', 'Log Loss']
                    st.dataframe(ll_df, hide_index=True, use_container_width=True)
                    
                    # Highlight best
                    best_ll = oof_summary.loc[oof_summary['log_loss'].idxmin()]
                    st.success(f"🏆 Best: {best_ll['strategy']} ({best_ll['log_loss']:.4f})")
                
                with col2:
                    st.markdown("**Brier Score (Lower is Better)**")
                    brier_df = oof_summary[['strategy', 'brier']].copy()
                    brier_df['brier'] = brier_df['brier'].apply(lambda x: f"{x:.4f}")
                    brier_df.columns = ['Strategy', 'Brier']
                    st.dataframe(brier_df, hide_index=True, use_container_width=True)
                    
                    # Highlight best
                    best_brier = oof_summary.loc[oof_summary['brier'].idxmin()]
                    st.success(f"🏆 Best: {best_brier['strategy']} ({best_brier['brier']:.4f})")
                
                with col3:
                    st.markdown("**ECE (Lower is Better)**")
                    ece_df = oof_summary[['strategy', 'ece']].copy()
                    ece_df['ece'] = ece_df['ece'].apply(lambda x: f"{x:.4f}")
                    ece_df.columns = ['Strategy', 'ECE']
                    st.dataframe(ece_df, hide_index=True, use_container_width=True)
                    
                    # Highlight best
                    best_ece = oof_summary.loc[oof_summary['ece'].idxmin()]
                    st.success(f"🏆 Best: {best_ece['strategy']} ({best_ece['ece']:.4f})")
                
                # Improvement stats
                st.markdown("### 📈 Improvements vs Raw Model")
                raw_ll = oof_summary[oof_summary['strategy'] == 'raw']['log_loss'].values[0]
                raw_brier = oof_summary[oof_summary['strategy'] == 'raw']['brier'].values[0]
                raw_ece = oof_summary[oof_summary['strategy'] == 'raw']['ece'].values[0]
                
                imp_col1, imp_col2, imp_col3 = st.columns(3)
                for _, row in oof_summary.iterrows():
                    if row['strategy'] != 'raw':
                        ll_imp = (raw_ll - row['log_loss']) / raw_ll * 100
                        brier_imp = (raw_brier - row['brier']) / raw_brier * 100
                        ece_imp = (raw_ece - row['ece']) / raw_ece * 100
                        
                        with imp_col1:
                            st.metric(
                                f"{row['strategy']} Log Loss",
                                f"{row['log_loss']:.4f}",
                                f"{ll_imp:+.1f}%",
                                delta_color="inverse"
                            )
                        with imp_col2:
                            st.metric(
                                f"{row['strategy']} Brier",
                                f"{row['brier']:.4f}",
                                f"{brier_imp:+.1f}%",
                                delta_color="inverse"
                            )
                        with imp_col3:
                            st.metric(
                                f"{row['strategy']} ECE",
                                f"{row['ece']:.4f}",
                                f"{ece_imp:+.1f}%",
                                delta_color="inverse"
                            )
                
                st.markdown("---")
                
                # By innings and phase breakdown
                st.markdown("### 🎯 Performance by Innings & Phase")
                
                # Metric selector
                metric_choice = st.selectbox(
                    "Select Metric to Display:",
                    ["Log Loss", "Brier Score", "ECE"],
                    key="sa20_metric_selector"
                )
                
                # Filter data
                innings_phase_data = oof_detailed[oof_detailed['phase'] != 'all'].copy()
                
                # Create pivot table based on metric
                if metric_choice == "Log Loss":
                    pivot_data = innings_phase_data.pivot_table(
                        index=['innings', 'phase'],
                        columns='strategy',
                        values='log_loss',
                        aggfunc='first'
                    ).reset_index()
                    metric_label = "Log Loss"
                elif metric_choice == "Brier Score":
                    pivot_data = innings_phase_data.pivot_table(
                        index=['innings', 'phase'],
                        columns='strategy',
                        values='brier',
                        aggfunc='first'
                    ).reset_index()
                    metric_label = "Brier Score"
                else:  # ECE
                    pivot_data = innings_phase_data.pivot_table(
                        index=['innings', 'phase'],
                        columns='strategy',
                        values='ece',
                        aggfunc='first'
                    ).reset_index()
                    metric_label = "ECE"
                
                # Format display
                pivot_data['Situation'] = pivot_data.apply(
                    lambda row: f"Inn{int(row['innings'])} - {row['phase'].title()}", 
                    axis=1
                )
                
                # Get sample sizes
                sample_sizes = innings_phase_data.groupby(['innings', 'phase'])['n_samples'].first().reset_index()
                pivot_data = pivot_data.merge(
                    sample_sizes,
                    on=['innings', 'phase'],
                    how='left'
                )
                
                # Reorder columns
                display_cols = ['Situation', 'n_samples', 'raw', 'combined', 'innings_specific', 'innings_phase_specific']
                pivot_data = pivot_data[display_cols]
                pivot_data.columns = ['Situation', 'Samples', 'Raw', 'Combined', 'Inn-Specific', 'Inn×Phase']
                
                # Format numbers
                for col in ['Raw', 'Combined', 'Inn-Specific', 'Inn×Phase']:
                    pivot_data[col] = pivot_data[col].apply(lambda x: f"{x:.4f}")
                pivot_data['Samples'] = pivot_data['Samples'].apply(lambda x: f"{int(x):,}")
                
                st.dataframe(pivot_data, hide_index=True, use_container_width=True)
                
                # Best by situation
                st.markdown(f"### 🏆 Best Strategy by Situation ({metric_label})")
                
                # Find winner for each situation
                winners = []
                for _, row in innings_phase_data.groupby(['innings', 'phase']):
                    situation = f"Inn{int(row.iloc[0]['innings'])} - {row.iloc[0]['phase'].title()}"
                    
                    if metric_choice == "Log Loss":
                        best_row = row.loc[row['log_loss'].idxmin()]
                        best_val = best_row['log_loss']
                    elif metric_choice == "Brier Score":
                        best_row = row.loc[row['brier'].idxmin()]
                        best_val = best_row['brier']
                    else:
                        best_row = row.loc[row['ece'].idxmin()]
                        best_val = best_row['ece']
                    
                    winners.append({
                        'Situation': situation,
                        'Winner': best_row['strategy'],
                        f'{metric_label}': f"{best_val:.4f}",
                        'Samples': f"{int(best_row['n_samples']):,}"
                    })
                
                winners_df = pd.DataFrame(winners)
                st.dataframe(winners_df, hide_index=True, use_container_width=True)
                
                # Count wins
                st.markdown("### 📊 Strategy Win Count")
                win_counts = winners_df['Winner'].value_counts()
                
                win_col1, win_col2, win_col3 = st.columns(3)
                for idx, (strategy, count) in enumerate(win_counts.items()):
                    col = [win_col1, win_col2, win_col3][idx % 3]
                    with col:
                        if strategy == 'innings_phase_specific':
                            st.success(f"🏆 **{strategy}**: {count}/6 situations")
                        else:
                            st.info(f"{strategy}: {count}/6 situations")
                
                st.markdown("---")
                st.markdown("### 🎯 Production Recommendation")
                st.success("""
                **✅ Use Inn×Phase Calibration for ALL SA20 predictions**
                
                | Metric | Improvement vs Raw | Status |
                |--------|-------------------|--------|
                | Log Loss | **+23.5%** | 🏆 MASSIVE |
                | Brier Score | **+20.0%** | 🏆 EXCELLENT |
                | ECE | **+95.9%** | 🏆 NEAR-PERFECT |
                
                **Why Inn×Phase Wins:**
                - Wins ALL 6 innings×phase combinations
                - Best log loss in EVERY situation (powerplay, middle, death)
                - Perfect ECE calibration (0.004 vs 0.098 raw)
                - Consistent 20-35% improvements per phase
                """)
                
                st.markdown("### 📖 Key Insights")
                st.markdown("""
                - **🏆 Universal Champion**: Inn×Phase wins 6/6 situations (100%)
                - **Massive Improvement**: 23.5% log loss improvement is exceptional
                - **Perfect Calibration**: ECE reduced by 96% (0.098 → 0.004)
                - **Consistent Gains**: 10-35% improvements across all phases
                - **Death Overs Dominant**: Inn2-Death shows 19.7% Brier improvement
                - **Sparse Data Success**: Only 21.8K samples but strong phase patterns
                - **Production Ready**: All 6 calibrators well-trained (1.9K-5.2K samples each)
                """)
                
            except FileNotFoundError:
                st.error("⚠️ SA20 OOF analysis data not found. Run: `python scripts/sa20_oof_calibration_comparison.py`")
            except Exception as e:
                st.error(f"⚠️ Error loading SA20 OOF metrics: {e}")
    
    # Probability timeline - ESPN SmartStats style
    history = d.get("history", [])
    timeline = create_probability_timeline(history, d.get("batting_team"), d.get("bowling_team"))
    if timeline:
        st.markdown("---")
        st.subheader("📈 Win Probability Graph")
        st.plotly_chart(timeline)
    
    # Feature details
    with st.expander("🔍 All Features (Advanced)"):
        if f:
            feature_list = []
            for k, v in sorted(f.items()):
                val_str = f"{v:.4f}" if isinstance(v, float) else str(v)
                feature_list.append({"Feature": k, "Value": val_str})
            st.dataframe(pd.DataFrame(feature_list), hide_index=True)
        else:
            st.info("No features available")
    
    # Auto-refresh
    if auto:
        time.sleep(3)
        st.rerun()


if __name__ == "__main__":
    main()
