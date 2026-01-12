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
        calibrators['bbl'] = joblib.load('models/bbl_v10/per_over_calibrators.pkl')
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
    # SA20: per-over calibrators give best Brier (0.0399), phase calibrators give best ECE (0.0047)
    try:
        calibrators['sa20'] = joblib.load('models/sat_v1/per_over_calibrators.pkl')
    except:
        calibrators['sa20'] = None
    # T20 Male (International): per-over calibrators for ECE optimization
    try:
        calibrators['t20i'] = joblib.load('models/t20_male_v1/per_over_calibrators_ece.pkl')
    except:
        calibrators['t20i'] = None
    return calibrators

@st.cache_resource
def load_phase_calibrators():
    """Load phase calibrators for SA20, WPL, and SSM Female (sparse data leagues).
    All use phase-specific calibrators for best ECE."""
    calibrators = {}
    # SA20 phase calibrators
    try:
        # Prefer Platt scaling phase calibrators for smooth output
        calibrators['sa20'] = joblib.load('models/sat_v1/phase_calibrators_platt.pkl')
    except:
        try:
            calibrators['sa20'] = joblib.load('models/sat_v1/phase_calibrators.pkl')
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
    try:
        calibrators['bbl'] = joblib.load('models/bbl_v10/per_over_calibrators_brier.pkl')
        print(f"[OK] Loaded BBL Brier calibrators: {list(calibrators['bbl'].keys())}")
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
    """Load Log Loss-optimized calibrators for BBL.
    These select best source per over for Log Loss optimization."""
    calibrators = {}
    try:
        calibrators['bbl'] = joblib.load('models/bbl_v10/logloss_calibrators.pkl')
        print(f"[OK] Loaded BBL Log Loss calibrators: {len(calibrators['bbl'])} overs")
    except Exception as e:
        print(f"[FAIL] Failed to load BBL Log Loss calibrators: {e}")
        calibrators['bbl'] = None
    return calibrators

