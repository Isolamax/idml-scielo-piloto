from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from idml_foundation.dependencies import Database, require_permission
from idml_foundation.models import Resource
from idml_foundation.rbac import Permission, TenantContext
from idml_foundation.schemas import ResourceCreate, ResourceRead

router = APIRouter(prefix="/v1/resources", tags=["resources"])


@router.post("", response_model=ResourceRead, status_code=status.HTTP_201_CREATED)
def create_resource(
    payload: ResourceCreate,
    db: Database,
    context: Annotated[TenantContext, require_permission(Permission.RESOURCE_WRITE)],
) -> Resource:
    resource = Resource(organization_id=context.organization_id, title=payload.title)
    db.add(resource)
    db.flush()
    return resource


@router.get("", response_model=list[ResourceRead])
def list_resources(
    db: Database,
    context: Annotated[TenantContext, require_permission(Permission.RESOURCE_READ)],
) -> list[Resource]:
    return list(
        db.scalars(
            select(Resource)
            .where(Resource.organization_id == context.organization_id)
            .order_by(Resource.created_at)
        )
    )


@router.get("/{resource_id}", response_model=ResourceRead)
def get_resource(
    resource_id: str,
    db: Database,
    context: Annotated[TenantContext, require_permission(Permission.RESOURCE_READ)],
) -> Resource:
    resource = db.scalar(
        select(Resource).where(
            Resource.id == resource_id,
            Resource.organization_id == context.organization_id,
        )
    )
    if resource is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")
    return resource
