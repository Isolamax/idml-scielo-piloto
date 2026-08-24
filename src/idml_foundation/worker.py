import logging
import signal
import time
from dataclasses import dataclass
from typing import cast
from uuid import uuid4

from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from idml_foundation.database import SessionLocal, session_scope
from idml_foundation.logging_config import configure_logging
from idml_foundation.models import Job
from idml_foundation.services.jobs import record_effect_once, schedule_retry, transition_job
from idml_foundation.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class Shutdown:
    requested: bool = False


def process_job(job_id: str, factory: sessionmaker[Session] = SessionLocal) -> None:
    correlation_id = str(uuid4())
    with session_scope(factory) as db:
        job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if job is None or job.state != "queued":
            return
        transition_job(
            db,
            job,
            to_state="running",
            correlation_id=correlation_id,
            actor_type="worker",
        )
        try:
            if job.kind != "foundation.noop":
                raise ValueError("unsupported job kind")
            created = record_effect_once(db, job, "foundation.noop.completed")
            job.result = {"effect_created": created}
            transition_job(
                db,
                job,
                to_state="succeeded",
                correlation_id=correlation_id,
                actor_type="worker",
            )
        except ValueError:
            transition_job(
                db,
                job,
                to_state="failed_permanent",
                correlation_id=correlation_id,
                actor_type="worker",
                error_code="unsupported_job",
            )
        except Exception:
            logger.exception("job execution failed", extra={"job_id": job.id})
            transition_job(
                db,
                job,
                to_state="failed_retryable",
                correlation_id=correlation_id,
                actor_type="worker",
                error_code="transient_failure",
            )
            schedule_retry(db, job, correlation_id=correlation_id, delay_seconds=30)


def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    redis = Redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=5)
    shutdown = Shutdown()

    def request_shutdown(signum: int, frame: object) -> None:
        del signum, frame
        shutdown.requested = True

    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)
    logger.info("worker started", extra={"event": "worker.started"})
    while not shutdown.requested:
        try:
            item = cast(tuple[str, str] | None, redis.brpop(["idml:jobs"], timeout=2))
            if item:
                _queue, job_id = item
                process_job(job_id)
        except Exception:
            logger.exception("worker loop failure", extra={"event": "worker.loop_failure"})
            time.sleep(2)
    logger.info("worker stopped", extra={"event": "worker.stopped"})


def main() -> None:
    run()


if __name__ == "__main__":
    main()
