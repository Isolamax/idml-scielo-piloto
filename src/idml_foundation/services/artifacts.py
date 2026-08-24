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
    scan = scanner.scan(data)
    if not scan.clean:
        raise ValueError("content scanner rejected upload")

    digest = hashlib.sha256(data).hexdigest()
    existing = db.scalar(
        select(Artifact).where(
            Artifact.organization_id == organization_id,
            Artifact.sha256 == digest,
        )
    )
    if existing is not None:
        return existing, inspection

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

    artifact = Artifact(
        organization_id=organization_id,
        sha256=digest,
        size_bytes=len(data),
        media_type="application/vnd.adobe.indesign-idml-package",
        original_name=PurePath(original_name).name[:255],
        storage_key=storage_key,
        scanner_status=scan.status,
    )
    db.add(artifact)
    db.flush()
    return artifact, inspection
