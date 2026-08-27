from __future__ import annotations

from typing import Any

from sqlalchemy import event, select
from sqlalchemy.orm import Mapper, Session

from idml_foundation.ai.contracts import ALLOWED_TOOLS, ToolScope
from idml_foundation.ai.orchestration import AgentBudget, OrchestrationRequest, Orchestrator
from idml_foundation.ai.outputs import AgentDomain, AgentProposalOutput, output_json_schema
from idml_foundation.ai.policy import route_proposal
from idml_foundation.ai.registry import AgentProfile, load_prompt
from idml_foundation.ai.security import payload_digest, redact_text, untrusted_envelope
from idml_foundation.ai.tools import AgentToolService
from idml_foundation.domain.common import canonical_bytes
from idml_foundation.models import AgentProposal, AgentRun


@event.listens_for(AgentRun, "before_update")
@event.listens_for(AgentRun, "before_delete")
@event.listens_for(AgentProposal, "before_update")
@event.listens_for(AgentProposal, "before_delete")
def _prevent_agent_history_mutation(
    mapper: Mapper[Any], connection: object, target: object
) -> None:
    del mapper, connection, target
    raise ValueError("agent history is append-only")


def build_assistance_payload(tools: AgentToolService) -> dict[str, Any]:
    """Build the compact, deduplicated model input from tenant-bound tool results."""
    review = tools.read_review_item().payload
    fragment = tools.read_canonical_fragment(tools.item.field_path).payload
    evidence = tools.read_evidence().payload["evidence"]
    current: dict[str, Any] = {
        "path": fragment["path"],
        "value": fragment["value"],
    }
    if "atomic_rich_text" in fragment:
        current["atomic_rich_text"] = fragment["atomic_rich_text"]
    return {
        "contract_version": "assistive-input-1.1",
        "task": {
            "review_item_id": review["review_item_id"],
            "review_version": review["version"],
            "domain": tools.scope.domain.value,
            "rule_code": review["rule_code"],
            "field_path": review["field_path"],
            "message": redact_text(str(review["message"]), max_characters=1_200),
        },
        "current": current,
        "evidence": evidence,
        "alternatives": [
            redact_text(str(value), max_characters=500)
            for value in review["alternatives"][:10]
        ],
    }


async def run_assistance(
    db: Session,
    *,
    scope: ToolScope,
    profile: AgentProfile,
    orchestrator: Orchestrator,
    idempotency_key: str,
    budget: AgentBudget,
) -> tuple[AgentRun, AgentProposal | None]:
    existing = db.scalar(
        select(AgentRun).where(
            AgentRun.organization_id == scope.organization_id,
            AgentRun.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        proposal = db.scalar(select(AgentProposal).where(AgentProposal.agent_run_id == existing.id))
        return existing, proposal

    tools = AgentToolService(db, scope)
    envelope = untrusted_envelope(build_assistance_payload(tools))
    envelope_bytes = len(canonical_bytes(envelope))
    request = OrchestrationRequest(
        organization_id=scope.organization_id,
        job_id=scope.job_id,
        resource_id=scope.resource_id,
        review_item_id=scope.review_item_id,
        base_snapshot_id=scope.base_snapshot_id,
        task_type="review_patch_proposal",
        domain=scope.domain.value,
        idempotency_key=idempotency_key,
        system_prompt=load_prompt(profile),
        input_envelope=envelope,
        output_schema=output_json_schema(scope.domain),
        tool_allowlist=ALLOWED_TOOLS,
        budget=budget,
    )
    result = await orchestrator.run(request)
    raw_output = result.payload
    output_hash = payload_digest(raw_output) if raw_output is not None else None
    proposal_record: AgentProposal | None = None
    error_code = result.error_code
    status = result.status
    validated: AgentProposalOutput | None = None
    validation: dict[str, Any] | None = None
    if result.status == "succeeded" and raw_output is not None:
        try:
            validated, validation_result = tools.propose_patch(raw_output)
            validation = validation_result.payload
            route_proposal(
                validated,
                confidence_threshold=profile.confidence_threshold,
                max_repair_cycles=profile.max_repair_cycles,
            )
        except (LookupError, PermissionError, RuntimeError, ValueError) as exc:
            status = "rejected"
            error_code = type(exc).__name__.upper()

    run = AgentRun(
        organization_id=scope.organization_id,
        job_id=scope.job_id,
        resource_id=scope.resource_id,
        review_item_id=scope.review_item_id,
        base_snapshot_id=scope.base_snapshot_id,
        idempotency_key=idempotency_key,
        task_type=request.task_type,
        domain=scope.domain.value,
        orchestrator=orchestrator.name,
        status=status,
        provider=result.provider,
        model=result.model,
        prompt_version=profile.prompt_version,
        output_schema_version=profile.output_schema_version,
        config_version=profile.config_version,
        input_sha256=payload_digest(envelope),
        output_sha256=output_hash,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cost_microusd=result.cost_microusd,
        latency_ms=result.latency_ms,
        attempts=result.attempts,
        budget={
            "timeout_seconds": budget.timeout_seconds,
            "max_attempts": budget.max_attempts,
            "max_input_tokens": budget.max_input_tokens,
            "max_output_tokens": budget.max_output_tokens,
            "max_cost_microusd": budget.max_cost_microusd,
            "input_envelope_bytes": envelope_bytes,
        },
        error_code=error_code,
    )
    db.add(run)
    db.flush()
    if validated is not None and validation is not None and status == "succeeded":
        proposal_payload = validated.model_dump(mode="json")
        proposal_record = AgentProposal(
            organization_id=scope.organization_id,
            agent_run_id=run.id,
            review_item_id=scope.review_item_id,
            base_snapshot_id=scope.base_snapshot_id,
            domain=scope.domain.value,
            patch=proposal_payload["patch"],
            confidence=validated.confidence,
            evidence=proposal_payload["evidence"],
            alternatives=proposal_payload["alternatives"],
            reason=validated.reason,
            needs_human=True,
            proposal_sha256=payload_digest(proposal_payload),
            validation=validation,
        )
        db.add(proposal_record)
        db.flush()
    return run, proposal_record


def domain_from_string(value: str) -> AgentDomain:
    return AgentDomain(value)
