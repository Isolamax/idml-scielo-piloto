from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from idml_foundation.models import AuditEvent, Membership, Organization, User
from idml_foundation.rbac import Permission, Role, TenantContext
from idml_foundation.security import hash_password


def test_login_and_logout_are_audited(client: TestClient, db: Session) -> None:
    user = User(
        email="admin@example.com", password_hash=hash_password("a very long valid password")
    )
    db.add(user)
    db.commit()

    login = client.post(
        "/v1/auth/login",
        json={"email": user.email, "password": "a very long valid password"},
        headers={"X-Correlation-ID": "auth-test-0001"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    assert token not in login.headers.values()

    logout = client.post(
        "/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}", "X-Correlation-ID": "auth-test-0002"},
    )
    assert logout.status_code == 204

    events = list(db.scalars(select(AuditEvent).order_by(AuditEvent.created_at)))
    assert [event.action for event in events] == ["auth.login", "auth.logout"]
    assert all(event.correlation_id.startswith("auth-test") for event in events)


def test_invalid_login_has_generic_error(client: TestClient) -> None:
    response = client.post(
        "/v1/auth/login",
        json={"email": "missing@example.com", "password": "this is not the password"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid credentials"}


def test_rbac_denies_by_default(db: Session) -> None:
    user = User(email="reviewer@example.test", password_hash="not-used")
    org = Organization(slug="review", name="Review")
    db.add_all([user, org])
    db.flush()
    db.add(Membership(user_id=user.id, organization_id=org.id, role=Role.REVIEWER.value))
    context = TenantContext(user=user, organization_id=org.id, role=Role.REVIEWER)
    assert context.allows(Permission.REVIEW_WRITE)
    assert not context.allows(Permission.RELEASE_APPROVE)