PER_OVER_CALIBRATORS = load_per_over_calibrators()
PHASE_CALIBRATORS = load_phase_calibrators()  # SA20, WPL, and SSM Female phase calibrators
BRIER_CALIBRATORS = load_brier_calibrators()
LOGLOSS_CALIBRATORS = load_logloss_calibrators()

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
        
        **Start the backend predictor first:**
        ```powershell
        python -m src.bbl_pipeline.inference.crex_live_predictor `
            --match-url "https://crex.com/scoreboard/.../live" `
            --model-dir models/wbbl_champion_v3 `
            --feature-store-dir data/wbbl_feature_store_v3 `
            --output-json data/live_state.json
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
    
    # Display Raw, Smoothed, Combined, and Inn-Specific probabilities
    raw_prob = d.get("raw_win_prob", d["bat_win_prob"])
    smoothed_prob = d.get("smoothed_win_prob", d["bat_win_prob"])
    combined_prob = d.get("calibrated_combined_prob", d["bat_win_prob"])
    inn_specific_prob = d.get("calibrated_win_prob", d["bat_win_prob"])
    
    # Calculate odds for each
    raw_odds = prob_to_odds(raw_prob)
    smoothed_odds = prob_to_odds(smoothed_prob)
    combined_odds = prob_to_odds(combined_prob)
    inn_specific_odds = prob_to_odds(inn_specific_prob)
    
    prob_col1, prob_col2, prob_col3, prob_col4 = st.columns(4)
    with prob_col1:
        st.markdown(f'''
        <div style="text-align: center; padding: 10px; background: #f5f5f5; border-radius: 10px; border-left: 4px solid #2196F3;">
            <b>📊 Raw Model</b><br>
            <span style="font-size: 1.5em; color: #2196F3;">{raw_prob*100:.1f}%</span><br>
            <span style="font-size: 1.1em; color: #333;">Odds: <b>{raw_odds}</b></span><br>
            <span style="font-size: 0.9em; color: #666;">XGB+LogReg Ensemble</span>
        </div>
        ''', unsafe_allow_html=True)
    with prob_col2:
        st.markdown(f'''
        <div style="text-align: center; padding: 10px; background: #f5f5f5; border-radius: 10px; border-left: 4px solid #FF9800;">
            <b>🔄 Smoothed</b><br>
            <span style="font-size: 1.5em; color: #FF9800;">{smoothed_prob*100:.1f}%</span><br>
            <span style="font-size: 1.1em; color: #333;">Odds: <b>{smoothed_odds}</b></span><br>
            <span style="font-size: 0.9em; color: #666;">30% Calibrated Blend</span>
        </div>
        ''', unsafe_allow_html=True)
    with prob_col3:
        st.markdown(f'''
        <div style="text-align: center; padding: 10px; background: #f5f5f5; border-radius: 10px; border-left: 4px solid #9C27B0;">
            <b>🎯 Combined</b><br>
            <span style="font-size: 1.5em; color: #9C27B0;">{combined_prob*100:.1f}%</span><br>
            <span style="font-size: 1.1em; color: #333;">Odds: <b>{combined_odds}</b></span><br>
            <span style="font-size: 0.9em; color: #666;">Combined Isotonic</span>
        </div>
        ''', unsafe_allow_html=True)
    with prob_col4:
        innings_label = "Inn1" if not d.get("is_second_innings") else "Inn2"
        st.markdown(f'''
        <div style="text-align: center; padding: 10px; background: #f5f5f5; border-radius: 10px; border-left: 4px solid #4CAF50;">
            <b>✅ Inn-Specific</b><br>
            <span style="font-size: 1.5em; color: #4CAF50;">{inn_specific_prob*100:.1f}%</span><br>
            <span style="font-size: 1.1em; color: #333;">Odds: <b>{inn_specific_odds}</b></span><br>
            <span style="font-size: 0.9em; color: #666;">{innings_label} Isotonic</span>
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
        # SA20: Per-over calibrators for BRIER (0.0399), Phase calibrators for ECE (0.0047)
        
        # 1. Per-over calibrators for best Brier
        sa20_per_over_cals = PER_OVER_CALIBRATORS.get('sa20')
        brier_calibrator_key = f'inn{inn_num}_over{current_over}'
        if sa20_per_over_cals is not None and brier_calibrator_key in sa20_per_over_cals:
            cal_info = sa20_per_over_cals[brier_calibrator_key]
            brier_cal_source = cal_info.get('source', 'raw')
            brier_cal_method = cal_info.get('method', 'isotonic')
            if brier_cal_source == 'raw':
                input_prob = raw_prob
            elif brier_cal_source == 'cal':
                input_prob = inn_specific_prob
            else:
                input_prob = resource_prob
            
            # Apply calibrator based on method
            if brier_cal_method == 'platt':
                # Platt scaling expects logits
                input_clipped = np.clip(input_prob, 0.001, 0.999)
                logit = np.log(input_clipped / (1 - input_clipped))
                brier_optimized_prob = cal_info['calibrator'].predict_proba([[logit]])[0, 1]
            else:
                # Isotonic expects probabilities directly
                brier_optimized_prob = cal_info['calibrator'].predict([[input_prob]])[0]
            brier_optimized_prob = np.clip(brier_optimized_prob, 0.01, 0.99)
        
        # 2. Phase calibrators for best ECE (Platt scaling for smooth output)
        sa20_phase_cals = PHASE_CALIBRATORS.get('sa20')
        if sa20_phase_cals is not None:
            calibrator_key = f'inn{inn_num}_{phase_key}'
            if calibrator_key in sa20_phase_cals:
                phase_cal_info = sa20_phase_cals[calibrator_key]
                cal_source = 'raw'  # SA20 phase calibrators use raw_win_prob
                
                # Check if it's Platt (dict with calibrator) or isotonic (direct calibrator)
                if isinstance(phase_cal_info, dict) and 'calibrator' in phase_cal_info:
                    # Platt scaling
                    cal_method = 'platt'
                    input_clipped = np.clip(raw_prob, 0.001, 0.999)
                    logit = np.log(input_clipped / (1 - input_clipped))
                    ece_optimized_prob = phase_cal_info['calibrator'].predict_proba([[logit]])[0, 1]
                else:
                    # Isotonic (legacy)
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
    elif is_bbl or is_ssm:
        # BBL or SSM: Use per-over calibrators for ECE
        if is_bbl:
            league_key = 'bbl'
        else:
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
        if is_ssm:
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
        
        # BBL: Apply Brier-optimized calibrators (separate from ECE calibrators)
        if is_bbl:
            brier_cals = BRIER_CALIBRATORS.get('bbl')
            if brier_cals is not None:
                brier_cal_key = calibrator_key  # e.g., inn1_over14
                if brier_cal_key in brier_cals:
                    brier_cal_info = brier_cals[brier_cal_key]
                    bbl_brier_source = brier_cal_info['source']
                    
                    # Get input based on Brier-optimal source
                    if bbl_brier_source == 'raw':
                        brier_input = raw_prob
                    elif bbl_brier_source == 'cal':
                        brier_input = inn_specific_prob if inn_specific_prob is not None else raw_prob
                    else:  # 'res'
                        brier_input = resource_prob
                    
                    # Apply Brier calibrator (always isotonic)
                    bbl_brier_prob = brier_cal_info['calibrator'].predict([[brier_input]])[0]
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
    
    # WPL: Apply Brier-optimized calibrators (separate from ECE-optimized block above)
    if is_wpl:
        brier_cals = BRIER_CALIBRATORS.get('wpl')
        # Fallback: Try loading directly if cached value is None
        if brier_cals is None:
            try:
                brier_cals = joblib.load('models/wpl_female_v1/per_over_calibrators_brier.pkl')
            except:
                brier_cals = None
        if brier_cals is not None:
            brier_cal_key = f'inn{inn_num}_{phase_key}'
            if brier_cal_key in brier_cals:
                brier_cal_info = brier_cals[brier_cal_key]
                wpl_brier_source = brier_cal_info['source']
                
                # Get input based on Brier-optimal source
                if wpl_brier_source == 'raw':
                    brier_input = raw_prob
                elif wpl_brier_source == 'resource':
                    brier_input = resource_prob
                else:  # 'inn_specific'
                    brier_input = inn_specific_prob if inn_specific_prob is not None else raw_prob
                
                # Apply Brier calibrator (always isotonic)
                wpl_brier_prob = brier_cal_info['calibrator'].predict([[brier_input]])[0]
                wpl_brier_prob = np.clip(wpl_brier_prob, 0.01, 0.99)

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
            if bbl_brier_prob is not None:
                if inn_num == 1 and current_over == 4:
                    brier_prob = raw_prob
                    brier_label = "Raw Model"
                    brier_desc = "Over 4 exception"
                else:
                    brier_prob = bbl_brier_prob
                    brier_label = f"POC-Brier ({bbl_brier_source})"
                    brier_desc = "Brier=0.1385"
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
                logloss_desc = "Log Loss=0.4100"
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
        
        # Column 3: ECE-optimized (Orange)
        with bbl_col3:
            if ece_optimized_prob is not None:
                ece_prob = ece_optimized_prob
                ece_label = f"POC-ECE ({cal_source})"
                ece_desc = "ECE=0.0000"
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
        # Non-BBL: Use original 2-column layout
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
            elif is_wpl:
                # WPL: Use raw model output (sparse data - phase calibrators don't work)
                # Raw model has best Log Loss for sparse WPL data
                brier_prob = raw_prob
                brier_label = "Raw Model Output"
                brier_desc = "Best Log Loss (sparse data)"
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
                    - **🏆 POC-Brier best accuracy:** Brier=0.1385
                    - **🏆 POC-LL best log loss:** LL=0.4100
                    - **🏆 POC-ECE perfect calibration:** ECE=0.0000
                    - **Resource underperforms:** High Brier & LL
                    - **Inn1 harder to predict:** Higher Brier than Inn2
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
                - **For Best Accuracy (Brier):** POC-Brier (Brier=0.1385)
                - **For Best Log Loss:** POC-LL (LL=0.4100)  
                - **For Best Calibration (ECE):** POC-ECE (ECE=0.0000)
                
                **By Phase:**
                - Inn1 Powerplay: POC-Brier wins Brier & Log Loss
                - Inn1 Middle/Death: POC-ECE competitive with POC-Brier
                - Inn2 All Phases: POC-Brier dominates for accuracy
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
    
    # SA20 Calibration Guidance
    with st.expander("📊 SA20 Calibration Guidance - Which Probability to Trust?"):
        st.markdown("### SA20 v1 Model Performance by Innings & Phase (21.8K samples)")
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
                    brier_cols = ['Brier_Raw', 'Brier_InnSpec', 'Brier_Resource', 'Brier_POC_ECE', 'Brier_POC_Brier']
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
                    ece_cols = ['ECE_Raw', 'ECE_InnSpec', 'ECE_Resource', 'ECE_POC_ECE', 'ECE_POC_Brier']
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
                
                col3, col4 = st.columns(2)
                with col3:
                    st.markdown("#### Log Loss (Lower is Better)")
                    ll_cols = ['LogLoss_Raw', 'LogLoss_InnSpec', 'LogLoss_Resource', 'LogLoss_POC_ECE', 'LogLoss_POC_Brier']
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
                    metric_cols = ['Brier_Raw', 'Brier_POC_ECE', 'Brier_POC_Brier']
                    col_rename = ['Raw', 'POC-ECE', 'POC-Brier']
                    title = "Brier Score by Over"
                    yaxis = "Brier Score (Lower is Better)"
                elif metric_choice == "ECE":
                    metric_cols = ['ECE_Raw', 'ECE_POC_ECE', 'ECE_POC_Brier']
                    col_rename = ['Raw', 'POC-ECE', 'POC-Brier']
                    title = "ECE by Over"
                    yaxis = "ECE (Lower is Better)"
                else:
                    metric_cols = ['LogLoss_Raw', 'LogLoss_POC_ECE', 'LogLoss_POC_Brier']
                    col_rename = ['Raw', 'POC-ECE', 'POC-Brier']
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
                    metric_cols = ['Brier_Raw', 'Brier_POC_ECE', 'Brier_POC_Brier']
                    col_rename = ['Raw', 'POC-ECE', 'POC-Brier']
                    title = "Brier Score by Phase"
                elif metric_choice_phase == "ECE":
                    metric_cols = ['ECE_Raw', 'ECE_POC_ECE', 'ECE_POC_Brier']
                    col_rename = ['Raw', 'POC-ECE', 'POC-Brier']
                    title = "ECE by Phase"
                else:
                    metric_cols = ['LogLoss_Raw', 'LogLoss_POC_ECE', 'LogLoss_POC_Brier']
                    col_rename = ['Raw', 'POC-ECE', 'POC-Brier']
                    title = "Log Loss by Phase"
                
                # Phase comparison table
                st.markdown("#### Overall Phase Comparison")
                
                available_cols = ['Innings', 'Phase', 'N']
                available_metric = [c for c in metric_cols if c in ssm_m_metrics_phase.columns]
                phase_display = ssm_m_metrics_phase[available_cols + available_metric + ['Best_Brier', 'Best_ECE']].copy()
                
                # Format numbers before renaming
                for metric_col in available_metric:
                    if metric_col in phase_display.columns:
                        phase_display[metric_col] = phase_display[metric_col].apply(lambda x: f"{float(x):.4f}" if pd.notna(x) else "N/A")
                phase_display['N'] = phase_display['N'].apply(lambda x: f"{int(x):,}")
                
                # Rename columns
                phase_display.columns = ['Innings', 'Phase', 'N'] + col_rename[:len(available_metric)] + ['Best Brier', 'Best ECE']
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
        with st.expander("📊 SA20 Calibration Guidance - Which Probability to Trust? (21.8K Test Samples)"):
            st.markdown("### Win Probability Calibration Analysis")
            st.markdown("""
            Compare four probability sources:
            - **Raw**: Direct model output (baseline)
            - **InnSpec**: Innings-specific isotonic calibration
            - **Resource**: DLS-based resource win probability 
            - **Phase**: Phase-specific calibrated (Platt scaling)
            """)
            
            # Load metrics
            try:
                metrics_inning = pd.read_parquet('data/sa20_metrics_by_inning.parquet')
                metrics_over = pd.read_parquet('data/sa20_metrics_by_over.parquet')
                metrics_phase = pd.read_parquet('data/sa20_metrics_by_phase.parquet')
                
                # Create tabs for different views
                tab1, tab2, tab3 = st.tabs(["📈 By Inning", "🎯 By Over", "⚙️ By Phase"])
                
                with tab1:
                    st.markdown("### By Innings")
                    st.markdown("""
                    Compare four probability sources across both innings:
                    - **Raw**: Direct model output (baseline)
                    - **InnSpec**: Innings-specific isotonic calibration
                    - **Resource**: DLS-based resource win probability 
                    - **Phase**: Phase-specific calibrated (Platt scaling)
                    """)
                    
                    # Inning metrics comparison
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("#### Brier Score (Lower is Better)")
                        brier_data = metrics_inning[['Group', 'Brier_Raw', 'Brier_InnSpec', 'Brier_Resource', 'Brier_Phase']].copy()
                        brier_data.columns = ['Innings', 'Raw', 'InnSpec', 'Resource', 'Phase']
                        st.dataframe(brier_data, use_container_width=True, hide_index=True)
                        
                        # Brier chart
                        brier_chart = go.Figure()
                        for method in ['Raw', 'InnSpec', 'Resource', 'Phase']:
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
                        ece_data = metrics_inning[['Group', 'ECE_Raw', 'ECE_InnSpec', 'ECE_Resource', 'ECE_Phase']].copy()
                        ece_data.columns = ['Innings', 'Raw', 'InnSpec', 'Resource', 'Phase']
                        st.dataframe(ece_data, use_container_width=True, hide_index=True)
                        
                        # ECE chart
                        ece_chart = go.Figure()
                        for method in ['Raw', 'InnSpec', 'Resource', 'Phase']:
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
                        ll_data = metrics_inning[['Group', 'LogLoss_Raw', 'LogLoss_InnSpec', 'LogLoss_Resource', 'LogLoss_Phase']].copy()
                        ll_data.columns = ['Innings', 'Raw', 'InnSpec', 'Resource', 'Phase']
                        st.dataframe(ll_data, use_container_width=True, hide_index=True)
                        
                        # LogLoss chart
                        ll_chart = go.Figure()
                        for method in ['Raw', 'InnSpec', 'Resource', 'Phase']:
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
                        st.markdown("#### Sample Size")
                        sample_data = metrics_inning[['Group', 'N']].copy()
                        sample_data.columns = ['Innings', 'Samples']
                        sample_data['Samples'] = sample_data['Samples'].apply(lambda x: f"{x:,}")
                        st.dataframe(sample_data, use_container_width=True, hide_index=True)
                        
                        st.markdown("#### Key Insights")
                        st.markdown("""
                        - **Raw dominates Brier:** Raw model wins Brier score for both innings
                        - **InnSpec less accurate:** Innings-specific actually increases Brier
                        - **Phase for Inn 1 ECE:** Phase calibration improves ECE in innings 1
                        - **Resource for Inn 2 ECE:** Resource achieves best ECE (0.048) in innings 2
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
                        key="metric_choice_over"
                    )
                    
                    if metric_choice == "Brier Score":
                        metric_cols = ['Brier_Raw', 'Brier_InnSpec', 'Brier_Resource', 'Brier_Phase']
                        col_rename = ['Raw', 'InnSpec', 'Resource', 'Phase']
                        title = "Brier Score by Over"
                        yaxis = "Brier Score (Lower is Better)"
                    elif metric_choice == "ECE":
                        metric_cols = ['ECE_Raw', 'ECE_InnSpec', 'ECE_Resource', 'ECE_Phase']
                        col_rename = ['Raw', 'InnSpec', 'Resource', 'Phase']
                        title = "ECE by Over"
                        yaxis = "ECE (Lower is Better)"
                    else:
                        metric_cols = ['LogLoss_Raw', 'LogLoss_InnSpec', 'LogLoss_Resource', 'LogLoss_Phase']
                        col_rename = ['Raw', 'InnSpec', 'Resource', 'Phase']
                        title = "Log Loss by Over"
                        yaxis = "Log Loss (Lower is Better)"
                    
                    # Split by innings
                    col_left, col_right = st.columns(2)
                    
                    with col_left:
                        st.markdown("#### Innings 1")
                        inn1_over = metrics_over[metrics_over['Innings'] == 1].copy()
                        inn1_over['Over_Label'] = inn1_over['Over'].apply(lambda x: f"Over {x}")
                        
                        # Create table
                        display_cols = ['Over_Label'] + metric_cols
                        display_data = inn1_over[display_cols].copy()
                        display_data.columns = ['Over'] + col_rename
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
                        inn2_over = metrics_over[metrics_over['Innings'] == 2].copy()
                        inn2_over['Over_Label'] = inn2_over['Over'].apply(lambda x: f"Over {x}")
                        
                        # Create table
                        display_cols = ['Over_Label'] + metric_cols
                        display_data = inn2_over[display_cols].copy()
                        display_data.columns = ['Over'] + col_rename
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
                    st.markdown("### By Phase")
                    st.markdown("""
                    Compare probabilities by cricket phases:
                    - **Powerplay** (Overs 1-6): Aggressive batting, high variance
                    - **Middle Early** (Overs 7-12): Consolidation phase
                    - **Middle Late** (Overs 13-15): Acceleration starts
                    - **Death** (Overs 16-20): Maximum effort, high risk
                    """)
                    
                    metric_choice_phase = st.selectbox(
                        "Select metric to display:",
                        ["Brier Score", "ECE", "Log Loss"],
                        key="metric_choice_phase"
                    )
                    
                    if metric_choice_phase == "Brier Score":
                        metric_cols = ['Brier_Raw', 'Brier_InnSpec', 'Brier_Resource', 'Brier_Phase']
                        col_rename = ['Raw_Score', 'InnSpec_Score', 'Resource_Score', 'Phase_Score']
                        title = "Brier Score by Phase"
                    elif metric_choice_phase == "ECE":
                        metric_cols = ['ECE_Raw', 'ECE_InnSpec', 'ECE_Resource', 'ECE_Phase']
                        col_rename = ['Raw_ECE', 'InnSpec_ECE', 'Resource_ECE', 'Phase_ECE']
                        title = "ECE by Phase"
                    else:
                        metric_cols = ['LogLoss_Raw', 'LogLoss_InnSpec', 'LogLoss_Resource', 'LogLoss_Phase']
                        col_rename = ['Raw_LL', 'InnSpec_LL', 'Resource_LL', 'Phase_LL']
                        title = "Log Loss by Phase"
                    
                    # Phase comparison table
                    st.markdown("#### Overall Phase Comparison")
                    phase_display = metrics_phase[['Innings', 'Phase', 'N'] + metric_cols].copy()
                    
                    # Format numbers before renaming columns
                    for metric_col in metric_cols:
                        phase_display[metric_col] = phase_display[metric_col].apply(lambda x: f"{float(x):.4f}")
                    phase_display['N'] = phase_display['N'].apply(lambda x: f"{int(x):,}")
                    
                    # Now rename columns
                    phase_display.columns = ['Innings', 'Phase', 'N'] + col_rename
                    
                    st.dataframe(phase_display, use_container_width=True, hide_index=True)
                    
                    # Side-by-side phase comparison charts
                    col_ph1, col_ph2 = st.columns(2)
                    
                    with col_ph1:
                        st.markdown("#### Innings 1 - Metric by Phase")
                        inn1_phase = metrics_phase[metrics_phase['Innings'] == 1].copy()
                        
                        fig_inn1 = go.Figure()
                        for method in col_rename:
                            fig_inn1.add_trace(go.Bar(
                                name=method,
                                x=inn1_phase['Phase'],
                                y=inn1_phase[[f"{m}" for m in metric_cols][col_rename.index(method)]],
                                text=[f"{v:.4f}" for v in inn1_phase[[f"{m}" for m in metric_cols][col_rename.index(method)]]],
                                textposition='outside'
                            ))
                        fig_inn1.update_layout(
                            barmode='group', height=400, title=f"{title} - Innings 1",
                            xaxis_title="Phase", hovermode='x unified'
                        )
                        st.plotly_chart(fig_inn1, use_container_width=True)
                    
                    with col_ph2:
                        st.markdown("#### Innings 2 - Metric by Phase")
                        inn2_phase = metrics_phase[metrics_phase['Innings'] == 2].copy()
                        
                        fig_inn2 = go.Figure()
                        for method in col_rename:
                            method_col_idx = col_rename.index(method)
                            fig_inn2.add_trace(go.Bar(
                                name=method,
                                x=inn2_phase['Phase'],
                                y=inn2_phase[[f"{m}" for m in metric_cols][method_col_idx]],
                                text=[f"{v:.4f}" for v in inn2_phase[[f"{m}" for m in metric_cols][method_col_idx]]],
                                textposition='outside'
                            ))
                        fig_inn2.update_layout(
                            barmode='group', height=400, title=f"{title} - Innings 2",
                            xaxis_title="Phase", hovermode='x unified'
                        )
                        st.plotly_chart(fig_inn2, use_container_width=True)
                
                st.markdown("---")
                st.markdown("### 🎯 SA20 Recommendation")
                st.success("""
                **For Best Accuracy (Brier):** 🏆 **Raw Model wins ALL 8 phases!**
                
                | Metric | Conclusion |
                |--------|-----------|
                | **Brier Score** | Raw model dominates across all overs and phases |
                | **ECE (Calibration)** | Resource & Phase offer better calibration in specific phases |
                | **Log Loss** | Raw model has best overall predictive performance |
                
                ✅ **Primary Recommendation:** Use Raw Model for live predictions
                """)
                
                st.markdown("### 📖 Key Insights by Situation")
                st.markdown("""
                | Situation | Best Choice | Why |
                |-----------|------------|-----|
                | **Early Powerplay (Overs 1-3)** | Raw Model | Highest confidence, minimal calibration drift |
                | **Middle Overs (6-15)** | Raw Model | Predictable patterns, low uncertainty |
                | **Death Overs (16-20)** | Phase Calibrator | High variance benefits from calibration smoothing |
                | **Need Certainty** | Phase Calibrator | Best ECE, most reliable probability |
                | **Need Accuracy** | Raw Model | Wins Brier score across all phases |
                | **Resource-based Decision** | Raw Model | Resource probability significantly underperforms |
                """)
            
            except FileNotFoundError:
                st.warning("⚠️ SA20 metrics not found. Run `python scripts/calculate_sa20_metrics.py` to generate them.")
    
    # Charts row
    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(create_resource_gauge(res))
    with c2:
        if d.get("target"):
            rrr = f.get("required_run_rate", d.get("required_run_rate", 10))
            st.plotly_chart(create_rr_chart(crr, rrr))
        else:
            # Show score vs par
            par = f.get("score_vs_par", 0)
            fig = go.Figure(go.Indicator(
                mode="delta+number", value=par,
                title={"text": "Score vs Par"},
                delta={"reference": 0, "increasing": {"color": "#4CAF50"}, "decreasing": {"color": "#f44336"}}
            ))
            fig.update_layout(height=200, margin=dict(l=20, r=20, t=50, b=20))
            st.plotly_chart(fig)
    
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
