"""Health check endpoint — no auth required."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings

router = APIRouter(tags=["System"])


@router.get("/health")
def health_check(settings: Settings = Depends(get_settings)):
    """Docker healthcheck + Caddy upstream probe."""
    return {"status": "ok", "version": settings.APP_VERSION}
