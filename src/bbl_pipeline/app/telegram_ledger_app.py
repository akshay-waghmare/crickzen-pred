"""
Telegram Prediction Ledger - Streamlit App.

Manual posting interface for creating immutable, timestamped predictions
on a Telegram channel.

Usage:
    streamlit run src/bbl_pipeline/app/telegram_ledger_app.py
"""

import streamlit as st
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="Telegram Prediction Ledger",
    page_icon="📢",
    layout="wide",
)


# Supported leagues
LEAGUES = [
    "BBL", "SA20", "ILT20", "WPL", "SSM", "T20I", 
    "IPL", "PSL", "CPL", "BPL", "LPL", "WBBL", "Other"
]


def get_telegram_client():
    """Get or create Telegram bot client from session state."""
    from bbl_pipeline.telegram.config import load_config, is_configured, ConfigError
    from bbl_pipeline.telegram.bot_client import TelegramBotClient
    
    if "telegram_client" not in st.session_state:
        if not is_configured():
            return None
        try:
            config = load_config()
            st.session_state.telegram_client = TelegramBotClient(config)
            st.session_state.telegram_config = config
        except ConfigError as e:
            st.error(f"Configuration error: {e}")
            return None
    
    return st.session_state.telegram_client


def get_storage():
    """Get or create prediction storage from session state."""
    from bbl_pipeline.telegram.storage import PredictionStorage
    
    if "prediction_storage" not in st.session_state:
        config = st.session_state.get("telegram_config")
        storage_path = config.storage_path if config else "data/telegram_predictions.jsonl"
        st.session_state.prediction_storage = PredictionStorage(storage_path)
    
    return st.session_state.prediction_storage


def calculate_edge(model_probability: float, market_odds: float) -> float:
    """Calculate model edge percentage."""
    implied_prob = 1.0 / market_odds
    model_prob = model_probability / 100.0
    return (model_prob - implied_prob) * 100


# ============================================================================
# PRE-MATCH PREDICTION MODAL (User Story 1)
# ============================================================================

