from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from idml_foundation.database import get_db
from idml_foundation.ingest.scanner import ContentScanner, build_scanner
from idml_foundation.models import Membership, Organization, User
from idml_foundation.rbac import Permission, Role, TenantContext
from idml_foundation.security import authenticate_session
from idml_foundation.settings import Settings, get_settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/login")
Database = Annotated[Session, Depends(get_db)]
Configuration = Annotated[Settings, Depends(get_settings)]


def get_current_user(
    db: Database,
    settings: Configuration,
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User:
    user = authenticate_session(db, token, settings)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_tenant_context(
    db: Database,
    user: CurrentUser,
    organization_id: Annotated[str, Header(alias="X-Organization-ID")],
) -> TenantContext:
    organization = db.scalar(
        select(Organization).where(
            Organization.id == organization_id,
            Organization.is_active.is_(True),
        )
    )
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="organization not found")
    if user.is_platform_admin:
        return TenantContext(user=user, organization_id=organization_id, role=Role.ORG_ADMIN)
    membership = db.scalar(
        select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.user_id == user.id,
            Membership.is_active.is_(True),
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="organization not found")
    try:
        role = Role(membership.role)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="membership role is invalid"
        ) from exc
    return TenantContext(user=user, organization_id=organization_id, role=role)


Tenant = Annotated[TenantContext, Depends(get_tenant_context)]


def require_permission(permission: Permission) -> object:
    def dependency(context: Tenant) -> TenantContext:
        context.require(permission)
        return context

    return Depends(dependency)


def get_correlation_id(request: Request) -> str:
    return str(request.state.correlation_id)


CorrelationId = Annotated[str, Depends(get_correlation_id)]


def get_content_scanner(settings: Configuration) -> ContentScanner:
    return build_scanner(settings)


Scanner = Annotated[ContentScanner, Depends(get_content_scanner)]
