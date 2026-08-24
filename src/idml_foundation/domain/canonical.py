from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, model_validator

from idml_foundation.domain.common import SHA256_PATTERN, Evidence, StrictModel

CANONICAL_SCHEMA_VERSION = "1.0.0"


class FieldState(StrEnum):
    PRESENT = "present"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"
    NEEDS_REVIEW = "needs_review"


class SourcedText(StrictModel):
    value: str | None = None
    state: FieldState
    evidence_ids: tuple[str, ...] = ()
    alternatives: tuple[str, ...] = ()
    transformation: str | None = Field(default=None, max_length=300)
    confidence: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def state_matches_value(self) -> Self:
        if self.state == FieldState.PRESENT and (self.value is None or not self.value.strip()):
            raise ValueError("present field requires a non-empty value")
        if self.state == FieldState.MISSING and self.value is not None:
            raise ValueError("missing field cannot contain a value")
        if self.state == FieldState.AMBIGUOUS and len(self.alternatives) < 2:
            raise ValueError("ambiguous field requires at least two alternatives")
        return self


class Identifier(StrictModel):
    kind: str = Field(min_length=1, max_length=80)
    value: SourcedText


class LocalizedText(StrictModel):
    language: str = Field(pattern=r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$")
    text: SourcedText


class JournalIdentity(StrictModel):
    title: SourcedText
    abbreviated_title: SourcedText | None = None
    identifiers: tuple[Identifier, ...] = ()


class Affiliation(StrictModel):
    id: str
    institution: SourcedText
    department: SourcedText | None = None
    city: SourcedText | None = None
    state_or_province: SourcedText | None = None
    country: SourcedText | None = None
    ror: SourcedText | None = None
    evidence_ids: tuple[str, ...] = ()


class ContributorName(StrictModel):
    given_names: SourcedText
    surname: SourcedText
    prefix: SourcedText | None = None
    suffix: SourcedText | None = None


class Contributor(StrictModel):
    id: str
    contributor_type: Literal["person", "group"]
    name: ContributorName | None = None
    group_name: SourcedText | None = None
    orcid: SourcedText | None = None
    affiliation_ids: tuple[str, ...] = ()
    roles: tuple[str, ...] = ()
    corresponding: bool = False
    email: SourcedText | None = None
    evidence_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def contributor_has_matching_name(self) -> Self:
        if self.contributor_type == "person" and self.name is None:
            raise ValueError("person contributor requires a structured name")
        if self.contributor_type == "group" and self.group_name is None:
            raise ValueError("group contributor requires group_name")
        return self


class FundingStatement(StrictModel):
    agency: SourcedText
    award_id: SourcedText | None = None
    statement: SourcedText | None = None


class FrontMatter(StrictModel):
    journal: JournalIdentity
    article_identifiers: tuple[Identifier, ...]
    article_category: SourcedText
    titles: tuple[LocalizedText, ...]
    contributors: tuple[Contributor, ...]
    affiliations: tuple[Affiliation, ...]
    publication_date: SourcedText
    volume: SourcedText | None = None
    issue: SourcedText | None = None
    abstracts: tuple[LocalizedText, ...] = ()
    keywords: tuple[LocalizedText, ...] = ()
    license_text: SourcedText | None = None
    funding: tuple[FundingStatement, ...] = ()


class CrossReference(StrictModel):
    target_id: str
    reference_type: Literal["figure", "table", "formula", "note", "section", "reference"]
    label: str | None = None
    evidence_ids: tuple[str, ...] = ()


class InlineKind(StrEnum):
    TEXT = "text"
    EMPHASIS = "emphasis"
    STRONG = "strong"
    SUBSCRIPT = "subscript"
    SUPERSCRIPT = "superscript"
    EXTERNAL_LINK = "external_link"
    CROSS_REFERENCE = "cross_reference"
    INLINE_FORMULA = "inline_formula"
    NAMED_CONTENT = "named_content"


class InlineNode(StrictModel):
    id: str
    kind: InlineKind
    text: str
    target_id: str | None = None
    href: str | None = None
    name: str | None = None
    attributes: dict[str, str] = Field(default_factory=dict)
    evidence_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def required_target_is_present(self) -> Self:
        if self.kind == InlineKind.CROSS_REFERENCE and self.target_id is None:
            raise ValueError("cross-reference inline requires target_id")
        if self.kind == InlineKind.EXTERNAL_LINK and self.href is None:
            raise ValueError("external link inline requires href")
        if self.kind == InlineKind.NAMED_CONTENT and self.name is None:
            raise ValueError("named content inline requires name")
        return self


class RichText(StrictModel):
    plain: SourcedText
    inlines: tuple[InlineNode, ...] = ()

    @model_validator(mode="after")
    def inline_text_preserves_plain_value(self) -> Self:
        if self.inlines and self.plain.value is not None:
            reconstructed = "".join(item.text for item in self.inlines)
            if reconstructed != self.plain.value:
                raise ValueError("inline text must preserve the plain value exactly")
        return self


class Paragraph(StrictModel):
    kind: Literal["paragraph"] = "paragraph"
    id: str
    content: RichText
    cross_references: tuple[CrossReference, ...] = ()
    evidence_ids: tuple[str, ...] = ()


class ListItem(StrictModel):
    id: str
    content: RichText
    evidence_ids: tuple[str, ...] = ()


class ListBlock(StrictModel):
    kind: Literal["list"] = "list"
    id: str
    ordered: bool
    items: tuple[ListItem, ...]
    evidence_ids: tuple[str, ...] = ()


class QuoteBlock(StrictModel):
    kind: Literal["quote"] = "quote"
    id: str
    content: RichText
    attribution: SourcedText | None = None
    evidence_ids: tuple[str, ...] = ()


class FigureBlock(StrictModel):
    kind: Literal["figure"] = "figure"
    id: str
    label: SourcedText
    caption: RichText
    asset_id: str | None = None
    evidence_ids: tuple[str, ...] = ()


class TableBlock(StrictModel):
    kind: Literal["table"] = "table"
    id: str
    label: SourcedText
    caption: RichText
    rows: tuple[tuple[RichText, ...], ...]
    footnotes: tuple[RichText, ...] = ()
    evidence_ids: tuple[str, ...] = ()


class FormulaBlock(StrictModel):
    kind: Literal["formula"] = "formula"
    id: str
    display: bool
    source: SourcedText
    representation: Literal["text", "latex", "mathml", "image", "unknown"]
    asset_id: str | None = None
    evidence_ids: tuple[str, ...] = ()


class NoteBlock(StrictModel):
    kind: Literal["note"] = "note"
    id: str
    note_type: str
    content: RichText
    evidence_ids: tuple[str, ...] = ()


ContentBlock = Annotated[
    Paragraph | ListBlock | QuoteBlock | FigureBlock | TableBlock | FormulaBlock | NoteBlock,
    Field(discriminator="kind"),
]


class Section(StrictModel):
    id: str
    title: SourcedText
    level: int = Field(ge=1, le=10)
    blocks: tuple[ContentBlock, ...] = ()
    children: tuple["Section", ...] = ()
    evidence_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def children_are_deeper(self) -> Self:
        if any(child.level <= self.level for child in self.children):
            raise ValueError("child section level must be deeper than its parent")
        return self


class Asset(StrictModel):
    id: str
    logical_name: str
    media_type: str
    sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    state: FieldState
    evidence_ids: tuple[str, ...] = ()


class Reference(StrictModel):
    id: str
    mixed_citation: RichText
    identifiers: tuple[Identifier, ...] = ()
    authors: tuple[SourcedText, ...] = ()
    year: SourcedText | None = None
    title: SourcedText | None = None
    source: SourcedText | None = None
    evidence_ids: tuple[str, ...] = ()


class BackMatter(StrictModel):
    acknowledgements: tuple[Paragraph, ...] = ()
    contribution_statement: SourcedText | None = None
    data_availability: SourcedText | None = None
    conflicts: SourcedText | None = None
    notes: tuple[NoteBlock, ...] = ()
    references: tuple[Reference, ...] = ()


def _walk_models(value: object) -> list[BaseModel]:
    found: list[BaseModel] = []
    if isinstance(value, BaseModel):
        found.append(value)
        for field_name in type(value).model_fields:
            found.extend(_walk_models(getattr(value, field_name)))
    elif isinstance(value, (tuple, list)):
        for item in value:
            found.extend(_walk_models(item))
    elif isinstance(value, dict):
        for item in value.values():
            found.extend(_walk_models(item))
    return found


class CanonicalArticle(StrictModel):
    schema_version: str = CANONICAL_SCHEMA_VERSION
    article_id: str
    journal_profile_id: str
    source_raw_sha256: str = Field(pattern=SHA256_PATTERN)
    front: FrontMatter
    body: tuple[Section, ...]
    back: BackMatter
    assets: tuple[Asset, ...] = ()
    evidence: tuple[Evidence, ...]
    review_reasons: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_graph(self) -> Self:
        if self.schema_version != CANONICAL_SCHEMA_VERSION:
            raise ValueError("unsupported Canonical Article schema version")
        models = _walk_models(self)
        identified = [item.id for item in models if hasattr(item, "id")]
        if len(set(identified)) != len(identified):
            raise ValueError("canonical IDs must be globally unique")

        evidence_ids = {item.id for item in self.evidence}
        for item in models:
            refs = getattr(item, "evidence_ids", ())
            if not set(refs) <= evidence_ids:
                raise ValueError("component references unknown evidence")

        affiliation_ids = {item.id for item in self.front.affiliations}
        for contributor in self.front.contributors:
            if not set(contributor.affiliation_ids) <= affiliation_ids:
                raise ValueError("contributor references an unknown affiliation")

        asset_ids = {item.id for item in self.assets}
        target_ids = set(identified)
        for item in models:
            if isinstance(item, (FigureBlock, FormulaBlock)):
                if item.asset_id and item.asset_id not in asset_ids:
                    raise ValueError("content references an unknown asset")
            if isinstance(item, CrossReference) and item.target_id not in target_ids:
                raise ValueError("cross-reference target is unknown")
            if (
                isinstance(item, InlineNode)
                and item.kind == InlineKind.CROSS_REFERENCE
                and item.target_id not in target_ids
            ):
                raise ValueError("inline cross-reference target is unknown")
        return self
