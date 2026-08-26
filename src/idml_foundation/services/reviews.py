from __future__ import annotations

import copy
import hashlib
from typing import Any

from sqlalchemy import event, func, select, update
from sqlalchemy.orm import Mapper, Session

from idml_foundation.domain.canonical import CanonicalArticle
from idml_foundation.domain.common import canonical_bytes
from idml_foundation.models import (
    DomainSnapshot,
    ReleaseApproval,
    ReviewBuild,
    ReviewDecision,
    ReviewItem,
    utcnow,
)
from idml_foundation.pipeline.jats_builder import JatsBuilder
from idml_foundation.pipeline.profile import JournalProfile
from idml_foundation.pipeline.validation import OfflineJatsValidator
from idml_foundation.schemas import JsonPatchOperation, ReviewDecisionCreate
from idml_foundation.services.snapshots import load_snapshot, store_snapshot

_FORBIDDEN_SEGMENTS = {
    "article_id",
    "content_sha256",
    "evidence",
    "evidence_ids",
    "id",
    "journal_profile_id",
    "schema_version",
    "source_raw_sha256",
}


@event.listens_for(ReviewDecision, "before_update")
@event.listens_for(ReviewDecision, "before_delete")
@event.listens_for(ReviewBuild, "before_update")
@event.listens_for(ReviewBuild, "before_delete")
@event.listens_for(ReleaseApproval, "before_update")
@event.listens_for(ReleaseApproval, "before_delete")
def _prevent_review_history_mutation(
    mapper: Mapper[Any], connection: object, target: object
) -> None:
    del mapper, connection, target
    raise ValueError("decision history is append-only")


def _segments(path: str) -> list[str]:
    if not path.startswith("/") or path == "/":
        raise ValueError("patch path must be a non-root JSON Pointer")
    segments = [part.replace("~1", "/").replace("~0", "~") for part in path[1:].split("/")]
    if any(not segment for segment in segments):
        raise ValueError("patch path contains an empty segment")
    if _FORBIDDEN_SEGMENTS.intersection(segments):
        raise ValueError("patch path targets an immutable field")
    return segments


def validate_review_path(path: str) -> None:
    segments = _segments(path)
    if segments[0] not in {"front", "body", "back", "assets"}:
        raise ValueError("review path is outside editable canonical content")


def _replace_pointer(document: Any, operation: JsonPatchOperation) -> None:
    segments = _segments(operation.path)
    current = document
    for segment in segments[:-1]:
        if isinstance(current, list):
            try:
                current = current[int(segment)]
            except (ValueError, IndexError) as exc:
                raise ValueError("patch path contains an invalid list index") from exc
        elif isinstance(current, dict) and segment in current:
            current = current[segment]
        else:
            raise ValueError("patch path does not exist")
    leaf = segments[-1]
    if isinstance(current, list):
        try:
            index = int(leaf)
            current[index] = operation.value
        except (ValueError, IndexError) as exc:
            raise ValueError("patch path contains an invalid list index") from exc
    elif isinstance(current, dict) and leaf in current:
        current[leaf] = operation.value
    else:
        raise ValueError("patch path does not exist")


def _path_is_scoped(operation_path: str, item_path: str) -> bool:
    return operation_path == item_path or operation_path.startswith(f"{item_path}/")


def claim_review_item(
    db: Session,
    *,
    organization_id: str,
    item_id: str,
    user_id: str,
    expected_version: int,
) -> ReviewItem | None:
    result = db.execute(
        update(ReviewItem)
        .where(
            ReviewItem.id == item_id,
            ReviewItem.organization_id == organization_id,
            ReviewItem.state == "open",
            ReviewItem.version == expected_version,
        )
        .values(
            state="claimed",
            assigned_user_id=user_id,
            version=ReviewItem.version + 1,
            updated_at=utcnow(),
        )
    )
    if result.rowcount != 1:  # type: ignore[attr-defined]
        return None
    return db.scalar(
        select(ReviewItem).where(
            ReviewItem.id == item_id,
            ReviewItem.organization_id == organization_id,
        )
    )


