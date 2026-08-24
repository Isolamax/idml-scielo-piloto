"""Live, non-secret Gate G1 validation executed inside the API container."""

from __future__ import annotations

import io
import json
import secrets
import time
import urllib.error
import urllib.request
import zipfile
from typing import Any

from sqlalchemy import func, select

from idml_foundation.database import session_scope
from idml_foundation.models import (
    AuditEvent,
    JobEffect,
    JobEvent,
    Membership,
    Organization,
    Resource,
    User,
)
from idml_foundation.rbac import Role
from idml_foundation.security import hash_password

API = "http://127.0.0.1:8000"


def call(
    method: str,
    path: str,
    *,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(  # noqa: S310 - fixed loopback API origin
        API + path, data=body, method=method, headers=headers or {}
    )
    try:
        with urllib.request.urlopen(  # noqa: S310 - request uses fixed loopback origin
            request, timeout=10
        ) as response:
            payload = response.read()
            try:
                decoded = json.loads(payload) if payload else {}
            except json.JSONDecodeError:
                decoded = {"non_json_response": True}
            return response.status, decoded
    except urllib.error.HTTPError as error:
        payload = error.read()
        try:
            decoded = json.loads(payload) if payload else {}
        except json.JSONDecodeError:
            decoded = {"non_json_response": True}
        return error.code, decoded


def json_call(
    method: str,
    path: str,
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    merged = {"Content-Type": "application/json", **(headers or {})}
    return call(method, path, body=json.dumps(payload).encode(), headers=merged)


suffix = secrets.token_hex(6)
password = secrets.token_urlsafe(24)
email = f"gate-g1-{suffix}@example.com"

with session_scope() as db:
    organization_a = Organization(slug=f"gate-a-{suffix}", name="Gate G1 Tenant A")
    organization_b = Organization(slug=f"gate-b-{suffix}", name="Gate G1 Tenant B")
    user = User(email=email, password_hash=hash_password(password))
    db.add_all([organization_a, organization_b, user])
    db.flush()
    db.add(
        Membership(
            organization_id=organization_a.id,
            user_id=user.id,
            role=Role.OPERATOR.value,
        )
    )
    foreign_resource = Resource(organization_id=organization_b.id, title="Tenant B secret")
    db.add(foreign_resource)
    db.flush()
    organization_a_id = organization_a.id
    foreign_resource_id = foreign_resource.id

login_correlation = f"gate-login-{suffix}"
status, login = json_call(
    "POST",
    "/v1/auth/login",
    {"email": email, "password": password},
    {"X-Correlation-ID": login_correlation},
)
assert status == 200, (status, login)
token = str(login["access_token"])
authorized = {
    "Authorization": f"Bearer {token}",
    "X-Organization-ID": organization_a_id,
}

status, _ = call("GET", f"/v1/resources/{foreign_resource_id}", headers=authorized)
assert status == 404, status
print("cross_tenant=blocked")

archive_bytes = io.BytesIO()
with zipfile.ZipFile(archive_bytes, "w") as archive:
    archive.writestr("../escape.txt", b"blocked")
boundary = f"gate-{suffix}"
multipart = (
    (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="upload"; filename="malicious.idml"\r\n'
        "Content-Type: application/vnd.adobe.indesign-idml-package\r\n\r\n"
    ).encode()
    + archive_bytes.getvalue()
    + f"\r\n--{boundary}--\r\n".encode()
)
status, rejected = call(
    "POST",
    "/v1/artifacts/idml",
    body=multipart,
    headers={**authorized, "Content-Type": f"multipart/form-data; boundary={boundary}"},
)
assert status == 422 and rejected.get("code") == "path_traversal", (status, rejected)
print("malicious_upload=blocked:path_traversal")

valid_archive = io.BytesIO()
with zipfile.ZipFile(valid_archive, "w") as archive:
    archive.writestr(
        "mimetype",
        b"application/vnd.adobe.indesign-idml-package",
        compress_type=zipfile.ZIP_STORED,
    )
    archive.writestr("designmap.xml", b"<Document/>", compress_type=zipfile.ZIP_DEFLATED)
valid_boundary = f"valid-{suffix}"
valid_multipart = (
    (
        f"--{valid_boundary}\r\n"
        'Content-Disposition: form-data; name="upload"; filename="valid.idml"\r\n'
        "Content-Type: application/vnd.adobe.indesign-idml-package\r\n\r\n"
    ).encode()
    + valid_archive.getvalue()
    + f"\r\n--{valid_boundary}--\r\n".encode()
)
status, stored = call(
    "POST",
    "/v1/artifacts/idml",
    body=valid_multipart,
    headers={
        **authorized,
        "Content-Type": f"multipart/form-data; boundary={valid_boundary}",
    },
)
assert status == 201 and len(str(stored.get("sha256", ""))) == 64, (status, stored)
print("artifact_storage=content_addressed_write_ok")

job_payload = {
    "kind": "foundation.noop",
    "idempotency_key": f"gate-idempotency-{suffix}",
    "payload": {"gate": "G1"},
}
status, first = json_call("POST", "/v1/jobs", job_payload, authorized)
assert status == 202, (status, first)
status, second = json_call("POST", "/v1/jobs", job_payload, authorized)
assert status == 202 and second["id"] == first["id"], (status, first, second)
job_id = str(first["id"])
print("idempotency=same_job")

job_state = "queued"
for _ in range(30):
    status, current = call("GET", f"/v1/jobs/{job_id}", headers=authorized)
    assert status == 200, (status, current)
    job_state = str(current["state"])
    if job_state == "succeeded":
        break
    time.sleep(0.5)
assert job_state == "succeeded", job_state

with session_scope() as db:
    effect_count = db.scalar(select(func.count(JobEffect.id)).where(JobEffect.job_id == job_id))
    events = list(
        db.scalars(select(JobEvent).where(JobEvent.job_id == job_id).order_by(JobEvent.sequence))
    )
    login_audit_count = db.scalar(
        select(func.count(AuditEvent.id)).where(
            AuditEvent.correlation_id == login_correlation,
            AuditEvent.action == "auth.login",
            AuditEvent.outcome == "success",
        )
    )

timeline = [event.to_state for event in events]
assert effect_count == 1, effect_count
assert timeline == ["queued", "running", "succeeded"], timeline
assert login_audit_count == 1, login_audit_count
print(f"job=succeeded effects={effect_count} timeline={','.join(timeline)}")
print("audit=login_and_job_timeline_recorded")

logout_status, _ = call("POST", "/v1/auth/logout", headers=authorized)
assert logout_status == 204, logout_status
print("G1_LIVE_TESTS=PASS")
