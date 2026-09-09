from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast
from urllib.parse import urlparse

from idml_foundation.domain.canonical import (
    Affiliation,
    ArticleHistoryDate,
    Asset,
    BackMatter,
    CanonicalArticle,
    Contributor,
    ContributorName,
    FieldState,
    FigureBlock,
    FormulaBlock,
    FormulaRepresentation,
    FrontMatter,
    FundingStatement,
    Identifier,
    InlineKind,
    InlineNode,
    JournalIdentity,
    ListBlock,
    ListItem,
    LocalizedText,
    NoteBlock,
    Paragraph,
    Reference,
    RichText,
    Section,
    SourcedText,
    TableBlock,
    TableCellSpan,
)
from idml_foundation.domain.common import (
    Evidence,
    EvidenceLocator,
    SourceKind,
    canonical_bytes,
    stable_id,
)
from idml_foundation.domain.raw import (
    AnchoredPlacement,
    RawAnchoredObject,
    RawArticle,
    RawAsset,
    RawObjectKind,
    RawParagraph,
    RawStory,
)
from idml_foundation.pipeline.citation_resolver import resolve_citations
from idml_foundation.pipeline.idml_parser import style_prefix
from idml_foundation.pipeline.profile import JournalProfile

_ARTICLE_NUMBER = re.compile(r"(?:^|_)(20\d{2})(\d{1,4})(?:_|$)")
_AUTHOR_MARKERS = re.compile(r"[\d*]+")
_NUMBERED_GRAPHIC = re.compile(r"^\s*(figure|table)\s*([1-9]\d*)\b", re.IGNORECASE)
_CAPTION_SEPARATOR = re.compile(r"^[\s.\-\u2013\u2014:]*")
_MISSING_INLINE_FORMULA = re.compile(r"(?m)^[ \t]*(?=:[ \t]+\S)")
_EMAIL = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.IGNORECASE)
_HISTORY = re.compile(
    r"^Received\s+on:\s*(\d{2}/\d{2}/\d{4})\s*[\-\u2013\u2014]\s*"
    r"Accepted\s+on:\s*(\d{2}/\d{2}/\d{4})$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _CorrespondenceData:
    email: SourcedText | None = None
    history_dates: tuple[ArticleHistoryDate, ...] = ()
    funding: tuple[FundingStatement, ...] = ()
    conflicts: SourcedText | None = None
    notes: tuple[NoteBlock, ...] = ()
    review_reasons: tuple[str, ...] = ()


def _safe_external_href(value: str) -> str | None:
    if len(value) > 2048 or any(ord(character) < 32 for character in value):
        return None
    parsed = urlparse(value)
    if parsed.scheme.casefold() in {"http", "https"} and parsed.netloc:
        return value
    if parsed.scheme.casefold() == "mailto" and parsed.path:
        return value
    return None


def _present(value: str, evidence_ids: tuple[str, ...], transformation: str) -> SourcedText:
    return SourcedText(
        value=value.strip(),
        state=FieldState.PRESENT,
        evidence_ids=evidence_ids,
        transformation=transformation,
        confidence=1.0,
    )


def _missing(transformation: str) -> SourcedText:
    return SourcedText(state=FieldState.MISSING, transformation=transformation, confidence=1.0)


def _without_prefix(value: RichText, length: int) -> RichText:
    plain = value.plain.value or ""
    if length <= 0 or length > len(plain):
        return value
    remaining = length
    inlines: list[InlineNode] = []
    for inline in value.inlines:
        if remaining >= len(inline.text):
            remaining -= len(inline.text)
            if not inline.text:
                inlines.append(inline)
            continue
        if remaining:
            inline = inline.model_copy(update={"text": inline.text[remaining:]})
            remaining = 0
        if inline.text or inline.kind == InlineKind.INLINE_FORMULA:
            inlines.append(inline)
    return value.model_copy(
        update={
            "plain": value.plain.model_copy(
                update={
                    "value": plain[length:] or None,
                    "transformation": "caption-label-extracted",
                }
            ),
            "inlines": tuple(inlines),
        }
    )


def _insert_missing_inline_formula_nodes(
    inlines: list[InlineNode],
    *,
    plain: str,
    paragraph: RawParagraph,
    article_id: str,
) -> list[InlineNode]:
    """Represent source-visible gaps without inventing formula text or changing plain content."""
    offsets = [match.start() for match in _MISSING_INLINE_FORMULA.finditer(plain)]
    for gap_position, offset in reversed(tuple(enumerate(offsets))):
        cursor = 0
        for index, inline in enumerate(inlines):
            next_cursor = cursor + len(inline.text)
            if cursor <= offset <= next_cursor and inline.kind != InlineKind.INLINE_FORMULA:
                local_offset = offset - cursor
                insertion = index
                if local_offset == len(inline.text):
                    insertion += 1
                elif local_offset > 0:
                    left = inline.model_copy(
                        update={
                            "id": stable_id(article_id, "inline-gap-left", f"{inline.id}:{offset}"),
                            "text": inline.text[:local_offset],
                        }
                    )
                    right = inline.model_copy(
                        update={
                            "id": stable_id(
                                article_id, "inline-gap-right", f"{inline.id}:{offset}"
                            ),
                            "text": inline.text[local_offset:],
                        }
                    )
                    inlines[index : index + 1] = [left, right]
                    insertion = index + 1
                inlines.insert(
                    insertion,
                    InlineNode(
                        id=stable_id(
                            article_id,
                            "inline-formula-gap",
                            f"{paragraph.id}:{gap_position}:{offset}",
                        ),
                        kind=InlineKind.INLINE_FORMULA,
                        text="",
                        formula_source=SourcedText(
                            state=FieldState.NEEDS_REVIEW,
                            evidence_ids=paragraph.evidence_ids,
                            transformation="source-visible-inline-formula-gap",
                            confidence=1.0,
                        ),
                        formula_representation=FormulaRepresentation.UNKNOWN,
                        evidence_ids=paragraph.evidence_ids,
                    ),
                )
                break
            cursor = next_cursor
    return inlines


def _article_id(source_id: str) -> str:
    match = _ARTICLE_NUMBER.search(source_id)
    if not match:
        return source_id.casefold()
    return f"e{match.group(1)}{match.group(2).zfill(4)}"


class CanonicalMapper:
    """Apply one explicit, versioned journal profile without semantic guessing."""

    def __init__(self, profile: JournalProfile) -> None:
        self.profile = profile

    def map(self, raw: RawArticle) -> CanonicalArticle:
        style_names = {style.id: style.source_name for style in raw.styles}
        style_properties = {style.id: style.properties for style in raw.styles}
        character_names = {style.id: style.normalized_name for style in raw.styles}
        story_by_id = {story.id: story for story in raw.stories}
        paragraphs_by_role: defaultdict[str, list[tuple[RawStory, RawParagraph]]] = defaultdict(
            list
        )
        unknown: set[str] = set()
        for story_id in raw.reading_order:
            story = story_by_id[story_id]
            runs = {run.id: run for run in story.runs}
            for paragraph in story.paragraphs:
                if paragraph.table_cell_id:
                    continue
                source_name = style_names.get(paragraph.paragraph_style_id or "", "")
                role = self.profile.role_for_prefix(style_prefix(source_name))
                text = "".join(runs[run_id].text for run_id in paragraph.text_run_ids)
                if role:
                    paragraphs_by_role[role].append((story, paragraph))
                elif text.strip():
                    unknown.add(source_name or "<no-style>")

        profile_evidence = Evidence(
            id=stable_id(raw.article_id, "evidence", self.profile.profile_id),
            source_kind=SourceKind.SYSTEM,
            locator=EvidenceLocator(
                artifact_sha256=raw.source_artifact_sha256,
                logical_path="profiles/esa-aop-1.0.json",
                element_id=self.profile.profile_id,
            ),
            content_sha256=hashlib.sha256(canonical_bytes(self.profile)).hexdigest(),
            description="Versioned deterministic journal profile",
        )
        evidence = (*raw.evidence, profile_evidence)
        article_id = _article_id(raw.article_id)

        def text_for(story: RawStory, paragraph: RawParagraph) -> str:
            runs = {run.id: run for run in story.runs}
            return "".join(runs[item].text for item in paragraph.text_run_ids).strip()

        def first_text(role: str) -> tuple[str, tuple[str, ...]] | None:
            for story, paragraph in paragraphs_by_role[role]:
                value = text_for(story, paragraph)
                if value:
                    return value, paragraph.evidence_ids
            return None

        titles: list[LocalizedText] = []
        for role, language in (
            ("title-primary", self.profile.primary_language),
            ("title-secondary", self.profile.secondary_language),
        ):
            candidate = first_text(role)
            if candidate:
                titles.append(
                    LocalizedText(
                        language=language,
                        text=_present(candidate[0], candidate[1], f"style-role:{role}"),
                    )
                )

        article_identifiers = [
            Identifier(
                kind="publisher-id",
                value=_present(article_id, (profile_evidence.id,), "filename-rule"),
            )
        ]
        article_doi = first_text("article-doi")
        if article_doi:
            doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", article_doi[0], flags=re.I)
            article_identifiers.append(
                Identifier(
                    kind="doi",
                    value=_present(doi, article_doi[1], "style-role:article-doi"),
                )
            )

        affiliations = self._affiliations(paragraphs_by_role, text_for, article_id)
        contributors = self._contributors(
            paragraphs_by_role,
            text_for,
            article_id,
            tuple(item.id for item in affiliations),
        )
        correspondence = self._correspondence(paragraphs_by_role, text_for, article_id)
        if correspondence.email is not None:
            corresponding_positions = [
                position
                for position, contributor in enumerate(contributors)
                if contributor.corresponding
            ]
            if len(corresponding_positions) == 1:
                position = corresponding_positions[0]
                contributors = tuple(
                    contributor.model_copy(update={"email": correspondence.email})
                    if index == position
                    else contributor
                    for index, contributor in enumerate(contributors)
                )
        abstracts: list[LocalizedText] = []
        keywords: list[LocalizedText] = []
        for position, (story, paragraph) in enumerate(paragraphs_by_role["abstract"]):
            language = (
                self.profile.primary_language if position == 0 else self.profile.secondary_language
            )
            value = text_for(story, paragraph)
            if value:
                abstracts.append(
                    LocalizedText(
                        language=language,
                        text=_present(value, paragraph.evidence_ids, "style-role:abstract"),
                    )
                )
        for position, (story, paragraph) in enumerate(paragraphs_by_role["keywords"]):
            language = (
                self.profile.primary_language if position == 0 else self.profile.secondary_language
            )
            value = text_for(story, paragraph)
            if ":" in value:
                value = value.split(":", 1)[1].strip()
            if value:
                keywords.append(
                    LocalizedText(
                        language=language,
                        text=_present(value, paragraph.evidence_ids, "style-role:keywords"),
                    )
                )

        references = self._references(paragraphs_by_role, text_for, article_id)
        sections, section_review_reasons = self._sections(
            raw,
            paragraphs_by_role,
            style_names,
            character_names,
            style_properties,
            article_id,
            references,
        )
        notes = (*self._notes(raw, character_names, article_id), *correspondence.notes)
        assets = tuple(
            Asset(
                id=item.id,
                logical_name=item.logical_path,
                media_type=item.media_type,
                sha256=item.sha256,
                state=FieldState.NEEDS_REVIEW if item.external else FieldState.PRESENT,
                evidence_ids=item.evidence_ids,
            )
            for item in raw.assets
        )
        review_reasons = [f"unmapped_style:{name}" for name in sorted(unknown)]
        review_reasons.extend(
            f"reading_order:{issue.code}:{issue.story_id or 'document'}"
            for issue in raw.reading_order_issues
        )
        if any(item.external for item in raw.assets):
            review_reasons.append("external_assets_require_package_resolution")
        review_reasons.extend(section_review_reasons)
        review_reasons.extend(correspondence.review_reasons)
        if correspondence.email is not None:
            corresponding_count = sum(item.corresponding for item in contributors)
            if corresponding_count != 1:
                review_reasons.append(
                    "correspondence_email_requires_single_marked_contributor"
                )

        return CanonicalArticle(
            article_id=article_id,
            journal_profile_id=self.profile.profile_id,
            source_raw_sha256=hashlib.sha256(canonical_bytes(raw)).hexdigest(),
            front=FrontMatter(
                journal=JournalIdentity(
                    title=_present(
                        self.profile.journal_title,
                        (profile_evidence.id,),
                        "journal-profile",
                    ),
                    abbreviated_title=_present(
                        self.profile.journal_abbreviated_title,
                        (profile_evidence.id,),
                        "journal-profile",
                    ),
                    identifiers=(
                        Identifier(
                            kind="electronic-issn",
                            value=_present(
                                self.profile.journal_issn,
                                (profile_evidence.id,),
                                "journal-profile",
                            ),
                        ),
                    ),
                ),
                article_identifiers=tuple(article_identifiers),
                article_category=_present(
                    self.profile.article_category,
                    (profile_evidence.id,),
                    "journal-profile",
                ),
                titles=tuple(titles),
                contributors=contributors,
                affiliations=affiliations,
                publication_date=_missing("not-present-in-idml-style-profile"),
                history_dates=correspondence.history_dates,
                abstracts=tuple(abstracts),
                keywords=tuple(keywords),
                funding=correspondence.funding,
            ),
            body=sections,
            back=BackMatter(
                conflicts=correspondence.conflicts,
                notes=notes,
                references=references,
            ),
            assets=assets,
            evidence=evidence,
            review_reasons=tuple(dict.fromkeys(review_reasons)),
        )

    def _correspondence(
        self,
        by_role: defaultdict[str, list[tuple[RawStory, RawParagraph]]],
        text_for: Callable[[RawStory, RawParagraph], str],
        article_id: str,
    ) -> _CorrespondenceData:
        email: SourcedText | None = None
        conflicts: SourcedText | None = None
        history_dates: list[ArticleHistoryDate] = []
        funding: list[FundingStatement] = []
        notes: list[NoteBlock] = []
        review_reasons: list[str] = []
        seen_history: set[str] = set()

        for story, paragraph in by_role["correspondence"]:
            evidence_ids = paragraph.evidence_ids
            lines = tuple(line.strip() for line in text_for(story, paragraph).splitlines())
            for line_position, line in enumerate(lines):
                if not line:
                    continue
                lowered = line.casefold()
                if lowered.startswith("*corresponding author:"):
                    match = _EMAIL.search(line)
                    if match is None:
                        review_reasons.append("correspondence_email_not_parseable")
                    elif email is None:
                        email = _present(
                            match.group(0), evidence_ids, "correspondence-labeled-email"
                        )
                    else:
                        review_reasons.append("multiple_correspondence_emails")
                    continue
                if lowered.startswith("conflicts of interest:"):
                    value = line.split(":", 1)[1].strip()
                    if value and conflicts is None:
                        conflicts = _present(
                            value, evidence_ids, "correspondence-labeled-conflicts"
                        )
                    elif value:
                        review_reasons.append("multiple_conflicts_statements")
                    else:
                        review_reasons.append("empty_conflicts_statement")
                    continue
                if lowered.startswith("funding:"):
                    value = line.split(":", 1)[1].strip()
                    if not value:
                        review_reasons.append("empty_funding_statement")
                        continue
                    agency = value.split(",", 1)[0].strip()
                    funding.append(
                        FundingStatement(
                            agency=_present(
                                agency, evidence_ids, "funding-agency-before-first-comma"
                            ),
                            statement=_present(
                                value, evidence_ids, "correspondence-labeled-funding"
                            ),
                        )
                    )
                    continue
                history_match = _HISTORY.fullmatch(line)
                if history_match is not None:
                    for date_type, raw_date in zip(
                        ("received", "accepted"), history_match.groups(), strict=True
                    ):
                        if date_type in seen_history:
                            review_reasons.append(f"duplicate_history_date:{date_type}")
                            continue
                        try:
                            iso_date = datetime.strptime(raw_date, "%d/%m/%Y").date().isoformat()
                        except ValueError:
                            review_reasons.append(f"invalid_history_date:{date_type}")
                            continue
                        history_dates.append(
                            ArticleHistoryDate(
                                date_type=cast(
                                    Literal["received", "rev-request", "rev-recd", "accepted"],
                                    date_type,
                                ),
                                date=_present(
                                    iso_date,
                                    evidence_ids,
                                    "correspondence-dd-mm-yyyy-to-iso-8601",
                                ),
                            )
                        )
                        seen_history.add(date_type)
                    continue
                editor_type = next(
                    (
                        label
                        for label in ("Associate editor", "Scientific editor")
                        if lowered.startswith(f"{label.casefold()}:")
                    ),
                    None,
                )
                if editor_type is not None:
                    value = line.split(":", 1)[1].strip()
                    if not value:
                        review_reasons.append(
                            f"empty_{editor_type.casefold().replace(' ', '_')}"
                        )
                        continue
                    content = f"{editor_type}: {value}"
                    notes.append(
                        NoteBlock(
                            id=stable_id(
                                article_id,
                                "correspondence-note",
                                f"{paragraph.id}:{line_position}:{editor_type.casefold()}",
                            ),
                            note_type=editor_type.casefold().replace(" ", "-"),
                            content=RichText(
                                plain=_present(
                                    content,
                                    evidence_ids,
                                    "correspondence-labeled-editor",
                                )
                            ),
                            evidence_ids=evidence_ids,
                        )
                    )
                    review_reasons.append(
                        f"{editor_type.casefold().replace(' ', '_')}_orcid_requires_enrichment"
                    )
                    continue
                review_reasons.append("unmapped_correspondence_line")

        return _CorrespondenceData(
            email=email,
            history_dates=tuple(history_dates),
            funding=tuple(funding),
            conflicts=conflicts,
            notes=tuple(notes),
            review_reasons=tuple(dict.fromkeys(review_reasons)),
        )

    def _notes(
        self,
        raw: RawArticle,
        character_names: dict[str, str],
        article_id: str,
    ) -> tuple[NoteBlock, ...]:
        story_by_note_id = {note_id: story for story in raw.stories for note_id in story.note_ids}
        hyperlinks_by_run = {
            link.source_id: target
            for link in raw.links
            if link.relationship == "external-hyperlink"
            and (target := _safe_external_href(link.target)) is not None
        }
        notes: list[NoteBlock] = []
        for position, note in enumerate(raw.notes):
            story = story_by_note_id.get(note.id)
            if story is None:
                continue
            paragraph = RawParagraph(
                id=stable_id(article_id, "note-paragraph", note.id),
                position=position,
                text_run_ids=note.text_run_ids,
                evidence_ids=note.evidence_ids,
            )
            notes.append(
                NoteBlock(
                    id=stable_id(article_id, "note", note.id),
                    note_type="footnote",
                    content=self._rich_text(
                        story,
                        paragraph,
                        character_names,
                        article_id,
                        run_ids=note.text_run_ids,
                        hyperlinks_by_run=hyperlinks_by_run,
                    ),
                    evidence_ids=note.evidence_ids,
                )
            )
        return tuple(notes)

    def _contributors(
        self,
        by_role: defaultdict[str, list[tuple[RawStory, RawParagraph]]],
        text_for: object,
        article_id: str,
        affiliation_ids: tuple[str, ...],
    ) -> tuple[Contributor, ...]:
        contributors: list[Contributor] = []
        for story, paragraph in by_role["contributors"]:
            value = text_for(story, paragraph)  # type: ignore[operator]
            for position, source_name in enumerate(re.split(r"\s*,\s*", value)):
                markers = [int(item) for item in re.findall(r"\d+", source_name)]
                clean_name = " ".join(_AUTHOR_MARKERS.sub("", source_name).split())
                parts = clean_name.split()
                if len(parts) < 2:
                    continue
                selected_affiliations = tuple(
                    affiliation_ids[index - 1]
                    for index in markers
                    if 0 < index <= len(affiliation_ids)
                )
                contributor_id = stable_id(article_id, "contributor", str(position))
                contributors.append(
                    Contributor(
                        id=contributor_id,
                        contributor_type="person",
                        name=ContributorName(
                            given_names=_present(
                                " ".join(parts[:-1]),
                                paragraph.evidence_ids,
                                "deterministic-last-token-name-split",
                            ),
                            surname=_present(
                                parts[-1],
                                paragraph.evidence_ids,
                                "deterministic-last-token-name-split",
                            ),
                        ),
                        affiliation_ids=selected_affiliations,
                        corresponding="*" in source_name,
                        evidence_ids=paragraph.evidence_ids,
                    )
                )
        return tuple(contributors)

    def _affiliations(
        self,
        by_role: defaultdict[str, list[tuple[RawStory, RawParagraph]]],
        text_for: object,
        article_id: str,
    ) -> tuple[Affiliation, ...]:
        affiliations: list[Affiliation] = []
        for story, paragraph in by_role["affiliations"]:
            value = text_for(story, paragraph)  # type: ignore[operator]
            for line in value.splitlines():
                clean = line.strip()
                if not clean:
                    continue
                clean = re.sub(r"^\d+", "", clean).strip()
                affiliations.append(
                    Affiliation(
                        id=stable_id(article_id, "affiliation", str(len(affiliations))),
                        institution=_present(
                            clean,
                            paragraph.evidence_ids,
                            "line-from-affiliation-style",
                        ),
                        evidence_ids=paragraph.evidence_ids,
                    )
                )
        return tuple(affiliations)

    def _rich_text(
        self,
        story: RawStory,
        paragraph: RawParagraph,
        character_names: dict[str, str],
        article_id: str,
        *,
        run_ids: tuple[str, ...] | None = None,
        inline_formulas_by_run: dict[str, list[RawAnchoredObject]] | None = None,
        raw_assets: dict[str, RawAsset] | None = None,
        hyperlinks_by_run: dict[str, str] | None = None,
    ) -> RichText:
        runs = {run.id: run for run in story.runs}
        inlines: list[InlineNode] = []
        plain = ""
        selected_run_ids = run_ids if run_ids is not None else paragraph.text_run_ids
        for run_id in selected_run_ids:
            run = runs[run_id]
            for formula_position, formula in enumerate(
                (inline_formulas_by_run or {}).get(run_id, ())
            ):
                asset_id = formula.asset_ids[0] if formula.asset_ids else None
                asset = (raw_assets or {}).get(asset_id or "")
                source = asset.logical_path if asset is not None else "unresolved-formula-asset"
                inlines.append(
                    InlineNode(
                        id=stable_id(
                            article_id,
                            "inline-formula",
                            f"{paragraph.id}:{run_id}:{formula_position}",
                        ),
                        kind=InlineKind.INLINE_FORMULA,
                        text="",
                        formula_source=_present(
                            source,
                            formula.evidence_ids,
                            "anchored-inline-pdf-formula",
                        ),
                        formula_representation=FormulaRepresentation.IMAGE,
                        formula_asset_id=asset_id,
                        evidence_ids=formula.evidence_ids,
                    )
                )
            plain += run.text
            if not run.text:
                continue
            style_name = character_names.get(run.character_style_id or "", "")
            kind = InlineKind.TEXT
            is_italic = "italic" in style_name or "italico" in style_name
            is_bold = "bold" in style_name or "negrito" in style_name
            if "superscript" in style_name or "sobrescrito" in style_name:
                kind = InlineKind.SUPERSCRIPT
            elif "subscript" in style_name or "subscrito" in style_name:
                kind = InlineKind.SUBSCRIPT
            elif is_bold:
                kind = InlineKind.STRONG
            elif is_italic:
                kind = InlineKind.EMPHASIS
            attributes: dict[str, str] = {}
            if is_bold and is_italic:
                attributes["source-emphasis"] = "bold italic"
            href = (hyperlinks_by_run or {}).get(run_id)
            if href is not None:
                kind = InlineKind.EXTERNAL_LINK
                if is_bold or is_italic:
                    attributes["source-emphasis"] = " ".join(
                        name
                        for name, enabled in (("bold", is_bold), ("italic", is_italic))
                        if enabled
                    )
            inlines.append(
                InlineNode(
                    id=stable_id(article_id, "inline", f"{paragraph.id}:{run_id}"),
                    kind=kind,
                    text=run.text,
                    href=href,
                    attributes=attributes,
                    evidence_ids=run.evidence_ids,
                )
            )
        inlines = _insert_missing_inline_formula_nodes(
            inlines,
            plain=plain,
            paragraph=paragraph,
            article_id=article_id,
        )
        return RichText(
            plain=SourcedText(
                value=plain or None,
                state=FieldState.PRESENT if plain.strip() else FieldState.NEEDS_REVIEW,
                evidence_ids=paragraph.evidence_ids,
                transformation="lossless-run-concatenation",
                confidence=1.0,
            ),
            inlines=tuple(inlines),
        )

    def _sections(
        self,
        raw: RawArticle,
        by_role: defaultdict[str, list[tuple[RawStory, RawParagraph]]],
        style_names: dict[str, str],
        character_names: dict[str, str],
        style_properties: dict[str, dict[str, str | int | float | bool | None]],
        article_id: str,
        references: tuple[Reference, ...],
    ) -> tuple[tuple[Section, ...], tuple[str, ...]]:
        body_items = [
            (*item, role)
            for role in ("section-level-1", "section-level-2", "paragraph")
            for item in by_role[role]
        ]
        body_items.sort(key=lambda item: (raw.reading_order.index(item[0].id), item[1].position))
        sections: list[dict[str, object]] = []
        section_stack: list[dict[str, object]] = []
        citation_review_reasons: list[str] = []
        formula_review_reasons: list[str] = []
        hyperlinks_by_run: dict[str, str] = {}
        for link in raw.links:
            if link.relationship != "external-hyperlink":
                continue
            if safe_target := _safe_external_href(link.target):
                hyperlinks_by_run[link.source_id] = safe_target
            else:
                citation_review_reasons.append(f"unsafe_external_hyperlink:{link.id}")
        raw_assets = {asset.id: asset for asset in raw.assets}
        block_formulas_by_run: defaultdict[str, list[RawAnchoredObject]] = defaultdict(list)
        inline_formulas_by_run: defaultdict[str, list[RawAnchoredObject]] = defaultdict(list)
        for anchored_object in raw.anchored_objects:
            if (
                anchored_object.kind == RawObjectKind.FORMULA
                and anchored_object.anchor_run_id is not None
            ):
                target = (
                    inline_formulas_by_run
                    if anchored_object.placement == AnchoredPlacement.INLINE
                    else block_formulas_by_run
                )
                target[anchored_object.anchor_run_id].append(anchored_object)
        current: dict[str, object] | None = None
        for story, paragraph, role in body_items:
            runs = {run.id: run for run in story.runs}
            text = "".join(runs[item].text for item in paragraph.text_run_ids).strip()
            block_formula_objects = [
                formula
                for run_id in paragraph.text_run_ids
                for formula in block_formulas_by_run.get(run_id, ())
            ]
            inline_formula_objects = [
                formula
                for run_id in paragraph.text_run_ids
                for formula in inline_formulas_by_run.get(run_id, ())
            ]
            if not text and not block_formula_objects and not inline_formula_objects:
                continue
            if role.startswith("section-level"):
                level = 1 if role.endswith("1") else 2
                current = {
                    "id": stable_id(article_id, "section", paragraph.id),
                    "title": _present(text, paragraph.evidence_ids, f"style-role:{role}"),
                    "level": level,
                    "blocks": [],
                    "children": [],
                    "evidence_ids": paragraph.evidence_ids,
                }
                while section_stack:
                    parent_level = section_stack[-1]["level"]
                    assert isinstance(parent_level, int)
                    if parent_level < level:
                        break
                    section_stack.pop()
                if section_stack:
                    children = section_stack[-1]["children"]
                    assert isinstance(children, list)
                    children.append(current)
                else:
                    sections.append(current)
                section_stack.append(current)
            else:
                if current is None:
                    current = {
                        "id": stable_id(article_id, "section", "untitled-body"),
                        "title": _missing("body-content-before-section-heading"),
                        "level": 1,
                        "blocks": [],
                        "children": [],
                        "evidence_ids": (),
                    }
                    sections.append(current)
                    section_stack.append(current)
                blocks = cast(list[object], current["blocks"])
                properties = style_properties.get(paragraph.paragraph_style_id or "", {})
                list_type = str(properties.get("BulletsAndNumberingListType", ""))
                if list_type in {"BulletList", "NumberedList"}:
                    content = self._rich_text(
                        story,
                        paragraph,
                        character_names,
                        article_id,
                        hyperlinks_by_run=hyperlinks_by_run,
                    )
                    item = ListItem(
                        id=stable_id(article_id, "list-item", paragraph.id),
                        content=content,
                        evidence_ids=paragraph.evidence_ids,
                    )
                    ordered = list_type == "NumberedList"
                    if (
                        blocks
                        and isinstance(blocks[-1], ListBlock)
                        and blocks[-1].ordered == ordered
                    ):
                        previous_list = blocks[-1]
                        blocks[-1] = previous_list.model_copy(
                            update={
                                "items": (*previous_list.items, item),
                                "evidence_ids": tuple(
                                    dict.fromkeys(
                                        (*previous_list.evidence_ids, *paragraph.evidence_ids)
                                    )
                                ),
                            }
                        )
                    else:
                        blocks.append(
                            ListBlock(
                                id=stable_id(article_id, "list", paragraph.id),
                                ordered=ordered,
                                items=(item,),
                                evidence_ids=paragraph.evidence_ids,
                            )
                        )
                    continue

                def append_paragraph(
                    run_ids: list[str],
                    segment: int,
                    story: RawStory = story,
                    paragraph: RawParagraph = paragraph,
                    block_formula_objects: list[RawAnchoredObject] = block_formula_objects,
                    blocks: list[object] = blocks,
                    inline_formula_objects: list[RawAnchoredObject] = inline_formula_objects,
                ) -> None:
                    if not run_ids:
                        return
                    rich_text = self._rich_text(
                        story,
                        paragraph,
                        character_names,
                        article_id,
                        run_ids=tuple(run_ids),
                        inline_formulas_by_run=inline_formulas_by_run,
                        raw_assets=raw_assets,
                        hyperlinks_by_run=hyperlinks_by_run,
                    )
                    if rich_text.plain.value is None and not any(
                        inline.kind == InlineKind.INLINE_FORMULA for inline in rich_text.inlines
                    ):
                        return
                    paragraph_locator = (
                        paragraph.id
                        if not block_formula_objects
                        else f"{paragraph.id}:segment:{segment}"
                    )
                    paragraph_id = stable_id(article_id, "paragraph", paragraph_locator)
                    citation_resolution = resolve_citations(
                        rich_text,
                        references,
                        article_id=article_id,
                        paragraph_id=paragraph_id,
                    )
                    blocks.append(
                        Paragraph(
                            id=paragraph_id,
                            content=citation_resolution.content,
                            cross_references=citation_resolution.cross_references,
                            evidence_ids=paragraph.evidence_ids,
                        )
                    )
                    citation_review_reasons.extend(citation_resolution.review_reasons)
                    plain_value = citation_resolution.content.plain.value or ""
                    for match in re.finditer(r"(?m)^[ \t]*:[ \t]+\S", plain_value):
                        formula_review_reasons.append(
                            f"possible_missing_inline_formula:{paragraph.id}:{match.start()}"
                        )
                    for inline_formula in inline_formula_objects:
                        if inline_formula.anchor_run_id not in run_ids:
                            continue
                        formula_review_reasons.append(
                            f"inline_formula_requires_mathml_transcription:{inline_formula.id}"
                        )

                def append_formula(
                    formula: RawAnchoredObject,
                    blocks: list[object] = blocks,
                ) -> None:
                    asset_id = formula.asset_ids[0] if formula.asset_ids else None
                    asset = raw_assets.get(asset_id or "")
                    source = asset.logical_path if asset is not None else "unresolved-formula-asset"
                    blocks.append(
                        FormulaBlock(
                            id=stable_id(article_id, "formula", formula.id),
                            display=True,
                            source=_present(
                                source,
                                formula.evidence_ids,
                                "anchored-pdf-formula",
                            ),
                            representation=FormulaRepresentation.IMAGE,
                            label=(
                                _present(
                                    formula.label,
                                    formula.evidence_ids,
                                    "anchored-formula-label",
                                )
                                if formula.label
                                else None
                            ),
                            asset_id=asset_id,
                            evidence_ids=formula.evidence_ids,
                        )
                    )
                    formula_review_reasons.append(
                        f"formula_requires_mathml_transcription:{formula.id}"
                    )

                segment_run_ids: list[str] = []
                segment = 0
                for run_id in paragraph.text_run_ids:
                    formulas = block_formulas_by_run.get(run_id, ())
                    if formulas:
                        append_paragraph(segment_run_ids, segment)
                        segment += 1
                        segment_run_ids = []
                        for formula in formulas:
                            append_formula(formula)
                    else:
                        segment_run_ids.append(run_id)
                append_paragraph(segment_run_ids, segment)

        raw_tables = {table.id: table for table in raw.tables}
        table_story = {table_id: story.id for story in raw.stories for table_id in story.table_ids}
        story_page = {
            story.id: min(
                (frame.page_index for frame in raw.frames if frame.parent_story_id == story.id),
                default=10**9,
            )
            for story in raw.stories
        }
        captions = by_role["caption"]
        graphic_blocks: list[FigureBlock | TableBlock] = []
        graphic_review_reasons: list[str] = [
            *citation_review_reasons,
            *formula_review_reasons,
        ]
        used_tables: set[str] = set()
        used_assets: set[str] = set()
        run_lookup = {run.id: run for item in raw.stories for run in item.runs}

        def table_rows(table_id: str) -> tuple[tuple[RichText, ...], ...]:
            table = raw_tables[table_id]
            rows: list[tuple[RichText, ...]] = []
            for row_index in range(table.row_count):
                row: list[RichText] = []
                for column_index in range(table.column_count):
                    cell = next(
                        (
                            item
                            for item in table.cells
                            if item.row == row_index and item.column == column_index
                        ),
                        None,
                    )
                    value = (
                        "".join(run_lookup[item].text for item in cell.text_run_ids) if cell else ""
                    )
                    cell_rich = RichText(
                        plain=(
                            _present(value, cell.evidence_ids, "idml-table-cell")
                            if value.strip() and cell
                            else _missing("empty-or-spanned-table-cell")
                        )
                    )
                    if value.strip() and cell:
                        cell_resolution = resolve_citations(
                            cell_rich,
                            references,
                            article_id=article_id,
                            paragraph_id=stable_id(
                                article_id,
                                "table-cell",
                                f"{table_id}:{row_index}:{column_index}",
                            ),
                        )
                        cell_rich = cell_resolution.content
                        graphic_review_reasons.extend(cell_resolution.review_reasons)
                    row.append(cell_rich)
                rows.append(tuple(row))
            return tuple(rows)

        def table_cell_spans(table_id: str) -> tuple[TableCellSpan, ...]:
            return tuple(
                TableCellSpan(
                    row=cell.row,
                    column=cell.column,
                    row_span=cell.row_span,
                    column_span=cell.column_span,
                )
                for cell in raw_tables[table_id].cells
                if cell.row_span > 1 or cell.column_span > 1
            )

        for story, paragraph in captions:
            runs = {run.id: run for run in story.runs}
            caption_value = "".join(runs[item].text for item in paragraph.text_run_ids)
            numbered = _NUMBERED_GRAPHIC.match(caption_value)
            if numbered is None:
                if caption_value.strip():
                    graphic_review_reasons.append(f"unnumbered_graphic_caption:{paragraph.id}")
                continue
            kind, number_text = numbered.group(1).casefold(), numbered.group(2)
            number = int(number_text)
            caption_source = (
                self._rich_text(
                    story,
                    paragraph,
                    character_names,
                    article_id,
                    hyperlinks_by_run=hyperlinks_by_run,
                )
                if caption_value.strip()
                else RichText(plain=_missing("caption-style-contained-no-caption-text"))
            )
            separator = _CAPTION_SEPARATOR.match(caption_value[numbered.end() :])
            prefix_length = numbered.end() + (separator.end() if separator else 0)
            caption_source = _without_prefix(caption_source, prefix_length)
            caption = caption_source
            if caption_value.strip():
                caption_resolution = resolve_citations(
                    caption_source,
                    references,
                    article_id=article_id,
                    paragraph_id=stable_id(article_id, "caption", paragraph.id),
                )
                caption = caption_resolution.content
                graphic_review_reasons.extend(caption_resolution.review_reasons)
            if kind == "table":
                candidate_tables = sorted(
                    (
                        table_id
                        for table_id in raw_tables
                        if table_id not in used_tables
                        and story_page.get(table_story.get(table_id, ""), 10**9)
                        == story_page.get(story.id, 10**9)
                    ),
                    key=lambda table_id: (
                        raw.reading_order.index(table_story[table_id]),
                        raw_tables[table_id].source_self_id,
                    ),
                )
                if not candidate_tables:
                    graphic_review_reasons.append(f"unmatched_table_caption:{number}")
                    continue
                table_id = candidate_tables[0]
                used_tables.add(table_id)
                table = raw_tables[table_id]
                graphic_blocks.append(
                    TableBlock(
                        id=stable_id(article_id, "canonical-table", table.id),
                        label=_present(
                            f"Table {number}",
                            paragraph.evidence_ids,
                            "numbered-caption-label",
                        ),
                        caption=caption,
                        rows=table_rows(table_id),
                        cell_spans=table_cell_spans(table_id),
                        evidence_ids=table.evidence_ids,
                    )
                )
            else:
                asset_pattern = re.compile(
                    rf"(?:^|[^a-z])figure[\s_-]*0*{number}(?:[^0-9]|$)", re.I
                )
                asset = next(
                    (
                        item
                        for item in raw.assets
                        if item.id not in used_assets and asset_pattern.search(item.logical_path)
                    ),
                    None,
                )
                if asset is None:
                    graphic_review_reasons.append(f"unmatched_figure_asset:{number}")
                    asset_id = None
                else:
                    used_assets.add(asset.id)
                    asset_id = asset.id
                graphic_blocks.append(
                    FigureBlock(
                        id=stable_id(article_id, "figure", paragraph.id),
                        label=_present(
                            f"Figure {number}",
                            paragraph.evidence_ids,
                            "numbered-caption-label",
                        ),
                        caption=caption,
                        asset_id=asset_id,
                        evidence_ids=paragraph.evidence_ids,
                    )
                )

        def graphic_number(block: FigureBlock | TableBlock) -> int:
            match = re.search(r"\d+", block.label.value or "")
            return int(match.group()) if match else 10**9

        ordered_figures = iter(
            sorted(
                (block for block in graphic_blocks if isinstance(block, FigureBlock)),
                key=graphic_number,
            )
        )
        ordered_tables = iter(
            sorted(
                (block for block in graphic_blocks if isinstance(block, TableBlock)),
                key=graphic_number,
            )
        )
        graphic_blocks = [
            next(ordered_figures) if isinstance(block, FigureBlock) else next(ordered_tables)
            for block in graphic_blocks
        ]
        if graphic_blocks:
            sections.append(
                {
                    "id": stable_id(article_id, "section", "graphic-elements"),
                    "title": _present(
                        "Elementos gráficos",
                        (),
                        "deterministic-container-label",
                    ),
                    "level": 1,
                    "blocks": graphic_blocks,
                    "children": [],
                    "evidence_ids": (),
                }
            )
        for table_id in sorted(set(raw_tables) - used_tables):
            graphic_review_reasons.append(f"unmatched_source_table:{table_id}")
        return (
            tuple(Section.model_validate(item) for item in sections),
            tuple(graphic_review_reasons),
        )

    def _references(
        self,
        by_role: defaultdict[str, list[tuple[RawStory, RawParagraph]]],
        text_for: object,
        article_id: str,
    ) -> tuple[Reference, ...]:
        references: list[Reference] = []
        for story, paragraph in by_role["references"]:
            value = text_for(story, paragraph)  # type: ignore[operator]
            for line in value.splitlines():
                if not line.strip():
                    continue
                reference_id = stable_id(article_id, "reference", str(len(references)))
                references.append(
                    Reference(
                        id=reference_id,
                        mixed_citation=RichText(
                            plain=_present(
                                line,
                                paragraph.evidence_ids,
                                "line-break-reference-split",
                            )
                        ),
                        evidence_ids=paragraph.evidence_ids,
                    )
                )
        return tuple(references)
