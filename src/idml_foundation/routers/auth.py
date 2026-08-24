from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select

from idml_foundation.dependencies import Configuration, CorrelationId, Database, oauth2_scheme
from idml_foundation.models import User, utcnow
from idml_foundation.schemas import LoginRequest, SessionResponse
from idml_foundation.security import (
    issue_session,
    normalize_email,
    revoke_session,
    verify_password,
)
from idml_foundation.services.audit import record_audit

router = APIRouter(prefix="/v1/auth", tags=["authentication"])


@router.post("/login", response_model=SessionResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Database,
    settings: Configuration,
    correlation_id: CorrelationId,
) -> SessionResponse:
    user = db.scalar(select(User).where(User.email == normalize_email(str(payload.email))))
    valid = (
        user is not None
        and user.is_active
        and verify_password(payload.password, user.password_hash)
    )
    if not valid or user is None:
        record_audit(
            db,
            action="auth.login",
            resource_type="session",
            correlation_id=correlation_id,
            outcome="denied",
            details={"reason": "invalid_credentials"},
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    issued = issue_session(
        db,
        user,
        settings,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    user.last_login_at = utcnow()
    record_audit(
        db,
        action="auth.login",
        resource_type="session",
        correlation_id=correlation_id,
        outcome="success",
        actor_user_id=user.id,
    )
    return SessionResponse(access_token=issued.raw_token, expires_at=issued.expires_at)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    db: Database,
    settings: Configuration,
    correlation_id: CorrelationId,
    token: Annotated[str, Depends(oauth2_scheme)],
) -> None:
    revoked = revoke_session(db, token, settings)
    record_audit(
        db,
        action="auth.logout",
        resource_type="session",
        correlation_id=correlation_id,
        outcome="success" if revoked else "not_found",
    )
