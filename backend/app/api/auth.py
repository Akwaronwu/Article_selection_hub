"""Authentication endpoints: register, login, logout, current user."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import User, UserSession
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserOut
from app.security import (
    PasswordPolicyError,
    generate_session_token,
    hash_password,
    hash_session_token,
    session_expiry,
    verify_password,
)
from app.services.audit import client_ip, log_action
from app.timeutil import utcnow

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(
    response: Response, request: Request, token: str, expires_at: datetime
) -> None:
    """Attach the session cookie with hardened attributes (SECURITY §1).

    ``expires`` must be timezone-aware UTC: Python's cookie formatter
    (``usegmt=True``) rejects naive datetimes.
    """
    settings = request.app.state.settings
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_hours * 3600,
        expires=expires_at,
        httponly=True,
        samesite="lax",
        secure=settings.environment == "production",
        path="/",
    )


def _create_session(db: Session, request: Request, user: User) -> tuple[str, UserSession]:
    """Persist a server-side session; returns (raw_token, row)."""
    settings = request.app.state.settings
    raw_token = generate_session_token()
    row = UserSession(
        user_id=user.id,
        token_hash=hash_session_token(raw_token),
        expires_at=session_expiry(settings.session_ttl_hours),
        ip_address=client_ip(request.client.host if request.client else None),
        user_agent=(request.headers.get("user-agent") or "")[:512] or None,
    )
    db.add(row)
    return raw_token, row


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new researcher",
)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> User:
    """Create an account and start a session.

    When ``SLR_ALLOW_OPEN_REGISTRATION=false``, only the very first (bootstrap)
    account may register; subsequent attempts get 403.
    """
    settings = request.app.state.settings
    email = payload.normalized_email()

    if not settings.allow_open_registration:
        user_count = db.scalar(select(func.count()).select_from(User)) or 0
        if user_count > 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Registration is closed; ask the project owner for an invitation.",
            )

    if db.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    try:
        password = payload.checked_password()
    except PasswordPolicyError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    user = User(
        email=email,
        display_name=payload.display_name.strip(),
        password_hash=hash_password(password),
    )
    db.add(user)
    db.flush()  # assign user.id

    log_action(
        db,
        action="user.register",
        entity_type="user",
        entity_id=user.id,
        user_id=user.id,
        object_after={"email": user.email, "display_name": user.display_name},
        ip_address=client_ip(request.client.host if request.client else None),
    )

    raw_token, session = _create_session(db, request, user)
    user.last_login_at = utcnow()
    db.commit()
    db.refresh(user)

    _set_session_cookie(response, request, raw_token, session.expires_at)
    return user


@router.post("/login", response_model=AuthResponse, summary="Log in")
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    """Verify credentials, start a session, and set the session cookie."""
    email = payload.normalized_email()
    user = db.scalar(select(User).where(User.email == email))

    # Constant-shape failure: hash a dummy password when the user is missing
    # so response timing does not reveal account existence.
    if user is None or not verify_password(user.password_hash, payload.password):
        if user is None:
            hash_password("dummy-password-timing-equaliser")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    raw_token, session = _create_session(db, request, user)
    user.last_login_at = utcnow()
    log_action(
        db,
        action="user.login",
        entity_type="user",
        entity_id=user.id,
        user_id=user.id,
        ip_address=client_ip(request.client.host if request.client else None),
    )
    db.commit()

    _set_session_cookie(response, request, raw_token, session.expires_at)
    return AuthResponse(
        user=UserOut.model_validate(user),
        expires_at=session.expires_at,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Log out")
def logout(
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Revoke the current session and clear the cookie."""
    settings = request.app.state.settings
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        session = db.scalar(
            select(UserSession).where(UserSession.token_hash == hash_session_token(token))
        )
        if session is not None and session.revoked_at is None:
            session.revoked_at = utcnow()
            log_action(
                db,
                action="user.logout",
                entity_type="user",
                entity_id=user.id,
                user_id=user.id,
                ip_address=client_ip(request.client.host if request.client else None),
            )
            db.commit()

    response.delete_cookie(settings.session_cookie_name, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserOut, summary="Current user")
def me(user: User = Depends(get_current_user)) -> User:
    """Return the authenticated user, or 401."""
    return user

