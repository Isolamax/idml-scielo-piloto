from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Mapper, Session

from idml_foundation.models import AuditEvent


@event.listens_for(AuditEvent, "before_update")
@event.listens_for(AuditEvent, "before_delete")
def _prevent_audit_mutation(
    mapper: Mapper[AuditEvent], connection: object, target: AuditEvent
) -> None:
    del mapper, connection, target
    raise ValueError("audit events are append-only")


def record_audit(
    db: Session,
    *,
    action: str,
    resource_type: str,
    correlation_id: str,
    outcome: str,
    organization_id: str | None = None,
    actor_user_id: str | None = None,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditEvent:
    event_record = AuditEvent(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        correlation_id=correlation_id,
        outcome=outcome,
        details=details or {},
    )
    db.add(event_record)
    db.flush()
    return event_record
