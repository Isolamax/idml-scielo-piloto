from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from redis import Redis
from sqlalchemy import select

from idml_foundation.dependencies import (
    Configuration,
    CorrelationId,
    Database,
    require_permission,
)
from idml_foundation.models import Job
from idml_foundation.rbac import Permission, TenantContext
from idml_foundation.schemas import JobCreate, JobRead
from idml_foundation.services.jobs import create_job

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])


@router.post("", response_model=JobRead, status_code=status.HTTP_202_ACCEPTED)
def enqueue_job(
    payload: JobCreate,
    db: Database,
    settings: Configuration,
    correlation_id: CorrelationId,
    context: Annotated[TenantContext, require_permission(Permission.JOB_CREATE)],
) -> Job:
    job, created = create_job(
        db,
        organization_id=context.organization_id,
        kind=payload.kind,
        idempotency_key=payload.idempotency_key,
        payload=payload.payload,
        correlation_id=correlation_id,
        actor_id=context.user.id,
    )
    if created:
        Redis.from_url(settings.redis_url).lpush("idml:jobs", job.id)
    return job


@router.get("/{job_id}", response_model=JobRead)
def get_job(
    job_id: str,
    db: Database,
    context: Annotated[TenantContext, require_permission(Permission.JOB_READ)],
) -> Job:
    job = db.scalar(
        select(Job).where(Job.id == job_id, Job.organization_id == context.organization_id)
    )
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return job
