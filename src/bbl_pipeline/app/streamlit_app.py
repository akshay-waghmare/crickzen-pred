"""
WBBL Live Match Prediction - Streamlit App
Real-time win probability visualization for Women's Big Bash League matches.
"""

import streamlit as st
import asyncio
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime
import time
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from bbl_pipeline.inference.predictor import Predictor
from bbl_pipeline.inference.schema import MatchState

# Page config
st.set_page_config(
    page_title="WBBL Live Predictor",
    page_icon="🏏",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        text-align: center;
        padding: 1rem;
        background: linear-gradient(90deg, #e91e63, #9c27b0);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .team-card {
        padding: 1.5rem;
        border-radius: 10px;
        text-align: center;
    }
    .batting-team {
        background: linear-gradient(135deg, #4CAF50, #45a049);
        color: white;
    }
    .bowling-team {
        background: linear-gradient(135deg, #2196F3, #1976D2);
        color: white;
    }
    .metric-card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        text-align: center;
        margin: 0.5rem 0;
    }
    .win-prob-high { color: #4CAF50; font-weight: bold; }
    .win-prob-low { color: #f44336; font-weight: bold; }
    .stMetric > div { text-align: center; }
</style>
""", unsafe_allow_html=True)


# Team colors for WBBL
TEAM_COLORS = {
    "Sydney Sixers": "#e91e63",
    "SYS-W": "#e91e63",
    "Perth Scorchers": "#ff5722",
    "PRS-W": "#ff5722",
    "Adelaide Strikers": "#2196f3",
    "ADL-W": "#2196f3",
    "Brisbane Heat": "#00bcd4",
    "BRH-W": "#00bcd4",
    "Melbourne Renegades": "#f44336",
    "MLR-W": "#f44336",
    "Melbourne Stars": "#4caf50",
    "MLS-W": "#4caf50",
    "Hobart Hurricanes": "#9c27b0",
    "HBH-W": "#9c27b0",
    "Sydney Thunder": "#8bc34a",
    "STR-W": "#8bc34a",
}

def get_team_color(team: str) -> str:
    """Get team color, with fallback."""
    return TEAM_COLORS.get(team, "#607d8b")


def create_win_probability_gauge(batting_team: str, bowling_team: str, 
                                  batting_prob: float, bowling_prob: float) -> go.Figure:
    """Create a dual gauge chart for win probabilities."""
    fig = make_subplots(
        rows=1, cols=2,
        specs=[[{"type": "indicator"}, {"type": "indicator"}]],
        subplot_titles=[batting_team, bowling_team]
    )
    
    # Batting team gauge
    fig.add_trace(
        go.Indicator(
            mode="gauge+number",
            value=batting_prob * 100,
            number={"suffix": "%", "font": {"size": 40}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1},
                "bar": {"color": get_team_color(batting_team)},
                "bgcolor": "white",
                "borderwidth": 2,
                "bordercolor": "gray",
                "steps": [
                    {"range": [0, 30], "color": "#ffebee"},
                    {"range": [30, 50], "color": "#fff3e0"},
                    {"range": [50, 70], "color": "#e8f5e9"},
                    {"range": [70, 100], "color": "#c8e6c9"}
                ],
                "threshold": {
                    "line": {"color": "black", "width": 4},
                    "thickness": 0.75,
                    "value": 50
                }
            }
        ),
        row=1, col=1
    )
    
    # Bowling team gauge
    fig.add_trace(
        go.Indicator(
            mode="gauge+number",
            value=bowling_prob * 100,
            number={"suffix": "%", "font": {"size": 40}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1},
                "bar": {"color": get_team_color(bowling_team)},
                "bgcolor": "white",
                "borderwidth": 2,
                "bordercolor": "gray",
                "steps": [
                    {"range": [0, 30], "color": "#ffebee"},
                    {"range": [30, 50], "color": "#fff3e0"},
                    {"range": [50, 70], "color": "#e8f5e9"},
                    {"range": [70, 100], "color": "#c8e6c9"}
                ],
                "threshold": {
                    "line": {"color": "black", "width": 4},
                    "thickness": 0.75,
                    "value": 50
                }
            }
        ),
        row=1, col=2
    )
    
    fig.update_layout(
        height=300,
        margin=dict(l=20, r=20, t=40, b=20),
        font={"family": "Arial"}
    )
    
    return fig


def create_resource_chart(resources_remaining: float, resources_used: float) -> go.Figure:
    """Create a DLS resources chart."""
    fig = go.Figure()
    
    fig.add_trace(go.Pie(
        values=[resources_remaining * 100, resources_used * 100],
        labels=["Remaining", "Used"],
        marker_colors=["#4CAF50", "#e0e0e0"],
        hole=0.6,
        textinfo="label+percent",
        textposition="outside"
    ))
    
    fig.add_annotation(
        text=f"{resources_remaining*100:.1f}%",
        x=0.5, y=0.5,
        font_size=24,
        showarrow=False
    )
    
    fig.update_layout(
        title="DLS Resources",
        height=250,
        margin=dict(l=20, r=20, t=40, b=20),
        showlegend=False
    )
    
    return fig


def create_run_rate_comparison(crr: float, rrr: float) -> go.Figure:
    """Create run rate comparison bar chart."""
    colors = ["#4CAF50" if crr >= rrr else "#f44336", "#2196F3"]
    
    fig = go.Figure(data=[
        go.Bar(
            x=["Current RR", "Required RR"],
            y=[crr, rrr],
            marker_color=colors,
            text=[f"{crr:.2f}", f"{rrr:.2f}"],
            textposition="outside"
        )
    ])
    
    fig.update_layout(
        title="Run Rate Comparison",
        yaxis_title="Runs per Over",
        height=250,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    
    return fig


def create_probability_timeline(history: list) -> go.Figure:
    """Create probability timeline chart."""
    if not history:
        return None
    
    df = pd.DataFrame(history)
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df["over"],
        y=df["batting_prob"] * 100,
        mode="lines+markers",
        name=df["batting_team"].iloc[0] if len(df) > 0 else "Batting",
        line=dict(width=3),
        marker=dict(size=8)
    ))
    
    fig.add_trace(go.Scatter(
        x=df["over"],
        y=df["bowling_prob"] * 100,
        mode="lines+markers",
        name=df["bowling_team"].iloc[0] if len(df) > 0 else "Bowling",
        line=dict(width=3, dash="dash"),
        marker=dict(size=8)
    ))
    
    fig.add_hline(y=50, line_dash="dot", line_color="gray", opacity=0.5)
    
    fig.update_layout(
        title="Win Probability Over Time",
        xaxis_title="Over",
        yaxis_title="Win Probability (%)",
        yaxis=dict(range=[0, 100]),
        height=300,
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    return fig


def create_feature_importance_chart(features: dict) -> go.Figure:
    """Create feature values chart for key features."""
    key_features = [
        ("run_rate_diff", "Run Rate Diff"),
        ("resources_remaining", "Resources %"),
        ("pressure_index", "Pressure Index"),
        ("chase_difficulty", "Chase Difficulty"),
        ("score_vs_par", "Score vs Par"),
        ("batsman_rolling_avg", "Batsman Avg"),
        ("bowler_rolling_econ", "Bowler Econ")
    ]
    
    labels = []
    values = []
    colors = []
    
    for feat_key, feat_label in key_features:
        if feat_key in features:
            val = features[feat_key]
            labels.append(feat_label)
            values.append(val)
            # Color based on whether it favors batting (green) or bowling (red)
            if feat_key == "run_rate_diff":
                colors.append("#4CAF50" if val > 0 else "#f44336")
            elif feat_key == "resources_remaining":
                colors.append("#4CAF50" if val > 0.5 else "#f44336")
            elif feat_key == "pressure_index":
                colors.append("#f44336" if val > 0.5 else "#4CAF50")
            else:
                colors.append("#2196F3")
    
    fig = go.Figure(data=[
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker_color=colors,
            text=[f"{v:.2f}" for v in values],
            textposition="outside"
        )
    ])
    
    fig.update_layout(
        title="Key Features",
        height=300,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    
    return fig


# Initialize session state
if "prediction_history" not in st.session_state:
    st.session_state.prediction_history = []
if "last_update" not in st.session_state:
    st.session_state.last_update = None
if "predictor" not in st.session_state:
    st.session_state.predictor = None
if "features_cache" not in st.session_state:
    st.session_state.features_cache = {}


def load_model(model_dir: str, feature_store_dir: str):
    """Load the prediction model."""
    try:
        predictor = Predictor.load(model_dir, feature_store_dir)
        return predictor
    except Exception as e:
        st.error(f"Failed to load model: {e}")
        return None


def main():
    # Header
    st.markdown('<h1 class="main-header">🏏 WBBL Live Match Predictor</h1>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        model_dir = st.text_input(
            "Model Directory",
            value="models/wbbl_champion_v3",
            help="Path to the trained model"
        )
        
        feature_store_dir = st.text_input(
            "Feature Store Directory", 
            value="data/wbbl_feature_store_v3",
            help="Path to the feature store"
        )
        
        if st.button("🔄 Load Model", type="primary"):
            with st.spinner("Loading model..."):
                predictor = load_model(model_dir, feature_store_dir)
                if predictor:
                    st.session_state.predictor = predictor
                    st.success("✅ Model loaded!")
        
        if st.session_state.predictor:
            st.success("✅ Model Ready")
            # Try to load metadata separately
            try:
                import json
                meta_path = Path(model_dir) / "champion_metadata.json"
                if meta_path.exists():
                    with open(meta_path) as f:
                        meta = json.load(f)
                    st.caption(f"Model: {meta.get('model_name', 'Unknown')}")
                    st.caption(f"Version: {meta.get('version', 'Unknown')}")
            except:
                st.caption("Model loaded")
        
        st.divider()
        st.header("📊 Match Input")
        
        # Manual input mode
        st.subheader("Match Details")
        
        col1, col2 = st.columns(2)
        with col1:
            batting_team = st.selectbox(
                "Batting Team",
                ["SYS-W", "PRS-W", "ADL-W", "BRH-W", "MLR-W", "MLS-W", "HBH-W", "STR-W"]
            )
        with col2:
            bowling_team = st.selectbox(
                "Bowling Team",
                ["PRS-W", "SYS-W", "ADL-W", "BRH-W", "MLR-W", "MLS-W", "HBH-W", "STR-W"]
            )
        
        venue = st.selectbox(
            "Venue",
            ["North Sydney Oval", "Adelaide Oval", "WACA Ground", "Allan Border Field",
             "Bellerive Oval", "Junction Oval", "Manuka Oval", "Aurora Stadium"]
        )
        
        innings = st.radio("Innings", [1, 2], horizontal=True)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            score = st.number_input("Score", min_value=0, max_value=300, value=74)
        with col2:
            wickets = st.number_input("Wickets", min_value=0, max_value=10, value=3)
        with col3:
            overs = st.number_input("Overs", min_value=0.0, max_value=20.0, value=10.0, step=0.1)
        
        if innings == 2:
            target = st.number_input("Target", min_value=1, max_value=300, value=184)
        else:
            target = None
        
        batsman1 = st.text_input("Striker", value="Amelia Kerr")
        batsman2 = st.text_input("Non-Striker", value="Ashleigh Gardner")
        bowler = st.text_input("Bowler", value="")
        
        # Recent balls for rolling stats
        st.subheader("Recent Balls (last 18)")
        recent_balls_str = st.text_area(
            "Ball results (comma separated: runs or W for wicket)",
            value="1,0,0,4,W,0,1,0,0,1,0,4,W,0,1,0,0,1",
            help="e.g., 1,0,4,W,0,1,0,0"
        )
        
        predict_btn = st.button("🎯 Predict", type="primary", use_container_width=True)
    
    # Main content
    if predict_btn and st.session_state.predictor:
        # Parse recent balls for ball history
        ball_history = []
        running_score = max(0, score - 20)  # Estimate starting score
        running_wickets = max(0, wickets - 1) if wickets > 0 else 0
        
        for b in recent_balls_str.split(","):
            b = b.strip()
            if b == "W":
                running_wickets += 1
                ball_history.append({
                    "runs_scored": 0, 
                    "is_wicket": 1, 
                    "is_boundary": 0,
                    "total_score": running_score,
                    "total_wickets": running_wickets
                })
            elif b.isdigit():
                runs = int(b)
                running_score += runs
                ball_history.append({
                    "runs_scored": runs, 
                    "is_wicket": 0, 
                    "is_boundary": 1 if runs >= 4 else 0,
                    "total_score": running_score,
                    "total_wickets": running_wickets
                })
        
        # Build MatchState
        over_int = int(overs)
        ball_int = int((overs % 1) * 10)
        
        match_state = MatchState(
            match_id="manual_input",
            venue=venue,
            batting_team=batting_team,
            bowling_team=bowling_team,
            innings=innings,
            over=over_int,
            ball=ball_int,
            current_score=score,
            wickets_lost=wickets,
            batsman_1=batsman1,
            batsman_2=batsman2,
            bowler=bowler if bowler else "Unknown",
            target_runs=target if innings == 2 else None,
        )
        
        # Get prediction with features
        predictor = st.session_state.predictor
        
        # Feed ball history to mapper
        predictor.feature_mapper.ball_history = ball_history
        
        # Make prediction (get features for display)
        raw_batting_prob = predictor.predict(match_state, debug=False, ball_history=ball_history)
        
        # Use brier_optimized (per-over) calibration if available, else fall back to raw
        if hasattr(predictor, 'last_calibrated_per_over') and predictor.last_calibrated_per_over != raw_batting_prob:
            batting_prob = predictor.last_calibrated_per_over
        else:
            batting_prob = raw_batting_prob
        bowling_prob = 1 - batting_prob
        
        # Get features from mapper for display
        scraped_data = {
            'innings_num': innings,
            'over_number': over_int,
            'ball_number': ball_int,
            'total_score': score,
            'total_wickets': wickets,
            'current_batsman': batsman1,
            'non_striker': batsman2,
            'current_bowler': bowler,
            'batting_team': batting_team,
            'bowling_team': bowling_team,
            'venue': venue,
            'target_score': target if innings == 2 else None,
            'runs_needed': (target - score) if target else 0,
        }
        features_df = predictor.feature_mapper.create_feature_dataframe(scraped_data)
        features = features_df.iloc[0].to_dict()
        
        # Store in history
        st.session_state.prediction_history.append({
            "over": overs,
            "batting_team": batting_team,
            "bowling_team": bowling_team,
            "batting_prob": batting_prob,
            "bowling_prob": bowling_prob,
            "score": score,
            "wickets": wickets
        })
        st.session_state.last_update = datetime.now()
        
        # Display results
        st.markdown("---")
        
        # Score display
        col1, col2, col3 = st.columns([2, 1, 2])
        
        with col1:
            st.markdown(f"""
            <div class="team-card batting-team">
                <h2>{batting_team}</h2>
                <h1>{score}/{wickets}</h1>
                <p>({overs} overs)</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown("<h2 style='text-align: center; padding-top: 30px;'>vs</h2>", unsafe_allow_html=True)
        
        with col3:
            if innings == 2:
                st.markdown(f"""
                <div class="team-card bowling-team">
                    <h2>{bowling_team}</h2>
                    <h1>{target-1}/{10}</h1>
                    <p>(20.0 overs)</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="team-card bowling-team">
                    <h2>{bowling_team}</h2>
                    <h3>Yet to bat</h3>
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Win probability gauges
        st.subheader("🎯 Win Probability")
        gauge_fig = create_win_probability_gauge(
            batting_team, bowling_team, batting_prob, bowling_prob
        )
        st.plotly_chart(gauge_fig, use_container_width=True)
        
        # Key metrics
        st.subheader("📈 Key Metrics")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            crr = features.get("current_run_rate", 0)
            st.metric("Current Run Rate", f"{crr:.2f}")
        
        with col2:
            rrr = features.get("required_run_rate", 0)
            if innings == 2:
                delta = crr - rrr
                st.metric("Required Run Rate", f"{rrr:.2f}", f"{delta:+.2f}")
            else:
                st.metric("Projected Score", f"{features.get('projected_score', 0):.0f}")
        
        with col3:
            resources = features.get("resources_remaining", 1.0)
            st.metric("DLS Resources", f"{resources*100:.1f}%")
        
        with col4:
            pressure = features.get("pressure_index", 0)
            st.metric("Pressure Index", f"{pressure:.2f}")
        
        # Charts row
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            resource_fig = create_resource_chart(
                features.get("resources_remaining", 0.5),
                1 - features.get("resources_remaining", 0.5)
            )
            st.plotly_chart(resource_fig, use_container_width=True)
        
        with col2:
            if innings == 2:
                rr_fig = create_run_rate_comparison(
                    features.get("current_run_rate", 0),
                    features.get("required_run_rate", 0)
                )
                st.plotly_chart(rr_fig, use_container_width=True)
            else:
                # First innings - show projected vs venue avg
                fig = go.Figure(data=[
                    go.Bar(
                        x=["Projected", "Venue Avg"],
                        y=[features.get("projected_score", 0), 
                           features.get("projected_score", 0) - features.get("projected_vs_venue_avg", 0)],
                        marker_color=["#4CAF50", "#2196F3"]
                    )
                ])
                fig.update_layout(title="Score Projection", height=250)
                st.plotly_chart(fig, use_container_width=True)
        
        with col3:
            feature_fig = create_feature_importance_chart(features)
            st.plotly_chart(feature_fig, use_container_width=True)
        
        # Probability timeline
        if len(st.session_state.prediction_history) > 1:
            st.markdown("---")
            st.subheader("📊 Probability Timeline")
            timeline_fig = create_probability_timeline(st.session_state.prediction_history)
            if timeline_fig:
                st.plotly_chart(timeline_fig, use_container_width=True)
        
        # Feature details (expandable)
        with st.expander("🔍 All Features"):
            feature_df_display = pd.DataFrame([
                {"Feature": k, "Value": f"{v:.4f}"} for k, v in sorted(features.items())
            ])
            st.dataframe(feature_df_display, use_container_width=True, hide_index=True)
        
        # DLS Resource explanation
        with st.expander("📖 DLS Resources Explained"):
            st.markdown("""
            **DLS (Duckworth-Lewis-Stern)** resources represent the batting potential remaining in an innings.
            
            - **100% resources**: Full 20 overs, 10 wickets in hand
            - **Resources decrease** as overs are bowled and wickets fall
            - **Resource-based win probability**: Compares actual score to par score based on resources used
            
            **Current Calculation:**
            """)
            st.write(f"- Resources Remaining: **{features.get('resources_remaining', 0)*100:.1f}%**")
            st.write(f"- Resource Win Prob: **{features.get('resource_win_prob', 0)*100:.1f}%**")
            st.write(f"- DLS Pressure Index: **{features.get('dls_pressure_index', 0):.3f}**")
    
    elif predict_btn and not st.session_state.predictor:
        st.warning("⚠️ Please load the model first using the sidebar.")
    
    # Footer
    st.markdown("---")
    st.caption("WBBL Live Predictor v3 | Model: XGBoost Tuned | Brier Score: 0.1737")
    if st.session_state.last_update:
        st.caption(f"Last updated: {st.session_state.last_update.strftime('%H:%M:%S')}")


if __name__ == "__main__":
    main()
