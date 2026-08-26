from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, replace
from typing import Any, Protocol

from idml_foundation.ai.contracts import ALLOWED_TOOLS, enforce_tool_allowlist
from idml_foundation.ai.outputs import parse_agent_output


@dataclass(frozen=True)
class AgentBudget:
    timeout_seconds: int = 45
    max_attempts: int = 2
    max_input_tokens: int = 12_000
    max_output_tokens: int = 2_000
    max_cost_microusd: int = 50_000

    def __post_init__(self) -> None:
        if not 1 <= self.timeout_seconds <= 300:
            raise ValueError("agent timeout is outside policy")
        if not 1 <= self.max_attempts <= 2:
            raise ValueError("agent attempts are outside policy")
        if min(self.max_input_tokens, self.max_output_tokens, self.max_cost_microusd) < 1:
            raise ValueError("agent budget values must be positive")


@dataclass(frozen=True)
class OrchestrationRequest:
    organization_id: str
    job_id: str | None
    resource_id: str
    review_item_id: str
    base_snapshot_id: str
    task_type: str
    domain: str
    idempotency_key: str
    system_prompt: str
    input_envelope: dict[str, Any]
    output_schema: dict[str, Any]
    tool_allowlist: frozenset[str]
    budget: AgentBudget
    initiator: str = "root"
    can_spawn: bool = True

    def __post_init__(self) -> None:
        enforce_tool_allowlist(self.tool_allowlist)
        if self.initiator not in {"root", "worker"}:
            raise ValueError("invalid orchestration initiator")
        if len(self.idempotency_key) < 8:
            raise ValueError("agent idempotency key is too short")


@dataclass(frozen=True)
class ProviderResponse:
    payload: dict[str, Any]
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_microusd: int


@dataclass(frozen=True)
class OrchestrationResult:
    status: str
    payload: dict[str, Any] | None
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_microusd: int
    latency_ms: int
    attempts: int
    error_code: str | None = None


class ProviderUnavailable(RuntimeError):
    pass


class AgentProvider(Protocol):
    name: str

    async def complete(self, request: OrchestrationRequest) -> ProviderResponse: ...


class Orchestrator(Protocol):
    name: str

    async def run(self, request: OrchestrationRequest) -> OrchestrationResult: ...


def _enforce_usage(response: ProviderResponse, budget: AgentBudget) -> None:
    if response.input_tokens > budget.max_input_tokens:
        raise RuntimeError("agent input token budget exceeded")
    if response.output_tokens > budget.max_output_tokens:
        raise RuntimeError("agent output token budget exceeded")
    if response.cost_microusd > budget.max_cost_microusd:
        raise RuntimeError("agent cost budget exceeded")


class SequentialOrchestrator:
    name = "sequential-v1"

    def __init__(self, provider: AgentProvider) -> None:
        self.provider = provider

    async def run(self, request: OrchestrationRequest) -> OrchestrationResult:
        started = time.monotonic()
        attempts = 0
        try:
            while attempts < request.budget.max_attempts:
                attempts += 1
                try:
                    response = await asyncio.wait_for(
                        self.provider.complete(request),
                        timeout=request.budget.timeout_seconds,
                    )
                    _enforce_usage(response, request.budget)
                    return OrchestrationResult(
                        status="succeeded",
                        payload=response.payload,
                        provider=response.provider,
                        model=response.model,
                        input_tokens=response.input_tokens,
                        output_tokens=response.output_tokens,
                        cost_microusd=response.cost_microusd,
                        latency_ms=int((time.monotonic() - started) * 1000),
                        attempts=attempts,
                    )
                except ProviderUnavailable:
                    if attempts >= request.budget.max_attempts:
                        raise
            raise AssertionError("unreachable attempts state")
        except TimeoutError:
            error_code = "AGENT_TIMEOUT"
        except ProviderUnavailable:
            error_code = "PROVIDER_UNAVAILABLE"
        except RuntimeError as exc:
            error_code = (
                "BUDGET_EXCEEDED" if "budget exceeded" in str(exc) else "AGENT_POLICY_ERROR"
            )
        except Exception:
            error_code = "AGENT_CRASH"
        return OrchestrationResult(
            status="failed",
            payload=None,
            provider=self.provider.name,
            model="unavailable",
            input_tokens=0,
            output_tokens=0,
            cost_microusd=0,
            latency_ms=int((time.monotonic() - started) * 1000),
            attempts=attempts,
            error_code=error_code,
        )


class NoOpOrchestrator:
    name = "disabled-v1"

    async def run(self, request: OrchestrationRequest) -> OrchestrationResult:
        del request
        return OrchestrationResult(
            status="disabled",
            payload=None,
            provider="none",
            model="none",
            input_tokens=0,
            output_tokens=0,
            cost_microusd=0,
            latency_ms=0,
            attempts=0,
            error_code="AI_DISABLED",
        )


class TestOrchestrator:
    name = "test-v1"

    def __init__(self, responses: dict[str, ProviderResponse]) -> None:
        self.responses = responses

    async def run(self, request: OrchestrationRequest) -> OrchestrationResult:
        response = self.responses.get(request.idempotency_key)
        if response is None:
            return OrchestrationResult(
                status="failed",
                payload=None,
                provider="test",
                model="fixture",
                input_tokens=0,
                output_tokens=0,
                cost_microusd=0,
                latency_ms=0,
                attempts=1,
                error_code="FIXTURE_NOT_FOUND",
            )
        _enforce_usage(response, request.budget)
        return OrchestrationResult(
            status="succeeded",
            payload=response.payload,
            provider=response.provider,
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cost_microusd=response.cost_microusd,
            latency_ms=0,
            attempts=1,
        )


