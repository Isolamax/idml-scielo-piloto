from __future__ import annotations

import hashlib
import re
from enum import StrEnum

from lxml import html
from pydantic import Field

from idml_foundation.domain.common import SHA256_PATTERN, StrictModel

_VERSION = re.compile(r"<!--\s*(\d+\.\d+\.\d+)\s+\d{2}/\d{2}/\d{4}\s*-->")
_TOTALS = {
    "blocking_errors": re.compile(r"Total of blocking errors\s*:\s*(\d+)", re.I),
    "fatal_errors": re.compile(r"Total of fatal errors\s*:\s*(\d+)", re.I),
    "errors": re.compile(r"Total of errors\s*:\s*(\d+)", re.I),
    "warnings": re.compile(r"Total of warnings\s*:\s*(\d+)", re.I),
}


class XpmStatus(StrEnum):
    COMPLETED = "completed"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


class XpmResult(StrictModel):
    contract_version: str = "1.0.0"
    status: XpmStatus
    candidate_package_sha256: str = Field(pattern=SHA256_PATTERN)
    xpm_version: str | None = None
    tool_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    report_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    blocking_errors: int = Field(default=0, ge=0)
    fatal_errors: int = Field(default=0, ge=0)
    errors: int = Field(default=0, ge=0)
    warnings: int = Field(default=0, ge=0)
    failure_code: str | None = None

    @property
    def passed(self) -> bool:
        return self.status == XpmStatus.COMPLETED and not (
            self.blocking_errors or self.fatal_errors or self.errors
        )


class XpmReportParser:
    def parse(
        self,
        report: bytes,
        *,
        candidate_package_sha256: str,
        tool_sha256: str | None,
    ) -> XpmResult:
        decoded = report.decode("utf-8", errors="strict")
        document = html.fromstring(decoded)
        visible_text = " ".join(" ".join(str(value) for value in document.itertext()).split())
        version_match = _VERSION.search(decoded)
        totals: dict[str, int] = {}
        for name, pattern in _TOTALS.items():
            match = pattern.search(visible_text)
            if match is None:
                raise ValueError(f"XPM report is missing {name}")
            totals[name] = int(match.group(1))
        return XpmResult(
            status=XpmStatus.COMPLETED,
            candidate_package_sha256=candidate_package_sha256,
            xpm_version=version_match.group(1) if version_match else None,
            tool_sha256=tool_sha256,
            report_sha256=hashlib.sha256(report).hexdigest(),
            **totals,
        )

    def unavailable(self, candidate_package_sha256: str, code: str) -> XpmResult:
        return XpmResult(
            status=XpmStatus.UNAVAILABLE,
            candidate_package_sha256=candidate_package_sha256,
            failure_code=code,
        )
