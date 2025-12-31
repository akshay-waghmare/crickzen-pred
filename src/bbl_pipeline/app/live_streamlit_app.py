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
}

DEFAULT_JSON = "data/live_state.json"

# Load SA20 phase calibrators for ECE-optimized predictions
@st.cache_resource
def load_sa20_phase_calibrators():
    """Load SA20 phase-specific calibrators trained on resource_win_prob."""
    try:
        return joblib.load('models/sat_v1/phase_calibrators.pkl')
    except:
        return None

SA20_PHASE_CALIBRATORS = load_sa20_phase_calibrators()

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
    current_over = d.get("overs", 0)
    
    # Determine phase
    if current_over <= 6:
        phase = "Powerplay"
    elif current_over <= 15:
        phase = "Middle"
    else:
        phase = "Death"
    
    # SA20 Specific: Show Raw vs ECE-Optimized prominently
    st.markdown("---")
    st.subheader("🇿🇦 SA20 Decision Probabilities")
    st.caption(f"Current Phase: **Innings {2 if is_inn2 else 1} - {phase}**")
    
    # Calculate ECE-optimized probability
    ece_optimized_prob = None
    if SA20_PHASE_CALIBRATORS is not None:
        inn_num = 2 if is_inn2 else 1
        phase_key = phase.lower()
        calibrator_key = f'inn{inn_num}_{phase_key}'
        
        if calibrator_key in SA20_PHASE_CALIBRATORS:
            ece_optimized_prob = SA20_PHASE_CALIBRATORS[calibrator_key].predict([[resource_prob]])[0]
            ece_optimized_prob = np.clip(ece_optimized_prob, 0.01, 0.99)
    
    sa_col1, sa_col2 = st.columns(2)
    with sa_col1:
        st.markdown(f'''
        <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #2196F3, #1565C0); border-radius: 15px; color: white; margin: 5px;">
            <div style="font-size: 0.9em; opacity: 0.9;">🎯 BEST ACCURACY (Brier)</div>
            <div style="font-size: 2.5em; font-weight: bold;">{raw_prob*100:.1f}%</div>
            <div style="font-size: 1.3em;">Odds: <b>{prob_to_odds(raw_prob)}</b></div>
            <div style="font-size: 0.85em; margin-top: 8px; opacity: 0.8;">Raw Model Output</div>
            <div style="font-size: 0.75em; opacity: 0.7;">Brier: 0.04-0.13 (Best)</div>
        </div>
        ''', unsafe_allow_html=True)
    
    with sa_col2:
        if ece_optimized_prob is not None:
            ece_odds = prob_to_odds(ece_optimized_prob)
            st.markdown(f'''
            <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #4CAF50, #2E7D32); border-radius: 15px; color: white; margin: 5px;">
                <div style="font-size: 0.9em; opacity: 0.9;">✅ BEST CALIBRATION (ECE)</div>
                <div style="font-size: 2.5em; font-weight: bold;">{ece_optimized_prob*100:.1f}%</div>
                <div style="font-size: 1.3em;">Odds: <b>{ece_odds}</b></div>
                <div style="font-size: 0.85em; margin-top: 8px; opacity: 0.8;">Phase-Calibrated Resource</div>
                <div style="font-size: 0.75em; opacity: 0.7;">ECE: 0.0000 (Perfect)</div>
            </div>
            ''', unsafe_allow_html=True)
        else:
            st.markdown(f'''
            <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #ff9800, #e65100); border-radius: 15px; color: white; margin: 5px;">
                <div style="font-size: 0.9em; opacity: 0.9;">📊 RESOURCE PROBABILITY</div>
                <div style="font-size: 2.5em; font-weight: bold;">{resource_prob*100:.1f}%</div>
                <div style="font-size: 1.3em;">Odds: <b>{prob_to_odds(resource_prob)}</b></div>
                <div style="font-size: 0.85em; margin-top: 8px; opacity: 0.8;">DLS-based Win Prob</div>
                <div style="font-size: 0.75em; opacity: 0.7;">Phase calibrators not loaded</div>
            </div>
            ''', unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    # BBL-specific guidance based on analysis
    with st.expander("📊 BBL Calibration Guidance - Which Probability to Trust?"):
        st.markdown("### BBL v10 Model Performance Analysis")
        st.markdown("""
        Based on comprehensive Brier Score (accuracy) and ECE (calibration) analysis:
        
        | Innings | Phase | Best Brier | Best ECE |
        |---------|-------|------------|----------|
        | **Inn 1** | Powerplay | **Raw (0.2013)** | **Raw (0.0925)** |
        | **Inn 1** | Middle | **Raw (0.1739)** | **Raw (0.0537)** |
        | **Inn 1** | Death | **Raw (0.1622)** | **Raw (0.0549)** |
        | **Inn 2** | Powerplay | **Cal (0.1565)** | **Cal (0.0497)** |
        | **Inn 2** | Middle | **Cal (0.1060)** | Resource (0.0281) |
        | **Inn 2** | Death | **Raw (0.0674)** | **Cal (0.0600)** |
        
        *Lower is better for both Brier and ECE*
        """)
        
        st.markdown("---")
        st.markdown("### 🎯 Current Recommendation")
        
        if not is_inn2:
            st.success(f"""
            **Innings 1 - {phase} Phase**
            
            ✅ **Use: Raw Model Probability ({raw_prob*100:.1f}%)**
            
            The raw model is already well-calibrated in innings 1. No calibration needed.
            """)
        else:
            if phase == "Middle":
                st.info(f"""
                **Innings 2 - {phase} Phase**
                
                📊 **For Best Accuracy (Brier):** Inn-Specific Calibrated ({inn_specific_prob*100:.1f}%)
                
                🎯 **For Best Calibration (ECE):** Resource Win Prob ({resource_prob*100:.1f}%)
                """)
            elif phase == "Powerplay":
                st.success(f"""
                **Innings 2 - {phase} Phase**
                
                ✅ **Use: Inn-Specific Calibrated ({inn_specific_prob*100:.1f}%)**
                
                Best for both accuracy and calibration in this phase.
                """)
            else:  # Death
                st.info(f"""
                **Innings 2 - {phase} Phase**
                
                📊 **For Best Accuracy (Brier):** Raw Model ({raw_prob*100:.1f}%)
                
                🎯 **For Best Calibration (ECE):** Inn-Specific Calibrated ({inn_specific_prob*100:.1f}%)
                """)
        
        st.markdown("---")
        st.markdown("### 📖 Key Insights")
        st.markdown("""
        - **Innings 1:** Raw model dominates - BBL's ensemble is very well-calibrated out of the box
        - **Innings 2:** Calibrators help, especially Inn-Specific Isotonic
        - **Resource Win Prob:** Only beats others for ECE in Innings 2 Middle Overs
        - **Main Odds Display uses:** Inn-Specific Calibrated probability
        """)
    
    # SA20 Calibration Guidance
    with st.expander("📊 SA20 Calibration Guidance - Which Probability to Trust?"):
        st.markdown("### SA20 v1 Model Performance Analysis")
        st.markdown("""
        Based on comprehensive Brier Score (accuracy) and ECE (calibration) analysis:
        
        | Innings | Phase | Best Brier | Best ECE |
        |---------|-------|------------|----------|
        | **Inn 1** | Powerplay | **Raw (0.1284)** | Resource (0.1437) |
        | **Inn 1** | Middle | **Raw (0.0911)** | Resource (0.1348) |
        | **Inn 1** | Death | **Raw (0.0761)** | Resource (0.1506) |
        | **Inn 2** | Powerplay | **Raw (0.0799)** | Resource (0.1385) |
        | **Inn 2** | Middle | **Raw (0.0507)** | Resource (0.0503) |
        | **Inn 2** | Death | **Raw (0.0375)** | **Raw (0.0892)** |
        
        *Lower is better for both Brier and ECE*
        """)
        
        st.markdown("---")
        
        # Calculate ECE-optimized probability using phase calibrators
        if SA20_PHASE_CALIBRATORS is not None:
            inn_num = 2 if is_inn2 else 1
            phase_key = phase.lower()
            calibrator_key = f'inn{inn_num}_{phase_key}'
            
            if calibrator_key in SA20_PHASE_CALIBRATORS:
                ece_optimized_prob = SA20_PHASE_CALIBRATORS[calibrator_key].predict([[resource_prob]])[0]
                ece_optimized_prob = np.clip(ece_optimized_prob, 0.01, 0.99)
                ece_odds = prob_to_odds(ece_optimized_prob)
                
                st.markdown("### 🎯 Current SA20 Probabilities")
                sa_col1, sa_col2, sa_col3 = st.columns(3)
                with sa_col1:
                    st.markdown(f'''
                    <div style="text-align: center; padding: 10px; background: #e3f2fd; border-radius: 10px; border-left: 4px solid #2196F3;">
                        <b>🎯 Raw (Best Brier)</b><br>
                        <span style="font-size: 1.5em; color: #2196F3;">{raw_prob*100:.1f}%</span><br>
                        <span style="font-size: 1.1em;">Odds: <b>{prob_to_odds(raw_prob)}</b></span>
                    </div>
                    ''', unsafe_allow_html=True)
                with sa_col2:
                    st.markdown(f'''
                    <div style="text-align: center; padding: 10px; background: #fff3e0; border-radius: 10px; border-left: 4px solid #ff9800;">
                        <b>📊 Resource</b><br>
                        <span style="font-size: 1.5em; color: #ff9800;">{resource_prob*100:.1f}%</span><br>
                        <span style="font-size: 1.1em;">Odds: <b>{prob_to_odds(resource_prob)}</b></span>
                    </div>
                    ''', unsafe_allow_html=True)
                with sa_col3:
                    st.markdown(f'''
                    <div style="text-align: center; padding: 10px; background: #e8f5e9; border-radius: 10px; border-left: 4px solid #4CAF50;">
                        <b>✅ ECE-Optimized</b><br>
                        <span style="font-size: 1.5em; color: #4CAF50;">{ece_optimized_prob*100:.1f}%</span><br>
                        <span style="font-size: 1.1em;">Odds: <b>{ece_odds}</b></span><br>
                        <span style="font-size: 0.8em; color: #666;">Inn{inn_num} {phase} Cal</span>
                    </div>
                    ''', unsafe_allow_html=True)
                
                st.markdown("<br>", unsafe_allow_html=True)
        
        st.markdown("### 🎯 SA20 Recommendation")
        
        st.success("""
        **For Best Accuracy (Brier):** Use Raw Model Probability - wins ALL phases
        
        **For Best Calibration (ECE):** Use ECE-Optimized (phase-calibrated resource prob) - perfect ECE
        
        ⚠️ Trade-off: ECE-Optimized has worse Brier but perfectly calibrated probabilities.
        """)
        
        st.markdown("---")
        st.markdown("### 📖 Key Insights")
        st.markdown("""
        - **Raw Model:** Dominates for accuracy (Brier) in every phase - use this for predictions
        - **ECE-Optimized:** Phase-specific calibrators on resource_win_prob → perfect ECE (0.0000)
        - **Trade-off:** You can't have both - ECE optimization hurts Brier
        - **SA20 vs BBL:** SA20 raw model is excellent; BBL needs calibration for Innings 2
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
