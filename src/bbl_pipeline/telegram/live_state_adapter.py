"""
Adapt live predictor JSON into Telegram public signal snapshots.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

from bbl_pipeline.telegram.signals import (
    PHASE_CHASE_MIDPOINT,
    PHASE_FINAL_REVIEW,
    PHASE_INNINGS_BREAK,
    PHASE_MID_INNINGS,
    PHASE_POWERPLAY,
    PHASE_PRE_MATCH,
    PHASE_TOSS,
    SignalSnapshot,
)


class LiveStateError(Exception):
    """Raised when live predictor state cannot be loaded or interpreted."""


@dataclass
class LiveSignalState:
    """Raw live predictor state bundle used for signal prefilling."""

    json_path: str
    main_state: dict[str, Any]
    sidecar_state: dict[str, Any] | None

    def to_debug_dict(self) -> dict[str, Any]:
        """Return a serializable summary for troubleshooting."""
        return {
            "json_path": self.json_path,
            "has_sidecar": self.sidecar_state is not None,
            "main_keys": sorted(self.main_state.keys()),
        }


def build_signal_snapshot_from_json(
    json_path: str | Path,
    phase: str,
    *,
    dashboard_url: str | None = None,
) -> SignalSnapshot:
    """Load live predictor artifacts and build a Telegram signal snapshot."""
    state = load_live_signal_state(json_path)
    main = state.main_state
    sidecar = state.sidecar_state or {}
    live_state = sidecar.get("state", {})
    history = main.get("history", []) or []

    team_a, team_b = _resolve_match_teams(main, history)
    current_batting = main.get("batting_team") or live_state.get("batting_team")
    current_bowling = main.get("bowling_team") or live_state.get("bowling_team")

    bat_prob = _safe_float(main.get("bat_win_prob"), 0.5)
    bowl_prob = _safe_float(main.get("bowl_win_prob"), 1.0 - bat_prob)
    if bat_prob >= bowl_prob:
        model_favorite = current_batting or team_a
        favorite_prob = bat_prob
    else:
        model_favorite = current_bowling or team_b
        favorite_prob = bowl_prob

    overs_value = main.get("overs", live_state.get("overs"))
    score_text = _score_text(main)
    overs_text = _overs_text(overs_value)
    target = _safe_int(main.get("target"))
    wickets = _safe_int(main.get("wickets"), 0)
    score = _safe_int(main.get("score"), 0)
    total_overs = _safe_float(main.get("total_overs"), 20.0)
    runs_needed = max(target - score, 0) if target else None
    balls_remaining = _balls_remaining(overs_value, total_overs) if target else None
    wickets_in_hand = max(10 - wickets, 0)
    probability_delta_pct = _favorite_delta_pct(history, model_favorite)
    winner = _determine_winner(main)

    snapshot = SignalSnapshot(
        match_id=_match_id_from_path(json_path),
        match=f"{team_a} vs {team_b}" if team_a and team_b else None,
        team_a=team_a,
        team_b=team_b,
        model_favorite=model_favorite,
        win_probability_pct=round(favorite_prob * 100),
        source_timestamp=main.get("timestamp"),
        score=score_text,
        overs=overs_text,
        toss_winner=live_state.get("toss_winner"),
        toss_decision=live_state.get("toss_decision"),
        probability_delta_pct=probability_delta_pct,
        reason=_phase_reason(phase, main, model_favorite, team_a, team_b),
        caveat=_phase_caveat(phase),
        target=target,
        runs_needed=runs_needed,
        balls_remaining=balls_remaining,
        wickets_in_hand=wickets_in_hand if target else None,
        winner=winner,
        what_changed=_what_changed(phase, main, model_favorite),
        review=_final_review_stub(main, winner, model_favorite) if phase == PHASE_FINAL_REVIEW else None,
        dashboard_url=dashboard_url,
    )

    if phase == PHASE_TOSS:
        snapshot.pre_match_favorite = model_favorite
    if phase == PHASE_FINAL_REVIEW:
        snapshot.pre_match_favorite = model_favorite

    return snapshot


def load_live_signal_state(json_path: str | Path) -> LiveSignalState:
    """Load live predictor JSON and its optional sidecar state."""
    main_path = Path(json_path)
    if not main_path.exists():
        raise LiveStateError(f"Live predictor JSON not found: {main_path}")

    main_state = _read_json(main_path)
    if not isinstance(main_state, dict):
        raise LiveStateError(f"Unexpected live predictor payload in {main_path}")

    history_path = _history_path_for_json(main_path)
    if history_path.exists():
        history_payload = _read_json(history_path)
        if isinstance(history_payload, dict):
            history = history_payload.get("history", [])
            if len(history) > len(main_state.get("history", []) or []):
                main_state["history"] = history

    sidecar_path = _sidecar_path_for_json(main_path)
    sidecar_state = _read_json(sidecar_path) if sidecar_path.exists() else None

    return LiveSignalState(
        json_path=str(main_path),
        main_state=main_state,
        sidecar_state=sidecar_state,
    )


def _read_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _history_path_for_json(path: Path) -> Path:
    return path.with_name(f"{path.stem}_history.json")


def _sidecar_path_for_json(path: Path) -> Path:
    return path.with_name(f"{path.stem}_livematch.json")


def _match_id_from_path(path: str | Path) -> str:
    return Path(path).stem


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int | None = None) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _resolve_match_teams(main: dict[str, Any], history: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    if history:
        first = history[0]
        innings = _safe_int(first.get("innings"), 1)
        if innings == 1:
            return first.get("batting_team"), first.get("bowling_team")
    current_batting = main.get("batting_team")
    current_bowling = main.get("bowling_team")
    if main.get("is_second_innings"):
        return current_bowling, current_batting
    return current_batting, current_bowling


def _score_text(main: dict[str, Any]) -> str | None:
    score = _safe_int(main.get("score"))
    wickets = _safe_int(main.get("wickets"))
    if score is None or wickets is None:
        return None
    return f"{score}/{wickets}"


def _overs_text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _balls_remaining(overs_value: Any, total_overs: float) -> int | None:
    overs_float = _safe_float(overs_value)
    if overs_float is None:
        return None
    completed_balls = _overs_to_balls(overs_float)
    return max(int(round(total_overs * 6)) - completed_balls, 0)


def _overs_to_balls(overs_value: float) -> int:
    whole = int(overs_value)
    part = int(round((overs_value - whole) * 10))
    return whole * 6 + min(part, 5)


def _favorite_delta_pct(history: list[dict[str, Any]], favorite_team: str | None) -> int | None:
    if not history or not favorite_team:
        return None
    first = history[0]
    last = history[-1]
    first_prob = _team_prob_from_history(first, favorite_team)
    last_prob = _team_prob_from_history(last, favorite_team)
    if first_prob is None or last_prob is None:
        return None
    return round((last_prob - first_prob) * 100)


def _team_prob_from_history(entry: dict[str, Any], team: str) -> float | None:
    batting_team = entry.get("batting_team")
    bowling_team = entry.get("bowling_team")
    bat_prob = _safe_float(entry.get("win_probability"))
    if bat_prob is None:
        bat_prob = _safe_float(entry.get("bat_win_prob"))
    if bat_prob is None:
        return None
    if team == batting_team:
        return bat_prob
    if team == bowling_team:
        return 1.0 - bat_prob
    return None


def _determine_winner(main: dict[str, Any]) -> str | None:
    if not main.get("is_second_innings"):
        return None
    batting_team = main.get("batting_team")
    bowling_team = main.get("bowling_team")
    score = _safe_int(main.get("score"), 0)
    wickets = _safe_int(main.get("wickets"), 0)
    overs = _safe_float(main.get("overs"), 0.0)
    total_overs = _safe_float(main.get("total_overs"), 20.0) or 20.0
    target = _safe_int(main.get("target"))
    if not target:
        return None
    if score >= target:
        return batting_team
    if wickets >= 10 or overs >= total_overs:
        return bowling_team
    return None


def _phase_reason(
    phase: str,
    main: dict[str, Any],
    favorite: str | None,
    team_a: str | None,
    team_b: str | None,
) -> str:
    if phase == PHASE_PRE_MATCH:
        return f"{favorite or 'The model'} holds the stronger current edge before toss."
    if phase == PHASE_TOSS:
        return "The toss context has been incorporated into the live model state."
    if phase == PHASE_POWERPLAY:
        return "The first six overs have materially moved the live win probability."
    if phase == PHASE_MID_INNINGS:
        return "The current scoring pace and wickets profile are driving the model view."
    if phase == PHASE_INNINGS_BREAK:
        return "The first innings total and chase setup now define the model edge."
    if phase == PHASE_CHASE_MIDPOINT:
        return "Required rate, wickets in hand, and balls remaining define the current pressure."
    if phase == PHASE_FINAL_REVIEW:
        return f"{favorite or 'The model favorite'} did not hold the final edge." if _determine_winner(main) and _determine_winner(main) != favorite else "The live model path can now be reviewed against the final result."
    return f"{team_a or 'Team A'} vs {team_b or 'Team B'} live state loaded."


def _phase_caveat(phase: str) -> str | None:
    if phase == PHASE_PRE_MATCH:
        return "Toss, confirmed XI, and venue conditions can still move this."
    return None


def _what_changed(phase: str, main: dict[str, Any], favorite: str | None) -> str | None:
    score = _score_text(main)
    overs = _overs_text(main.get("overs"))
    if phase == PHASE_POWERPLAY:
        return f"Live state moved to {score} after {overs} overs, shifting the edge toward {favorite}."
    if phase == PHASE_MID_INNINGS:
        return f"At {score} after {overs} overs, the scoring pace and wickets profile shifted the balance."
    if phase == PHASE_INNINGS_BREAK:
        return f"The innings closed at {score}, setting a defined chase target and new model base rate."
    if phase == PHASE_CHASE_MIDPOINT:
        target = _safe_int(main.get('target'))
        if target:
            return f"Chase pressure is now driven by {target - _safe_int(main.get('score'), 0)} needed with limited balls left."
    if phase == PHASE_FINAL_REVIEW:
        winner = _determine_winner(main)
        if winner:
            return f"The match finished with {winner} taking the final result despite earlier swings."
    return None


def _final_review_stub(main: dict[str, Any], winner: str | None, favorite: str | None) -> str | None:
    if not winner:
        return None
    if winner == favorite:
        return "The closing result matched the latest favorite. Review the major swings before the next match."
    return "The result went against the latest favorite. Review where the edge moved and whether the pre-match call held up."
