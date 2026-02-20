"""Live match state endpoint."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status

from app.auth import get_current_user
from app.config import Settings, get_settings
from app.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Live"])


@router.get("/live-state")
def get_live_state(
    response: Response,
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    if_none_match: str | None = Header(default=None),
    league: str | None = None,
):
    """Return the current live match state from the JSON file.

    - Requires valid JWT bearer token.
    - Returns 304 if ETag matches (file unchanged).
    - Returns 404 if state file does not exist.
    - Appends `stale: true` if timestamp > 60s old.
    - Injects `poll_interval_ms` from server config.
    """
    state_path = Path(settings.STATE_FILE)

    if not state_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No live match state available",
        )

    # Compute ETag from file modification time
    try:
        mtime = state_path.stat().st_mtime
    except OSError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cannot read state file",
        )

    etag = f'"{mtime}"'

    # 304 Not Modified
    if if_none_match and if_none_match == etag:
        response.status_code = status.HTTP_304_NOT_MODIFIED
        response.headers["ETag"] = etag
        response.headers["Cache-Control"] = "no-store"
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag, "Cache-Control": "no-store"})

    # Read and parse JSON
    try:
        raw = state_path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Error reading state file: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cannot parse state file",
        )

    # Stale detection
    timestamp_str = data.get("timestamp")
    if timestamp_str:
        try:
            ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - ts).total_seconds()
            if age > 60:
                data["stale"] = True
        except (ValueError, TypeError):
            data["stale"] = True
    else:
        data["stale"] = True

    # Inject server config
    data["poll_interval_ms"] = settings.POLL_INTERVAL_MS

    # League override
    if league:
        data["selected_league"] = league

    # Check for league calibrator availability
    if league:
        calibrator_path = Path(f"models/t20_male_v2/league_calibrators/{league}")
        if calibrator_path.exists():
            data["calibration_chain"] = f"raw → phase → per-over → {league}"
        else:
            data["calibration_chain"] = "raw (global T20 model)"

    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "no-store"

    return data
