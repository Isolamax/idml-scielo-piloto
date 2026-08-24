from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from idml_foundation.dependencies import (
    Configuration,
    Database,
    Scanner,
    require_permission,
)
from idml_foundation.rbac import Permission, TenantContext
from idml_foundation.schemas import ArtifactRead
from idml_foundation.services.artifacts import store_idml_artifact

router = APIRouter(prefix="/v1/artifacts", tags=["artifacts"])


@router.post("/idml", response_model=ArtifactRead, status_code=status.HTTP_201_CREATED)
async def upload_idml(
    db: Database,
    settings: Configuration,
    scanner: Scanner,
    context: Annotated[TenantContext, require_permission(Permission.ARTIFACT_UPLOAD)],
    upload: Annotated[UploadFile, File()],
) -> object:
    data = await upload.read(settings.upload_max_bytes + 1)
    if len(data) > settings.upload_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="too large"
        )
    artifact, _inspection = store_idml_artifact(
        db,
        organization_id=context.organization_id,
        original_name=upload.filename or "upload.idml",
        data=data,
        settings=settings,
        scanner=scanner,
    )
    return artifact
