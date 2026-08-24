from typing import Literal, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from idml_foundation.domain.canonical import CanonicalArticle
from idml_foundation.domain.common import content_digest
from idml_foundation.domain.raw import RawArticle
from idml_foundation.domain.schema_migrations import migrate_payload
from idml_foundation.models import Artifact, DomainSnapshot, Resource

SnapshotKind = Literal["raw", "canonical"]
DomainDocument = RawArticle | CanonicalArticle


def store_snapshot(
    db: Session,
    *,
    organization_id: str,
    resource_id: str,
    document: DomainDocument,
    revision: int,
    source_artifact_id: str | None = None,
    parent_snapshot_id: str | None = None,
) -> tuple[DomainSnapshot, bool]:
    if revision < 1:
        raise ValueError("revision must be positive")
    resource = db.scalar(
        select(Resource).where(
            Resource.id == resource_id,
            Resource.organization_id == organization_id,
        )
    )
    if resource is None:
        raise ValueError("resource does not belong to organization")
    if source_artifact_id is not None:
        artifact = db.scalar(
            select(Artifact).where(
                Artifact.id == source_artifact_id,
                Artifact.organization_id == organization_id,
            )
        )
        if artifact is None:
            raise ValueError("source artifact does not belong to organization")

    kind: SnapshotKind = "raw" if isinstance(document, RawArticle) else "canonical"
    digest = content_digest(document)
    existing = db.scalar(
        select(DomainSnapshot).where(
            DomainSnapshot.resource_id == resource_id,
            DomainSnapshot.model_kind == kind,
            DomainSnapshot.content_sha256 == digest,
        )
    )
    if existing is not None:
        return existing, False

    if parent_snapshot_id is not None:
        parent = db.scalar(
            select(DomainSnapshot).where(
                DomainSnapshot.id == parent_snapshot_id,
                DomainSnapshot.organization_id == organization_id,
                DomainSnapshot.resource_id == resource_id,
                DomainSnapshot.model_kind == kind,
            )
        )
        if parent is None:
            raise ValueError("parent snapshot is outside the model lineage")

    snapshot = DomainSnapshot(
        organization_id=organization_id,
        resource_id=resource_id,
        source_artifact_id=source_artifact_id,
        parent_snapshot_id=parent_snapshot_id,
        model_kind=kind,
        schema_version=document.schema_version,
        revision=revision,
        content_sha256=digest,
        payload=document.model_dump(mode="json", exclude_none=False),
    )
    db.add(snapshot)
    db.flush()
    return snapshot, True


def load_snapshot(snapshot: DomainSnapshot) -> DomainDocument:
    if snapshot.model_kind not in {"raw", "canonical"}:
        raise ValueError("unsupported snapshot kind")
    kind = cast(SnapshotKind, snapshot.model_kind)
    payload = migrate_payload(kind, snapshot.payload)
    if kind == "raw":
        return RawArticle.model_validate(payload)
    if kind == "canonical":
        return CanonicalArticle.model_validate(payload)
    raise AssertionError("unreachable snapshot kind")
