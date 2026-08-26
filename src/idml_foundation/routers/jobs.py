import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import select

from idml_foundation.dependencies import (
    Configuration,
    CorrelationId,
    Database,
    require_permission,
)
from idml_foundation.models import Job, JobEvent
from idml_foundation.rbac import Permission, TenantContext
from idml_foundation.schemas import JobCreate, JobEventRead, JobRead
from idml_foundation.services.jobs import create_job

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])
logger = logging.getLogger(__name__)


@router.get("", response_model=list[JobRead])
def list_jobs(
    db: Database,
    context: Annotated[TenantContext, require_permission(Permission.JOB_READ)],
) -> list[Job]:
    return list(
        db.scalars(
            select(Job)
            .where(Job.organization_id == context.organization_id)
            .order_by(Job.created_at.desc())
            .limit(200)
        )
    )


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
        # The database is the durable queue. Commit before sending the best-effort
        # Redis wake-up so a fast worker can always observe the job.
        db.commit()
        db.refresh(job)
        try:
            Redis.from_url(settings.redis_url).lpush("idml:jobs", job.id)
        except RedisError:
            logger.warning(
                "job persisted; Redis wake-up failed",
                extra={
                    "event": "job.redis_wakeup_failed",
                    "job_id": job.id,
                    "organization_id": context.organization_id,
                    "correlation_id": correlation_id,
                },
            )
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


@router.get("/{job_id}/events", response_model=list[JobEventRead])
def get_job_events(
    job_id: str,
    db: Database,
    context: Annotated[TenantContext, require_permission(Permission.JOB_READ)],
) -> list[JobEvent]:
    job = db.scalar(
        select(Job.id).where(
            Job.id == job_id,
            Job.organization_id == context.organization_id,
        )
    )
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return list(
        db.scalars(
            select(JobEvent)
            .where(
                JobEvent.job_id == job_id,
                JobEvent.organization_id == context.organization_id,
            )
            .order_by(JobEvent.sequence)
        )
    )
