"""Live prediction router — start/stop/poll/stream matches."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.auth import get_current_user
from app.config import LEAGUE_CONFIGS, detect_league_from_url, get_settings
from app.models import User
from app.prediction_manager import PredictionManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/matches", tags=["Live Predictions"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class StartMatchRequest(BaseModel):
    match_url: str
    league: str | None = None  # auto-detected if omitted


class MatchSummary(BaseModel):
    id: str
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
    user: User = Depends(get_current_user),
):
    manager = PredictionManager.get_instance()
    try:
        pred = manager.start_match(
            user_id=user.id,
            match_url=body.match_url,
            league_key=body.league,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return MatchSummary(
        id=pred.id,
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
            id=p["id"], match_url=p["match_url"], league=p["league"],
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
            id=p["id"], match_url=p["match_url"], league=p["league"],
            league_code=p["league_code"], status=p["status"],
            created_at=p["created_at"],
        )
        for p in preds
        if p["status"] == "running"
    ]


@router.get("/{prediction_id}/state", response_model=MatchStateResponse)
def get_match_state(
    prediction_id: str,
    user: User = Depends(get_current_user),
):
    manager = PredictionManager.get_instance()
    pred = manager.get_prediction(prediction_id)
    if pred is None:
        raise HTTPException(status_code=404, detail="Prediction not found")

    state = pred.read_state()
    return MatchStateResponse(
        prediction_id=prediction_id,
        status=pred.status if pred.is_alive else ("finished" if pred.status != "error" else "error"),
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
            state = pred.read_state()
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
