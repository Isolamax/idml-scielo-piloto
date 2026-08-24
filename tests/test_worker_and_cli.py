import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from idml_foundation.cli import bootstrap
from idml_foundation.models import Job, JobEffect, Membership, Organization, User
from idml_foundation.services.jobs import create_job
from idml_foundation.worker import find_queued_job, process_job


def test_worker_completes_noop_once(db: Session, session_factory: sessionmaker[Session]) -> None:
    org = Organization(slug="worker", name="Worker")
    db.add(org)
    db.flush()
    job, _ = create_job(
        db,
        organization_id=org.id,
        kind="foundation.noop",
        idempotency_key="worker-noop-0001",
        payload={},
        correlation_id="worker-create",
        actor_id="test-user",
    )
    job_id = job.id
    db.commit()

    process_job(job_id, session_factory)
    process_job(job_id, session_factory)

    db.expire_all()
    completed = db.get(Job, job_id)
    effects = list(db.scalars(select(JobEffect).where(JobEffect.job_id == job_id)))
    assert completed is not None
    assert completed.state == "succeeded"
    assert completed.attempt_count == 1
    assert len(effects) == 1


def test_worker_quarantines_unsupported_kind(
    db: Session, session_factory: sessionmaker[Session]
) -> None:
    org = Organization(slug="unsupported", name="Unsupported")
    db.add(org)
    db.flush()
    job, _ = create_job(
        db,
        organization_id=org.id,
        kind="unknown.kind",
        idempotency_key="worker-unsupported-0001",
        payload={},
        correlation_id="worker-create",
        actor_id="test-user",
    )
    job_id = job.id
    db.commit()
    process_job(job_id, session_factory)
    db.expire_all()
    failed = db.get(Job, job_id)
    assert failed is not None
    assert failed.state == "failed_permanent"
    assert failed.error_code == "unsupported_job"


def test_worker_recovers_durable_queued_job(
    db: Session, session_factory: sessionmaker[Session]
) -> None:
    org = Organization(slug="recovery", name="Recovery")
    db.add(org)
    db.flush()
    job, _ = create_job(
        db,
        organization_id=org.id,
        kind="foundation.noop",
        idempotency_key="recovery-noop-0001",
        payload={},
        correlation_id="worker-recovery",
        actor_id="test-user",
    )
    job_id = job.id
    db.commit()

    assert find_queued_job(session_factory) == job_id
    process_job(job_id, session_factory)
    assert find_queued_job(session_factory) is None


def test_bootstrap_is_idempotent(
    monkeypatch: pytest.MonkeyPatch, session_factory: sessionmaker[Session]
) -> None:
    monkeypatch.setenv("IDML_BOOTSTRAP_PASSWORD", "bootstrap password long enough")
    bootstrap("pilot", "Pilot Company", "owner@example.com", session_factory)
    bootstrap("pilot", "Pilot Company", "owner@example.com", session_factory)
    with session_factory() as db:
        assert len(list(db.scalars(select(Organization)))) == 1
        assert len(list(db.scalars(select(User)))) == 1
        assert len(list(db.scalars(select(Membership)))) == 1
