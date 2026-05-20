"""Public, unauthenticated prediction API."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from app.public import public_payload, service_from_request

router = APIRouter(prefix="/api/public", tags=["Public"])


@router.get("/matches")
def public_matches(request: Request):
    service = service_from_request(request)
    return {
        "matches": [public_payload(match) for match in service.list_matches()],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ipl-today")
def public_ipl_today(request: Request):
    service = service_from_request(request)
    return {
        "matches": [public_payload(match) for match in service.list_ipl_today()],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/matches/{slug}")
def public_match_detail(slug: str, request: Request):
    service = service_from_request(request)
    match = service.get_match(slug)
    if match is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Match not found",
                "suggested_url": "/ipl-prediction-today",
            },
        )
    return {"match": public_payload(match)}
