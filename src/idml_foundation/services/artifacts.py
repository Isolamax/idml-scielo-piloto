import hashlib
import os
import tempfile
from pathlib import Path, PurePath

from sqlalchemy import select
from sqlalchemy.orm import Session

from idml_foundation.ingest.safe_zip import ArchiveInspection, inspect_idml
from idml_foundation.ingest.scanner import ContentScanner
from idml_foundation.models import Artifact
from idml_foundation.settings import Settings

_ASSET_SIGNATURES = (
    (b"%PDF-", "application/pdf"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
)


class UnsafeContentError(ValueError):
    pass


def _store_bytes(
    db: Session,
    *,
    organization_id: str,
    original_name: str,
    data: bytes,
    media_type: str,
    settings: Settings,
    scanner: ContentScanner,
) -> Artifact:
    scan = scanner.scan(data)
    if not scan.clean:
        raise UnsafeContentError("content scanner rejected upload")
    digest = hashlib.sha256(data).hexdigest()
    existing = db.scalar(
        select(Artifact).where(
            Artifact.organization_id == organization_id,
            Artifact.sha256 == digest,
        )
    )
    if existing is not None:
        return existing
    storage_key = f"{organization_id}/{digest[:2]}/{digest}"
    destination = settings.artifact_root / storage_key
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
    if not destination.exists():
        descriptor, temporary_name = tempfile.mkstemp(prefix=".upload-", dir=destination.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, destination)
            destination.chmod(0o640)
        finally:
            temporary.unlink(missing_ok=True)
    basename = PurePath(original_name).name
    safe_name = "".join(
        character
        for character in basename
        if character.isprintable() and character not in {'"', "\\", "/"}
    )[:255]
    artifact = Artifact(
        organization_id=organization_id,
        sha256=digest,
        size_bytes=len(data),
        media_type=media_type,
        original_name=safe_name or "artifact",
        storage_key=storage_key,
        scanner_status=scan.status,
    )
    db.add(artifact)
    db.flush()
    return artifact


def store_supporting_artifact(
    db: Session,
    *,
    organization_id: str,
    original_name: str,
    data: bytes,
    settings: Settings,
    scanner: ContentScanner,
) -> Artifact:
    media_type = next(
        (candidate for signature, candidate in _ASSET_SIGNATURES if data.startswith(signature)),
        None,
    )
    if media_type is None:
        raise ValueError("unsupported asset format")
    return _store_bytes(
        db,
        organization_id=organization_id,
        original_name=original_name,
        data=data,
        media_type=media_type,
        settings=settings,
        scanner=scanner,
    )


def store_idml_artifact(
    db: Session,
    *,
    organization_id: str,
    original_name: str,
    data: bytes,
    settings: Settings,
    scanner: ContentScanner,
) -> tuple[Artifact, ArchiveInspection]:
    inspection = inspect_idml(data, settings)
    artifact = _store_bytes(
        db,
        organization_id=organization_id,
        original_name=original_name,
        data=data,
        media_type="application/vnd.adobe.indesign-idml-package",
        settings=settings,
        scanner=scanner,
    )
    return artifact, inspection