class SwarmOrchestrator:
    """Bounded consensus wrapper. Child runs cannot create further swarms."""

    name = "swarm-v1"

    def __init__(self, children: tuple[Orchestrator, ...], *, enabled: bool) -> None:
        if not 2 <= len(children) <= 3:
            raise ValueError("swarm requires two or three bounded workers")
        self.children = children
        self.enabled = enabled

    async def run(self, request: OrchestrationRequest) -> OrchestrationResult:
        if not self.enabled:
            return await NoOpOrchestrator().run(request)
        if request.initiator != "root" or not request.can_spawn:
            raise PermissionError("workers cannot create swarms")
        child_request = replace(request, initiator="worker", can_spawn=False)
        results = [await child.run(child_request) for child in self.children]
        succeeded = [item for item in results if item.status == "succeeded" and item.payload]
        if not succeeded:
            return OrchestrationResult(
                status="failed",
                payload=None,
                provider="swarm",
                model="consensus",
                input_tokens=sum(item.input_tokens for item in results),
                output_tokens=sum(item.output_tokens for item in results),
                cost_microusd=sum(item.cost_microusd for item in results),
                latency_ms=sum(item.latency_ms for item in results),
                attempts=sum(item.attempts for item in results),
                error_code="SWARM_NO_VALID_RESULT",
            )
        parsed = []
        for item in succeeded:
            assert item.payload is not None
            try:
                parsed.append((parse_agent_output(item.payload), item))
            except ValueError:
                continue
        if not parsed:
            return OrchestrationResult(
                status="failed",
                payload=None,
                provider="swarm",
                model="consensus",
                input_tokens=sum(item.input_tokens for item in results),
                output_tokens=sum(item.output_tokens for item in results),
                cost_microusd=sum(item.cost_microusd for item in results),
                latency_ms=sum(item.latency_ms for item in results),
                attempts=sum(item.attempts for item in results),
                error_code="SWARM_NO_VALID_RESULT",
            )
        parsed.sort(key=lambda pair: pair[0].confidence, reverse=True)
        selected = parsed[0][1]
        total_cost = sum(item.cost_microusd for item in results)
        if total_cost > request.budget.max_cost_microusd:
            raise RuntimeError("agent cost budget exceeded")
        total_input = sum(item.input_tokens for item in results)
        total_output = sum(item.output_tokens for item in results)
        if total_input > request.budget.max_input_tokens:
            raise RuntimeError("agent input token budget exceeded")
        if total_output > request.budget.max_output_tokens:
            raise RuntimeError("agent output token budget exceeded")
        return replace(
            selected,
            provider="swarm",
            model="consensus",
            input_tokens=total_input,
            output_tokens=total_output,
            cost_microusd=total_cost,
            latency_ms=sum(item.latency_ms for item in results),
            attempts=sum(item.attempts for item in results),
        )


@dataclass(frozen=True)
class OpenClawPolicyAttestation:
    openclaw_version: str
    agent_id: str
    allowed_tools: frozenset[str]
    skills: tuple[str, ...]
    output_schema_enforced: bool
    shell_denied: bool
    filesystem_denied: bool
    browser_denied: bool
    network_denied: bool
    elevated_denied: bool
    spawn_denied: bool

    def validate(self) -> None:
        enforce_tool_allowlist(self.allowed_tools)
        if self.skills:
            raise PermissionError("assistive OpenClaw agent must not load skills")
        controls = (
            self.output_schema_enforced,
            self.shell_denied,
            self.filesystem_denied,
            self.browser_denied,
            self.network_denied,
            self.elevated_denied,
            self.spawn_denied,
        )
        if not all(controls):
            raise PermissionError("OpenClaw policy attestation is incomplete")


class OpenClawGatewayClient(Protocol):
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
    ) -> ProviderResponse: ...


class OpenClawGatewayProvider:
    name = "openclaw"

    def __init__(
        self,
        client: OpenClawGatewayClient,
        attestation: OpenClawPolicyAttestation,
        *,
        feature_enabled: bool,
    ) -> None:
        if not feature_enabled:
            raise PermissionError("OpenClaw feature flag is disabled")
        attestation.validate()
        self.client = client
        self.attestation = attestation

    async def complete(self, request: OrchestrationRequest) -> ProviderResponse:
        if request.can_spawn is False and request.initiator != "worker":
            raise PermissionError("invalid worker orchestration state")
        if not request.tool_allowlist <= self.attestation.allowed_tools:
            raise PermissionError("request exceeds attested OpenClaw tools")
        session_key = f"idml:{request.organization_id}:{request.review_item_id}"
        return await self.client.run_agent(
            agent_id=self.attestation.agent_id,
            session_key=session_key,
            system_prompt=request.system_prompt,
            input_envelope=request.input_envelope,
            output_schema=request.output_schema,
            tool_allowlist=request.tool_allowlist,
            timeout_seconds=request.budget.timeout_seconds,
        )


DEFAULT_ASSISTIVE_TOOLS = frozenset(ALLOWED_TOOLS)
