"""Live prediction router — start/stop/poll/stream matches."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.auth import get_current_user, require_admin
from app.config import LEAGUE_CONFIGS, detect_league_from_url, get_settings
from app.models import User
from app.prediction_manager import PredictionManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/matches", tags=["Live Predictions"])


# ---------------------------------------------------------------------------
# Blend logic
# ---------------------------------------------------------------------------

def _blend_weights(over: int, is_second_innings: bool) -> tuple[float, float]:
    """Return (ml_weight, mc_weight) for the given match situation.

    1st innings:
        overs 1-15  → 10% ML + 90% MC
        overs 15-20 → 50% ML + 50% MC

    2nd innings:
        overs 1-2   → 10% ML + 90% MC
        overs 3-16  → 70% ML + 30% MC
        overs 16-20 → 50% ML + 50% MC  (death)
    """
    if not is_second_innings:
        if over <= 15:
            return 0.10, 0.90
        return 0.50, 0.50
    else:
        if over <= 2:
            return 0.10, 0.90
        if over <= 16:
            return 0.70, 0.30
        return 0.50, 0.50


def _enrich_state(state: dict) -> dict:
    """Inject blended_prob and blend metadata into a live state dict."""
    if not state:
        return state

    ml_prob = float(state.get("league_calibrated_prob") or state.get("bat_win_prob") or 0.0)
    mc = state.get("monte_carlo") or {}
    mc_available = bool(mc.get("available"))
    mc_prob = float((mc.get("simulation_6ball") or {}).get("mean_prob") or 0.0) if mc_available else None

    over = int(state.get("over") or 0)
    is_second = bool(state.get("is_second_innings"))

    ml_w, mc_w = _blend_weights(over, is_second)

    if mc_available and mc_prob is not None:
        blended = ml_w * ml_prob + mc_w * mc_prob
    else:
        # MC not available — fall back to pure ML
        blended = ml_prob
        ml_w, mc_w = 1.0, 0.0

    state["blend"] = {
        "blended_prob": round(blended, 4),
        "ml_prob": round(ml_prob, 4),
        "mc_prob": round(mc_prob, 4) if mc_prob is not None else None,
        "mc_available": mc_available,
        "ml_weight": ml_w,
        "mc_weight": mc_w,
        "over": over,
        "is_second_innings": is_second,
    }
    return state


def _read_json(path: Path) -> dict[str, Any] | None:
    """Read a sidecar JSON file if it is present and complete."""
    try:
        if not path.exists() or path.stat().st_size == 0:
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("Failed to read live sidecar %s: %s", path, exc)
        return None


def _prediction_sidecar_paths(output_json_path: str) -> dict[str, Path]:
    path = Path(output_json_path)
    return {
        "history": path.with_name(f"{path.stem}_history.json"),
        "legacy_history": path.with_name("prediction_history.json"),
        "livematch": path.with_name(f"{path.stem}_livematch.json"),
    }


def _as_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _overs_to_balls(overs: float | None) -> int:
    if overs is None:
        return 0
    whole_overs = int(overs)
    balls = int(round((overs - whole_overs) * 10))
    balls = max(0, min(5, balls))
    return whole_overs * 6 + balls


def _fallback_projected_total(
    *,
    score: float,
    overs: float | None,
    current_run_rate: float | None,
    total_overs: int,
) -> float | None:
    """Estimate a first-innings final score when predictor features are missing."""
    if overs in (None, 0) or current_run_rate in (None, 0):
        return None

    balls_remaining = max(total_overs * 6 - _overs_to_balls(overs), 0)
    if balls_remaining <= 0:
        return score

    return score + (float(current_run_rate) * (balls_remaining / 6.0))


def _history_key(point: dict[str, Any]) -> tuple[int, float, int, int]:
    return (
        _as_int(point.get("innings"), 1),
        round(_as_float(point.get("overs"), 0.0) or 0.0, 3),
        _as_int(point.get("score")),
        _as_int(point.get("wickets")),
    )


def _dedupe_history(history: list[dict[str, Any]], limit: int = 600) -> list[dict[str, Any]]:
    """Keep the latest distinct score state for each innings/over/score/wicket point."""
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[int, float, int, int]] = set()
    for point in reversed(history or []):
        if not isinstance(point, dict):
            continue
        key = _history_key(point)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(point)
        if len(deduped) >= limit:
            break
    return list(reversed(deduped))


def _merge_sidecar_state(state: dict[str, Any], output_json_path: str) -> dict[str, Any]:
    """Merge predictor sidecars into the state returned by the dashboard API."""
    paths = _prediction_sidecar_paths(output_json_path)

    history_data = _read_json(paths["history"])
    if history_data is None:
        history_data = _read_json(paths["legacy_history"])
    if history_data:
        full_history = history_data.get("history") or []
        if isinstance(full_history, list) and len(full_history) > len(state.get("history") or []):
            state["history"] = full_history

    livematch = _read_json(paths["livematch"])
    if livematch:
        live_state = livematch.get("state") or {}
        if isinstance(live_state, dict):
            for key, value in live_state.items():
                if state.get(key) in (None, "", []):
                    state[key] = value

        for key in ("features", "pred_state", "scraped_data", "ball_history", "balls_data"):
            value = livematch.get(key)
            if value not in (None, "", []):
                if key == "features" and isinstance(value, dict):
                    merged_features = dict(value)
                    merged_features.update(state.get("features") or {})
                    state["features"] = merged_features
                elif state.get(key) in (None, "", []):
                    state[key] = value

        live_history = livematch.get("history") or []
        if isinstance(live_history, list) and len(live_history) > len(state.get("history") or []):
            state["history"] = live_history

    return state


def _build_projection(state: dict[str, Any]) -> dict[str, Any]:
    features = state.get("features") or {}
    score = _as_float(state.get("score"), 0.0) or 0.0
    wickets = _as_int(state.get("wickets"))
    overs = _as_float(state.get("overs"), 0.0)
    total_overs = _as_int(state.get("total_overs") or (state.get("pred_state") or {}).get("total_overs"), 20)
    current_run_rate = _as_float(
        features.get("current_run_rate"),
        _as_float(state.get("current_run_rate"), 0.0),
    )
    target = _as_float(state.get("target"))
    balls_remaining = max(total_overs * 6 - _overs_to_balls(overs), 0)

    projected = _as_float(features.get("projected_score"))
    expected_final = _as_float(features.get("expected_final_score"))
    fallback_projected = _fallback_projected_total(
        score=score,
        overs=overs,
        current_run_rate=current_run_rate,
        total_overs=total_overs,
    )

    if projected is None:
        projected = expected_final
    if expected_final is None:
        expected_final = projected

    # When live feature projection is missing, avoid showing the current score
    # as the "expected final" while the innings is still in progress.
    if balls_remaining > 0 and target in (None, 0):
        if projected is None or projected <= score:
            projected = fallback_projected or score
        if expected_final is None or expected_final <= score:
            expected_final = fallback_projected or projected or score

    if projected is None:
        projected = fallback_projected or score
    if expected_final is None:
        expected_final = projected

    projection = {
        "score": score,
        "wickets": wickets,
        "overs": overs,
        "target": target,
        "projected_score": projected,
        "expected_final_score": expected_final,
        "par_score": _as_float(features.get("par_score")),
        "venue_avg_score": _as_float(features.get("venue_avg_score")),
        "score_vs_par": _as_float(features.get("score_vs_par")),
        "projected_vs_venue_avg": _as_float(features.get("projected_vs_venue_avg")),
        "resource_win_prob": _as_float(features.get("resource_win_prob")),
        "resources_remaining": _as_float(features.get("resources_remaining")),
        "current_run_rate": current_run_rate,
        "required_run_rate": _as_float(features.get("required_run_rate"), _as_float(state.get("required_run_rate"), 0.0)),
        "pressure_index": _as_float(features.get("pressure_index")),
        "runs_required": None,
        "balls_remaining": None,
    }

    if target:
        projection["runs_required"] = max(int(target - score), 0)
    projection["balls_remaining"] = balls_remaining
    return projection


def _normalise_ball_commentary(balls: list[Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for idx, ball in enumerate(balls or []):
        if not isinstance(ball, dict):
            continue
        overs = _as_float(ball.get("overs") or ball.get("ball_number") or ball.get("over"))
        runs = _as_int(ball.get("runs") or ball.get("runs_scored"))
        is_wicket = bool(ball.get("is_wicket") or ball.get("wicket"))
        text = ball.get("commentary") or ball.get("description") or ball.get("text")
        if not text:
            event = "Wicket" if is_wicket else ("Boundary" if runs == 4 else "Six" if runs == 6 else "Runs")
            text = f"{event}: {runs} run{'s' if runs != 1 else ''}"
        entries.append({
            "id": str(ball.get("id") or f"ball-{idx}"),
            "innings": _as_int(ball.get("innings"), 1),
            "overs": overs,
            "over": f"{overs:.1f}" if overs is not None else "",
            "score": ball.get("score") or "",
            "event": "Wicket" if is_wicket else ("Boundary" if runs == 4 else "Six" if runs == 6 else "Runs"),
            "runs": runs,
            "is_wicket": is_wicket,
            "text": text,
            "bat_prob": _as_float(ball.get("bat_prob") or ball.get("win_probability")),
            "timestamp": ball.get("timestamp"),
        })
    return list(reversed(entries[-80:]))


def _normalise_recent_balls_from_balls(balls: list[Any], limit: int = 6) -> list[dict[str, Any]]:
    recent: list[dict[str, Any]] = []
    for idx, ball in enumerate(balls or []):
        if not isinstance(ball, dict):
            continue
        runs = _as_int(ball.get("runs") or ball.get("runs_scored"))
        is_wicket = bool(ball.get("is_wicket") or ball.get("wicket"))
        overs = _as_float(ball.get("overs") or ball.get("ball_number") or ball.get("over"))
        recent.append({
            "id": str(ball.get("id") or f"recent-ball-{idx}"),
            "over": f"{overs:.1f}" if overs is not None else "",
            "label": "W" if is_wicket else str(runs),
            "runs": runs,
            "is_wicket": is_wicket,
            "is_boundary": runs in (4, 6),
            "text": ball.get("commentary") or ball.get("description") or ball.get("text") or "",
        })
    return recent[-limit:]


def _derive_recent_balls_from_history(history: list[dict[str, Any]], limit: int = 6) -> list[dict[str, Any]]:
    points = _dedupe_history(history, limit=limit + 8)
    recent: list[dict[str, Any]] = []
    previous: dict[str, Any] | None = None
    for point in points:
        if previous is None:
            previous = point
            continue
        overs = _as_float(point.get("overs"), 0.0) or 0.0
        score = _as_int(point.get("score"))
        wickets = _as_int(point.get("wickets"))
        prev_score = _as_int(previous.get("score"))
        prev_wickets = _as_int(previous.get("wickets"))
        runs = max(score - prev_score, 0)
        wicket_delta = max(wickets - prev_wickets, 0)
        if runs == 0 and wicket_delta == 0:
            previous = point
            continue
        is_wicket = wicket_delta > 0
        recent.append({
            "id": f"recent-{overs:.1f}-{score}-{wickets}",
            "over": f"{overs:.1f}",
            "label": "W" if is_wicket else str(runs),
            "runs": runs,
            "is_wicket": is_wicket,
            "is_boundary": runs in (4, 6),
            "text": f"{score}/{wickets}",
        })
        previous = point
    return recent[-limit:]


def _derive_commentary_from_history(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Create a readable timeline when CREX has not exposed ball text."""
    points = _dedupe_history(history, limit=120)
    entries: list[dict[str, Any]] = []
    previous: dict[str, Any] | None = None
    for point in points:
        overs = _as_float(point.get("overs"), 0.0) or 0.0
        score = _as_int(point.get("score"))
        wickets = _as_int(point.get("wickets"))
        innings = _as_int(point.get("innings"), 1)
        batting_team = point.get("batting_team") or "Batting side"
        bat_prob = _as_float(point.get("bat_prob") or point.get("bat_win_prob"))

        if previous is None:
            text = f"{batting_team} are {score}/{wickets} after {overs:.1f} overs."
            event = "Update"
            runs = 0
            is_wicket = False
        else:
            runs = max(score - _as_int(previous.get("score")), 0)
            wicket_delta = max(wickets - _as_int(previous.get("wickets")), 0)
            if runs == 0 and wicket_delta == 0:
                continue
            is_wicket = wicket_delta > 0
            if is_wicket:
                event = "Wicket"
                text = f"Wicket. {batting_team} move to {score}/{wickets}."
            elif runs >= 6:
                event = "Six"
                text = f"Six-run swing. {batting_team} move to {score}/{wickets}."
            elif runs == 4:
                event = "Boundary"
                text = f"Boundary. {batting_team} move to {score}/{wickets}."
            else:
                event = "Runs"
                text = f"{runs} run{'s' if runs != 1 else ''}. {batting_team} move to {score}/{wickets}."

        entries.append({
            "id": f"{innings}-{overs:.1f}-{score}-{wickets}",
            "innings": innings,
            "overs": overs,
            "over": f"{overs:.1f}",
            "score": f"{score}/{wickets}",
            "event": event,
            "runs": runs,
            "is_wicket": is_wicket,
            "text": text,
            "bat_prob": bat_prob,
            "timestamp": point.get("timestamp"),
        })
        previous = point

    return list(reversed(entries[-80:]))


