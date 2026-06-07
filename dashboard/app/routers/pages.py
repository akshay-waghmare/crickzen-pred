"""Page router — serves HTML templates."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.config import get_settings
from app.prematch_page import (
    build_prematch_detail_context,
    build_prematch_list_context,
)
from app.proof_page import build_proof_page_context
from app.public import public_payload, service_from_request

router = APIRouter(tags=["Pages"])

_template_dir = Path(__file__).resolve().parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(_template_dir))


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    settings = get_settings()
    service = service_from_request(request)
    matches = [public_payload(match) for match in service.list_ipl_today()[:6]]
    if not matches:
        matches = [public_payload(match) for match in service.list_matches()[:6]]
    return templates.TemplateResponse(request, "public.html", {
        "settings": settings,
        "matches": matches,
        "seo": {
            "title": "CrickenZen | Live Cricket Win Probability",
            "description": "Live cricket prediction engine with public win probability, projected score, and model insights.",
            "canonical": "/",
            "noindex": False,
        },
    })


@router.get("/proof", response_class=HTMLResponse)
def proof_page(request: Request):
    settings = get_settings()
    league = request.query_params.get("league", "ipl")
    ctx = build_proof_page_context(league=league)
    return templates.TemplateResponse(request, "proof.html", {
        "settings": settings,
        "ctx": ctx,
        "seo": {
            "title": "Model Proof & Performance | CrickenZen",
            "description": "Transparent model performance: Brier score, ECE, accuracy, proof ledger, and segment performance for CrickenZen predictions.",
            "canonical": "/proof",
            "noindex": False,
        },
    })


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


@router.get("/ipl-prediction-today", response_class=HTMLResponse)
def ipl_prediction_today_page(request: Request):
    settings = get_settings()
    service = service_from_request(request)
    matches = [public_payload(match) for match in service.list_ipl_today()]
    return templates.TemplateResponse(request, "ipl_today.html", {
        "settings": settings,
        "matches": matches,
        "seo": {
            "title": "IPL Prediction Today | Live Win Probability - CrickenZen",
            "description": "Today's IPL prediction, live win probability, score state, projected score, and model insight from CrickenZen.",
            "canonical": "/ipl-prediction-today",
            "noindex": False,
        },
    })


@router.get("/match/{slug}", response_class=HTMLResponse)
def public_match_page(slug: str, request: Request):
    settings = get_settings()
    service = service_from_request(request)
    match = service.get_match(slug)
    if match is None:
        return templates.TemplateResponse(request, "match_public.html", {
            "settings": settings,
            "match": None,
            "seo": {
                "title": "Match Prediction Not Found | CrickenZen",
                "description": "This public match prediction is not currently available. See today's IPL prediction page for live cards.",
                "canonical": f"/match/{slug}",
                "noindex": True,
            },
        }, status_code=404)
    payload = public_payload(match)
    return templates.TemplateResponse(request, "match_public.html", {
        "settings": settings,
        "match": payload,
        "seo": {
            "title": f"{payload['title']} Win Probability | CrickenZen",
            "description": f"{payload['title']} live prediction, score, win probability, and model insight.",
            "canonical": f"/match/{payload['slug']}",
            "noindex": False,
        },
    })


@router.get("/prediction/{league}/{teams}", response_class=HTMLResponse)
def public_prediction_alias_page(league: str, teams: str, request: Request):
    settings = get_settings()
    service = service_from_request(request)
    match = service.get_match(f"{teams}-{league}-win-probability") or service.get_match(teams)
    if match is not None:
        payload = public_payload(match)
        return templates.TemplateResponse(request, "match_public.html", {
            "settings": settings,
            "match": payload,
            "seo": {
                "title": f"{payload['title']} Prediction | CrickenZen",
                "description": f"{payload['title']} public cricket prediction with live win probability and model insight.",
                "canonical": f"/prediction/{league}/{teams}",
                "noindex": False,
            },
        })
    matches = [public_payload(match) for match in service.list_ipl_today() if league.lower() == "ipl"]
    return templates.TemplateResponse(request, "ipl_today.html", {
        "settings": settings,
        "matches": matches,
        "seo": {
            "title": f"{league.upper()} Prediction | CrickenZen",
            "description": "Public cricket prediction cards with live win probability and model insight.",
            "canonical": f"/prediction/{league}/{teams}",
            "noindex": not bool(matches),
        },
    })


@router.get("/ipl-match-brief-today", response_class=HTMLResponse)
def prematch_list_page(request: Request):
    settings = get_settings()
    ctx = build_prematch_list_context(request)
    return templates.TemplateResponse(request, "ipl_match_brief_today.html", {
        "settings": settings,
        "ctx": ctx,
        "seo": {
            "title": "IPL Pre-Match Brief Today | Before-Toss Model Insight — CrickenZen",
            "description": "Today's IPL pre-match briefs with win probability, venue context, toss sensitivity, and 3-5 reasons for the model lean before toss.",
            "canonical": "/ipl-match-brief-today",
            "noindex": False,
        },
    })


@router.get("/pre-match/{slug}", response_class=HTMLResponse)
def prematch_detail_page(slug: str, request: Request):
    settings = get_settings()
    league = request.query_params.get("league", "ipl")
    ctx = build_prematch_detail_context(request, slug, league=league)
    title = ctx.title or "Pre-Match Brief"
    return templates.TemplateResponse(request, "prematch_brief.html", {
        "settings": settings,
        "ctx": ctx,
        "seo": {
            "title": f"{title} | Pre-Match Brief — CrickenZen",
            "description": f"Pre-match brief for {title}: win probability, projected score, venue context, toss sensitivity, and model reasons before toss.",
            "canonical": f"/pre-match/{slug}",
            "noindex": ctx.status == "not_ready",
        },
    })
