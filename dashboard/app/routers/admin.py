"""Admin router — subscriber CRUD (admin-only)."""

from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.analytics import build_analytics_summary
from app.auth import hash_password, require_admin
from app.database import get_session
from app.models import User

router = APIRouter(prefix="/admin", tags=["Admin"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CreateSubscriberRequest(BaseModel):
    email: str
    password: str
    plan: str = "monthly"  # free | monthly | yearly


class SubscriberResponse(BaseModel):
    id: str
    email: str
    is_active: bool
    plan: str
    created_at: str


class TrafficBucketResponse(BaseModel):
    label: str
    count: int
    registrations: int = 0


class RecentVisitResponse(BaseModel):
    event_name: str
    path: str
    landing_path: str | None = None
    source: str
    campaign: str
    created_at: str


class AnalyticsSummaryResponse(BaseModel):
    total_page_views: int
    unique_visitors: int
    total_registrations: int
    page_views_last_7_days: int
    top_sources: list[TrafficBucketResponse]
    top_pages: list[TrafficBucketResponse]
    top_campaigns: list[TrafficBucketResponse]
    recent_visits: list[RecentVisitResponse]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/subscribers", response_model=list[SubscriberResponse])
def list_subscribers(
    _admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
):
    users = session.exec(select(User).order_by(User.created_at.desc())).all()
    return [
        SubscriberResponse(
            id=u.id, email=u.email, is_active=u.is_active,
            plan=u.plan, created_at=u.created_at.isoformat(),
        )
        for u in users
    ]


@router.post("/subscribers", response_model=SubscriberResponse, status_code=201)
def create_subscriber(
    body: CreateSubscriberRequest,
    _admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
):
    existing = session.exec(select(User).where(User.email == body.email)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        is_active=True,
        plan=body.plan,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return SubscriberResponse(
        id=user.id, email=user.email, is_active=user.is_active,
        plan=user.plan, created_at=user.created_at.isoformat(),
    )


@router.patch("/subscribers/{user_id}/suspend")
def suspend_subscriber(
    user_id: str,
    _admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
):
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    session.add(user)
    session.commit()
    return {"detail": f"User {user.email} suspended"}


@router.patch("/subscribers/{user_id}/reactivate")
def reactivate_subscriber(
    user_id: str,
    _admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
):
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = True
    session.add(user)
    session.commit()
    return {"detail": f"User {user.email} reactivated"}


@router.get("/analytics/summary", response_model=AnalyticsSummaryResponse)
def analytics_summary(
    _admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
):
    return AnalyticsSummaryResponse(**build_analytics_summary(session))
