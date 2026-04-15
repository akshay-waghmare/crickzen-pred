"""Auth router — login, register, refresh, logout, me."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth import (
    create_access_token,
    create_refresh_token,
    enforce_session_cap,
    get_current_user,
    hash_password,
    revoke_refresh_token,
    rotate_refresh_token,
    verify_password,
)
from app.config import Settings, get_settings
from app.database import get_session
from app.models import User

router = APIRouter(prefix="/auth", tags=["Auth"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: str
    email: str
    is_active: bool
    plan: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    user = session.exec(select(User).where(User.email == body.email)).first()
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account suspended")

    enforce_session_cap(session, settings)

    access_token, expires_in = create_access_token(user.id, settings)
    refresh_token = create_refresh_token(user.id, session, settings)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )


@router.post("/register", response_model=TokenResponse)
def register(
    body: RegisterRequest,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    if not settings.REGISTRATION_OPEN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Registration closed")

    existing = session.exec(select(User).where(User.email == body.email)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    if len(body.password) < 8:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Password must be at least 8 characters")

    enforce_session_cap(session, settings)

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        is_active=True,
        plan="free",
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    access_token, expires_in = create_access_token(user.id, settings)
    refresh_token = create_refresh_token(user.id, session, settings)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    body: RefreshRequest,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    new_raw, user_id = rotate_refresh_token(body.refresh_token, session, settings)
    access_token, expires_in = create_access_token(user_id, settings)
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_raw,
        expires_in=expires_in,
    )


@router.post("/logout")
def logout(
    body: RefreshRequest,
    session: Session = Depends(get_session),
):
    revoke_refresh_token(body.refresh_token, session)
    return {"detail": "Logged out"}


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)):
    return UserResponse(id=user.id, email=user.email, is_active=user.is_active, plan=user.plan)