@st.dialog("📢 Post Pre-Match Prediction", width="large")
def show_prematch_prediction_modal():
    """Modal dialog for posting pre-match predictions."""
    from bbl_pipeline.telegram.message_formatter import format_prematch_prediction
    from bbl_pipeline.telegram.storage import PredictionStorage
    
    st.markdown("Create an immutable, timestamped prediction record on Telegram.")
    
    # Form for prediction data
    with st.form("prediction_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        
        with col1:
            match_id = st.text_input(
                "Match ID *",
                placeholder="e.g., 1234567 (Cricsheet ID)",
                help="Unique identifier for the match"
            )
            league = st.selectbox(
                "League *",
                options=LEAGUES,
                help="Select the league/competition"
            )
            team_a = st.text_input(
                "Team A *",
                placeholder="e.g., Sydney Sixers",
                help="First team name"
            )
            team_b = st.text_input(
                "Team B *",
                placeholder="e.g., Melbourne Stars",
                help="Second team name"
            )
        
        with col2:
            selection_type = st.radio(
                "Selection Type *",
                options=["BACK", "LAY"],
                horizontal=True,
                help="BACK = team wins, LAY = team loses"
            )
            selected_team = st.selectbox(
                "Selected Team *",
                options=["(Select team)", team_a, team_b] if team_a and team_b else ["(Enter teams first)"],
                help="Team you are backing or laying"
            )
            model_probability = st.number_input(
                "Model Win Probability (%) *",
                min_value=0.0,
                max_value=100.0,
                value=50.0,
                step=0.1,
                help="Model's probability for the selected team to win"
            )
            market_odds = st.number_input(
                "Market Odds (Decimal) *",
                min_value=1.01,
                max_value=1000.0,
                value=2.00,
                step=0.01,
                help="Current market decimal odds for the selected team"
            )
        
        # Calculate edge
        model_edge = calculate_edge(model_probability, market_odds)
        st.metric(
            "Calculated Model Edge",
            f"{model_edge:+.1f}%",
            delta=None,
            help="Edge = Model Probability - Implied Probability from Odds"
        )
        
        st.divider()
        
        # Preview
        st.markdown("**Message Preview:**")
        if match_id and team_a and team_b and selected_team not in ["(Select team)", "(Enter teams first)"]:
            preview = format_prematch_prediction(
                match_id=match_id,
                league=league,
                team_a=team_a,
                team_b=team_b,
                selection_type=selection_type,
                selected_team=selected_team,
                model_probability=model_probability,
                market_odds=market_odds,
                model_edge=model_edge,
            )
            # Show preview (convert HTML to displayable format)
            st.code(preview.replace("<b>", "").replace("</b>", ""), language=None)
        else:
            st.info("Fill in all fields to see preview")
        
        st.divider()
        
        # Submit button
        submitted = st.form_submit_button("🚀 Post to Telegram", type="primary", use_container_width=True)
        
        if submitted:
            # Validation
            errors = []
            if not match_id:
                errors.append("Match ID is required")
            if not team_a:
                errors.append("Team A is required")
            if not team_b:
                errors.append("Team B is required")
            if selected_team in ["(Select team)", "(Enter teams first)"]:
                errors.append("Selected Team is required")
            
            if errors:
                for error in errors:
                    st.error(f"❌ {error}")
            else:
                # Post to Telegram
                client = get_telegram_client()
                if client is None:
                    st.error("❌ Telegram not configured. Please set TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID in your .env file.")
                else:
                    message = format_prematch_prediction(
                        match_id=match_id,
                        league=league,
                        team_a=team_a,
                        team_b=team_b,
                        selection_type=selection_type,
                        selected_team=selected_team,
                        model_probability=model_probability,
                        market_odds=market_odds,
                        model_edge=model_edge,
                    )
                    
                    with st.spinner("Posting to Telegram..."):
                        result = client.send_message(message)
                    
                    if result.success:
                        # Store record
                        storage = get_storage()
                        record = {
                            "match_id": match_id,
                            "league": league,
                            "team_a": team_a,
                            "team_b": team_b,
                            "selection_type": selection_type,
                            "selected_team": selected_team,
                            "model_probability": model_probability,
                            "market_odds": market_odds,
                            "model_edge": model_edge,
                            "telegram_message_id": result.message_id,
                            "telegram_timestamp": result.timestamp.isoformat() if result.timestamp else None,
                            "post_type": "pre_match",
                        }
                        storage.append_record(record)
                        
                        st.success(f"✅ Posted successfully! Message ID: {result.message_id}")
                        st.balloons()
                    else:
                        st.error(f"❌ Failed to post: {result.error_message}")
                        if result.error_type == "unauthorized":
                            st.info("💡 Check that your bot is an admin of the channel with 'Post Messages' permission.")


# ============================================================================
# MATCH START MODAL (User Story 2)
# ============================================================================

@st.dialog("🏏 Post Match Start Info", width="large")
def show_match_start_modal():
    """Modal dialog for posting match start context."""
    from bbl_pipeline.telegram.message_formatter import format_match_start
    
    st.markdown("Log the toss result and match start conditions.")
    
    with st.form("match_start_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        
        with col1:
            match_id = st.text_input(
                "Match ID *",
                placeholder="e.g., 1234567",
                help="Same Match ID as pre-match prediction"
            )
            team_a = st.text_input("Team A *", placeholder="e.g., Sydney Sixers")
            team_b = st.text_input("Team B *", placeholder="e.g., Melbourne Stars")
        
        with col2:
            toss_winner = st.selectbox(
                "Toss Winner *",
                options=["(Select team)", team_a, team_b] if team_a and team_b else ["(Enter teams first)"],
                help="Team that won the toss"
            )
            toss_decision = st.radio(
                "Toss Decision *",
                options=["Bat", "Bowl"],
                horizontal=True,
                help="What the toss winner elected to do"
            )
            model_prematch_probability = st.number_input(
                "Pre-Match Model Probability (%)",
                min_value=0.0,
                max_value=100.0,
                value=50.0,
                step=0.1,
                help="Optional: reference from pre-match prediction"
            )
        
        st.divider()
        
        # Preview
        st.markdown("**Message Preview:**")
        if match_id and team_a and team_b and toss_winner not in ["(Select team)", "(Enter teams first)"]:
            preview = format_match_start(
                match_id=match_id,
                team_a=team_a,
                team_b=team_b,
                toss_winner=toss_winner,
                toss_decision=toss_decision,
                model_prematch_probability=model_prematch_probability,
            )
            st.code(preview.replace("<b>", "").replace("</b>", ""), language=None)
        else:
            st.info("Fill in all fields to see preview")
        
        st.divider()
        
        submitted = st.form_submit_button("🚀 Post to Telegram", type="primary", use_container_width=True)
        
        if submitted:
            errors = []
            if not match_id:
                errors.append("Match ID is required")
            if not team_a:
                errors.append("Team A is required")
            if not team_b:
                errors.append("Team B is required")
            if toss_winner in ["(Select team)", "(Enter teams first)"]:
                errors.append("Toss Winner is required")
            
            if errors:
                for error in errors:
                    st.error(f"❌ {error}")
            else:
                client = get_telegram_client()
                if client is None:
                    st.error("❌ Telegram not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID in .env")
                else:
                    message = format_match_start(
                        match_id=match_id,
                        team_a=team_a,
                        team_b=team_b,
                        toss_winner=toss_winner,
                        toss_decision=toss_decision,
                        model_prematch_probability=model_prematch_probability,
                    )
                    
                    with st.spinner("Posting to Telegram..."):
                        result = client.send_message(message)
                    
                    if result.success:
                        storage = get_storage()
                        record = {
                            "match_id": match_id,
                            "team_a": team_a,
                            "team_b": team_b,
                            "toss_winner": toss_winner,
                            "toss_decision": toss_decision,
                            "model_prematch_probability": model_prematch_probability,
                            "telegram_message_id": result.message_id,
                            "telegram_timestamp": result.timestamp.isoformat() if result.timestamp else None,
                            "post_type": "match_start",
                        }
                        storage.append_record(record)
                        
                        st.success(f"✅ Posted successfully! Message ID: {result.message_id}")
                        st.balloons()
                    else:
                        st.error(f"❌ Failed to post: {result.error_message}")


# ============================================================================
# MATCH RESULT MODAL (User Story 3)
# ============================================================================

@st.dialog("🏆 Post Match Result", width="large")
def show_match_result_modal():
    """Modal dialog for posting match results."""
    from bbl_pipeline.telegram.message_formatter import format_match_result, determine_correctness
    
    st.markdown("Record the match outcome and whether the prediction was correct.")
    
    with st.form("match_result_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        
        with col1:
            match_id = st.text_input(
                "Match ID *",
                placeholder="e.g., 1234567",
                help="Same Match ID as pre-match prediction"
            )
            
            # Try to look up original prediction
            lookup_clicked = st.form_submit_button("🔍 Look up prediction", type="secondary")
        
        # Show looked up data if available
        original_prediction = None
        if match_id:
            storage = get_storage()
            original_prediction = storage.find_prediction_by_match_id(match_id)
            
            if original_prediction:
                st.success(f"Found prediction: {original_prediction.get('selection_type')} {original_prediction.get('selected_team')} @ {original_prediction.get('model_probability')}%")
                team_options = [original_prediction.get("team_a", ""), original_prediction.get("team_b", "")]
            else:
                st.info("No pre-match prediction found for this Match ID")
                team_options = []
        
        with col2:
            if team_options:
                winning_team = st.selectbox("Winning Team *", options=team_options)
            else:
                winning_team = st.text_input("Winning Team *", placeholder="e.g., Sydney Sixers")
        
        st.divider()
        
        # Calculate correctness if we have original prediction
        model_call_correct = None
        original_selection_type = None
        original_selected_team = None
        original_probability = None
        
        if original_prediction and winning_team:
            original_selection_type = original_prediction.get("selection_type")
            original_selected_team = original_prediction.get("selected_team")
            original_probability = original_prediction.get("model_probability")
            
            model_call_correct = determine_correctness(
                winning_team=winning_team,
                selection_type=original_selection_type,
                selected_team=original_selected_team,
            )
            
            if model_call_correct:
                st.success(f"✓ Model call was CORRECT ({original_selection_type} {original_selected_team})")
            else:
                st.error(f"✗ Model call was INCORRECT ({original_selection_type} {original_selected_team})")
        
        # Preview
        st.markdown("**Message Preview:**")
        if match_id and winning_team:
            preview = format_match_result(
                match_id=match_id,
                winning_team=winning_team,
                model_call_correct=model_call_correct,
                original_selection_type=original_selection_type,
                original_probability=original_probability,
            )
            st.code(preview.replace("<b>", "").replace("</b>", ""), language=None)
        else:
            st.info("Fill in all fields to see preview")
        
        st.divider()
        
        submitted = st.form_submit_button("🚀 Post to Telegram", type="primary", use_container_width=True)
        
        if submitted:
            errors = []
            if not match_id:
                errors.append("Match ID is required")
            if not winning_team:
                errors.append("Winning Team is required")
            
            if errors:
                for error in errors:
                    st.error(f"❌ {error}")
            else:
                client = get_telegram_client()
                if client is None:
                    st.error("❌ Telegram not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID in .env")
                else:
                    message = format_match_result(
                        match_id=match_id,
                        winning_team=winning_team,
                        model_call_correct=model_call_correct,
                        original_selection_type=original_selection_type,
                        original_probability=original_probability,
                    )
                    
                    with st.spinner("Posting to Telegram..."):
                        result = client.send_message(message)
                    
                    if result.success:
                        storage = get_storage()
                        record = {
                            "match_id": match_id,
                            "winning_team": winning_team,
                            "model_call_correct": model_call_correct,
                            "original_selection_type": original_selection_type,
                            "original_selected_team": original_selected_team,
                            "original_probability": original_probability,
                            "telegram_message_id": result.message_id,
                            "telegram_timestamp": result.timestamp.isoformat() if result.timestamp else None,
                            "post_type": "result",
                        }
                        storage.append_record(record)
                        
                        st.success(f"✅ Posted successfully! Message ID: {result.message_id}")
                        st.balloons()
                    else:
                        st.error(f"❌ Failed to post: {result.error_message}")


# ============================================================================
# MAIN APP
# ============================================================================

def main():
    """Main application entry point."""
    st.title("📢 Telegram Prediction Ledger")
    st.markdown("""
    Create immutable, timestamped prediction records on Telegram.
    All posts are permanent and cannot be edited or deleted.
    """)
    
    # Check configuration status
    from bbl_pipeline.telegram.config import is_configured
    
    if not is_configured():
        st.warning("""
        ⚠️ **Telegram not configured**
        
        To use this feature, create a `.env` file with:
        ```
        TELEGRAM_BOT_TOKEN=your_bot_token_here
        TELEGRAM_CHANNEL_ID=@your_channel_here
        ```
        
        See `config/.env.example` for a template.
        """)
    else:
        st.success("✅ Telegram configured")
    
    st.divider()
    
    # Main action buttons
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("### 📋 Pre-Match")
        st.caption("Post a prediction before the match starts")
        if st.button("Post Pre-Match Prediction", type="primary", use_container_width=True):
            show_prematch_prediction_modal()
    
    with col2:
        st.markdown("### 🏏 Match Start")
        st.caption("Log toss result and match conditions")
        if st.button("Post Match Start Info", use_container_width=True):
            show_match_start_modal()
    
    with col3:
        st.markdown("### 🏆 Result")
        st.caption("Record match outcome and result")
        if st.button("Post Match Result", use_container_width=True):
            show_match_result_modal()
    
    st.divider()
    
    # Recent posts section
    st.markdown("### 📜 Recent Posts")
    
    storage = get_storage()
    recent_records = storage.get_recent_records(limit=10)
    
    if not recent_records:
        st.info("No posts yet. Use the buttons above to create your first prediction record.")
    else:
        for record in recent_records:
            post_type = record.get("post_type", "unknown")
            match_id = record.get("match_id", "N/A")
            timestamp = record.get("posted_at_utc", "N/A")
            
            # Format display based on post type
            if post_type == "pre_match":
                icon = "📋"
                title = f"{record.get('selection_type')} {record.get('selected_team')}"
                details = f"Prob: {record.get('model_probability')}% | Odds: {record.get('market_odds')} | Edge: {record.get('model_edge'):+.1f}%"
            elif post_type == "match_start":
                icon = "🏏"
                title = f"Toss: {record.get('toss_winner')} ({record.get('toss_decision')})"
                details = f"Teams: {record.get('team_a')} vs {record.get('team_b')}"
            elif post_type == "result":
                icon = "🏆"
                correct = record.get("model_call_correct")
                result_text = "✓ Correct" if correct else "✗ Incorrect" if correct is False else "N/A"
                title = f"Winner: {record.get('winning_team')}"
                details = f"Model Call: {result_text}"
            else:
                icon = "❓"
                title = "Unknown"
                details = ""
            
            with st.expander(f"{icon} **{match_id}** - {title}", expanded=False):
                st.markdown(f"**Type:** {post_type}")
                st.markdown(f"**Details:** {details}")
                st.markdown(f"**Posted:** {timestamp}")
                if record.get("telegram_message_id"):
                    st.markdown(f"**Telegram ID:** {record.get('telegram_message_id')}")
    
    # Stats
    st.divider()
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Posts", storage.count_records())
    with col2:
        st.metric("Predictions", storage.count_records(post_type="pre_match"))
    with col3:
        st.metric("Match Starts", storage.count_records(post_type="match_start"))
    with col4:
        st.metric("Results", storage.count_records(post_type="result"))


if __name__ == "__main__":
    main()
