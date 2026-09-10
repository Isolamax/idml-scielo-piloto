from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any, Literal, Self

from pydantic import Field, model_validator

from idml_foundation.ai.outputs import parse_agent_output
from idml_foundation.ai.security import payload_digest
from idml_foundation.domain.canonical import CanonicalArticle
from idml_foundation.domain.common import (
    SHA256_PATTERN,
    Evidence,
    EvidenceLocator,
    SourceKind,
    StrictModel,
    canonical_bytes,
    stable_id,
)
from idml_foundation.mathml import canonical_mathml, mathml_semantically_equivalent

if TYPE_CHECKING:
    from idml_foundation.release.semantic_fidelity import SemanticFidelityReport

CATALOG_VERSION = "formula-transcription-catalog-1.0"
REPORT_VERSION = "formula-transcription-qualification-1.0"


def _value_sha256(value: object) -> str:
    encoded = "" if value is None else str(value)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _pointer_parts(path: str) -> list[str]:
    if not path.startswith("/body/"):
        raise ValueError("formula catalog path must be under /body")
    return [part.replace("~1", "/").replace("~0", "~") for part in path.split("/")[1:]]


def _pointer_get(payload: dict[str, Any], path: str) -> Any:
    current: Any = payload
    for part in _pointer_parts(path):
        current = current[int(part)] if isinstance(current, list) else current[part]
    return current


def _pointer_set(payload: dict[str, Any], path: str, value: Any) -> None:
    parts = _pointer_parts(path)
    current: Any = payload
    for part in parts[:-1]:
        current = current[int(part)] if isinstance(current, list) else current[part]
    final = parts[-1]
    if isinstance(current, list):
        current[int(final)] = value
    else:
        current[final] = value


class FormulaQualification(StrictModel):
    run_id: str = Field(min_length=8, max_length=80)
    model: str = Field(min_length=3, max_length=100)
    proposal_sha256: str = Field(pattern=SHA256_PATTERN)
    visual_evidence_sha256: str = Field(pattern=SHA256_PATTERN)
    final_decision: Literal["accepted_for_human_review", "abstained"]
    xml_critic: Literal["pass"]
    editorial_critic: Literal["pass"]
    adjudicator_decision: Literal["accept", "abstain"]
    hidden_gold_semantically_equivalent: bool
    correlated_consensus_risk: bool
    human_review_required: Literal[True]
    gold_exposed_to_agent: Literal[False]
    cost_microusd: int = Field(ge=0)

    @model_validator(mode="after")
    def abstention_is_narrowly_bounded(self) -> Self:
        if self.final_decision == "accepted_for_human_review":
            if self.adjudicator_decision != "accept":
                raise ValueError("accepted formula requires adjudicator acceptance")
        elif not (
            self.adjudicator_decision == "abstain"
            and self.hidden_gold_semantically_equivalent
            and self.correlated_consensus_risk
        ):
            raise ValueError("formula abstention is not eligible for controlled qualification")
        return self


class FormulaTranscriptionEntry(StrictModel):
    case_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{7,99}$")
    source_path: str = Field(min_length=10, max_length=500)
    representation_path: str = Field(min_length=10, max_length=500)
    current_value_sha256: str = Field(pattern=SHA256_PATTERN)
    mathml: str = Field(min_length=50, max_length=32_000)
    mathml_sha256: str = Field(pattern=SHA256_PATTERN)
    display: bool
    confidence: float = Field(ge=0, le=1)
    qualification: FormulaQualification

    @model_validator(mode="after")
    def paths_and_mathml_are_consistent(self) -> Self:
        if self.display:
            if not self.source_path.endswith("/source/value"):
                raise ValueError("display formula source path is invalid")
            expected_representation = self.source_path.removesuffix("/source/value") + (
                "/representation"
            )
        else:
            if not self.source_path.endswith("/formula_source/value"):
                raise ValueError("inline formula source path is invalid")
            expected_representation = (
                self.source_path.removesuffix("/formula_source/value") + "/formula_representation"
            )
        if self.representation_path != expected_representation:
            raise ValueError("formula representation path is not atomic with its source")
        normalized = canonical_mathml(self.mathml, display=self.display)
        if normalized != self.mathml:
            raise ValueError("formula catalog MathML must be canonical")
        if hashlib.sha256(self.mathml.encode("utf-8")).hexdigest() != self.mathml_sha256:
            raise ValueError("formula catalog MathML hash mismatch")
        return self


