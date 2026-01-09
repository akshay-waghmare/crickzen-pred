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

# Team colors and names - BBL, WBBL, ILT20, SA20
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
}

DEFAULT_JSON = "data/live_state.json"

# Load per-over calibrators for ECE-optimized predictions (smoother than phase calibrators)
# NOTE: SA20 uses phase calibrators (8 phases) instead of per-over due to small dataset
@st.cache_resource
def load_per_over_calibrators():
    """Load per-over calibrators for BBL and SSM."""
    calibrators = {}
    try:
        calibrators['bbl'] = joblib.load('models/bbl_v10/per_over_calibrators.pkl')
    except:
        calibrators['bbl'] = None
    try:
        calibrators['ssm'] = joblib.load('models/ssm_v1/per_over_calibrators.pkl')
    except:
        calibrators['ssm'] = None
    # SA20: per-over calibrators give best Brier (0.0399), phase calibrators give best ECE (0.0047)
    try:
        calibrators['sa20'] = joblib.load('models/sat_v1/per_over_calibrators.pkl')
    except:
        calibrators['sa20'] = None
    return calibrators

@st.cache_resource
def load_phase_calibrators():
    """Load Platt phase calibrators for SA20 (8 phases: powerplay, middle_early, middle_late, death).
    Platt scaling gives smooth probabilities instead of isotonic step functions."""
    try:
        # Prefer Platt scaling phase calibrators for smooth output
        return joblib.load('models/sat_v1/phase_calibrators_platt.pkl')
    except:
        try:
            # Fallback to isotonic if Platt not available
            return joblib.load('models/sat_v1/phase_calibrators.pkl')
        except:
            return None

@st.cache_resource
def load_brier_calibrators():
    """Load Brier-optimized calibrators for SSM.
    These select best source per over for accuracy (Brier score)."""
    calibrators = {}
    try:
        calibrators['ssm'] = joblib.load('models/ssm_v1/brier_calibrators.pkl')
    except:
        calibrators['ssm'] = None
    return calibrators