def _enrich_detail_state(state: dict[str, Any] | None, output_json_path: str | None = None) -> dict[str, Any] | None:
    if not state:
        return state

    if output_json_path:
        state = _merge_sidecar_state(state, output_json_path)

    chart_history = _dedupe_history(state.get("history") or [])
    state["chart_history"] = chart_history
    state["projection"] = _build_projection(state)

    balls = state.get("balls_data") or state.get("ball_history") or []
    commentary = _normalise_ball_commentary(balls) if isinstance(balls, list) and balls else []
    recent_balls = _normalise_recent_balls_from_balls(balls) if isinstance(balls, list) and balls else []
    if not commentary:
        commentary = _derive_commentary_from_history(chart_history)
    if not recent_balls:
        recent_balls = _derive_recent_balls_from_history(chart_history)
    state["commentary"] = commentary
    state["recent_balls"] = recent_balls

    return _enrich_state(state)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class StartMatchRequest(BaseModel):
    match_url: str
    league: str | None = None  # auto-detected if omitted
    # Optional provider-authoritative pair. Required for ambiguous short codes
    # such as DG, whose meaning varies by competition.
    team1_name: str | None = None
    team2_name: str | None = None


class MatchSummary(BaseModel):
    id: str
    user_id: str | None = None
    match_url: str
    league: str
    league_code: str
    status: str
    created_at: str


