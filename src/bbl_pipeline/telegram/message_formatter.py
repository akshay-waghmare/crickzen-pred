"""
Message formatting for Telegram prediction posts.

Provides functions to format prediction data into structured
Telegram messages using HTML parse mode.
"""

from typing import Dict, Any, Optional
import html


# Message templates with HTML formatting
PRE_MATCH_TEMPLATE = """<b>MATCH ID:</b> {match_id}
<b>LEAGUE:</b> {league}

<b>MATCH:</b>
{team_a} vs {team_b}

<b>MODEL PROBABILITY:</b>
{selected_team} win: {model_probability:.1f}%

<b>MARKET ODDS (at post time):</b>
{selected_team}: {market_odds:.2f}

<b>POSITION:</b>
{selection_type} – {selected_team}

<b>MODEL EDGE:</b>
{model_edge:+.1f}%

<b>STATUS:</b>
Pre-Match Prediction"""


MATCH_START_TEMPLATE = """<b>MATCH ID:</b> {match_id}

<b>MATCH START UPDATE:</b>
Toss: {toss_winner} won the toss
Decision: {toss_decision}

<b>MODEL (Pre-Match):</b>
{model_info}

<b>STATUS:</b>
Match Started"""


MATCH_RESULT_TEMPLATE = """<b>MATCH ID:</b> {match_id}

<b>RESULT:</b>
Winner: {winning_team}

<b>MODEL CALL:</b>
{model_call_result}
{original_info}

<b>STATUS:</b>
Match Complete"""


def escape_html(text: str) -> str:
    """
    Escape HTML special characters in user input.
    
    Args:
        text: Raw text that may contain HTML characters
        
    Returns:
        HTML-escaped text safe for Telegram message
    """
    return html.escape(str(text))


def calculate_model_edge(model_probability: float, market_odds: float) -> float:
    """
    Calculate model edge percentage.
    
    Formula: (model_probability/100 - 1/market_odds) × 100
    
    Args:
        model_probability: Model's win probability (0-100)
        market_odds: Decimal market odds (e.g., 1.52)
        
    Returns:
        Edge percentage (can be negative)
    """
    implied_prob = 1.0 / market_odds
    model_prob = model_probability / 100.0
    return (model_prob - implied_prob) * 100


def format_prematch_prediction(
    match_id: str,
    league: str,
    team_a: str,
    team_b: str,
    selection_type: str,
    selected_team: str,
    model_probability: float,
    market_odds: float,
    model_edge: Optional[float] = None,
) -> str:
    """
    Format a pre-match prediction message.
    
    Args:
        match_id: Unique match identifier
        league: League name (e.g., "BBL", "SA20")
        team_a: First team name
        team_b: Second team name
        selection_type: "BACK" or "LAY"
        selected_team: Team being backed/laid
        model_probability: Model's win probability (0-100)
        market_odds: Decimal market odds
        model_edge: Pre-calculated edge (optional, will calculate if not provided)
        
    Returns:
        Formatted HTML message for Telegram
    """
    # Calculate edge if not provided
    if model_edge is None:
        model_edge = calculate_model_edge(model_probability, market_odds)
    
    return PRE_MATCH_TEMPLATE.format(
        match_id=escape_html(match_id),
        league=escape_html(league),
        team_a=escape_html(team_a),
        team_b=escape_html(team_b),
        selection_type=escape_html(selection_type),
        selected_team=escape_html(selected_team),
        model_probability=model_probability,
        market_odds=market_odds,
        model_edge=model_edge,
    )


def format_match_start(
    match_id: str,
    team_a: str,
    team_b: str,
    toss_winner: str,
    toss_decision: str,
    model_prematch_probability: Optional[float] = None,
    selected_team: Optional[str] = None,
) -> str:
    """
    Format a match start update message.
    
    Args:
        match_id: Match identifier linking to prediction
        team_a: First team name
        team_b: Second team name
        toss_winner: Team that won the toss
        toss_decision: "Bat" or "Bowl"
        model_prematch_probability: Pre-match model probability (optional)
        selected_team: Team from original prediction (optional)
        
    Returns:
        Formatted HTML message for Telegram
    """
    # Format model info line
    if model_prematch_probability is not None and selected_team:
        model_info = f"{escape_html(selected_team)} win probability: {model_prematch_probability:.1f}%"
    elif model_prematch_probability is not None:
        model_info = f"Win probability: {model_prematch_probability:.1f}%"
    else:
        model_info = "N/A (no pre-match prediction)"
    
    return MATCH_START_TEMPLATE.format(
        match_id=escape_html(match_id),
        toss_winner=escape_html(toss_winner),
        toss_decision=escape_html(toss_decision),
        model_info=model_info,
    )


def format_match_result(
    match_id: str,
    winning_team: str,
    model_call_correct: Optional[bool] = None,
    original_selection_type: Optional[str] = None,
    original_selected_team: Optional[str] = None,
    original_probability: Optional[float] = None,
) -> str:
    """
    Format a match result message.
    
    Args:
        match_id: Match identifier
        winning_team: Team that won the match
        model_call_correct: Whether prediction was correct (None if no prediction)
        original_selection_type: "BACK" or "LAY" from original prediction
        original_selected_team: Team from original prediction
        original_probability: Model probability from original prediction
        
    Returns:
        Formatted HTML message for Telegram
    """
    # Format model call result
    if model_call_correct is None:
        model_call_result = "N/A (no pre-match prediction)"
        original_info = ""
    elif model_call_correct:
        model_call_result = "✓ CORRECT"
        original_info = ""
        if original_selection_type and original_probability is not None:
            original_info = f"({original_selection_type} @ {original_probability:.1f}%)"
    else:
        model_call_result = "✗ INCORRECT"
        original_info = ""
        if original_selection_type and original_probability is not None:
            original_info = f"({original_selection_type} @ {original_probability:.1f}%)"
    
    return MATCH_RESULT_TEMPLATE.format(
        match_id=escape_html(match_id),
        winning_team=escape_html(winning_team),
        model_call_result=model_call_result,
        original_info=original_info,
    )


def determine_correctness(
    winning_team: str,
    selection_type: str,
    selected_team: str,
) -> bool:
    """
    Determine if a prediction was correct.
    
    Args:
        winning_team: Team that won the match
        selection_type: "BACK" or "LAY"
        selected_team: Team from the prediction
        
    Returns:
        True if prediction was correct, False otherwise
    """
    if selection_type.upper() == "BACK":
        # BACK is correct if selected team won
        return winning_team == selected_team
    elif selection_type.upper() == "LAY":
        # LAY is correct if selected team lost
        return winning_team != selected_team
    else:
        raise ValueError(f"Invalid selection_type: {selection_type}")
