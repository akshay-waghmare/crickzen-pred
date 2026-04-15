"""Page router — serves HTML templates."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.config import get_settings

router = APIRouter(tags=["Pages"])

_template_dir = Path(__file__).resolve().parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(_template_dir))


@router.get("/", response_class=HTMLResponse)
def index():
    return RedirectResponse(url="/dashboard", status_code=302)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    settings = get_settings()
    return templates.TemplateResponse(request, "login.html", {
        "settings": settings,
    })


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request):
    settings = get_settings()
    return templates.TemplateResponse(request, "dashboard.html", {
        "settings": settings,
        "poll_interval_ms": settings.POLL_INTERVAL_MS,
    })


@router.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    settings = get_settings()
    return templates.TemplateResponse(request, "admin.html", {
        "settings": settings,
    })