class MatchStateResponse(BaseModel):
    prediction_id: str
    status: str
    state: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/leagues")
def list_leagues():
    """Return available leagues for the UI dropdown."""
    return [
        {"key": k, "code": v["league"]}
        for k, v in LEAGUE_CONFIGS.items()
    ]


@router.post("/start", response_model=MatchSummary, status_code=201)
def start_match(
    body: StartMatchRequest,
    user: User = Depends(require_admin),
):
    manager = PredictionManager.get_instance()
    try:
        pred = manager.start_match(
            user_id=user.id,
            match_url=body.match_url,
            league_key=body.league,
            team1_name=body.team1_name,
            team2_name=body.team2_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return MatchSummary(
        id=pred.id,
        user_id=pred.user_id,
        match_url=pred.match_url,
        league=pred.league_key,
        league_code=pred.league_code,
        status=pred.status,
        created_at=pred.created_at.isoformat(),
    )


@router.get("", response_model=list[MatchSummary])
def list_matches(user: User = Depends(get_current_user)):
    """List active/recent predictions for the current user."""
    manager = PredictionManager.get_instance()
    preds = manager.list_predictions(user_id=user.id)
    return [
        MatchSummary(
            id=p["id"], user_id=p["user_id"], match_url=p["match_url"], league=p["league"],
            league_code=p["league_code"], status=p["status"],
            created_at=p["created_at"],
        )
        for p in preds
    ]


@router.get("/all", response_model=list[MatchSummary])
def list_all_matches(user: User = Depends(get_current_user)):
    """List ALL active predictions across all users (for public dashboard view)."""
    manager = PredictionManager.get_instance()
    preds = manager.list_predictions()
    return [
        MatchSummary(
            id=p["id"], user_id=p["user_id"], match_url=p["match_url"], league=p["league"],
            league_code=p["league_code"], status=p["status"],
            created_at=p["created_at"],
        )
        for p in preds
        if p["status"] == "running"
    ]


@router.get("/auto/status")
def auto_scheduler_status(
    request: Request,
    user: User = Depends(get_current_user),
):
    """Return automatic prediction scheduler state."""
    scheduler = getattr(request.app.state, "auto_scheduler", None)
    if scheduler is None:
        return {
            "enabled": get_settings().AUTO_PREDICTIONS_ENABLED,
            "running": False,
            "last_checked_at": None,
            "last_error": None,
            "last_candidates": [],
            "last_prematch_candidates": [],
            "last_started": [],
        }
    return scheduler.status()


@router.get("/{prediction_id}/state", response_model=MatchStateResponse)
def get_match_state(
    prediction_id: str,
    user: User = Depends(get_current_user),
):
    manager = PredictionManager.get_instance()
    pred = manager.get_prediction(prediction_id)
    if pred is None:
        raise HTTPException(status_code=404, detail="Prediction not found")

    state = _enrich_detail_state(pred.read_state(), pred.output_json_path)
    return MatchStateResponse(
        prediction_id=prediction_id,
        status=pred.status,
        state=state,
    )


@router.delete("/{prediction_id}/stop")
def stop_match(
    prediction_id: str,
    user: User = Depends(get_current_user),
):
    manager = PredictionManager.get_instance()
    stopped = manager.stop_match(prediction_id, user_id=user.id)
    if not stopped:
        raise HTTPException(status_code=404, detail="Prediction not found or not yours")
    return {"detail": "Prediction stopped"}


@router.get("/{prediction_id}/stream")
async def stream_match(
    prediction_id: str,
    user: User = Depends(get_current_user),
):
    """SSE endpoint — streams match state updates every POLL_INTERVAL_MS."""
    manager = PredictionManager.get_instance()
    pred = manager.get_prediction(prediction_id)
    if pred is None:
        raise HTTPException(status_code=404, detail="Prediction not found")

    settings = get_settings()
    interval = settings.POLL_INTERVAL_MS / 1000.0

    async def event_generator():
        last_timestamp = None
        while True:
            state = _enrich_detail_state(pred.read_state(), pred.output_json_path)
            if state:
                ts = state.get("timestamp")
                if ts != last_timestamp:
                    last_timestamp = ts
                    yield {"event": "state", "data": json.dumps(state)}
            if not pred.is_alive and pred.status != "running":
                yield {"event": "ended", "data": json.dumps({"status": pred.status})}
                break
            await asyncio.sleep(interval)

    return EventSourceResponse(event_generator())


@router.get("/detect-league")
def detect_league(url: str):
    """Detect league from a CREX URL (for auto-fill in UI)."""
    key = detect_league_from_url(url)
    if key is None:
        return {"league": None}
    return {"league": key, "code": LEAGUE_CONFIGS[key]["league"]}
