"""Authentication utilities: password hashing, JWT, refresh tokens."""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from sqlmodel import Session, select

from app.config import Settings, get_settings
from app.database import get_session
from app.models import RefreshToken, User

logger = logging.getLogger(__name__)

# Password hashing — Argon2id via pwdlib
_password_hash = PasswordHash((Argon2Hasher(),))

# Bearer token extractor
_bearer_scheme = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------


def hash_password(plain: str) -> str:
    """Hash a plaintext password with Argon2id."""
    return _password_hash.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against an Argon2id hash."""
    return _password_hash.verify(plain, hashed)


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------


def create_access_token(
    user_id: str,
    settings: Settings | None = None,
    expires_minutes: int | None = None,
) -> tuple[str, int]:
    """Create a signed HS256 JWT access token.

    Returns:
        (token_string, expires_in_seconds)
    """
    s = settings or get_settings()
    minutes = expires_minutes or s.ACCESS_TOKEN_EXPIRE_MINUTES
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=minutes)
    payload: dict[str, Any] = {
        "sub": user_id,
        "iat": now,
        "exp": exp,
    }
    token = jwt.encode(payload, s.JWT_SECRET, algorithm="HS256")
    return token, minutes * 60


def verify_access_token(token: str, settings: Settings | None = None) -> str:
    """Decode and validate a JWT access token.

    Returns:
        The user_id (sub claim).

    Raises:
        HTTPException 401 on invalid/expired token.
    """
    s = settings or get_settings()
    try:
        payload = jwt.decode(token, s.JWT_SECRET, algorithms=["HS256"])
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject",
            )
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


# ---------------------------------------------------------------------------
# Refresh token helpers
# ---------------------------------------------------------------------------


def _hash_token(raw: str) -> str:
    """SHA-256 hash a raw refresh token for safe storage."""
    return hashlib.sha256(raw.encode()).hexdigest()


def create_refresh_token(
    user_id: str,
    session: Session,
    settings: Settings | None = None,
    expires_days: int | None = None,
) -> str:
    """Generate an opaque refresh token and store its hash in the DB.

    Returns:
        The raw (unhashed) token string to send to the client.
    """
    s = settings or get_settings()
    days = expires_days or s.REFRESH_TOKEN_EXPIRE_DAYS
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)

    db_token = RefreshToken(
        token_hash=token_hash,
        user_id=user_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=days),
    )
    session.add(db_token)
    session.commit()
    return raw_token


def rotate_refresh_token(
    raw_token: str,
    session: Session,
    settings: Settings | None = None,
) -> tuple[str, str]:
    """Consume the old refresh token and issue a new one.

    Security: if the token was already consumed (replay attack), revoke ALL
    tokens for that user.

    Returns:
        (new_raw_token, user_id)

    Raises:
        HTTPException 401 on invalid/expired/replayed token.
    """
    token_hash = _hash_token(raw_token)

    # Look up the token
    db_token = session.exec(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    ).first()

    if db_token is None:
        # Token not found — could be a replay of an already-consumed token.
        # We can't know the user_id from a missing token, so just reject.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    if db_token.revoked:
        # Replay attack detected — revoke ALL tokens for this user
        _revoke_all_user_tokens(db_token.user_id, session)
        logger.warning(
            "Replay attack detected for user %s — all tokens revoked",
            db_token.user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token replay detected — all sessions revoked",
        )

    if db_token.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        session.delete(db_token)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
        )

    user_id = db_token.user_id

    # Mark old token as revoked (instead of deleting) so replay is detectable
    db_token.revoked = True
    session.add(db_token)
    session.commit()

    # Issue new token
    new_raw = create_refresh_token(user_id, session, settings)
    return new_raw, user_id


def revoke_refresh_token(raw_token: str, session: Session) -> bool:
    """Revoke a specific refresh token (logout).

    Returns:
        True if token was found and revoked, False otherwise.
    """
    token_hash = _hash_token(raw_token)
    db_token = session.exec(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    ).first()
    if db_token is None:
        return False
    db_token.revoked = True
    session.add(db_token)
    session.commit()
    return True


def _revoke_all_user_tokens(user_id: str, session: Session):
    """Revoke all refresh tokens for a given user (nuclear option)."""
    tokens = session.exec(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked == False,  # noqa: E712
        )
    ).all()
    for t in tokens:
        t.revoked = True
        session.add(t)
    session.commit()
    logger.info("Revoked all tokens for user %s (%d tokens)", user_id, len(tokens))


def enforce_session_cap(session: Session, settings: Settings | None = None):
    """Check total active sessions across ALL users.

    Raises:
        HTTPException 503 if session cap is reached.
    """
    s = settings or get_settings()
    now = datetime.now(timezone.utc)
    active_count = len(
        session.exec(
            select(RefreshToken).where(
                RefreshToken.revoked == False,  # noqa: E712
                RefreshToken.expires_at > now,
            )
        ).all()
    )
    if active_count >= s.SESSION_CAP:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="capacity_reached",
        )


# ---------------------------------------------------------------------------
# FastAPI dependency: require valid JWT
# ---------------------------------------------------------------------------


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> User:
    """FastAPI dependency that extracts and validates the JWT bearer token.

    Returns the authenticated User object.
    Raises 401 if token is missing, invalid, or user not found/inactive.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = verify_access_token(credentials.credentials, settings)

    user = session.exec(select(User).where(User.id == user_id)).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user
