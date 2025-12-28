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
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
from pathlib import Path
import time

# Page config
st.set_page_config(
    page_title="WBBL Live Predictor",
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

# Team colors and names
TEAM_COLORS = {
    "SYS-W": "#e91e63", "PRS-W": "#ff5722", "ADL-W": "#2196f3", "BRH-W": "#00bcd4",
    "MLR-W": "#f44336", "MLS-W": "#4caf50", "HBH-W": "#9c27b0", "STR-W": "#8bc34a",
}
TEAM_NAMES = {
    "SYS-W": "Sydney Sixers", "PRS-W": "Perth Scorchers", "ADL-W": "Adelaide Strikers",
    "BRH-W": "Brisbane Heat", "MLR-W": "Melbourne Renegades", "MLS-W": "Melbourne Stars",
    "HBH-W": "Hobart Hurricanes", "STR-W": "Sydney Thunder",
}

DEFAULT_JSON = "data/live_state.json"

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
            return json.load(f)
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


def create_probability_timeline(history):
    """Create probability over time chart showing full 20 overs."""
    if not history or len(history) < 2:
        return None
    
    df = pd.DataFrame(history)
    fig = go.Figure()
    
    # Use first entry to get team names
    bat_team = df.get("batting_team", pd.Series(["Team A"])).iloc[0] if "batting_team" in df else "Batting"
    bowl_team = df.get("bowling_team", pd.Series(["Team B"])).iloc[0] if "bowling_team" in df else "Bowling"
    
    # Get team colors
    bat_color = get_color(bat_team) if bat_team else "#e91e63"
    bowl_color = get_color(bowl_team) if bowl_team else "#2196f3"
    
    fig.add_trace(go.Scatter(
        x=df["overs"], y=df["bat_prob"].apply(lambda x: x * 100),
        name=get_name(bat_team), mode="lines+markers",
        line=dict(color=bat_color, width=3),
        marker=dict(size=6),
        fill='tozeroy', fillcolor=f'rgba{tuple(list(int(bat_color.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)) + [0.1])}' if bat_color.startswith('#') else None
    ))
    fig.add_trace(go.Scatter(
        x=df["overs"], y=df["bowl_prob"].apply(lambda x: x * 100),
        name=get_name(bowl_team), mode="lines+markers",
        line=dict(color=bowl_color, width=3),
        marker=dict(size=6)
    ))
    
    fig.add_hline(y=50, line_dash="dash", line_color="gray", annotation_text="50%")
    
    # Determine max overs for x-axis (at least current over + buffer, max 20)
    max_over = max(df["overs"].max(), 1)
    x_max = min(20, max(max_over + 2, 6))  # Show at least 6 overs or current + 2
    
    fig.update_layout(
        title="Win Probability Over Time",
        xaxis_title="Overs", yaxis_title="Win Probability (%)",
        xaxis=dict(range=[0, x_max], dtick=2, tickmode='linear'),
        yaxis=dict(range=[0, 100], dtick=10),
        height=350, margin=dict(l=20, r=20, t=50, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        hovermode='x unified'
    )
    return fig


def main():
    st.markdown('<h1 class="main-header">🏏 WBBL Live Predictor</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align:center;color:#666;">Powered by WBBL Champion Model v3 (Brier: 0.1737)</p>', unsafe_allow_html=True)
    
    # Controls
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        json_path = st.text_input("JSON State File", value=DEFAULT_JSON, 
                                  help="Path to the live state JSON file produced by crex_live_predictor")
    with col2:
        refresh = st.button("🔄 Refresh", use_container_width=True)
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
        create_gauges(d["batting_team"], d["bowling_team"], d["bat_win_prob"], d["bowl_win_prob"]), 
        use_container_width=True
    )
    
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
        st.plotly_chart(create_resource_gauge(res), use_container_width=True)
    with c2:
        if d.get("target"):
            rrr = f.get("required_run_rate", d.get("required_run_rate", 10))
            st.plotly_chart(create_rr_chart(crr, rrr), use_container_width=True)
        else:
            # Show score vs par
            par = f.get("score_vs_par", 0)
            fig = go.Figure(go.Indicator(
                mode="delta+number", value=par,
                title={"text": "Score vs Par"},
                delta={"reference": 0, "increasing": {"color": "#4CAF50"}, "decreasing": {"color": "#f44336"}}
            ))
            fig.update_layout(height=200, margin=dict(l=20, r=20, t=50, b=20))
            st.plotly_chart(fig, use_container_width=True)
    
    # Probability timeline
    history = d.get("history", [])
    timeline = create_probability_timeline(history)
    if timeline:
        st.markdown("---")
        st.plotly_chart(timeline, use_container_width=True)
    
    # Feature details
    with st.expander("🔍 All Features (Advanced)"):
        if f:
            feature_list = []
            for k, v in sorted(f.items()):
                val_str = f"{v:.4f}" if isinstance(v, float) else str(v)
                feature_list.append({"Feature": k, "Value": val_str})
            st.dataframe(pd.DataFrame(feature_list), use_container_width=True, hide_index=True)
        else:
            st.info("No features available")
    
    # Auto-refresh
    if auto:
        time.sleep(3)
        st.rerun()


if __name__ == "__main__":
    main()
