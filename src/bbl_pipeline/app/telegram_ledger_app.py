"""
Telegram Prediction Ledger - Streamlit App.

Manual posting interface for creating immutable, timestamped predictions
on a Telegram channel.

Usage:
    streamlit run src/bbl_pipeline/app/telegram_ledger_app.py
"""

import streamlit as st
from datetime import datetime, timezone
from pathlib import Path
import sys
import logging

# Ensure this app imports the local repo package, not a sibling editable install.
SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

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

PUBLIC_SIGNAL_PHASES = [
    ("Pre-match", "pre_match"),
    ("Toss", "toss"),
    ("Powerplay", "powerplay"),
    ("Mid-innings", "mid_innings"),
    ("Innings break", "innings_break"),
    ("Chase midpoint", "chase_midpoint"),
    ("Final review", "final_review"),
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
        tracker_path = (
            config.signal_tracker_path
            if config else
            "data/telegram_signal_accuracy_tracker.csv"
        )
        st.session_state.prediction_storage = PredictionStorage(
            storage_path,
            tracker_path=tracker_path,
        )
    
    return st.session_state.prediction_storage


def get_signal_publisher():
    """Get a public signal publisher bound to the configured bot and storage."""
    from bbl_pipeline.telegram.signal_publisher import PublicSignalPublisher

    client = get_telegram_client()
    if client is None:
        return None

    if "signal_publisher" not in st.session_state:
        config = st.session_state.get("telegram_config")
        storage = get_storage()
        st.session_state.signal_publisher = PublicSignalPublisher(
            client,
            storage,
            dashboard_base_url=(config.public_dashboard_base_url if config else None),
        )
    return st.session_state.signal_publisher


def parse_optional_int(value: str):
    """Parse an optional integer from a text input."""
    text = (value or "").strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _phase_default_values():
    """Return default form values for the public signal form."""
    return {
        "match_id": "",
        "match_title": "",
        "team_a": "",
        "team_b": "",
        "source_timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "dashboard_url": "",
        "model_favorite": "",
        "pre_match_favorite": "",
        "win_probability_pct": "",
        "probability_delta_pct": "",
        "reason": "",
        "what_changed": "",
        "caveat": "",
        "score": "",
        "overs": "",
        "target": "",
        "toss_winner": "",
        "toss_decision": "",
        "winner": "",
        "runs_needed": "",
        "balls_remaining": "",
        "wickets_in_hand": "",
        "review": "",
    }


def _snapshot_to_form_values(snapshot):
    """Convert a SignalSnapshot into Streamlit form defaults."""
    values = _phase_default_values()
    values.update(
        {
            "match_id": snapshot.match_id or "",
            "match_title": snapshot.match or "",
            "team_a": snapshot.team_a or "",
            "team_b": snapshot.team_b or "",
            "source_timestamp": snapshot.source_timestamp or values["source_timestamp"],
            "dashboard_url": snapshot.dashboard_url or "",
            "model_favorite": snapshot.model_favorite or "",
            "pre_match_favorite": snapshot.pre_match_favorite or "",
            "win_probability_pct": str(snapshot.win_probability_pct) if snapshot.win_probability_pct is not None else "",
            "probability_delta_pct": str(snapshot.probability_delta_pct) if snapshot.probability_delta_pct is not None else "",
            "reason": snapshot.reason or "",
            "what_changed": snapshot.what_changed or "",
            "caveat": snapshot.caveat or "",
            "score": snapshot.score or "",
            "overs": snapshot.overs or "",
            "target": str(snapshot.target) if snapshot.target is not None else "",
            "toss_winner": snapshot.toss_winner or "",
            "toss_decision": snapshot.toss_decision or "",
            "winner": snapshot.winner or "",
            "runs_needed": str(snapshot.runs_needed) if snapshot.runs_needed is not None else "",
            "balls_remaining": str(snapshot.balls_remaining) if snapshot.balls_remaining is not None else "",
            "wickets_in_hand": str(snapshot.wickets_in_hand) if snapshot.wickets_in_hand is not None else "",
            "review": snapshot.review or "",
        }
    )
    return values


def calculate_edge(model_probability: float, market_odds: float) -> float:
    """Calculate model edge percentage."""
    implied_prob = 1.0 / market_odds
    model_prob = model_probability / 100.0
    return (model_prob - implied_prob) * 100


@st.dialog("📡 Post Public Signal", width="large")
def show_public_signal_modal():
    """Modal dialog for public Telegram signal lifecycle posts."""
    from bbl_pipeline.telegram.signals import SignalSnapshot
    from bbl_pipeline.telegram.live_state_adapter import LiveStateError, build_signal_snapshot_from_json

    st.markdown("Draft and publish public model signals with publish checks and tracker updates.")
    publisher = get_signal_publisher()

    phase_labels = [label for label, _ in PUBLIC_SIGNAL_PHASES]
    phase_lookup = dict(PUBLIC_SIGNAL_PHASES)
    default_timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    default_dashboard_url = ""
    default_source_json = "data/ipl_live_ml.json"
    config = st.session_state.get("telegram_config")
    if config and config.public_dashboard_base_url:
        default_dashboard_url = config.public_dashboard_base_url
    if config and getattr(config, "signal_source_json", None):
        default_source_json = config.signal_source_json

    if "public_signal_form_values" not in st.session_state:
        st.session_state.public_signal_form_values = _phase_default_values()
        st.session_state.public_signal_form_values["dashboard_url"] = default_dashboard_url

    st.markdown("**Live Prefill**")
    load_col1, load_col2 = st.columns([4, 1])
    with load_col1:
        live_source_json = st.text_input(
            "Live Predictor JSON",
            key="public_signal_live_source_json",
            value=st.session_state.get("public_signal_live_source_json", default_source_json),
            help="Example: data/ipl_live_ml.json",
        )
    with load_col2:
        st.write("")
        st.write("")
        load_live = st.button("Load Live Snapshot", use_container_width=True)

    phase_for_prefill = phase_lookup.get(
        st.session_state.get("public_signal_phase_label", phase_labels[0]),
        "pre_match",
    )
    if load_live:
        try:
            snapshot = build_signal_snapshot_from_json(
                live_source_json,
                phase_for_prefill,
                dashboard_url=default_dashboard_url or None,
            )
            prefill_values = _snapshot_to_form_values(snapshot)
            tracker_row = get_storage().find_tracker_row(snapshot.match or "")
            if tracker_row and tracker_row.get("pre_match_favorite"):
                prefill_values["pre_match_favorite"] = tracker_row["pre_match_favorite"]
            st.session_state.public_signal_form_values = prefill_values
            st.session_state.public_signal_form_values["dashboard_url"] = (
                st.session_state.public_signal_form_values["dashboard_url"] or default_dashboard_url
            )
            st.success(f"Loaded live snapshot from `{live_source_json}`")
        except LiveStateError as e:
            st.error(f"❌ Failed to load live snapshot: {e}")

    with st.form("public_signal_form", clear_on_submit=False):
        form_values = st.session_state.public_signal_form_values
        col1, col2 = st.columns(2)

        with col1:
            phase_label = st.selectbox(
                "Signal Phase *",
                options=phase_labels,
                key="public_signal_phase_label",
            )
            match_id = st.text_input("Match ID", placeholder="e.g., ipl-rr-vs-dc-2026-05-01", value=form_values["match_id"])
            match_title = st.text_input("Match *", placeholder="e.g., RR vs DC", value=form_values["match_title"])
            team_a = st.text_input("Team A", placeholder="e.g., RR", value=form_values["team_a"])
            team_b = st.text_input("Team B", placeholder="e.g., DC", value=form_values["team_b"])
            source_timestamp = st.text_input(
                "Source Timestamp (UTC ISO) *",
                value=form_values["source_timestamp"] or default_timestamp,
                help="Freshness guardrail uses this timestamp.",
            )
            dashboard_url = st.text_input(
                "Dashboard URL",
                value=form_values["dashboard_url"] or default_dashboard_url,
                help="Optional override. If blank, configured PUBLIC_DASHBOARD_BASE_URL is used.",
            )

        with col2:
            model_favorite = st.text_input("Current Favorite", placeholder="e.g., RR", value=form_values["model_favorite"])
            pre_match_favorite = st.text_input("Pre-match Favorite", placeholder="Needed for toss/final review when it changed", value=form_values["pre_match_favorite"])
            win_probability_pct = st.text_input("Current Win Probability (%)", placeholder="e.g., 57", value=form_values["win_probability_pct"])
            probability_delta_pct = st.text_input("Probability Delta (pts)", placeholder="e.g., -7", value=form_values["probability_delta_pct"])
            reason = st.text_area("Reason / Read", placeholder="What is the model seeing right now?", value=form_values["reason"])
            what_changed = st.text_area("What Changed", placeholder="What moved the game state or model edge?", value=form_values["what_changed"])
            caveat = st.text_area("Caveat", placeholder="Optional caution for pre-match or live uncertainty", value=form_values["caveat"])

        st.divider()
        st.markdown("**Phase Context**")

        ctx1, ctx2, ctx3 = st.columns(3)
        with ctx1:
            score = st.text_input("Score", placeholder="e.g., 42/2", value=form_values["score"])
            overs = st.text_input("Overs", placeholder="e.g., 6 or 10.2", value=form_values["overs"])
            target = st.text_input("Target", placeholder="e.g., 176", value=form_values["target"])
        with ctx2:
            toss_winner = st.text_input("Toss Winner", placeholder="e.g., DC", value=form_values["toss_winner"])
            toss_decision = st.selectbox(
                "Toss Decision",
                options=["", "bat", "bowl"],
                index=["", "bat", "bowl"].index(form_values["toss_decision"]) if form_values["toss_decision"] in {"", "bat", "bowl"} else 0,
            )
            winner = st.text_input("Winner", placeholder="Needed for final review", value=form_values["winner"])
        with ctx3:
            runs_needed = st.text_input("Runs Needed", placeholder="e.g., 67", value=form_values["runs_needed"])
            balls_remaining = st.text_input("Balls Remaining", placeholder="e.g., 42", value=form_values["balls_remaining"])
            wickets_in_hand = st.text_input("Wickets In Hand", placeholder="e.g., 6", value=form_values["wickets_in_hand"])
            review = st.text_area("Final Review", placeholder="Brutally honest post-match review", value=form_values["review"])

        phase = phase_lookup[phase_label]
        snapshot = SignalSnapshot(
            match_id=match_id.strip() or None,
            match=match_title.strip() or None,
            team_a=team_a.strip() or None,
            team_b=team_b.strip() or None,
            model_favorite=model_favorite.strip() or None,
            pre_match_favorite=pre_match_favorite.strip() or None,
            win_probability_pct=parse_optional_int(win_probability_pct),
            source_timestamp=source_timestamp.strip() or None,
            score=score.strip() or None,
            overs=overs.strip() or None,
            toss_winner=toss_winner.strip() or None,
            toss_decision=toss_decision or None,
            probability_delta_pct=parse_optional_int(probability_delta_pct),
            reason=reason.strip() or None,
            what_changed=what_changed.strip() or None,
            caveat=caveat.strip() or None,
            target=parse_optional_int(target),
            runs_needed=parse_optional_int(runs_needed),
            balls_remaining=parse_optional_int(balls_remaining),
            wickets_in_hand=parse_optional_int(wickets_in_hand),
            winner=winner.strip() or None,
            review=review.strip() or None,
            dashboard_url=dashboard_url.strip() or None,
        )

        preview_draft = None
        if publisher is not None:
            preview_draft = publisher.draft(
                phase,
                snapshot,
                expected_match=match_title.strip() or None,
            )

        st.divider()
        st.markdown("**Draft Preview**")
        if preview_draft is None:
            st.info("Telegram is not configured yet.")
        else:
            st.code(preview_draft.message, language=None)
            status_text = "Ready" if preview_draft.publish_ready else "Blocked"
            st.markdown(f"**Status:** {status_text} | **Tracker Action:** {preview_draft.tracker_action}")
            for check in preview_draft.source_checks:
                icon = "✅" if check.passed else "⚠️"
                st.markdown(f"{icon} **{check.name}**: {check.detail}")

        submitted = st.form_submit_button("🚀 Post Public Signal", type="primary", use_container_width=True)

        if submitted:
            st.session_state.public_signal_form_values = {
                "match_id": match_id,
                "match_title": match_title,
                "team_a": team_a,
                "team_b": team_b,
                "source_timestamp": source_timestamp,
                "dashboard_url": dashboard_url,
                "model_favorite": model_favorite,
                "pre_match_favorite": pre_match_favorite,
                "win_probability_pct": win_probability_pct,
                "probability_delta_pct": probability_delta_pct,
                "reason": reason,
                "what_changed": what_changed,
                "caveat": caveat,
                "score": score,
                "overs": overs,
                "target": target,
                "toss_winner": toss_winner,
                "toss_decision": toss_decision,
                "winner": winner,
                "runs_needed": runs_needed,
                "balls_remaining": balls_remaining,
                "wickets_in_hand": wickets_in_hand,
                "review": review,
            }
            if publisher is None:
                st.error("❌ Telegram not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID in .env")
            elif preview_draft is None or not preview_draft.publish_ready:
                st.error("❌ Signal is not ready to publish. Fix the failed checks shown above.")
            else:
                with st.spinner("Posting public signal to Telegram..."):
                    result = publisher.publish(
                        phase,
                        snapshot,
                        expected_match=match_title.strip() or None,
                    )

                if result.success:
                    st.success(f"✅ Posted successfully! Message ID: {result.post_result.message_id}")
                    if result.tracker_row is not None:
                        st.info("Accuracy tracker updated.")
                    st.balloons()
                else:
                    error_message = (
                        result.post_result.error_message
                        if result.post_result else
                        "Signal was blocked by publish checks."
                    )
                    st.error(f"❌ Failed to post: {error_message}")


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
            # Build team options dynamically
            team_options = []
            if team_a and team_b:
                team_options = [team_a, team_b]
            
            selected_team = st.selectbox(
                "Selected Team *",
                options=team_options if team_options else ["(Enter teams first)"],
                help="Team you are backing or laying",
                disabled=not team_options
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
        if match_id and team_a and team_b and selected_team and selected_team != "(Enter teams first)":
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
            if not selected_team or selected_team == "(Enter teams first)":
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
            # Build team options dynamically
            team_options_toss = []
            if team_a and team_b:
                team_options_toss = [team_a, team_b]
            
            toss_winner = st.selectbox(
                "Toss Winner *",
                options=team_options_toss if team_options_toss else ["(Enter teams first)"],
                help="Team that won the toss",
                disabled=not team_options_toss
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
        if match_id and team_a and team_b and toss_winner and toss_winner != "(Enter teams first)":
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
            if not toss_winner or toss_winner == "(Enter teams first)":
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
# SIGNAL QUEUE APPROVAL SECTION
# ============================================================================

def _show_signal_queue_section() -> None:
    """Show pending signal drafts from the runner queue with approve/reject controls."""
    from bbl_pipeline.telegram.config import is_configured, load_config
    from bbl_pipeline.telegram.signal_review_queue import SignalReviewQueue
    from bbl_pipeline.telegram.signal_runner import SignalAutomationRunner
    from bbl_pipeline.telegram.signal_publisher import PublicSignalPublisher

    st.markdown("### 🔔 Signal Queue")

    if not is_configured():
        st.info("Configure Telegram to use the signal queue.")
        return

    cfg = load_config()
    queue = SignalReviewQueue(cfg.signal_queue_path)

    col_r, col_s = st.columns([1, 7])
    with col_r:
        if st.button("🔄 Refresh", key="refresh_queue"):
            st.rerun()

    pending = queue.list_items(status="pending")

    if not pending:
        st.success("No pending signals — nothing awaiting approval.")
        return

    st.info(f"**{len(pending)} draft(s) waiting for your approval.** Review each and click Approve to post live.")

    for item in pending:
        queue_id = item["queue_id"]
        phase = item.get("phase", "").replace("_", " ").title()
        match = item.get("match") or item.get("match_id", "Unknown match")
        draft_msg = item.get("draft_message", "")
        created = (item.get("created_at_utc") or "")[:19].replace("T", " ")
        checks = item.get("source_checks", [])
        all_ok = all(c.get("passed") for c in checks)
        trigger = item.get("trigger_reason", "")

        header_icon = "✅" if all_ok else "⚠️"
        with st.expander(f"{header_icon} **{phase}** — {match}  ·  {created} UTC", expanded=True):

            # Source checks row
            if checks:
                check_cols = st.columns(len(checks))
                for i, chk in enumerate(checks):
                    with check_cols[i]:
                        icon = "✅" if chk["passed"] else "❌"
                        st.caption(f"{icon} {chk['name']}: {chk['detail']}")

            st.caption(f"Trigger: {trigger}")
            st.markdown("**Draft message:**")
            st.code(draft_msg, language=None)

            btn_approve, btn_reject, _ = st.columns([1, 1, 5])

            with btn_approve:
                if st.button("✅ Approve & Post", key=f"approve_{queue_id}", type="primary"):
                    storage = get_storage()
                    client = get_telegram_client()
                    if client is None:
                        st.error("Telegram not configured.")
                    else:
                        publisher = PublicSignalPublisher(
                            client,
                            storage,
                            dashboard_base_url=cfg.public_dashboard_base_url,
                        )
                        runner = SignalAutomationRunner(
                            source_json=cfg.signal_source_json,
                            queue_path=cfg.signal_queue_path,
                            storage=storage,
                            publisher=publisher,
                            dashboard_url=cfg.public_dashboard_base_url,
                        )
                        try:
                            result = runner.approve(queue_id)
                            tg_id = result.get("telegram_message_id")
                            st.success(f"✅ Posted to Telegram! (message_id: {tg_id})")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Failed to post: {exc}")

            with btn_reject:
                if st.button("❌ Reject", key=f"reject_{queue_id}"):
                    queue.update_status(
                        queue_id,
                        status="rejected",
                        approval_note="Rejected via operator UI",
                    )
                    st.rerun()


# ============================================================================
# MAIN APP
# ============================================================================

def main():
    """Main application entry point."""
    st.title("📢 Telegram Prediction Ledger")
    st.markdown("""
    Create immutable, timestamped Telegram posts for both ledger entries and public model signals.
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
        PUBLIC_DASHBOARD_BASE_URL=https://app.crickzen.com/dashboard
        ```
        
        See `config/.env.example` for a template.
        """)
    else:
        st.success("✅ Telegram configured")
    
    st.divider()
    _show_signal_queue_section()
    st.divider()

    # Main action buttons
    col1, col2, col3, col4 = st.columns(4)
    
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

    with col4:
        st.markdown("### 📡 Public Signal")
        st.caption("Post trust-building public lifecycle updates")
        if st.button("Post Public Signal", use_container_width=True):
            show_public_signal_modal()
    
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
            elif post_type == "public_signal":
                icon = "📡"
                title = f"{record.get('phase', 'signal')} | {record.get('match', match_id)}"
                details = f"Status: {record.get('status')} | Tracker: {record.get('tracker_action')}"
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
                if post_type == "public_signal":
                    st.code(record.get("message", ""), language=None)

    st.divider()
    st.markdown("### 📊 Accuracy Tracker")
    tracker_rows = storage.read_tracker_rows()
    if not tracker_rows:
        st.info("No accuracy tracker rows yet. A pre-match public signal opens a row and final review closes it.")
    else:
        st.dataframe(tracker_rows, use_container_width=True, hide_index=True)
    
    # Stats
    st.divider()
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Total Posts", storage.count_records())
    with col2:
        st.metric("Predictions", storage.count_records(post_type="pre_match"))
    with col3:
        st.metric("Match Starts", storage.count_records(post_type="match_start"))
    with col4:
        st.metric("Results", storage.count_records(post_type="result"))
    with col5:
        st.metric("Public Signals", storage.count_records(post_type="public_signal"))


if __name__ == "__main__":
    main()