def apply_review_decision(
    db: Session,
    *,
    organization_id: str,
    item_id: str,
    user_id: str,
    payload: ReviewDecisionCreate,
    profile: JournalProfile,
    validator: OfflineJatsValidator,
) -> tuple[ReviewItem, ReviewDecision, ReviewBuild | None]:
    item = db.scalar(
        select(ReviewItem).where(
            ReviewItem.id == item_id,
            ReviewItem.organization_id == organization_id,
        )
    )
    if item is None:
        raise LookupError("review item not found")
    if item.state not in {"open", "claimed"}:
        raise RuntimeError("review item is not active")
    if item.assigned_user_id not in {None, user_id}:
        raise PermissionError("review item is claimed by another user")
    if item.version != payload.expected_version:
        raise RuntimeError("review item version conflict")

    claimed = db.execute(
        update(ReviewItem)
        .where(
            ReviewItem.id == item.id,
            ReviewItem.organization_id == organization_id,
            ReviewItem.version == payload.expected_version,
            ReviewItem.state.in_(("open", "claimed")),
        )
        .values(version=ReviewItem.version + 1, updated_at=utcnow())
        .execution_options(synchronize_session=False)
    )
    if claimed.rowcount != 1:  # type: ignore[attr-defined]
        raise RuntimeError("review item version conflict")
    item.version += 1

    patch_payload = [operation.model_dump(mode="json") for operation in payload.patch]
    patch_sha = hashlib.sha256(canonical_bytes({"patch": patch_payload})).hexdigest()
    decision = ReviewDecision(
        organization_id=organization_id,
        review_item_id=item.id,
        actor_user_id=user_id,
        base_snapshot_id=item.base_snapshot_id,
        action=payload.action,
        patch=patch_payload,
        justification=payload.justification,
        expected_version=payload.expected_version,
        patch_sha256=patch_sha,
    )

    if payload.action == "reject":
        if payload.patch:
            raise ValueError("reject decision cannot include a patch")
        db.add(decision)
        item.state = "rejected"
        item.assigned_user_id = user_id
        item.resolved_at = utcnow()
        db.flush()
        return item, decision, None
    if not payload.patch:
        raise ValueError("apply_patch decision requires at least one operation")
    for operation in payload.patch:
        validate_review_path(operation.path)
        if not _path_is_scoped(operation.path, item.field_path):
            raise ValueError("patch path is outside the review item scope")

    base_snapshot = db.scalar(
        select(DomainSnapshot).where(
            DomainSnapshot.id == item.base_snapshot_id,
            DomainSnapshot.organization_id == organization_id,
            DomainSnapshot.resource_id == item.resource_id,
            DomainSnapshot.model_kind == "canonical",
        )
    )
    if base_snapshot is None:
        raise ValueError("review base snapshot is unavailable")
    latest_snapshot_id = db.scalar(
        select(DomainSnapshot.id)
        .where(
            DomainSnapshot.organization_id == organization_id,
            DomainSnapshot.resource_id == item.resource_id,
            DomainSnapshot.model_kind == "canonical",
        )
        .order_by(DomainSnapshot.revision.desc())
        .limit(1)
    )
    if latest_snapshot_id != base_snapshot.id:
        raise RuntimeError("review base snapshot is stale")
    base_document = load_snapshot(base_snapshot)
    if not isinstance(base_document, CanonicalArticle):
        raise ValueError("review base is not canonical")
    updated_payload = copy.deepcopy(base_snapshot.payload)
    for operation in payload.patch:
        _replace_pointer(updated_payload, operation)
    reasons = updated_payload.get("review_reasons", [])
    updated_payload["review_reasons"] = [reason for reason in reasons if reason != item.rule_code]
    updated_document = CanonicalArticle.model_validate(updated_payload)
    if updated_document == base_document:
        raise ValueError("patch does not change the canonical model")

    next_revision = (
        db.scalar(
            select(func.max(DomainSnapshot.revision)).where(
                DomainSnapshot.organization_id == organization_id,
                DomainSnapshot.resource_id == item.resource_id,
                DomainSnapshot.model_kind == "canonical",
            )
        )
        or 0
    ) + 1
    snapshot, created = store_snapshot(
        db,
        organization_id=organization_id,
        resource_id=item.resource_id,
        document=updated_document,
        revision=next_revision,
        source_artifact_id=base_snapshot.source_artifact_id,
        parent_snapshot_id=base_snapshot.id,
    )
    if not created:
        raise ValueError("patch duplicates an existing canonical revision")
    decision.result_snapshot_id = snapshot.id
    db.add(decision)
    db.flush()
    xml = JatsBuilder(sps_version=profile.sps_version).build(updated_document)
    validation = validator.validate(
        xml, asset_names={asset.logical_name for asset in updated_document.assets}
    )
    build = ReviewBuild(
        organization_id=organization_id,
        review_decision_id=decision.id,
        snapshot_id=snapshot.id,
        xml_sha256=hashlib.sha256(xml).hexdigest(),
        xml_content=xml.decode("utf-8"),
        validation=validation.model_dump(mode="json"),
        validation_valid=validation.valid,
    )
    db.add(build)
    item.state = "resolved"
    item.assigned_user_id = user_id
    item.resolved_at = utcnow()
    db.execute(
        update(ReviewItem)
        .where(
            ReviewItem.organization_id == organization_id,
            ReviewItem.resource_id == item.resource_id,
            ReviewItem.id != item.id,
            ReviewItem.state.in_(("open", "claimed")),
            ReviewItem.base_snapshot_id == base_snapshot.id,
        )
        .values(
            base_snapshot_id=snapshot.id,
            version=ReviewItem.version + 1,
            state="open",
            assigned_user_id=None,
            updated_at=utcnow(),
        )
    )
    db.flush()
    return item, decision, build


def snapshot_diff(before: Any, after: Any, path: str = "") -> list[dict[str, Any]]:
    if before == after:
        return []
    if isinstance(before, dict) and isinstance(after, dict):
        changes: list[dict[str, Any]] = []
        for key in sorted(set(before) | set(after)):
            escaped = key.replace("~", "~0").replace("/", "~1")
            child = f"{path}/{escaped}"
            if key not in before:
                changes.append({"path": child, "after": after[key]})
            elif key not in after:
                changes.append({"path": child, "before": before[key]})
            else:
                changes.extend(snapshot_diff(before[key], after[key], child))
        return changes
    if isinstance(before, list) and isinstance(after, list):
        changes = []
        for index in range(max(len(before), len(after))):
            child = f"{path}/{index}"
            if index >= len(before):
                changes.append({"path": child, "after": after[index]})
            elif index >= len(after):
                changes.append({"path": child, "before": before[index]})
            else:
                changes.extend(snapshot_diff(before[index], after[index], child))
        return changes
    return [{"path": path or "/", "before": before, "after": after}]
