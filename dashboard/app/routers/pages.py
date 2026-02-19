"""Page routes: login page, dashboard page."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import Settings, get_settings
from app.main import templates

router = APIRouter(tags=["Pages"])


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, settings: Settings = Depends(get_settings)):
    """Render the login page."""
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "settings": settings},
    )


@router.get("/", response_class=HTMLResponse)
def dashboard_page(request: Request, settings: Settings = Depends(get_settings)):
    """Render the dashboard page.

    Note: Auth is enforced client-side — the page loads, then JS checks
    for a valid access token. If none exists, it redirects to /login.
    This keeps the server-rendered page stateless and cacheable.
    """
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "settings": settings,
            "poll_interval_ms": settings.POLL_INTERVAL_MS,
        },
    )
