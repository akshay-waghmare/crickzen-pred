"""Auth routes: login, refresh, logout, user management."""

from fastapi import APIRouter, Body, Cookie, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr
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
from app.main import limiter
from app.models import User

router = APIRouter(prefix="/auth", tags=["Auth"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class CreateUserRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    confirm_password: str


class UserResponse(BaseModel):
    id: str
    email: str
    is_active: bool


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    """Authenticate with email + password. Returns JWT + sets refresh cookie."""
    # Find user
    user = session.exec(select(User).where(User.email == body.email)).first()
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    # Enforce global session cap
    enforce_session_cap(session, settings)

    # Issue tokens
    access_token, expires_in = create_access_token(user.id, settings)
    raw_refresh = create_refresh_token(user.id, session, settings)

    # Set refresh token as HttpOnly cookie
    response.set_cookie(
        key="refresh_token",
        value=raw_refresh,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/auth",
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
    )


# ---------------------------------------------------------------------------
# POST /auth/refresh
# ---------------------------------------------------------------------------


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    """Rotate refresh token and issue a new access token."""
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token",
        )

    new_raw, user_id = rotate_refresh_token(refresh_token, session, settings)

    access_token, expires_in = create_access_token(user_id, settings)

    response.set_cookie(
        key="refresh_token",
        value=new_raw,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/auth",
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
    )


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    session: Session = Depends(get_session),
):
    """Revoke the current refresh token and clear the cookie."""
    if refresh_token:
        revoke_refresh_token(refresh_token, session)

    response.delete_cookie(
        key="refresh_token",
        path="/auth",
        httponly=True,
        secure=True,
        samesite="strict",
    )
    return None


# ---------------------------------------------------------------------------
# POST /auth/users  (admin only)
# ---------------------------------------------------------------------------


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    body: CreateUserRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    """Create a new subscriber. Admin only (first registered user)."""
    # Simple admin check: the admin is the user whose email matches ADMIN_EMAIL
    if current_user.email != settings.ADMIN_EMAIL:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    # Check if email already exists
    existing = session.exec(select(User).where(User.email == body.email)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    return UserResponse(id=user.id, email=user.email, is_active=user.is_active)


# ---------------------------------------------------------------------------
# POST /auth/register  (public self-registration)
# ---------------------------------------------------------------------------


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register(
    request: Request,
    body: RegisterRequest,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    """Self-registration endpoint. Only available when REGISTRATION_OPEN=True."""
    if not settings.REGISTRATION_OPEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is currently closed. Contact the administrator.",
        )

    # Validate passwords match
    if body.password != body.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Passwords do not match",
        )

    # Minimum password length
    if len(body.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 8 characters",
        )

    # Check duplicate email
    existing = session.exec(select(User).where(User.email == body.email)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    return UserResponse(id=user.id, email=user.email, is_active=user.is_active)