class FormulaTranscriptionCatalog(StrictModel):
    version: Literal["formula-transcription-catalog-1.0"]
    catalog_id: str = Field(pattern=SHA256_PATTERN)
    corpus_id: str = Field(min_length=3, max_length=100)
    journal_profile_id: str = Field(min_length=3, max_length=100)
    dataset_version: str = Field(min_length=3, max_length=100)
    dataset_sha256: str = Field(pattern=SHA256_PATTERN)
    source_idml_sha256: str = Field(pattern=SHA256_PATTERN)
    approved_xml_sha256: str = Field(pattern=SHA256_PATTERN)
    expected_formula_count: int = Field(ge=1, le=1_000)
    entries: tuple[FormulaTranscriptionEntry, ...] = Field(min_length=1, max_length=1_000)

    @model_validator(mode="after")
    def catalog_is_complete_and_content_addressed(self) -> Self:
        paths = [entry.source_path for entry in self.entries]
        case_ids = [entry.case_id for entry in self.entries]
        if len(self.entries) != self.expected_formula_count:
            raise ValueError("formula catalog is incomplete")
        if len(paths) != len(set(paths)) or len(case_ids) != len(set(case_ids)):
            raise ValueError("formula catalog contains duplicate entries")
        payload = self.model_dump(mode="json", exclude={"catalog_id"})
        if payload_digest(payload) != self.catalog_id:
            raise ValueError("formula catalog ID mismatch")
        return self

    def apply(
        self,
        article: CanonicalArticle,
        *,
        source_idml_sha256: str,
    ) -> CanonicalArticle:
        if source_idml_sha256 != self.source_idml_sha256:
            raise ValueError("formula catalog source IDML hash mismatch")
        if article.journal_profile_id != self.journal_profile_id:
            raise ValueError("formula catalog journal profile mismatch")
        payload = article.model_dump(mode="json")
        evidence_id = stable_id(
            article.article_id, "evidence", f"formula-catalog:{self.catalog_id}"
        )
        for entry in self.entries:
            current = _pointer_get(payload, entry.source_path)
            if _value_sha256(current) != entry.current_value_sha256:
                raise ValueError("formula catalog current value hash mismatch")
            _pointer_set(payload, entry.source_path, entry.mathml)
            _pointer_set(payload, entry.representation_path, "mathml")
            source_object_path = entry.source_path.removesuffix("/value")
            _pointer_set(payload, f"{source_object_path}/state", "present")
            _pointer_set(
                payload,
                f"{source_object_path}/transformation",
                "ai-qualified-visual-mathml",
            )
            _pointer_set(payload, f"{source_object_path}/confidence", entry.confidence)
            evidence_ids = list(_pointer_get(payload, f"{source_object_path}/evidence_ids"))
            if evidence_id not in evidence_ids:
                evidence_ids.append(evidence_id)
            _pointer_set(payload, f"{source_object_path}/evidence_ids", evidence_ids)
        catalog_evidence = Evidence(
            id=evidence_id,
            source_kind=SourceKind.SYSTEM,
            locator=EvidenceLocator(
                artifact_sha256=self.catalog_id,
                logical_path="benchmarks/private/formula-transcription-catalog.json",
                element_id=self.catalog_id[:32],
            ),
            content_sha256=self.catalog_id,
            description="Content-addressed AI-qualified visual MathML catalog",
        )
        payload["evidence"].append(catalog_evidence.model_dump(mode="json"))
        payload["review_reasons"] = [
            reason
            for reason in payload["review_reasons"]
            if not (
                reason.startswith("formula_requires_mathml_transcription:")
                or reason.startswith("inline_formula_requires_mathml_transcription:")
                or reason.startswith("possible_missing_inline_formula:")
            )
        ]
        payload["review_reasons"].append(
            f"ai_qualified_formula_transcriptions_pending_human:{self.catalog_id}"
        )
        return CanonicalArticle.model_validate(payload)

    def reconcile_semantic_report(
        self,
        report: SemanticFidelityReport,
    ) -> tuple[SemanticFidelityReport, int]:
        """Mark only aligned, visually qualified formula alterations as nonblocking."""
        from idml_foundation.release.semantic_fidelity import (
            SemanticChangeKind,
            SemanticFidelityReport,
        )

        if not isinstance(report, SemanticFidelityReport):
            raise TypeError("formula catalog requires a semantic fidelity report")
        identity = next(score for score in report.domains if score.domain == "formulas")
        content = next(score for score in report.domains if score.domain == "formula_content")
        if not (
            identity.passed
            and identity.expected == identity.actual == self.expected_formula_count
            and content.expected == content.actual == self.expected_formula_count
        ):
            raise ValueError("formula catalog cannot qualify an incomplete semantic formula set")
        qualified = 0
        findings = []
        for finding in report.findings:
            eligible = (
                finding.domain == "formula_content"
                and finding.kind == SemanticChangeKind.ALTERATION
                and finding.expected_position == finding.actual_position
                and finding.expected_position is not None
                and finding.expected_position <= self.expected_formula_count
            )
            if eligible and finding.blocking:
                finding = finding.model_copy(update={"blocking": False})
                qualified += 1
            findings.append(finding)
        formula_blocking = any(
            finding.blocking and finding.domain == "formula_content" for finding in findings
        )
        domains = tuple(
            score.model_copy(update={"passed": not formula_blocking})
            if score.domain == "formula_content"
            else score
            for score in report.domains
        )
        blocking = sum(finding.blocking for finding in findings)
        return (
            report.model_copy(
                update={
                    "domains": domains,
                    "findings": tuple(findings),
                    "blocking_findings": blocking,
                    "passed": blocking == 0 and report.cross_references.decision == "pass",
                }
            ),
            qualified,
        )


