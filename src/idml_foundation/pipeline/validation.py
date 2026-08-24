from __future__ import annotations

import hashlib
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any, cast

from lxml import etree
from pydantic import Field

from idml_foundation.domain.common import SHA256_PATTERN, StrictModel
from idml_foundation.pipeline.jats_builder import JATS_DTD_NAME, XLINK_NS


class ValidationSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class ValidationStage(StrEnum):
    XML = "xml"
    JATS_DTD = "jats-dtd"
    SPS_BASELINE = "sps-baseline"


class ValidationIssue(StrictModel):
    stage: ValidationStage
    severity: ValidationSeverity
    code: str
    message: str
    line: int | None = Field(default=None, ge=1)
    element_id: str | None = None


class ValidationReport(StrictModel):
    report_version: str = "1.0.0"
    validator_profile: str = "jats-1.3-mathml3+sps-baseline-1.0.0"
    xml_sha256: str = Field(pattern=SHA256_PATTERN)
    valid: bool
    issues: tuple[ValidationIssue, ...]


class OfflineJatsValidator:
    def __init__(self, vendor_directory: Path) -> None:
        vendor_root = vendor_directory.resolve(strict=True)
        dtd_path = (vendor_root / JATS_DTD_NAME).resolve(strict=True)
        if not dtd_path.is_relative_to(vendor_root):
            raise ValueError("JATS DTD must remain inside the allowlisted vendor directory")
        self._dtd = etree.DTD(str(dtd_path))

    def validate(self, xml: bytes, *, asset_names: set[str] | None = None) -> ValidationReport:
        digest = hashlib.sha256(xml).hexdigest()
        issues: list[ValidationIssue] = []
        parser = etree.XMLParser(
            resolve_entities=False,
            load_dtd=False,
            no_network=True,
            recover=False,
            huge_tree=False,
        )
        try:
            root = etree.fromstring(xml, parser=parser)
        except etree.XMLSyntaxError as exc:
            issues.append(
                ValidationIssue(
                    stage=ValidationStage.XML,
                    severity=ValidationSeverity.ERROR,
                    code="xml-not-well-formed",
                    message=str(exc),
                    line=max(exc.lineno or 1, 1),
                )
            )
            return ValidationReport(xml_sha256=digest, valid=False, issues=tuple(issues))

        if not self._dtd.validate(root):
            error_log = cast(Any, self._dtd.error_log)
            for error in error_log:
                issues.append(
                    ValidationIssue(
                        stage=ValidationStage.JATS_DTD,
                        severity=ValidationSeverity.ERROR,
                        code=f"dtd-{error.type_name.casefold().replace('_', '-')}",
                        message=error.message,
                        line=max(error.line, 1),
                    )
                )
        issues.extend(self._sps_baseline(root, asset_names or set()))
        issues.sort(key=lambda item: (item.severity, item.stage, item.code, item.line or 0))
        return ValidationReport(
            xml_sha256=digest,
            valid=not any(item.severity == ValidationSeverity.ERROR for item in issues),
            issues=tuple(issues),
        )

    def _sps_baseline(
        self,
        root: etree._Element,
        asset_names: set[str],
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []

        def require(xpath: str, code: str, message: str) -> None:
            if not root.xpath(xpath):
                issues.append(
                    ValidationIssue(
                        stage=ValidationStage.SPS_BASELINE,
                        severity=ValidationSeverity.ERROR,
                        code=code,
                        message=message,
                    )
                )

        if root.tag != "article" or root.get("dtd-version") != "1.3":
            issues.append(
                ValidationIssue(
                    stage=ValidationStage.SPS_BASELINE,
                    severity=ValidationSeverity.ERROR,
                    code="unsupported-jats-version",
                    message="article must declare JATS dtd-version 1.3",
                )
            )
        require(
            "front/article-meta/article-id[@pub-id-type='publisher-id'][normalize-space()]",
            "missing-publisher-id",
            "publisher article ID is required",
        )
        require(
            "front/article-meta/title-group/article-title[normalize-space()]",
            "missing-article-title",
            "primary article title is required",
        )
        ids = [element.get("id", "") for element in root.iter() if element.get("id")]
        if len(ids) != len(set(ids)):
            issues.append(
                ValidationIssue(
                    stage=ValidationStage.SPS_BASELINE,
                    severity=ValidationSeverity.ERROR,
                    code="duplicate-xml-id",
                    message="XML IDs must be unique",
                )
            )
        for xref in (element for element in root.iter() if element.get("rid")):
            rid = xref.get("rid")
            if rid not in ids:
                issues.append(
                    ValidationIssue(
                        stage=ValidationStage.SPS_BASELINE,
                        severity=ValidationSeverity.ERROR,
                        code="orphan-rid",
                        message="cross-reference RID does not resolve",
                        element_id=xref.get("id"),
                    )
                )
        for graphic in (element for element in root.iter() if element.tag == "graphic"):
            href = graphic.get(f"{{{XLINK_NS}}}href", "")
            if PurePosixPath(href.replace("\\", "/")).name != href or "://" in href:
                issues.append(
                    ValidationIssue(
                        stage=ValidationStage.SPS_BASELINE,
                        severity=ValidationSeverity.ERROR,
                        code="unsafe-asset-reference",
                        message="asset references must be package-local basenames",
                    )
                )
            elif asset_names and href not in asset_names:
                issues.append(
                    ValidationIssue(
                        stage=ValidationStage.SPS_BASELINE,
                        severity=ValidationSeverity.ERROR,
                        code="unknown-asset-reference",
                        message="graphic reference is absent from the canonical asset set",
                    )
                )
        return issues
