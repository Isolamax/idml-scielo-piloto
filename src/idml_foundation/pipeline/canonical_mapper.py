from __future__ import annotations

import hashlib
import re
from collections import defaultdict

from idml_foundation.domain.canonical import (
    Affiliation,
    Asset,
    BackMatter,
    CanonicalArticle,
    Contributor,
    ContributorName,
    FieldState,
    FigureBlock,
    FrontMatter,
    Identifier,
    InlineKind,
    InlineNode,
    JournalIdentity,
    LocalizedText,
    Paragraph,
    Reference,
    RichText,
    Section,
    SourcedText,
    TableBlock,
)
from idml_foundation.domain.common import (
    Evidence,
    EvidenceLocator,
    SourceKind,
    canonical_bytes,
    stable_id,
)
from idml_foundation.domain.raw import RawArticle, RawParagraph, RawStory
from idml_foundation.pipeline.idml_parser import style_prefix
from idml_foundation.pipeline.profile import JournalProfile

_ARTICLE_NUMBER = re.compile(r"(?:^|_)(20\d{2})(\d{1,4})(?:_|$)")
_AUTHOR_MARKERS = re.compile(r"[\d*]+")
_NUMBERED_GRAPHIC = re.compile(r"^\s*(figure|table)\s*([1-9]\d*)\b", re.IGNORECASE)


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

        affiliations = self._affiliations(paragraphs_by_role, text_for, article_id)
        contributors = self._contributors(
            paragraphs_by_role,
            text_for,
            article_id,
            tuple(item.id for item in affiliations),
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

        sections, graphic_review_reasons = self._sections(
            raw,
            paragraphs_by_role,
            style_names,
            character_names,
            article_id,
        )
        references = self._references(paragraphs_by_role, text_for, article_id)
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
        review_reasons.extend(graphic_review_reasons)

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
                article_identifiers=(
                    Identifier(
                        kind="publisher-id",
                        value=_present(article_id, (profile_evidence.id,), "filename-rule"),
                    ),
                ),
                article_category=_present(
                    self.profile.article_category,
                    (profile_evidence.id,),
                    "journal-profile",
                ),
                titles=tuple(titles),
                contributors=contributors,
                affiliations=affiliations,
                publication_date=_missing("not-present-in-idml-style-profile"),
                abstracts=tuple(abstracts),
                keywords=tuple(keywords),
            ),
            body=sections,
            back=BackMatter(references=references),
            assets=assets,
            evidence=evidence,
            review_reasons=tuple(dict.fromkeys(review_reasons)),
        )

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
    ) -> RichText:
        runs = {run.id: run for run in story.runs}
        inlines: list[InlineNode] = []
        plain = ""
        for position, run_id in enumerate(paragraph.text_run_ids):
            run = runs[run_id]
            plain += run.text
            style_name = character_names.get(run.character_style_id or "", "")
            kind = InlineKind.TEXT
            if "italic" in style_name or "italico" in style_name:
                kind = InlineKind.EMPHASIS
            elif "superscript" in style_name or "sobrescrito" in style_name:
                kind = InlineKind.SUPERSCRIPT
            elif "subscript" in style_name or "subscrito" in style_name:
                kind = InlineKind.SUBSCRIPT
            inlines.append(
                InlineNode(
                    id=stable_id(article_id, "inline", f"{paragraph.id}:{position}"),
                    kind=kind,
                    text=run.text,
                    evidence_ids=run.evidence_ids,
                )
            )
        return RichText(
            plain=SourcedText(
                value=plain,
                state=FieldState.PRESENT,
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
        article_id: str,
    ) -> tuple[tuple[Section, ...], tuple[str, ...]]:
        body_items = [
            (*item, role)
            for role in ("section-level-1", "section-level-2", "paragraph")
            for item in by_role[role]
        ]
        body_items.sort(key=lambda item: (raw.reading_order.index(item[0].id), item[1].position))
        sections: list[dict[str, object]] = []
        current: dict[str, object] | None = None
        for story, paragraph, role in body_items:
            runs = {run.id: run for run in story.runs}
            text = "".join(runs[item].text for item in paragraph.text_run_ids).strip()
            if not text:
                continue
            if role.startswith("section-level"):
                level = 1 if role.endswith("1") else 2
                current = {
                    "id": stable_id(article_id, "section", paragraph.id),
                    "title": _present(text, paragraph.evidence_ids, f"style-role:{role}"),
                    "level": level,
                    "blocks": [],
                    "evidence_ids": paragraph.evidence_ids,
                }
                sections.append(current)
            else:
                if current is None:
                    current = {
                        "id": stable_id(article_id, "section", "untitled-body"),
                        "title": _missing("body-content-before-section-heading"),
                        "level": 1,
                        "blocks": [],
                        "evidence_ids": (),
                    }
                    sections.append(current)
                blocks = current["blocks"]
                assert isinstance(blocks, list)
                blocks.append(
                    Paragraph(
                        id=stable_id(article_id, "paragraph", paragraph.id),
                        content=self._rich_text(story, paragraph, character_names, article_id),
                        evidence_ids=paragraph.evidence_ids,
                    )
                )

        raw_tables = {table.id: table for table in raw.tables}
        table_story = {
            table_id: story.id for story in raw.stories for table_id in story.table_ids
        }
        story_page = {
            story.id: min(
                (frame.page_index for frame in raw.frames if frame.parent_story_id == story.id),
                default=10**9,
            )
            for story in raw.stories
        }
        captions = by_role["caption"]
        graphic_blocks: list[FigureBlock | TableBlock] = []
        graphic_review_reasons: list[str] = []
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
                        "".join(run_lookup[item].text for item in cell.text_run_ids)
                        if cell
                        else ""
                    )
                    row.append(
                        RichText(
                            plain=(
                                _present(value, cell.evidence_ids, "idml-table-cell")
                                if value.strip() and cell
                                else _missing("empty-or-spanned-table-cell")
                            )
                        )
                    )
                rows.append(tuple(row))
            return tuple(rows)

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
            caption = (
                self._rich_text(story, paragraph, character_names, article_id)
                if caption_value.strip()
                else RichText(plain=_missing("caption-style-contained-no-caption-text"))
            )
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
