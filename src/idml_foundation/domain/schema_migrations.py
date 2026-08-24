import copy
from collections.abc import Callable
from typing import Any, Literal

from idml_foundation.domain.canonical import CANONICAL_SCHEMA_VERSION
from idml_foundation.domain.raw import RAW_SCHEMA_VERSION

ModelKind = Literal["raw", "canonical"]
Migration = Callable[[dict[str, Any]], dict[str, Any]]


class UnsupportedSchemaVersion(ValueError):
    pass


def _raw_0_1_to_1_0(payload: dict[str, Any]) -> dict[str, Any]:
    migrated = copy.deepcopy(payload)
    migrated["source_artifact_sha256"] = migrated.pop("source_sha256")
    migrated["schema_version"] = RAW_SCHEMA_VERSION
    return migrated


def _canonical_0_1_to_1_0(payload: dict[str, Any]) -> dict[str, Any]:
    migrated = copy.deepcopy(payload)
    migrated["journal_profile_id"] = migrated.pop("profile")
    migrated["source_raw_sha256"] = migrated.pop("raw_sha256")
    migrated.setdefault("assets", [])
    migrated.setdefault("review_reasons", [])
    migrated["schema_version"] = CANONICAL_SCHEMA_VERSION
    return migrated


MIGRATIONS: dict[tuple[ModelKind, str], tuple[str, Migration]] = {
    ("raw", "0.1.0"): (RAW_SCHEMA_VERSION, _raw_0_1_to_1_0),
    ("canonical", "0.1.0"): (CANONICAL_SCHEMA_VERSION, _canonical_0_1_to_1_0),
}

LATEST_VERSIONS: dict[ModelKind, str] = {
    "raw": RAW_SCHEMA_VERSION,
    "canonical": CANONICAL_SCHEMA_VERSION,
}


def migrate_payload(
    kind: ModelKind,
    payload: dict[str, Any],
    target_version: str | None = None,
) -> dict[str, Any]:
    target = target_version or LATEST_VERSIONS[kind]
    migrated = copy.deepcopy(payload)
    seen: set[str] = set()
    while migrated.get("schema_version") != target:
        current = migrated.get("schema_version")
        if not isinstance(current, str) or current in seen:
            raise UnsupportedSchemaVersion(f"cannot migrate {kind} schema from {current!r}")
        seen.add(current)
        step = MIGRATIONS.get((kind, current))
        if step is None:
            raise UnsupportedSchemaVersion(f"no {kind} schema migration from {current}")
        _next_version, migration = step
        migrated = migration(migrated)
    return migrated
