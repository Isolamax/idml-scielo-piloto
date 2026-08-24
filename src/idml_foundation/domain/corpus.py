import hashlib
import json
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import cast

from pydantic import Field, field_validator

from idml_foundation.domain.common import SHA256_PATTERN, StrictModel


class AccessClass(StrEnum):
    RESTRICTED = "restricted"
    INTERNAL = "internal"
    PUBLIC = "public"


class CorpusSplit(StrEnum):
    DEVELOPMENT = "development"
    CONTRAST = "contrast"
    HOMOLOGATION_HOLDOUT = "homologation_holdout"


class CorpusArtifact(StrictModel):
    logical_path: str
    role: str = Field(min_length=1, max_length=80)
    media_type: str
    sha256: str = Field(pattern=SHA256_PATTERN)
    size_bytes: int = Field(ge=0)
    access_class: AccessClass

    @field_validator("logical_path")
    @classmethod
    def path_is_relative_and_portable(cls, value: str) -> str:
        path = PurePosixPath(value)
        if "\\" in value or path.is_absolute() or ".." in path.parts or not path.parts:
            raise ValueError("logical_path must be a safe relative POSIX path")
        return value


class RetentionPolicy(StrictModel):
    retain_until: str | None = None
    review_interval_days: int = Field(ge=1)
    deletion_requires_approval: bool = True


class CorpusPolicy(StrictModel):
    purpose: str
    license_status: str
    confidentiality: AccessClass
    contains_personal_data: bool
    redistribution_allowed: bool
    anonymization: str
    retention: RetentionPolicy


class ExpectedStructure(StrictModel):
    pages: int | None = Field(default=None, ge=0)
    stories: int | None = Field(default=None, ge=0)
    text_frames: int | None = Field(default=None, ge=0)
    body_sections: int | None = Field(default=None, ge=0)
    body_paragraphs: int | None = Field(default=None, ge=0)
    contributors: int | None = Field(default=None, ge=0)
    affiliations: int | None = Field(default=None, ge=0)
    figures: int | None = Field(default=None, ge=0)
    tables: int | None = Field(default=None, ge=0)
    inline_formulas: int | None = Field(default=None, ge=0)
    display_formulas: int | None = Field(default=None, ge=0)
    references: int | None = Field(default=None, ge=0)
    notes: int | None = Field(default=None, ge=0)


class CorpusManifest(StrictModel):
    manifest_version: str
    corpus_id: str
    journal: str
    template: str
    split: CorpusSplit
    source_root_hint: str
    policy: CorpusPolicy
    artifacts: tuple[CorpusArtifact, ...]
    expected: ExpectedStructure


class ArtifactVerification(StrictModel):
    logical_path: str
    valid: bool
    reason: str | None = None


class CorpusVerification(StrictModel):
    corpus_id: str
    valid: bool
    artifacts: tuple[ArtifactVerification, ...]


def load_manifest(path: Path) -> CorpusManifest:
    return CorpusManifest.model_validate_json(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest(manifest: CorpusManifest, root: Path) -> CorpusVerification:
    resolved_root = root.resolve(strict=True)
    results: list[ArtifactVerification] = []
    for descriptor in manifest.artifacts:
        candidate = (resolved_root / Path(*PurePosixPath(descriptor.logical_path).parts)).resolve()
        if not candidate.is_relative_to(resolved_root):
            results.append(
                ArtifactVerification(
                    logical_path=descriptor.logical_path,
                    valid=False,
                    reason="outside_root",
                )
            )
            continue
        if candidate.is_symlink() or not candidate.is_file():
            results.append(
                ArtifactVerification(
                    logical_path=descriptor.logical_path,
                    valid=False,
                    reason="missing_or_symlink",
                )
            )
            continue
        if candidate.stat().st_size != descriptor.size_bytes:
            results.append(
                ArtifactVerification(
                    logical_path=descriptor.logical_path,
                    valid=False,
                    reason="size_mismatch",
                )
            )
            continue
        if _sha256(candidate) != descriptor.sha256:
            results.append(
                ArtifactVerification(
                    logical_path=descriptor.logical_path,
                    valid=False,
                    reason="sha256_mismatch",
                )
            )
            continue
        results.append(ArtifactVerification(logical_path=descriptor.logical_path, valid=True))
    return CorpusVerification(
        corpus_id=manifest.corpus_id,
        valid=all(item.valid for item in results),
        artifacts=tuple(results),
    )


def manifest_json_schema() -> dict[str, object]:
    normalized = json.loads(json.dumps(CorpusManifest.model_json_schema(), sort_keys=True))
    return cast(dict[str, object], normalized)
