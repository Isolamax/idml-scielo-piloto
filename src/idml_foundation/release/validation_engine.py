from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import Any

from pydantic import Field

from idml_foundation.domain.common import SHA256_PATTERN, StrictModel
from idml_foundation.pipeline.validation import ValidationReport


class ValidatorStatus(StrEnum):
    COMPLETED = "completed"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


class IssueSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class IssueCategory(StrEnum):
    DETERMINISTIC = "deterministic"
    SEMANTIC = "semantic"
    MISSING_SOURCE = "missing-source"
    SOURCE_CONFLICT = "source-conflict"
    SYSTEM = "system"


class UnifiedIssue(StrictModel):
    validator: str
    severity: IssueSeverity
    category: IssueCategory
    code: str
    message: str
    location: str | None = None


class ValidatorRun(StrictModel):
    name: str
    version: str
    status: ValidatorStatus
    candidate_sha256: str = Field(pattern=SHA256_PATTERN)
    tool_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    issues: tuple[UnifiedIssue, ...] = ()
    failure_code: str | None = None

    @property
    def passed(self) -> bool:
        return self.status == ValidatorStatus.COMPLETED and not any(
            issue.severity == IssueSeverity.ERROR for issue in self.issues
        )


class UnifiedValidationReport(StrictModel):
    report_version: str = "1.0.0"
    candidate_sha256: str = Field(pattern=SHA256_PATTERN)
    required_validators: tuple[str, ...]
    runs: tuple[ValidatorRun, ...]

    @property
    def complete(self) -> bool:
        completed = {run.name for run in self.runs if run.status == ValidatorStatus.COMPLETED}
        return set(self.required_validators) <= completed

    @property
    def valid(self) -> bool:
        required = set(self.required_validators)
        return self.complete and all(run.passed for run in self.runs if run.name in required)


class ValidationEngine:
    """Normalize validator outputs without weakening an unavailable validator."""

    def offline_run(
        self, report: ValidationReport, *, candidate_sha256: str | None = None
    ) -> ValidatorRun:
        issues = tuple(
            UnifiedIssue(
                validator="offline-jats",
                severity=IssueSeverity(issue.severity.value),
                category=IssueCategory.DETERMINISTIC,
                code=issue.code,
                message=issue.message,
                location=str(issue.line) if issue.line else issue.element_id,
            )
            for issue in report.issues
        )
        return ValidatorRun(
            name="offline-jats",
            version=report.validator_profile,
            status=ValidatorStatus.COMPLETED,
            candidate_sha256=candidate_sha256 or report.xml_sha256,
            issues=issues,
        )

    def packtools_run(
        self,
        xml: bytes,
        raw_results: object,
        *,
        version: str = "4.16.11",
        tool_sha256: str,
    ) -> ValidatorRun:
        return self.external_run(
            xml,
            raw_results,
            name="packtools",
            version=version,
            tool_sha256=tool_sha256,
        )

    def external_run(
        self,
        candidate: bytes,
        raw_results: object,
        *,
        name: str,
        version: str,
        tool_sha256: str,
    ) -> ValidatorRun:
        candidate_sha = hashlib.sha256(candidate).hexdigest()
        issues: list[UnifiedIssue] = []
        for position, item in enumerate(self._result_items(raw_results)):
            severity_text = str(
                item.get(
                    "level",
                    item.get("severity", item.get("status", item.get("type", "error"))),
                )
            ).casefold()
            severity = IssueSeverity.WARNING if "warn" in severity_text else IssueSeverity.ERROR
            code = str(item.get("code", item.get("id", f"{name}-{position + 1}")))
            message = str(item.get("message", item.get("msg", item.get("text", code))))
            location_value = item.get("xpath", item.get("path", item.get("line")))
            issues.append(
                UnifiedIssue(
                    validator=name,
                    severity=severity,
                    category=(
                        IssueCategory.SYSTEM
                        if str(item.get("response", "")).casefold() == "exception"
                        else self._category(code, message)
                    ),
                    code=code[:200],
                    message=message[:2000],
                    location=str(location_value)[:500] if location_value is not None else None,
                )
            )
        issues.sort(key=lambda issue: (issue.severity, issue.code, issue.location or ""))
        return ValidatorRun(
            name=name,
            version=version,
            status=ValidatorStatus.COMPLETED,
            candidate_sha256=candidate_sha,
            tool_sha256=tool_sha256,
            issues=tuple(issues),
        )

    def unavailable(self, name: str, version: str, candidate: bytes, code: str) -> ValidatorRun:
        return ValidatorRun(
            name=name,
            version=version,
            status=ValidatorStatus.UNAVAILABLE,
            candidate_sha256=hashlib.sha256(candidate).hexdigest(),
            failure_code=code,
        )

    def aggregate(
        self, candidate: bytes, runs: tuple[ValidatorRun, ...], required: tuple[str, ...]
    ) -> UnifiedValidationReport:
        digest = hashlib.sha256(candidate).hexdigest()
        if any(run.candidate_sha256 != digest for run in runs):
            raise ValueError("validator result does not belong to this candidate")
        if len({run.name for run in runs}) != len(runs):
            raise ValueError("validator names must be unique")
        return UnifiedValidationReport(
            candidate_sha256=digest,
            required_validators=required,
            runs=runs,
        )

    def _result_items(self, value: object) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        if isinstance(value, dict):
            if any(key in value for key in ("message", "msg", "text")):
                found.append({str(key): item for key, item in value.items()})
            else:
                for item in value.values():
                    found.extend(self._result_items(item))
        elif isinstance(value, (list, tuple)):
            for item in value:
                found.extend(self._result_items(item))
        return found

    def _category(self, code: str, message: str) -> IssueCategory:
        text = f"{code} {message}".casefold()
        if any(token in text for token in ("missing", "required", "not found", "absent")):
            return IssueCategory.MISSING_SOURCE
        if any(token in text for token in ("conflict", "inconsistent", "mismatch")):
            return IssueCategory.SOURCE_CONFLICT
        if any(token in text for token in ("xpath", "schema", "dtd", "attribute", "element")):
            return IssueCategory.DETERMINISTIC
        return IssueCategory.SEMANTIC
