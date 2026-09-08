import hashlib
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Response, UploadFile, status
from sqlalchemy import select

from idml_foundation.dependencies import (
    Configuration,
    CorrelationId,
    Database,
    Scanner,
    require_permission,
)
from idml_foundation.models import Artifact
from idml_foundation.rbac import Permission, TenantContext
from idml_foundation.schemas import ArtifactRead
from idml_foundation.services.artifacts import (
    UnsafeContentError,
    store_idml_artifact,
    store_supporting_artifact,
)
from idml_foundation.services.audit import record_audit

router = APIRouter(prefix="/v1/artifacts", tags=["artifacts"])


@router.post("/idml", response_model=ArtifactRead, status_code=status.HTTP_201_CREATED)
async def upload_idml(
    db: Database,
    settings: Configuration,
    scanner: Scanner,
    correlation_id: CorrelationId,
    context: Annotated[TenantContext, require_permission(Permission.ARTIFACT_UPLOAD)],
    upload: Annotated[UploadFile, File()],
) -> object:
    data = await upload.read(settings.upload_max_bytes + 1)
    if len(data) > settings.upload_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="too large"
        )
    try:
        artifact, _inspection = store_idml_artifact(
            db,
            organization_id=context.organization_id,
            original_name=upload.filename or "upload.idml",
            data=data,
            settings=settings,
            scanner=scanner,
        )
    except UnsafeContentError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    record_audit(
        db,
        action="artifact.upload",
        resource_type="artifact",
        resource_id=artifact.id,
        organization_id=context.organization_id,
        actor_user_id=context.user.id,
        correlation_id=correlation_id,
        outcome="success",
        details={"sha256": artifact.sha256, "media_type": artifact.media_type},
    )
    return artifact


@router.post("/assets", response_model=ArtifactRead, status_code=status.HTTP_201_CREATED)
async def upload_asset(
    db: Database,
    settings: Configuration,
    scanner: Scanner,
    correlation_id: CorrelationId,
    context: Annotated[TenantContext, require_permission(Permission.ARTIFACT_UPLOAD)],
    upload: Annotated[UploadFile, File()],
) -> Artifact:
    data = await upload.read(settings.upload_max_bytes + 1)
    if len(data) > settings.upload_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="too large"
        )
    try:
        artifact = store_supporting_artifact(
            db,
            organization_id=context.organization_id,
            original_name=upload.filename or "asset",
            data=data,
            settings=settings,
            scanner=scanner,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    record_audit(
        db,
        action="artifact.upload",
        resource_type="artifact",
        resource_id=artifact.id,
        organization_id=context.organization_id,
        actor_user_id=context.user.id,
        correlation_id=correlation_id,
        outcome="success",
        details={"sha256": artifact.sha256, "media_type": artifact.media_type},
    )
    return artifact


@router.get("", response_model=list[ArtifactRead])
def list_artifacts(
    db: Database,
    context: Annotated[TenantContext, require_permission(Permission.RESOURCE_READ)],
) -> list[Artifact]:
    return list(
        db.scalars(
            select(Artifact)
            .where(Artifact.organization_id == context.organization_id)
            .order_by(Artifact.created_at.desc())
            .limit(200)
        )
    )


@router.get("/{artifact_id}/download")
def download_artifact(
    artifact_id: str,
    db: Database,
    settings: Configuration,
    correlation_id: CorrelationId,
    context: Annotated[TenantContext, require_permission(Permission.RESOURCE_READ)],
) -> Response:
    artifact = db.scalar(
        select(Artifact).where(
            Artifact.id == artifact_id,
            Artifact.organization_id == context.organization_id,
        )
    )
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="artifact not found")
    root = settings.artifact_root.resolve()
    path = (root / artifact.storage_key).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="artifact not found")
    content = Path(path).read_bytes()
    if hashlib.sha256(content).hexdigest() != artifact.sha256:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="artifact integrity failure",
        )
    record_audit(
        db,
        action="artifact.download",
        resource_type="artifact",
        resource_id=artifact.id,
        organization_id=context.organization_id,
        actor_user_id=context.user.id,
        correlation_id=correlation_id,
        outcome="success",
        details={"sha256": artifact.sha256},
    )
    return Response(
        content=content,
        media_type=artifact.media_type,
        headers={"Content-Disposition": f'attachment; filename="{artifact.original_name}"'},
    )
