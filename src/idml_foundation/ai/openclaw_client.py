from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from idml_foundation.ai.orchestration import ProviderResponse, ProviderUnavailable
from idml_foundation.domain.common import canonical_bytes

MAX_GATEWAY_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_GATEWAY_ERROR_BYTES = 64 * 1024
_SAFE_ERROR_FRAGMENT = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")


class JsonPostTransport(Protocol):
    def post_json(
        self,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout_seconds: int,
    ) -> dict[str, Any]: ...


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        del req, fp, code, msg, headers, newurl
        return None


class UrllibJsonPostTransport:
    def post_json(
        self,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        if urlsplit(url).scheme not in {"http", "https"}:
            raise ValueError("gateway transport only permits HTTP(S)")
        request = Request(  # noqa: S310 - scheme is restricted immediately above
            url,
            data=canonical_bytes(payload),
            headers=headers,
            method="POST",
        )
        try:
            with build_opener(_NoRedirects).open(request, timeout=timeout_seconds) as response:
                content_type = response.headers.get_content_type()
                if content_type != "application/json":
                    raise RuntimeError("OpenClaw gateway returned an unsupported content type")
                raw = response.read(MAX_GATEWAY_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            error_code = _gateway_http_error_code(exc)
            if exc.code >= 500 or exc.code == 429:
                raise ProviderUnavailable(error_code) from exc
            raise RuntimeError(error_code) from exc
        except (TimeoutError, URLError) as exc:
            raise ProviderUnavailable("OpenClaw gateway is unavailable") from exc
        if len(raw) > MAX_GATEWAY_RESPONSE_BYTES:
            raise RuntimeError("OpenClaw gateway response exceeds the size limit")
        try:
            decoded = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("OpenClaw gateway returned invalid JSON") from exc
        if not isinstance(decoded, dict):
            raise RuntimeError("OpenClaw gateway response must be an object")
        return decoded


def _gateway_http_error_code(exc: HTTPError) -> str:
    fragments = ["OPENCLAW", "HTTP", str(exc.code)]
    try:
        raw = exc.read(MAX_GATEWAY_ERROR_BYTES + 1)
        if len(raw) <= MAX_GATEWAY_ERROR_BYTES:
            decoded = json.loads(raw)
            error = decoded.get("error") if isinstance(decoded, dict) else None
            if isinstance(error, dict):
                for field in ("type", "code"):
                    value = error.get(field)
                    if isinstance(value, str) and _SAFE_ERROR_FRAGMENT.fullmatch(value):
                        fragment = re.sub(r"[^A-Za-z0-9]", "_", value).upper()
                        if fragment not in fragments:
                            fragments.append(fragment)
    except (AttributeError, UnicodeDecodeError, json.JSONDecodeError, OSError):
        pass
    return "_".join(fragments)[:100]


@dataclass(frozen=True)
class ParsedUsage:
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int


def _integer(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RuntimeError(f"OpenClaw gateway returned invalid {field}")
    return value


def _parse_usage(payload: dict[str, Any]) -> ParsedUsage:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        raise RuntimeError("OpenClaw gateway response has no usage metadata")
    input_tokens = _integer(usage.get("input_tokens"), field="input token usage")
    output_tokens = _integer(usage.get("output_tokens"), field="output token usage")
    cached_input_tokens = 0
    details = usage.get("input_tokens_details")
    if details is not None:
        if not isinstance(details, dict):
            raise RuntimeError("OpenClaw gateway returned invalid input token details")
        cached_input_tokens = _integer(
            details.get("cached_tokens", 0),
            field="cached input token usage",
        )
    else:
        for alias in ("cache_read_tokens", "cacheRead"):
            if alias in usage:
                cached_input_tokens = _integer(
                    usage[alias],
                    field="cached input token usage",
                )
                break
    if cached_input_tokens > input_tokens:
        raise RuntimeError("OpenClaw cached input exceeds total input")
    return ParsedUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=cached_input_tokens,
    )


def _parse_output(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("status") not in {None, "completed"}:
        raise RuntimeError("OpenClaw gateway response did not complete")
    output = payload.get("output")
    if not isinstance(output, list):
        raise RuntimeError("OpenClaw gateway response has no output items")
    texts: list[str] = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            raise RuntimeError("OpenClaw gateway returned a non-message output")
        content = item.get("content")
        if not isinstance(content, list):
            raise RuntimeError("OpenClaw gateway returned invalid message content")
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "output_text":
                raise RuntimeError("OpenClaw gateway returned unsupported output content")
            text = part.get("text")
            if not isinstance(text, str):
                raise RuntimeError("OpenClaw gateway output text is invalid")
            texts.append(text)
    if len(texts) != 1:
        raise RuntimeError("OpenClaw gateway must return exactly one JSON output")
    try:
        decoded = json.loads(texts[0])
    except json.JSONDecodeError as exc:
        raise RuntimeError("OpenClaw gateway output is not JSON") from exc
    if not isinstance(decoded, dict):
        raise RuntimeError("OpenClaw gateway output must be a JSON object")
    return decoded


class OpenClawResponsesClient:
    """Restricted OpenResponses client. It never follows redirects or exposes secrets in errors."""

    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        expected_model_key: str,
        transport: JsonPostTransport | None = None,
    ) -> None:
        parsed = urlsplit(base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("invalid OpenClaw gateway URL")
        if len(token) < 32:
            raise ValueError("OpenClaw gateway token is missing or too short")
        provider, separator, model = expected_model_key.partition("/")
        if (
            not separator
            or not provider
            or not model
            or expected_model_key != expected_model_key.casefold()
        ):
            raise ValueError("OpenClaw expected model must be exact provider/model")
        self.endpoint = f"{base_url.rstrip('/')}/v1/responses"
        self.token = token
        self.expected_provider = provider
        self.expected_model = model
        self.expected_model_key = expected_model_key
        self.transport = transport or UrllibJsonPostTransport()

    async def run_agent(
        self,
        *,
        agent_id: str,
        session_key: str,
        system_prompt: str,
        input_envelope: dict[str, Any],
        output_schema: dict[str, Any],
        tool_allowlist: frozenset[str],
        timeout_seconds: int,
        max_output_tokens: int,
    ) -> ProviderResponse:
        if not agent_id or not session_key:
            raise ValueError("OpenClaw agent and session are required")
        del tool_allowlist
        schema_text = canonical_bytes(output_schema).decode("utf-8")
        envelope_text = canonical_bytes(input_envelope).decode("utf-8")
        request_payload: dict[str, Any] = {
            "model": f"openclaw/{agent_id}",
            "instructions": (
                f"{system_prompt}\n\n"
                "Return exactly one JSON object matching this schema. "
                "No gateway tools are available or permitted.\n"
                f"JSON schema: {schema_text}"
            ),
            "input": envelope_text,
            "max_output_tokens": max_output_tokens,
            "user": session_key,
        }
        response_payload = await asyncio.to_thread(
            self.transport.post_json,
            url=self.endpoint,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "x-openclaw-agent-id": agent_id,
                "x-openclaw-model": self.expected_model_key,
                "x-openclaw-session-key": session_key,
            },
            payload=request_payload,
            timeout_seconds=timeout_seconds,
        )
        usage = _parse_usage(response_payload)
        return ProviderResponse(
            payload=_parse_output(response_payload),
            provider=self.expected_provider,
            model=self.expected_model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cached_input_tokens=usage.cached_input_tokens,
        )
