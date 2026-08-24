from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from idml_foundation.ingest.safe_zip import UnsafeArchiveError, inspect_idml
from idml_foundation.ingest.xml_security import UnsafeXmlError, parse_untrusted_xml
from idml_foundation.models import Membership, Organization, Resource, User, utcnow
from idml_foundation.rbac import Role
from idml_foundation.security import hash_password, issue_session
from idml_foundation.settings import Settings
from tests.helpers import make_idml


@pytest.mark.security
def test_path_traversal_is_blocked(settings: Settings) -> None:
    data = make_idml(extra_name="../escaped.xml")
    with pytest.raises(UnsafeArchiveError, match="path traversal") as error:
        inspect_idml(data, settings)
    assert error.value.code == "path_traversal"


@pytest.mark.security
def test_zip_bomb_ratio_is_blocked(settings: Settings) -> None:
    data = make_idml(extra_name="Stories/Story.xml", extra_data=b"A" * (2 * 1024 * 1024))
    with pytest.raises(UnsafeArchiveError, match="compression ratio") as error:
        inspect_idml(data, settings)
    assert error.value.code == "compression_ratio"


@pytest.mark.security
def test_nested_archive_is_blocked(settings: Settings) -> None:
    data = make_idml(extra_name="Links/payload.zip")
    with pytest.raises(UnsafeArchiveError) as error:
        inspect_idml(data, settings)
    assert error.value.code == "nested_archive"


@pytest.mark.security
def test_xxe_is_blocked() -> None:
    payload = b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><x>&e;</x>'
    with pytest.raises(UnsafeXmlError):
        parse_untrusted_xml(payload)


def test_safe_xml_is_parsed_without_network() -> None:
    root = parse_untrusted_xml(b"<article><p>safe</p></article>")
    assert root.tag == "article"
    assert root.findtext("p") == "safe"


@pytest.mark.security
def test_user_cannot_access_other_organization(
    client: TestClient, db: Session, settings: Settings
) -> None:
    org_a = Organization(slug="org-a", name="Organization A")
    org_b = Organization(slug="org-b", name="Organization B")
    user = User(
        email="operator@example.com", password_hash=hash_password("correct horse battery staple")
    )
    db.add_all([org_a, org_b, user])
    db.flush()
    db.add(Membership(organization_id=org_a.id, user_id=user.id, role=Role.OPERATOR.value))
    foreign = Resource(organization_id=org_b.id, title="Foreign resource")
    db.add(foreign)
    db.flush()
    token = issue_session(db, user, settings).raw_token
    db.commit()

    response = client.get(
        f"/v1/resources/{foreign.id}",
        headers={"Authorization": f"Bearer {token}", "X-Organization-ID": org_a.id},
    )
    assert response.status_code == 404

    response = client.get(
        "/v1/resources",
        headers={"Authorization": f"Bearer {token}", "X-Organization-ID": org_b.id},
    )
    assert response.status_code == 404


def test_session_expiration_is_configured(settings: Settings) -> None:
    assert settings.session_ttl_seconds <= int(timedelta(days=1).total_seconds())
    assert utcnow().tzinfo is not None
