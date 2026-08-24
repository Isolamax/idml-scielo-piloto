from sqlalchemy.orm import Session

from idml_foundation.ingest.scanner import PolicyOnlyScanner, ScanResult
from idml_foundation.models import Organization
from idml_foundation.services.artifacts import store_idml_artifact
from idml_foundation.settings import Settings
from tests.helpers import make_idml


class RejectingScanner:
    def scan(self, data: bytes) -> ScanResult:
        del data
        return ScanResult(clean=False, status="malware_detected")


def test_artifact_is_content_addressed_and_immutable(db: Session, settings: Settings) -> None:
    org = Organization(slug="artifacts", name="Artifacts")
    db.add(org)
    db.flush()
    payload = make_idml(extra_name="Stories/Story_u1.xml", extra_data=b"<Story/>")
    first, inspection = store_idml_artifact(
        db,
        organization_id=org.id,
        original_name="article.idml",
        data=payload,
        settings=settings,
        scanner=PolicyOnlyScanner(),
    )
    second, _ = store_idml_artifact(
        db,
        organization_id=org.id,
        original_name="renamed.idml",
        data=payload,
        settings=settings,
        scanner=PolicyOnlyScanner(),
    )
    assert first.id == second.id
    assert inspection.entry_count == 3
    stored = settings.artifact_root / first.storage_key
    assert stored.read_bytes() == payload


def test_rejected_scan_is_not_stored(db: Session, settings: Settings) -> None:
    org = Organization(slug="rejected", name="Rejected")
    db.add(org)
    db.flush()
    try:
        store_idml_artifact(
            db,
            organization_id=org.id,
            original_name="article.idml",
            data=make_idml(),
            settings=settings,
            scanner=RejectingScanner(),
        )
    except ValueError as exc:
        assert "scanner rejected" in str(exc)
    else:
        raise AssertionError("scanner rejection was ignored")
