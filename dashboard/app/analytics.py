"""First-party visitor analytics helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import Request, Response
from sqlmodel import Session, select

from app.models import VisitorEvent

VISITOR_COOKIE_NAME = "cz_vid"
LANDING_PATH_COOKIE_NAME = "cz_landing_path"
TRACKING_COOKIE_MAX_AGE = 60 * 60 * 24 * 30
UTM_KEYS = ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term")
UTM_COOKIE_NAMES = {key: f"cz_{key}" for key in UTM_KEYS}


@dataclass(frozen=True)
class TrackingContext:
    visitor_id: str
    landing_path: str
    utm_source: str | None
    utm_medium: str | None
    utm_campaign: str | None
    utm_content: str | None
    utm_term: str | None
    referrer_url: str | None
    referrer_host: str | None
    user_agent: str | None


def should_track_page_view(request: Request, response: Response) -> bool:
    """Track HTML page loads, not API or asset requests."""
    if request.method != "GET":
        return False
    if request.url.path.startswith("/static"):
        return False
    content_type = response.headers.get("content-type", "")
    return content_type.startswith("text/html")


def record_page_view(session: Session, request: Request, response: Response) -> VisitorEvent:
    """Persist a page-view event and ensure visitor attribution cookies exist."""
    context = ensure_tracking_context(request, response)
    event = VisitorEvent(
        visitor_id=context.visitor_id,
        event_name="page_view",
        path=truncate_value(request.url.path, 255) or "/",
        landing_path=context.landing_path,
        utm_source=context.utm_source,
        utm_medium=context.utm_medium,
        utm_campaign=context.utm_campaign,
        utm_content=context.utm_content,
        utm_term=context.utm_term,
        referrer_url=context.referrer_url,
        referrer_host=context.referrer_host,
        user_agent=context.user_agent,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def record_registration_success(session: Session, request: Request, user_id: str) -> VisitorEvent:
    """Persist a conversion event using the visitor's first-touch attribution."""
    context = build_tracking_context(request)
    event = VisitorEvent(
        visitor_id=context.visitor_id,
        event_name="register_success",
        path="/auth/register",
        landing_path=context.landing_path,
        user_id=user_id,
        utm_source=context.utm_source,
        utm_medium=context.utm_medium,
        utm_campaign=context.utm_campaign,
        utm_content=context.utm_content,
        utm_term=context.utm_term,
        referrer_url=context.referrer_url,
        referrer_host=context.referrer_host,
        user_agent=context.user_agent,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def build_analytics_summary(session: Session) -> dict:
    """Return the admin analytics summary payload."""
    events = session.exec(
        select(VisitorEvent).order_by(VisitorEvent.created_at.desc())
    ).all()
    page_views = [event for event in events if event.event_name == "page_view"]
    registrations = [event for event in events if event.event_name == "register_success"]
    since = datetime.now(timezone.utc) - timedelta(days=7)
    page_views_last_7_days = sum(1 for event in page_views if normalize_timestamp(event.created_at) >= since)

    source_counts = bucket_counts(page_views, source_bucket)
    source_registrations = bucket_counts(registrations, source_bucket)
    campaign_counts = bucket_counts(page_views, campaign_bucket)
    campaign_registrations = bucket_counts(registrations, campaign_bucket)
    page_counts = bucket_counts(page_views, lambda event: event.path or "/")

    top_sources = [
        {
            "label": label,
            "count": count,
            "registrations": source_registrations.get(label, 0),
        }
        for label, count in top_n(source_counts)
    ]
    top_pages = [
        {"label": label, "count": count}
        for label, count in top_n(page_counts)
    ]
    top_campaigns = [
        {
            "label": label,
            "count": count,
            "registrations": campaign_registrations.get(label, 0),
        }
        for label, count in top_n(campaign_counts)
    ]

    return {
        "total_page_views": len(page_views),
        "unique_visitors": len({event.visitor_id for event in page_views}),
        "total_registrations": len(registrations),
        "page_views_last_7_days": page_views_last_7_days,
        "top_sources": top_sources,
        "top_pages": top_pages,
        "top_campaigns": top_campaigns,
        "recent_visits": [
            {
                "event_name": event.event_name,
                "path": event.path,
                "landing_path": event.landing_path,
                "source": source_bucket(event),
                "campaign": campaign_bucket(event),
                "created_at": normalize_timestamp(event.created_at).isoformat(),
            }
            for event in events[:25]
        ],
    }


def ensure_tracking_context(request: Request, response: Response) -> TrackingContext:
    """Build tracking context and set sticky attribution cookies."""
    visitor_id = truncate_value(request.cookies.get(VISITOR_COOKIE_NAME), 64)
    if not visitor_id:
        visitor_id = uuid4().hex
        response.set_cookie(
            VISITOR_COOKIE_NAME,
            visitor_id,
            max_age=TRACKING_COOKIE_MAX_AGE,
            samesite="lax",
        )

    landing_path = truncate_value(request.cookies.get(LANDING_PATH_COOKIE_NAME), 255)
    if not landing_path:
        landing_path = truncate_value(request.url.path, 255) or "/"
        response.set_cookie(
            LANDING_PATH_COOKIE_NAME,
            landing_path,
            max_age=TRACKING_COOKIE_MAX_AGE,
            samesite="lax",
        )

    for key in UTM_KEYS:
        query_value = truncate_value(request.query_params.get(key), 255)
        if query_value:
            response.set_cookie(
                UTM_COOKIE_NAMES[key],
                query_value,
                max_age=TRACKING_COOKIE_MAX_AGE,
                samesite="lax",
            )

    return build_tracking_context(request, visitor_id=visitor_id, landing_path=landing_path)


def build_tracking_context(
    request: Request,
    *,
    visitor_id: str | None = None,
    landing_path: str | None = None,
) -> TrackingContext:
    """Build tracking context from the request and stored cookies."""
    referrer_url = truncate_value(request.headers.get("referer"), 1024)
    user_agent = truncate_value(request.headers.get("user-agent"), 512)
    return TrackingContext(
        visitor_id=visitor_id or truncate_value(request.cookies.get(VISITOR_COOKIE_NAME), 64) or uuid4().hex,
        landing_path=landing_path or truncate_value(request.cookies.get(LANDING_PATH_COOKIE_NAME), 255) or truncate_value(request.url.path, 255) or "/",
        utm_source=resolve_utm_value(request, "utm_source"),
        utm_medium=resolve_utm_value(request, "utm_medium"),
        utm_campaign=resolve_utm_value(request, "utm_campaign"),
        utm_content=resolve_utm_value(request, "utm_content"),
        utm_term=resolve_utm_value(request, "utm_term"),
        referrer_url=referrer_url,
        referrer_host=truncate_value(urlparse(referrer_url).netloc.lower(), 255) if referrer_url else None,
        user_agent=user_agent,
    )


def resolve_utm_value(request: Request, key: str) -> str | None:
    return truncate_value(
        request.query_params.get(key) or request.cookies.get(UTM_COOKIE_NAMES[key]),
        255,
    )


def truncate_value(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    return value[:limit]


def source_bucket(event: VisitorEvent) -> str:
    if event.utm_source:
        return event.utm_source
    if event.referrer_host:
        return event.referrer_host
    return "(direct)"


def campaign_bucket(event: VisitorEvent) -> str:
    return event.utm_campaign or "(none)"


def bucket_counts(events: Iterable[VisitorEvent], label_func) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        label = label_func(event)
        counts[label] = counts.get(label, 0) + 1
    return counts


def top_n(counts: dict[str, int], limit: int = 10) -> list[tuple[str, int]]:
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]


def normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
