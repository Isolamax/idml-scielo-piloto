from __future__ import annotations

import json
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AgentDomain(StrEnum):
    METADATA = "metadata"
    CONTRIBUTORS = "contributors_affiliations"
    STRUCTURE = "structure"
    REFERENCES = "references"
    FIGURES_TABLES = "figures_tables"
    MATH_NOTES = "math_notes"


class AgentPatchOperation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    op: Literal["replace"]
    path: str = Field(pattern=r"^/", min_length=2, max_length=500)
    value: Any


class AgentEvidenceReference(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    evidence_id: str = Field(min_length=1, max_length=200)
    source_kind: Literal["idml", "pdf", "validation", "canonical"]
    locator: str = Field(min_length=1, max_length=500)
    excerpt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class AgentProposalOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["agent-proposal-1.0"]
    domain: AgentDomain
    patch: tuple[AgentPatchOperation, ...] = Field(min_length=1, max_length=5)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: tuple[AgentEvidenceReference, ...] = Field(min_length=1, max_length=20)
    alternatives: tuple[str, ...] = Field(min_length=1, max_length=10)
    reason: str = Field(min_length=20, max_length=2000)
    needs_human: bool

    @model_validator(mode="after")
    def low_confidence_requires_human(self) -> Self:
        if self.confidence < 0.85 and not self.needs_human:
            raise ValueError("low-confidence proposals must require human review")
        return self


DOMAIN_PATH_PREFIXES: dict[AgentDomain, tuple[str, ...]] = {
    AgentDomain.METADATA: ("/front",),
    AgentDomain.CONTRIBUTORS: ("/front/contributors", "/front/affiliations"),
    AgentDomain.STRUCTURE: ("/body",),
    AgentDomain.REFERENCES: ("/back/references",),
    AgentDomain.FIGURES_TABLES: ("/body", "/assets"),
    AgentDomain.MATH_NOTES: ("/body", "/back/notes"),
}


def output_json_schema(domain: AgentDomain) -> dict[str, Any]:
    schema = AgentProposalOutput.model_json_schema()
    schema["$id"] = f"https://idml.local/schemas/agents/{domain.value}-proposal-1.0.json"
    schema["title"] = f"{domain.value} assistive proposal"
    schema["properties"]["domain"] = {"const": domain.value, "type": "string"}
    schema["additionalProperties"] = False
    return schema


def parse_agent_output(payload: dict[str, Any]) -> AgentProposalOutput:
    """Validate provider JSON while retaining strict Python-side models."""
    return AgentProposalOutput.model_validate_json(json.dumps(payload, ensure_ascii=False))