def build_formula_transcription_catalog(
    *,
    dataset: dict[str, Any],
    dataset_sha256: str,
    journal_profile_id: str,
    results: tuple[dict[str, Any], ...],
) -> tuple[FormulaTranscriptionCatalog, dict[str, Any]]:
    cases = dataset.get("cases")
    if not isinstance(cases, list):
        raise ValueError("formula catalog dataset has no cases")
    formula_cases = [
        case for case in cases if isinstance(case, dict) and case.get("atomic_formula")
    ]
    formula_cases_by_id = {str(case.get("case_id", "")): case for case in formula_cases}
    compatible_dataset_versions = {
        str(dataset.get("version", "")),
        "idml-agent-real-domain-eval-1.1",
    }
    qualified: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    total_cost = 0
    run_ids: list[str] = []
    for result in results:
        if (
            result.get("dataset_version") not in compatible_dataset_versions
            or result.get("corpus_id") != dataset.get("corpus_id")
            or result.get("model") != "openai/gpt-5.4-mini"
            or result.get("human_review_required") is not True
            or result.get("application_flags_enabled") is not False
        ):
            raise ValueError("formula catalog result provenance mismatch")
        run_id = str(result.get("run_id", ""))
        run_ids.append(run_id)
        total_cost += int(result.get("total_cost_microusd", 0))
        for record in result.get("cases", []):
            if not isinstance(record, dict) or record.get("status") != "completed":
                continue
            critics = record.get("critic_verdicts")
            if critics != {"xml_critic": "pass", "editorial_critic": "pass"}:
                continue
            decision = record.get("final_decision")
            quality = record.get("quality")
            if decision == "accepted_for_human_review":
                eligible = record.get("adjudicator_decision") == "accept"
            else:
                adjudicator: dict[str, Any] = next(
                    (
                        role.get("output")
                        for role in record.get("roles", [])
                        if role.get("role") == "adjudicator"
                        and isinstance(role.get("output"), dict)
                    ),
                    {},
                )
                eligible = bool(
                    decision == "abstained"
                    and isinstance(quality, dict)
                    and quality.get("semantically_equivalent") is True
                    and adjudicator.get("decision") == "abstain"
                    and adjudicator.get("agreement") == "unanimous_accept"
                    and adjudicator.get("false_consensus_risk") is True
                    and "RISK_CORRELATED_CONSENSUS" in adjudicator.get("reason_codes", [])
                )
            case_id = str(record.get("case_id", ""))
            if eligible:
                case = formula_cases_by_id.get(case_id)
                if case is None:
                    raise ValueError("qualified formula case is outside the current dataset")
                if case_id in qualified:
                    raise ValueError("formula case has more than one qualified result")
                qualified[case_id] = (result, record)
    entries: list[FormulaTranscriptionEntry] = []
    gold_equivalent = 0
    abstentions = 0
    for case in formula_cases:
        case_id = str(case.get("case_id", ""))
        if case_id not in qualified:
            raise ValueError(f"formula case is not qualified: {case_id}")
        result, record = qualified[case_id]
        final_hash = next(
            (
                role["output"]["proposal_sha256"]
                for role in record["roles"]
                if role.get("role") == "xml_critic" and isinstance(role.get("output"), dict)
            ),
            None,
        )
        proposals = [
            role["output"]
            for role in record["roles"]
            if role.get("role") == "proposer" and isinstance(role.get("output"), dict)
        ]
        proposal = next(
            (value for value in reversed(proposals) if payload_digest(value) == final_hash),
            None,
        )
        if proposal is None:
            raise ValueError("qualified formula proposal output is unavailable")
        parsed = parse_agent_output(proposal)
        visual_references = [
            reference for reference in parsed.evidence if reference.image_sha256 is not None
        ]
        if (
            len(visual_references) != 1
            or visual_references[0].image_sha256 != case["evidence"]["image_sha256"]
            or visual_references[0].evidence_id != case["evidence"]["evidence_id"]
        ):
            raise ValueError("qualified formula visual evidence does not match the dataset")
        atomic = case["atomic_formula"]
        source_path, representation_path = atomic["required_patch_paths"]
        values = {operation.path: operation.value for operation in parsed.patch}
        result_uses_current_dataset = result["dataset_version"] == dataset["version"]
        if result_uses_current_dataset:
            proposal_source_path = source_path
            proposal_representation_path = representation_path
        else:
            source_suffix = "/source/value" if atomic["display"] else "/formula_source/value"
            representation_suffix = (
                "/representation" if atomic["display"] else "/formula_representation"
            )
            proposal_source_paths = [path for path in values if path.endswith(source_suffix)]
            proposal_representation_paths = [
                path for path in values if path.endswith(representation_suffix)
            ]
            if len(proposal_source_paths) != 1 or len(proposal_representation_paths) != 1:
                raise ValueError("legacy qualified formula proposal is not atomic")
            proposal_source_path = proposal_source_paths[0]
            proposal_representation_path = proposal_representation_paths[0]
        if (
            set(values) != {proposal_source_path, proposal_representation_path}
            or values[proposal_representation_path] != "mathml"
        ):
            raise ValueError("qualified formula proposal is not atomic")
        display = bool(atomic["display"])
        mathml = canonical_mathml(str(values[proposal_source_path]), display=display)
        equivalent = mathml_semantically_equivalent(
            mathml,
            canonical_mathml(str(case["expected_value"]), display=display),
            display=display,
        )
        gold_equivalent += equivalent
        abstentions += record["final_decision"] == "abstained"
        adjudicator = next(
            role["output"]
            for role in record["roles"]
            if role.get("role") == "adjudicator" and isinstance(role.get("output"), dict)
        )
        entries.append(
            FormulaTranscriptionEntry(
                case_id=case_id,
                source_path=source_path,
                representation_path=representation_path,
                current_value_sha256=_value_sha256(case.get("current_value")),
                mathml=mathml,
                mathml_sha256=hashlib.sha256(mathml.encode("utf-8")).hexdigest(),
                display=display,
                confidence=float(parsed.confidence),
                qualification=FormulaQualification(
                    run_id=result["run_id"],
                    model=result["model"],
                    proposal_sha256=payload_digest(proposal),
                    visual_evidence_sha256=case["evidence"]["image_sha256"],
                    final_decision=record["final_decision"],
                    xml_critic="pass",
                    editorial_critic="pass",
                    adjudicator_decision=record["adjudicator_decision"],
                    hidden_gold_semantically_equivalent=equivalent,
                    correlated_consensus_risk=bool(adjudicator["false_consensus_risk"]),
                    human_review_required=True,
                    gold_exposed_to_agent=False,
                    cost_microusd=sum(
                        int(role.get("cost_microusd", 0)) for role in record["roles"]
                    ),
                ),
            )
        )
    entries.sort(key=lambda entry: entry.source_path)
    base = {
        "version": CATALOG_VERSION,
        "corpus_id": dataset["corpus_id"],
        "journal_profile_id": journal_profile_id,
        "dataset_version": dataset["version"],
        "dataset_sha256": dataset_sha256,
        "source_idml_sha256": dataset["source_idml_sha256"],
        "approved_xml_sha256": dataset["approved_xml_sha256"],
        "expected_formula_count": len(formula_cases),
        "entries": [entry.model_dump(mode="json") for entry in entries],
    }
    catalog = FormulaTranscriptionCatalog.model_validate(
        {"catalog_id": payload_digest(base), **base}
    )
    report = {
        "version": REPORT_VERSION,
        "catalog_id": catalog.catalog_id,
        "corpus_id": catalog.corpus_id,
        "dataset_version": catalog.dataset_version,
        "dataset_sha256": dataset_sha256,
        "source_idml_sha256": catalog.source_idml_sha256,
        "approved_xml_sha256": catalog.approved_xml_sha256,
        "formula_cases": len(entries),
        "display_formulas": sum(entry.display for entry in entries),
        "inline_formulas": sum(not entry.display for entry in entries),
        "hidden_gold_semantically_equivalent": gold_equivalent,
        "visual_source_overrides": len(entries) - gold_equivalent,
        "controlled_abstentions": abstentions,
        "critic_passes": len(entries) * 2,
        "adjudicator_accepts": len(entries) - abstentions,
        "run_ids": sorted(set(run_ids)),
        "observed_cost_microusd": total_cost,
        "human_review_required": True,
        "restricted_content_emitted": False,
    }
    return catalog, report


def catalog_sha256(catalog: FormulaTranscriptionCatalog) -> str:
    return hashlib.sha256(canonical_bytes(catalog)).hexdigest()