PER_OVER_CALIBRATORS = load_per_over_calibrators()
SA20_PHASE_CALIBRATORS = load_phase_calibrators()
BRIER_CALIBRATORS = load_brier_calibrators()

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
    ssm_teams = {'AA', 'AKL', 'Auckland', 'CD', 'Central Districts', 'CS', 'CK', 'Canterbury',
                 'ND', 'NB', 'Northern Districts', 'OV', 'OTG', 'Otago', 'WF', 'WEL', 'Wellington'}
    
    batting_team = d.get("batting_team", "")
    is_bbl = batting_team in bbl_teams
    is_sa20 = batting_team in sa20_teams
    is_ssm = batting_team in ssm_teams
    
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
        if SA20_PHASE_CALIBRATORS is not None:
            calibrator_key = f'inn{inn_num}_{phase_key}'
            if calibrator_key in SA20_PHASE_CALIBRATORS:
                phase_cal_info = SA20_PHASE_CALIBRATORS[calibrator_key]
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
    elif is_bbl or is_ssm:
        # BBL or SSM: Use per-over calibrators for ECE
        league_key = 'bbl' if is_bbl else 'ssm'
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
    
    # ECE-Optimized Decision Probabilities section
    league_name = "🏏 BBL" if is_bbl else ("🇿🇦 SA20" if is_sa20 else ("🇳🇿 SSM" if is_ssm else "🏏 T20"))
    st.markdown("---")
    st.subheader(f"{league_name} Decision Probabilities")
    method_label = "Platt" if cal_method == "platt" else "Isotonic"
    
    # For SA20, show per-over calibrator info for Brier column
    if is_sa20 and brier_optimized_prob is not None:
        st.caption(f"**Innings {inn_num} - Over {current_over} ({phase})** | Brier Cal: {brier_calibrator_key} | ECE Cal: {calibrator_key}")
    else:
        st.caption(f"**Innings {inn_num} - Over {current_over} ({phase})** | Calibrator: {calibrator_key} | Source: {cal_source or 'N/A'} | Method: {method_label}")
    
    sa_col1, sa_col2 = st.columns(2)
    with sa_col1:
        # SA20: Use raw model output for display (calibrators output 1.0 at high probs)
        # SSM: Use Brier-optimized calibrator (best accuracy)
        # BBL: Use raw model
        if is_sa20:
            brier_prob = raw_prob
            brier_label = "Raw Model Output"
            brier_desc = "Brier=0.0773 (Well-calibrated)"
        elif is_ssm and ssm_brier_prob is not None:
            brier_prob = ssm_brier_prob
            brier_label = f"Brier-Optimized ({ssm_brier_source})"
            brier_desc = "Brier=0.0867, ECE=0.000"
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
        elif ece_optimized_prob is not None:
            ece_odds = prob_to_odds(ece_optimized_prob)
            # Calculate the adjustment for display
            adjustment = ece_optimized_prob - raw_prob
            adj_text = f"+{adjustment*100:.0f}%" if adjustment > 0 else f"{adjustment*100:.0f}%"
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
    # BBL-specific guidance based on analysis
    with st.expander("📊 BBL Calibration Guidance - Which Probability to Trust?"):
        st.markdown("### BBL v10 Model Performance Analysis (141K+ samples)")
        st.markdown("""
        **Detailed ECE & Brier by Over (based on ~3,500 samples per over):**
        
        #### Innings 1 - Raw Model wins ECE & Brier for almost ALL overs
        | Over | ECE_Raw | ECE_Cal | ECE_Res | Brier_Raw | Brier_Cal | Brier_Res | Best ECE | Best Brier |
        |------|---------|---------|---------|-----------|-----------|-----------|----------|------------|
        | 1 | **0.0904** | 0.0910 | 0.1114 | **0.2155** | 0.2159 | 0.2617 | Raw | Raw |
        | 2 | **0.1040** | 0.1060 | 0.1099 | **0.2106** | 0.2117 | 0.2596 | Raw | Raw |
        | 3 | 0.1074 | **0.1023** | 0.1038 | **0.2002** | 0.2026 | 0.2535 | Cal | Raw |
        | 4 | 0.0964 | 0.1016 | **0.0958** | **0.1920** | 0.1953 | 0.2457 | Res | Raw |
        | 5 | **0.0745** | 0.1001 | 0.1051 | **0.1884** | 0.1916 | 0.2395 | Raw | Raw |
        | 6 | **0.0696** | 0.0839 | 0.0913 | **0.1886** | 0.1923 | 0.2345 | Raw | Raw |
        | 7 | **0.0597** | 0.0750 | 0.0953 | **0.1845** | 0.1895 | 0.2309 | Raw | Raw |
        | 8 | **0.0525** | 0.0739 | 0.0899 | **0.1806** | 0.1871 | 0.2269 | Raw | Raw |
        | 9 | **0.0504** | 0.0805 | 0.0835 | **0.1764** | 0.1839 | 0.2227 | Raw | Raw |
        | 10 | **0.0521** | 0.0725 | 0.0801 | **0.1739** | 0.1805 | 0.2189 | Raw | Raw |
        | 11 | **0.0465** | 0.0768 | 0.0795 | **0.1711** | 0.1775 | 0.2171 | Raw | Raw |
        | 12 | **0.0538** | 0.0825 | 0.0908 | **0.1668** | 0.1734 | 0.2159 | Raw | Raw |
        | 13 | **0.0591** | 0.0850 | 0.0966 | **0.1617** | 0.1684 | 0.2117 | Raw | Raw |
        | 14 | **0.0577** | 0.0848 | 0.1037 | **0.1616** | 0.1681 | 0.2119 | Raw | Raw |
        | 15 | **0.0544** | 0.0827 | 0.1045 | **0.1613** | 0.1676 | 0.2137 | Raw | Raw |
        | 16 | **0.0566** | 0.0841 | 0.1128 | **0.1601** | 0.1671 | 0.2125 | Raw | Raw |
        | 17 | **0.0521** | 0.0850 | 0.1102 | **0.1618** | 0.1686 | 0.2127 | Raw | Raw |
        | 18 | **0.0591** | 0.0917 | 0.1176 | **0.1641** | 0.1712 | 0.2127 | Raw | Raw |
        | 19 | **0.0602** | 0.0981 | 0.1021 | **0.1636** | 0.1713 | 0.2095 | Raw | Raw |
        | 20 | **0.0772** | 0.1147 | 0.0888 | **0.1650** | 0.1741 | 0.2068 | Raw | Raw |
        
        #### Innings 2 - Inn-Specific Calibrated wins ECE for 19/20 overs
        | Over | ECE_Raw | ECE_Cal | ECE_Res | Brier_Raw | Brier_Cal | Brier_Res | Best ECE | Best Brier |
        |------|---------|---------|---------|-----------|-----------|-----------|----------|------------|
        | 1 | 0.0633 | **0.0513** | 0.1641 | 0.1705 | **0.1690** | 0.2248 | Cal | Cal |
        | 2 | 0.0570 | **0.0516** | 0.1562 | 0.1655 | **0.1649** | 0.2183 | Cal | Cal |
        | 3 | 0.0561 | **0.0537** | 0.1496 | 0.1607 | **0.1601** | 0.2132 | Cal | Cal |
        | 4 | 0.0652 | **0.0512** | 0.1409 | 0.1495 | **0.1486** | 0.2051 | Cal | Cal |
        | 5 | 0.0656 | **0.0604** | 0.1339 | 0.1409 | **0.1400** | 0.1950 | Cal | Cal |
        | 6 | 0.0832 | **0.0765** | 0.1194 | 0.1299 | **0.1289** | 0.1817 | Cal | Cal |
        | 7 | 0.0700 | **0.0619** | 0.1018 | 0.1216 | **0.1210** | 0.1688 | Cal | Cal |
        | 8 | 0.0654 | **0.0532** | 0.0812 | 0.1165 | **0.1155** | 0.1592 | Cal | Cal |
        | 9 | 0.0608 | **0.0549** | 0.0632 | 0.1087 | **0.1080** | 0.1454 | Cal | Cal |
        | 10 | 0.0473 | **0.0401** | 0.0561 | 0.1063 | **0.1061** | 0.1383 | Cal | Cal |
        | 11 | 0.0467 | **0.0384** | 0.0492 | 0.1010 | **0.1003** | 0.1321 | Cal | Cal |
        | 12 | 0.0494 | **0.0409** | 0.0494 | 0.0962 | **0.0955** | 0.1273 | Cal | Cal |
        | 13 | 0.0465 | **0.0453** | 0.0644 | **0.0920** | 0.0921 | 0.1268 | Cal | Raw |
        | 14 | 0.0462 | **0.0401** | 0.0785 | 0.0858 | **0.0850** | 0.1212 | Cal | Cal |
        | 15 | 0.0527 | **0.0492** | 0.1035 | 0.0774 | **0.0767** | 0.1194 | Cal | Cal |
        | 16 | 0.0575 | **0.0541** | 0.1253 | **0.0710** | 0.0711 | 0.1183 | Cal | Raw |
        | 17 | 0.0709 | **0.0653** | 0.1461 | **0.0685** | 0.0691 | 0.1284 | Cal | Raw |
        | 18 | 0.0730 | **0.0721** | 0.1632 | **0.0608** | 0.0614 | 0.1324 | Cal | Raw |
        | 19 | **0.0685** | 0.0687 | 0.1535 | **0.0542** | 0.0548 | 0.1181 | Raw | Raw |
        | 20 | 0.0416 | **0.0355** | 0.0982 | **0.0476** | 0.0477 | 0.0797 | Cal | Raw |
        
        *Lower is better for both Brier and ECE*
        """)
        
        st.markdown("---")
        st.markdown("### 🎯 Current Recommendation")
        
        if not is_inn2:
            st.success(f"""
            **Innings 1 - Over {current_over} ({phase})**
            
            ✅ **Use: Raw Model Probability ({raw_prob*100:.1f}%)**
            
            Raw model wins ECE for 18/20 overs in Innings 1. Only exceptions: Over 3 (Cal), Over 4 (Res).
            Raw model wins Brier for ALL 20 overs in Innings 1.
            """)
        else:
            if phase == "Death" and current_over == 19:
                st.info(f"""
                **Innings 2 - Over {current_over} ({phase})**
                
                📊 **For Best Accuracy (Brier):** Raw Model ({raw_prob*100:.1f}%)
                
                🎯 **For Best Calibration (ECE):** Raw Model ({raw_prob*100:.1f}%)
                
                Over 19 is the ONLY over in Innings 2 where Raw wins ECE.
                """)
            else:
                # Cal wins ECE for most of Innings 2 (overs 1-18, 20)
                st.success(f"""
                **Innings 2 - Over {current_over} ({phase})**
                
                ✅ **Use: Inn-Specific Calibrated ({inn_specific_prob*100:.1f}%)**
                
                Inn-Specific Cal wins ECE for 19/20 overs in Innings 2.
                Inn-Specific Cal wins Brier for overs 1-12, 14-15.
                """)
        
        st.markdown("---")
        st.markdown("### 📖 Key Insights")
        st.markdown("""
        - **Innings 1:** Raw model dominates ECE (18/20 overs) & Brier (ALL overs)
        - **Innings 2:** Inn-Specific Cal dominates ECE (19/20 overs), mixed for Brier
        - **Resource Win Prob:** Never best for ECE in Innings 2 (unlike SSM)
        - **Only exception:** Inn 2 Over 19 - Raw wins both ECE and Brier
        - **Main Odds Display uses:** Inn-Specific Calibrated probability
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
    
    # SSM Calibration Guidance
    with st.expander("📊 SSM (Super Smash) Calibration Guidance - Which Probability to Trust?"):
        st.markdown("### SSM v1 Model Performance Analysis (55K samples)")
        st.markdown("""
        **Overall Model Performance Summary:**
        
        | Metric | Raw Model | ECE-Optimized | Brier-Optimized | Winner |
        |--------|-----------|---------------|-----------------|--------|
        | **Brier Score** | 0.1088 | 0.1067 | **0.0867** | 🏆 Brier-Opt |
        | **ECE** | 0.1050 | 0.0439 | **0.0000** | 🏆 Brier-Opt |
        | **Log Loss** | 0.3558 | 0.6037 | **0.2709** | 🏆 Brier-Opt |
        
        **⚠️ Key Insight: ECE-Optimized HURTS Log Loss!** (0.6037 vs 0.3558 Raw)
        
        **Winner Summary (38 overs analyzed):**
        - **Brier Score:** Brier-Opt wins ALL 38 overs!
        - **ECE:** Both Brier-Opt and ECE-Opt achieve ~0.00 (perfect after isotonic)
        - **Log Loss:** Brier-Opt wins ALL 38 overs!
        """)
        
        st.markdown("---")
        st.markdown("#### Per-Over Comparison: Raw vs ECE-Opt vs Brier-Opt")
        st.markdown("""
        | Inn | Over | N | B_Raw | B_ECE | B_Brier | L_Raw | L_ECE | L_Brier | Best |
        |-----|------|---|-------|-------|---------|-------|-------|---------|------|
        | 1 | 2 | 1410 | 0.185 | 0.272 | **0.123** | 0.558 | 7.781 | **0.372** | 🏆 Brier |
        | 1 | 5 | 1475 | 0.157 | 0.129 | **0.118** | 0.493 | 0.996 | **0.367** | 🏆 Brier |
        | 1 | 10 | 1431 | 0.138 | 0.146 | **0.112** | 0.441 | 0.456 | **0.337** | 🏆 Brier |
        | 1 | 15 | 1447 | 0.119 | 0.121 | **0.094** | 0.391 | 0.491 | **0.288** | 🏆 Brier |
        | 1 | 20 | 2838 | 0.117 | 0.115 | **0.089** | 0.385 | 0.478 | **0.287** | 🏆 Brier |
        | 2 | 2 | 1410 | 0.129 | 0.127 | **0.118** | 0.406 | 0.541 | **0.365** | 🏆 Brier |
        | 2 | 5 | 1462 | 0.091 | 0.086 | **0.077** | 0.306 | 0.278 | **0.250** | 🏆 Brier |
        | 2 | 10 | 1426 | 0.077 | 0.075 | **0.065** | 0.263 | 0.266 | **0.218** | 🏆 Brier |
        | 2 | 15 | 1354 | 0.074 | 0.071 | **0.065** | 0.248 | 0.262 | **0.198** | 🏆 Brier |
        | 2 | 20 | 1539 | 0.044 | 0.026 | **0.025** | 0.165 | 0.189 | **0.094** | 🏆 Brier |
        
        *Lower is better. Brier-Optimized wins ALL overs for both Brier and Log Loss!*
        *Note: ECE-Opt causes Log Loss explosions (e.g., Over 2 Inn1: 7.78 vs 0.37)*
        """)
        
        st.markdown("---")
        st.markdown("#### By Innings Summary")
        st.markdown("""
        | Innings | Method | Brier | ECE | Log Loss | Notes |
        |---------|--------|-------|-----|----------|-------|
        | **1** | Raw | 0.1363 | 0.1384 | 0.4368 | Baseline |
        | **1** | ECE-Opt | 0.1387 | 0.0690 | 0.8925 | ⚠️ Hurts Log Loss! |
        | **1** | **Brier-Opt** | **0.1063** | **0.0000** | **0.3277** | 🏆 Best all metrics |
        | **2** | Raw | 0.0789 | 0.0686 | 0.2677 | Baseline |
        | **2** | ECE-Opt | 0.0718 | 0.0190 | 0.2892 | Slight LL increase |
        | **2** | **Brier-Opt** | **0.0654** | **0.0000** | **0.2091** | 🏆 Best all metrics |
        """)
        
        st.markdown("---")
        st.markdown("#### By Phase Summary")
        st.markdown("""
        | Inn | Phase | N | B_Raw | B_ECE | B_Brier | L_Raw | L_ECE | L_Brier |
        |-----|-------|---|-------|-------|---------|-------|-------|---------|
        | 1 | Powerplay | 7316 | 0.167 | 0.172 | **0.119** | 0.515 | 2.037 | **0.365** |
        | 1 | Middle | 13027 | 0.134 | 0.137 | **0.109** | 0.431 | 0.559 | **0.334** |
        | 1 | Death | 8573 | 0.114 | 0.112 | **0.092** | 0.379 | 0.422 | **0.287** |
        | 2 | Powerplay | 7296 | 0.102 | 0.095 | **0.089** | 0.337 | 0.404 | **0.279** |
        | 2 | Middle | 12723 | 0.077 | 0.073 | **0.064** | 0.263 | 0.264 | **0.205** |
        | 2 | Death | 6535 | 0.056 | 0.044 | **0.042** | 0.200 | 0.211 | **0.139** |
        
        *Brier-Optimized wins ALL 6 phases for both Brier Score and Log Loss!*
        """)
        
        st.markdown("---")
        st.markdown("### 🎯 SSM Decision Guide")
        
        st.success("""
        **🏆 BRIER-OPTIMIZED CALIBRATOR IS THE CLEAR WINNER FOR SSM!**
        
        | Metric | Improvement over Raw | Improvement over ECE-Opt |
        |--------|---------------------|-------------------------|
        | **Brier** | -20% (0.0867 vs 0.1088) | -19% (0.0867 vs 0.1067) |
        | **ECE** | Perfect 0.000 | Perfect 0.000 |
        | **Log Loss** | -24% (0.2709 vs 0.3558) | -55% (0.2709 vs 0.6037) |
        
        ✅ **Use Brier-Optimized for ALL SSM predictions!**
        ⚠️ **Never use ECE-Optimized for SSM** - it causes Log Loss explosions
        """)
        
        st.markdown("---")
        st.markdown("### 📖 Key Insights")
        st.markdown("""
        - **Brier-Opt dominates:** Wins ALL 38 overs for Brier AND Log Loss
        - **ECE-Opt is harmful:** Causes massive Log Loss increases (overconfident predictions)
        - **Perfect calibration:** Brier-Opt achieves ECE 0.0000 (same as ECE-Opt)
        - **Best of both worlds:** Brier-Opt gives accuracy + calibration + low log loss
        - **55K samples:** Robust analysis with ~1,400 samples per over
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
