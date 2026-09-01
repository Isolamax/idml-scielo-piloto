from __future__ import annotations

import asyncio
import io
import json
from typing import Any
from urllib.error import HTTPError

import pytest

from idml_foundation.ai.contracts import ALLOWED_TOOLS
from idml_foundation.ai.openclaw_client import (
    OpenClawResponsesClient,
    UrllibJsonPostTransport,
)
from idml_foundation.ai.orchestration import ProviderUnavailable


class _FixtureTransport:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.call: dict[str, Any] | None = None

    def post_json(
        self,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        self.call = {
            "url": url,
            "headers": headers,
            "payload": payload,
            "timeout_seconds": timeout_seconds,
        }
        return self.response


def _gateway_response() -> dict[str, Any]:
    return {
        "id": "resp_fixture",
        "status": "completed",
        "model": "openclaw/idml-evaluator",
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": '{"schema_version":"agent-proposal-1.1"}',
                    }
                ],
            }
        ],
        "usage": {
            "input_tokens": 120,
            "output_tokens": 10,
            "input_tokens_details": {"cached_tokens": 20},
        },
    }


def test_openclaw_client_builds_restricted_request_and_parses_usage() -> None:
    transport = _FixtureTransport(_gateway_response())
    client = OpenClawResponsesClient(
        base_url="http://openclaw:47716",
        token="t" * 32,
        expected_model_key="openai/gpt-5.4-mini",
        transport=transport,
    )
    result = asyncio.run(
        client.run_agent(
            agent_id="idml-evaluator",
            session_key="idml:org:review",
            system_prompt="Return JSON.",
            input_envelope={"untrusted_content": {"title": "Example"}},
            output_schema={"type": "object"},
            tool_allowlist=ALLOWED_TOOLS,
            timeout_seconds=12,
            max_output_tokens=200,
        )
    )

    assert result.provider == "openai"
    assert result.model == "gpt-5.4-mini"
    assert result.input_tokens == 120
    assert result.cached_input_tokens == 20
    assert result.output_tokens == 10
    assert result.cost_microusd is None
    assert result.payload == {"schema_version": "agent-proposal-1.1"}
    assert transport.call is not None
    assert transport.call["url"] == "http://openclaw:47716/v1/responses"
    assert transport.call["headers"]["Authorization"] == f"Bearer {'t' * 32}"
    assert transport.call["headers"]["x-openclaw-model"] == "openai/gpt-5.4-mini"
    assert transport.call["payload"]["model"] == "openclaw/idml-evaluator"
    assert transport.call["payload"]["max_output_tokens"] == 200
    assert "JSON schema" in transport.call["payload"]["instructions"]


@pytest.mark.parametrize(
    "mutation, message",
    [
        (lambda value: value.pop("usage"), "no usage metadata"),
        (
            lambda value: value["usage"]["input_tokens_details"].update({"cached_tokens": 121}),
            "cached input exceeds",
        ),
        (lambda value: value.update({"output": []}), "exactly one JSON output"),
        (
            lambda value: value["output"][0]["content"][0].update({"text": "not json"}),
            "output is not JSON",
        ),
    ],
)
def test_openclaw_client_rejects_unusable_response(
    mutation: Any,
    message: str,
) -> None:
    response = _gateway_response()
    mutation(response)
    client = OpenClawResponsesClient(
        base_url="https://gateway.example.test",
        token="t" * 32,
        expected_model_key="openai/gpt-5.4-mini",
        transport=_FixtureTransport(response),
    )
    with pytest.raises(RuntimeError, match=message):
        asyncio.run(
            client.run_agent(
                agent_id="idml-evaluator",
                session_key="idml:org:review",
                system_prompt="Return JSON.",
                input_envelope={},
                output_schema={"type": "object"},
                tool_allowlist=ALLOWED_TOOLS,
                timeout_seconds=12,
                max_output_tokens=200,
            )
        )


def test_openclaw_client_rejects_unsafe_configuration() -> None:
    with pytest.raises(ValueError, match="URL"):
        OpenClawResponsesClient(
            base_url="file:///etc/passwd",
            token="t" * 32,
            expected_model_key="openai/gpt-5.4-mini",
        )
    with pytest.raises(ValueError, match="token"):
        OpenClawResponsesClient(
            base_url="https://gateway.example.test",
            token="short",
            expected_model_key="openai/gpt-5.4-mini",
        )


class _HttpErrorOpener:
    def __init__(self, status: int, body: dict[str, Any] | None = None) -> None:
        self.status = status
        self.body = body

    def open(self, request: Any, timeout: int) -> None:
        del request, timeout
        raise HTTPError(
            url="https://gateway.example.test/v1/responses",
            code=self.status,
            msg="redacted",
            hdrs=None,
            fp=io.BytesIO(json.dumps(self.body).encode()) if self.body else None,
        )


@pytest.mark.parametrize(
    "status, body, expected_exception, expected_code",
    [
        (400, None, RuntimeError, "OPENCLAW_HTTP_400"),
        (
            408,
            {
                "error": {
                    "type": "request_timeout",
                    "code": "upstream.timeout",
                    "message": "must never be copied into the exception",
                }
            },
            RuntimeError,
            "OPENCLAW_HTTP_408_REQUEST_TIMEOUT_UPSTREAM_TIMEOUT",
        ),
        (502, None, ProviderUnavailable, "OPENCLAW_HTTP_502"),
    ],
)
def test_gateway_http_errors_expose_only_safe_status_code(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    body: dict[str, Any] | None,
    expected_exception: type[Exception],
    expected_code: str,
) -> None:
    monkeypatch.setattr(
        "idml_foundation.ai.openclaw_client.build_opener",
        lambda *args: _HttpErrorOpener(status, body),
    )

    with pytest.raises(expected_exception, match=f"^{expected_code}$"):
        UrllibJsonPostTransport().post_json(
            url="https://gateway.example.test/v1/responses",
            headers={"Authorization": "Bearer redacted"},
            payload={"model": "openclaw"},
            timeout_seconds=1,
        )
