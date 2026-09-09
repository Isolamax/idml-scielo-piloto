from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from lxml import etree

from idml_foundation.domain.canonical import (
    CanonicalArticle,
    FieldState,
    FigureBlock,
    FormulaBlock,
    FormulaRepresentation,
    InlineKind,
    ListBlock,
    NoteBlock,
    Paragraph,
    QuoteBlock,
    RichText,
    Section,
    TableBlock,
)
from idml_foundation.mathml import MATHML_NS, parse_mathml_fragment

XLINK_NS = "http://www.w3.org/1999/xlink"
XML_NS = "http://www.w3.org/XML/1998/namespace"
JATS_DTD_NAME = "JATS-journalpublishing1-3-mathml3.dtd"
JATS_PUBLIC_ID = "-//NLM//DTD JATS (Z39.96) Journal Publishing DTD v1.3 20210610//EN"
_INVALID_NCNAME = re.compile(r"[^A-Za-z0-9_.-]+")
_UNSAFE_INVISIBLE_CHARACTERS = frozenset(
    {
        "\ufeff",
        "\u200b",
        "\u2060",
        *(chr(value) for value in range(0x202A, 0x202F)),
        *(chr(value) for value in range(0x2066, 0x206A)),
    }
)
_CREDIT_ROLE_URIS = {
    role: f"https://credit.niso.org/contributor-roles/{slug}/"
    for role, slug in (
        ("Conceptualization", "conceptualization"),
        ("Data curation", "data-curation"),
        ("Formal analysis", "formal-analysis"),
        ("Funding acquisition", "funding-acquisition"),
        ("Investigation", "investigation"),
        ("Methodology", "methodology"),
        ("Project administration", "project-administration"),
        ("Resources", "resources"),
        ("Software", "software"),
        ("Supervision", "supervision"),
        ("Validation", "validation"),
        ("Visualization", "visualization"),
        ("Writing \N{EN DASH} original draft", "writing-original-draft"),
        ("Writing \N{EN DASH} review & editing", "writing-review-editing"),
    )
}


class IdRegistryError(ValueError):
    pass


@dataclass
class IdRegistry:
    _by_source: dict[str, str] = field(default_factory=dict)
    _used: set[str] = field(default_factory=set)
    _target_types: dict[str, str] = field(default_factory=dict)

    def register(self, source_id: str, *, target_type: str | None = None) -> str:
        if source_id in self._by_source:
            raise IdRegistryError(f"duplicate canonical ID: {source_id}")
        candidate = _INVALID_NCNAME.sub("-", source_id).strip("-.") or "id"
        if not candidate[0].isalpha() and candidate[0] != "_":
            candidate = f"id-{candidate}"
        if target_type == "disp-formula" and not candidate.startswith("e"):
            candidate = f"e-{candidate}"
        if candidate in self._used:
            raise IdRegistryError(f"normalized XML ID collision: {candidate}")
        self._by_source[source_id] = candidate
        self._used.add(candidate)
        if target_type is not None:
            self._target_types[source_id] = target_type
        return candidate

    def resolve(self, source_id: str) -> str:
        try:
            return self._by_source[source_id]
        except KeyError as exc:
            raise IdRegistryError(f"orphan cross-reference target: {source_id}") from exc

    def target_type(self, source_id: str) -> str:
        try:
            return self._target_types[source_id]
        except KeyError as exc:
            raise IdRegistryError(f"untyped cross-reference target: {source_id}") from exc


def _add(
    parent: etree._Element,
    tag: str,
    text: str | None = None,
    **attributes: str,
) -> etree._Element:
    element = etree.SubElement(parent, tag, attrib=attributes)
    if text is not None:
        element.text = _xml_text(text)
    return element


def _xml_text(value: str) -> str:
    return "".join(
        character for character in value if character not in _UNSAFE_INVISIBLE_CHARACTERS
    )


class JatsBuilder:
    def __init__(self, *, sps_version: str = "sps-1.10") -> None:
        if sps_version != "sps-1.10":
            raise ValueError("only SPS 1.10 is supported by this builder")
        self._sps_version = sps_version

    def build(self, article: CanonicalArticle) -> bytes:
        registry = IdRegistry()
        self._register_ids(article, registry)
        root = etree.Element(
            "article",
            nsmap={"xlink": XLINK_NS, "mml": MATHML_NS},
            attrib={
                "article-type": article.front.article_category.value or "research-article",
                "dtd-version": "1.3",
                "specific-use": self._sps_version,
                f"{{{XML_NS}}}lang": self._primary_language(article),
            },
        )
        asset_names = {asset.id: asset.logical_name for asset in article.assets}
        self._front(root, article, registry)
        self._body(root, article, registry, asset_names)
        self._back(root, article, registry, asset_names)
        tree = etree.ElementTree(root)
        return etree.tostring(
            tree,
            encoding="UTF-8",
            xml_declaration=True,
            pretty_print=False,
            doctype=f'<!DOCTYPE article PUBLIC "{JATS_PUBLIC_ID}" "{JATS_DTD_NAME}">',
        )

    def _register_ids(self, article: CanonicalArticle, registry: IdRegistry) -> None:
        for contributor in article.front.contributors:
            registry.register(contributor.id)
            if contributor.corresponding and contributor.email and contributor.email.value:
                registry.register(f"{contributor.id}:corresp", target_type="corresp")
        for affiliation in article.front.affiliations:
            registry.register(affiliation.id)
        for section in article.body:
            self._register_section(section, registry)
        for note in article.back.notes:
            registry.register(note.id, target_type="fn")
        for reference in article.back.references:
            registry.register(reference.id, target_type="bibr")
        for paragraph in article.back.acknowledgements:
            registry.register(paragraph.id)

    def _register_section(self, section: Section, registry: IdRegistry) -> None:
        registry.register(section.id, target_type="sec")
        for block in section.blocks:
            target_type = {
                FigureBlock: "fig",
                TableBlock: "table",
                FormulaBlock: "disp-formula",
                NoteBlock: "other",
            }.get(type(block))
            registry.register(block.id, target_type=target_type)
            if isinstance(block, ListBlock):
                for item in block.items:
                    registry.register(item.id)
        for child in section.children:
            self._register_section(child, registry)

    def _primary_language(self, article: CanonicalArticle) -> str:
        return article.front.titles[0].language if article.front.titles else "pt"

    def _front(
        self,
        root: etree._Element,
        article: CanonicalArticle,
        registry: IdRegistry,
    ) -> None:
        front = _add(root, "front")
        journal_meta = _add(front, "journal-meta")
        journal_id = next(
            (item.value.value for item in article.front.journal.identifiers if item.value.value),
            article.journal_profile_id,
        )
        _add(journal_meta, "journal-id", journal_id, **{"journal-id-type": "publisher-id"})
        title_group = _add(journal_meta, "journal-title-group")
        _add(title_group, "journal-title", article.front.journal.title.value or "")
        if (
            article.front.journal.abbreviated_title
            and article.front.journal.abbreviated_title.value
        ):
            _add(
                title_group,
                "abbrev-journal-title",
                article.front.journal.abbreviated_title.value,
                **{"abbrev-type": "publisher"},
            )
        for identifier in article.front.journal.identifiers:
            if identifier.value.value and "issn" in identifier.kind:
                _add(journal_meta, "issn", identifier.value.value, **{"pub-type": "epub"})
        if article.front.journal.publisher_name and article.front.journal.publisher_name.value:
            publisher = _add(journal_meta, "publisher")
            _add(publisher, "publisher-name", article.front.journal.publisher_name.value)

        article_meta = _add(front, "article-meta")
        for identifier in article.front.article_identifiers:
            if identifier.value.value:
                _add(
                    article_meta,
                    "article-id",
                    identifier.value.value,
                    **{"pub-id-type": identifier.kind},
                )
        categories = _add(article_meta, "article-categories")
        subject_group = _add(categories, "subj-group", **{"subj-group-type": "heading"})
        _add(subject_group, "subject", article.front.article_category.value or "research-article")

        title_group = _add(article_meta, "title-group")
        for position, localized in enumerate(article.front.titles):
            if localized.text.value is None:
                continue
            if position == 0:
                _add(title_group, "article-title", localized.text.value)
            else:
                translated = _add(
                    title_group,
                    "trans-title-group",
                    **{f"{{{XML_NS}}}lang": localized.language},
                )
                _add(translated, "trans-title", localized.text.value)

        if article.front.contributors:
            group = _add(article_meta, "contrib-group")
            for contributor in article.front.contributors:
                contrib = _add(
                    group,
                    "contrib",
                    id=registry.resolve(contributor.id),
                    **{
                        "contrib-type": "author",
                        "corresp": "yes" if contributor.corresponding else "no",
                    },
                )
                if contributor.orcid and contributor.orcid.value:
                    orcid = contributor.orcid.value.removeprefix("https://orcid.org/").removeprefix(
                        "http://orcid.org/"
                    )
                    _add(
                        contrib,
                        "contrib-id",
                        orcid,
                        **{"contrib-id-type": "orcid", "authenticated": "false"},
                    )
                if contributor.name:
                    name = _add(contrib, "name", **{"name-style": "western"})
                    _add(name, "surname", contributor.name.surname.value or "")
                    _add(name, "given-names", contributor.name.given_names.value or "")
                    if contributor.name.prefix and contributor.name.prefix.value:
                        _add(name, "prefix", contributor.name.prefix.value)
                    if contributor.name.suffix and contributor.name.suffix.value:
                        _add(name, "suffix", contributor.name.suffix.value)
                elif contributor.group_name and contributor.group_name.value:
                    _add(contrib, "collab", contributor.group_name.value)
                for affiliation_id in contributor.affiliation_ids:
                    _add(
                        contrib,
                        "xref",
                        str(
                            article.front.affiliations.index(
                                next(
                                    item
                                    for item in article.front.affiliations
                                    if item.id == affiliation_id
                                )
                            )
                            + 1
                        ),
                        **{"ref-type": "aff", "rid": registry.resolve(affiliation_id)},
                    )
                if contributor.corresponding and contributor.email and contributor.email.value:
                    _add(
                        contrib,
                        "xref",
                        "*",
                        **{
                            "ref-type": "corresp",
                            "rid": registry.resolve(f"{contributor.id}:corresp"),
                        },
                    )
                for role in contributor.roles:
                    attributes = {}
                    if role in _CREDIT_ROLE_URIS:
                        attributes["content-type"] = _CREDIT_ROLE_URIS[role]
                    _add(contrib, "role", role, **attributes)
                if contributor.email and contributor.email.value:
                    _add(contrib, "email", contributor.email.value)
        for position, affiliation in enumerate(article.front.affiliations, start=1):
            aff = _add(article_meta, "aff", id=registry.resolve(affiliation.id))
            _add(aff, "label", str(position))
            if affiliation.original_text and affiliation.original_text.value:
                _add(
                    aff,
                    "institution",
                    affiliation.original_text.value,
                    **{"content-type": "original"},
                )
            if affiliation.ror and affiliation.ror.value:
                institution_wrap = _add(aff, "institution-wrap")
                _add(
                    institution_wrap,
                    "institution-id",
                    affiliation.ror.value,
                    **{"institution-id-type": "ror"},
                )
            if affiliation.department and affiliation.department.value:
                _add(
                    aff,
                    "institution",
                    affiliation.department.value,
                    **{"content-type": "orgdiv1"},
                )
            _add(
                aff,
                "institution",
                affiliation.institution.value or "",
                **{"content-type": "orgname"},
            )
            if any(
                (
                    affiliation.city and affiliation.city.value,
                    affiliation.state_or_province and affiliation.state_or_province.value,
                )
            ):
                address = _add(aff, "addr-line")
                if affiliation.city and affiliation.city.value:
                    _add(
                        address,
                        "named-content",
                        affiliation.city.value,
                        **{"content-type": "city"},
                    )
                if affiliation.state_or_province and affiliation.state_or_province.value:
                    _add(
                        address,
                        "named-content",
                        affiliation.state_or_province.value,
                        **{"content-type": "state"},
                    )
            if affiliation.country and affiliation.country.value:
                country_attributes = {}
                if affiliation.country_code and affiliation.country_code.value:
                    country_attributes["country"] = affiliation.country_code.value
                _add(aff, "country", affiliation.country.value, **country_attributes)

        corresponding = tuple(
            contributor
            for contributor in article.front.contributors
            if contributor.corresponding and contributor.email and contributor.email.value
        )
        if corresponding:
            author_notes = _add(article_meta, "author-notes")
            for contributor in corresponding:
                email = contributor.email
                if email is None or email.value is None:
                    continue
                corresp = _add(
                    author_notes,
                    "corresp",
                    id=registry.resolve(f"{contributor.id}:corresp"),
                )
                _add(corresp, "label", "*")
                _add(corresp, "email", email.value)

        if article.front.publication_date.state == FieldState.PRESENT:
            self._publication_date(article_meta, article.front.publication_date.value or "")
        if article.front.volume and article.front.volume.value:
            _add(article_meta, "volume", article.front.volume.value)
        if article.front.issue and article.front.issue.value:
            _add(article_meta, "issue", article.front.issue.value)
        publisher_id = next(
            (
                identifier.value.value
                for identifier in article.front.article_identifiers
                if identifier.kind == "publisher-id" and identifier.value.value
            ),
            None,
        )
        if publisher_id and publisher_id.lower().startswith("e"):
            _add(article_meta, "elocation-id", publisher_id)
        if article.front.history_dates:
            history = _add(article_meta, "history")
            for event in article.front.history_dates:
                self._history_date(history, event.date.value or "", event.date_type)
            if article.front.publication_date.state == FieldState.PRESENT:
                publication_value = article.front.publication_date.value or ""
                try:
                    date.fromisoformat(publication_value)
                except ValueError:
                    pass
                else:
                    self._history_date(history, publication_value, "pub")
        if article.front.license_text and article.front.license_text.value:
            permissions = _add(article_meta, "permissions")
            license_attributes = {
                "license-type": "open-access",
                f"{{{XML_NS}}}lang": self._primary_language(article),
            }
            if article.front.license_url and article.front.license_url.value:
                license_attributes[f"{{{XLINK_NS}}}href"] = article.front.license_url.value
            license_element = _add(permissions, "license", **license_attributes)
            _add(license_element, "license-p", article.front.license_text.value)
        for abstract in article.front.abstracts:
            if abstract.text.value:
                element = _add(
                    article_meta,
                    "abstract",
                    **{f"{{{XML_NS}}}lang": abstract.language},
                )
                _add(element, "title", "Abstract")
                _add(element, "p", abstract.text.value)
        for keyword_group in article.front.keywords:
            if not keyword_group.text.value:
                continue
            group = _add(
                article_meta,
                "kwd-group",
                **{f"{{{XML_NS}}}lang": keyword_group.language},
            )
            for keyword in re.split(r"\s*;\s*", keyword_group.text.value.rstrip(". ")):
                if keyword:
                    _add(group, "kwd", keyword)
        if article.front.funding:
            funding_group = _add(article_meta, "funding-group")
            for funding in article.front.funding:
                if funding.agency.value or (funding.award_id and funding.award_id.value):
                    award_group = _add(funding_group, "award-group")
                    if funding.agency.value:
                        _add(award_group, "funding-source", funding.agency.value)
                    if funding.award_id and funding.award_id.value:
                        _add(award_group, "award-id", funding.award_id.value)
                if funding.statement and funding.statement.value:
                    _add(funding_group, "funding-statement", funding.statement.value)

    def _publication_date(self, article_meta: etree._Element, value: str) -> None:
        attributes = {"publication-format": "electronic", "date-type": "pub"}
        parsed: date | None = None
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            pass
        if parsed is not None:
            attributes["iso-8601-date"] = parsed.isoformat()
        pub_date = _add(article_meta, "pub-date", **attributes)
        if parsed is not None:
            _add(pub_date, "day", str(parsed.day).zfill(2))
            _add(pub_date, "month", str(parsed.month).zfill(2))
            _add(pub_date, "year", str(parsed.year))
        elif re.fullmatch(r"\d{4}", value):
            _add(pub_date, "year", value)
        else:
            _add(pub_date, "string-date", value)
        if parsed is not None or re.fullmatch(r"\d{4}", value):
            collection = _add(
                article_meta,
                "pub-date",
                **{"publication-format": "electronic", "date-type": "collection"},
            )
            _add(collection, "year", str(parsed.year) if parsed is not None else value)

    def _history_date(
        self,
        history: etree._Element,
        value: str,
        date_type: str,
    ) -> None:
        parsed = date.fromisoformat(value)
        element = _add(
            history,
            "date",
            **{"date-type": date_type, "iso-8601-date": parsed.isoformat()},
        )
        _add(element, "day", str(parsed.day).zfill(2))
        _add(element, "month", str(parsed.month).zfill(2))
        _add(element, "year", str(parsed.year))

    def _body(
        self,
        root: etree._Element,
        article: CanonicalArticle,
        registry: IdRegistry,
        asset_names: dict[str, str],
    ) -> None:
        body = _add(root, "body")
        for section in article.body:
            self._section(body, section, registry, asset_names)

    def _section(
        self,
        parent: etree._Element,
        section: Section,
        registry: IdRegistry,
        asset_names: dict[str, str],
    ) -> None:
        element = _add(parent, "sec", id=registry.resolve(section.id))
        if section.title.value:
            _add(element, "title", section.title.value)
        for block in section.blocks:
            if isinstance(block, Paragraph):
                paragraph = _add(element, "p", id=registry.resolve(block.id))
                self._rich(paragraph, block.content, registry, asset_names)
            elif isinstance(block, FigureBlock):
                figure = _add(element, "fig", id=registry.resolve(block.id))
                if block.label.value:
                    _add(figure, "label", block.label.value)
                caption = _add(figure, "caption")
                caption_paragraph = _add(caption, "p")
                self._rich(caption_paragraph, block.caption, registry, asset_names)
                if block.asset_id:
                    _add(
                        figure,
                        "graphic",
                        id=f"{registry.resolve(block.id)}-g1",
                        **{f"{{{XLINK_NS}}}href": asset_names[block.asset_id]},
                    )
            elif isinstance(block, TableBlock):
                wrapper = _add(element, "table-wrap", id=registry.resolve(block.id))
                if block.label.value:
                    _add(wrapper, "label", block.label.value)
                caption = _add(wrapper, "caption")
                caption_paragraph = _add(caption, "p")
                self._rich(caption_paragraph, block.caption, registry, asset_names)
                table = _add(wrapper, "table")
                tbody = _add(table, "tbody")
                spans = {(span.row, span.column): span for span in block.cell_spans}
                covered = {
                    (row, column)
                    for span in block.cell_spans
                    for row in range(span.row, span.row + span.row_span)
                    for column in range(span.column, span.column + span.column_span)
                    if (row, column) != (span.row, span.column)
                }
                for row_index, row in enumerate(block.rows):
                    tr = _add(tbody, "tr")
                    for column_index, cell in enumerate(row):
                        if (row_index, column_index) in covered:
                            continue
                        attributes: dict[str, str] = {}
                        span = spans.get((row_index, column_index))
                        if span and span.row_span > 1:
                            attributes["rowspan"] = str(span.row_span)
                        if span and span.column_span > 1:
                            attributes["colspan"] = str(span.column_span)
                        td = _add(tr, "td", **attributes)
                        if cell.plain.value:
                            self._rich(td, cell, registry, asset_names)
                if block.footnotes:
                    table_footer = _add(wrapper, "table-wrap-foot")
                    for position, footnote in enumerate(block.footnotes, start=1):
                        footnote_element = _add(table_footer, "fn")
                        _add(footnote_element, "label", str(position))
                        paragraph = _add(footnote_element, "p")
                        self._rich(paragraph, footnote, registry, asset_names)
            elif isinstance(block, ListBlock):
                listing = _add(
                    element,
                    "list",
                    id=registry.resolve(block.id),
                    **{"list-type": "order" if block.ordered else "bullet"},
                )
                for item in block.items:
                    list_item = _add(listing, "list-item", id=registry.resolve(item.id))
                    paragraph = _add(list_item, "p")
                    self._rich(paragraph, item.content, registry, asset_names)
            elif isinstance(block, QuoteBlock):
                quote = _add(element, "disp-quote", id=registry.resolve(block.id))
                paragraph = _add(quote, "p")
                self._rich(paragraph, block.content, registry, asset_names)
                if block.attribution and block.attribution.value:
                    _add(quote, "attrib", block.attribution.value)
            elif isinstance(block, FormulaBlock):
                formula = _add(element, "disp-formula", id=registry.resolve(block.id))
                if block.label and block.label.value:
                    _add(formula, "label", block.label.value)
                if block.representation == FormulaRepresentation.IMAGE and block.asset_id:
                    _add(
                        formula,
                        "graphic",
                        id=f"{registry.resolve(block.id)}-g1",
                        **{f"{{{XLINK_NS}}}href": asset_names[block.asset_id]},
                    )
                elif block.representation == FormulaRepresentation.MATHML:
                    formula.append(parse_mathml_fragment(block.source.value or "", display=True))
                else:
                    _add(formula, "tex-math", block.source.value or "")
            elif isinstance(block, NoteBlock):
                note = _add(element, "boxed-text", id=registry.resolve(block.id))
                paragraph = _add(note, "p")
                self._rich(paragraph, block.content, registry, asset_names)
        for child in section.children:
            self._section(element, child, registry, asset_names)

    def _rich(
        self,
        parent: etree._Element,
        rich_text: RichText,
        registry: IdRegistry,
        asset_names: dict[str, str],
    ) -> None:
        if not rich_text.inlines:
            parent.text = _xml_text(rich_text.plain.value or "")
            return
        previous: etree._Element | None = None
        for inline in rich_text.inlines:
            if inline.kind == InlineKind.TEXT:
                safe_text = _xml_text(inline.text)
                if previous is None:
                    parent.text = (parent.text or "") + safe_text
                else:
                    previous.tail = (previous.tail or "") + safe_text
                continue
            if inline.kind == InlineKind.INLINE_FORMULA:
                if inline.formula_representation == FormulaRepresentation.UNKNOWN and (
                    inline.formula_source is None or inline.formula_source.value is None
                ):
                    continue
                inline_formula = _add(parent, "inline-formula")
                if inline.formula_representation == FormulaRepresentation.MATHML:
                    inline_formula.append(
                        parse_mathml_fragment(
                            (inline.formula_source.value or "") if inline.formula_source else "",
                            display=False,
                        )
                    )
                elif (
                    inline.formula_representation == FormulaRepresentation.IMAGE
                    and inline.formula_asset_id
                ):
                    _add(
                        inline_formula,
                        "inline-graphic",
                        id=f"{_INVALID_NCNAME.sub('-', inline.id).strip('-.') or 'inline'}-g1",
                        **{f"{{{XLINK_NS}}}href": asset_names[inline.formula_asset_id]},
                    )
                else:
                    _add(
                        inline_formula,
                        "tex-math",
                        inline.formula_source.value if inline.formula_source else inline.text,
                    )
                previous = inline_formula
                continue
            tag = {
                InlineKind.EMPHASIS: "italic",
                InlineKind.STRONG: "bold",
                InlineKind.SUBSCRIPT: "sub",
                InlineKind.SUPERSCRIPT: "sup",
                InlineKind.EXTERNAL_LINK: "ext-link",
                InlineKind.CROSS_REFERENCE: "xref",
                InlineKind.NAMED_CONTENT: "named-content",
            }[inline.kind]
            attributes: dict[str, str] = {}
            if inline.kind == InlineKind.EXTERNAL_LINK and inline.href:
                attributes[f"{{{XLINK_NS}}}href"] = inline.href
                attributes["ext-link-type"] = "uri"
            elif inline.kind == InlineKind.CROSS_REFERENCE and inline.target_id:
                attributes["rid"] = registry.resolve(inline.target_id)
                attributes["ref-type"] = registry.target_type(inline.target_id)
            elif inline.kind == InlineKind.NAMED_CONTENT and inline.name:
                attributes["content-type"] = inline.name
            combined_emphasis = inline.attributes.get("source-emphasis") == "bold italic"
            if combined_emphasis and inline.kind == InlineKind.STRONG:
                previous = _add(parent, "bold", **attributes)
                _add(previous, "italic", inline.text)
            elif combined_emphasis and inline.kind == InlineKind.EXTERNAL_LINK:
                previous = _add(parent, tag, **attributes)
                bold = _add(previous, "bold")
                _add(bold, "italic", inline.text)
            else:
                previous = _add(parent, tag, inline.text, **attributes)

    def _back(
        self,
        root: etree._Element,
        article: CanonicalArticle,
        registry: IdRegistry,
        asset_names: dict[str, str],
    ) -> None:
        if not any(
            (
                bool(article.back.references),
                bool(article.back.notes),
                bool(article.back.acknowledgements),
                bool(
                    article.back.contribution_statement
                    and article.back.contribution_statement.value
                ),
                bool(article.back.data_availability and article.back.data_availability.value),
                bool(article.back.conflicts and article.back.conflicts.value),
            )
        ):
            return
        back = _add(root, "back")
        if article.back.acknowledgements:
            acknowledgements = _add(back, "ack")
            _add(acknowledgements, "title", "Acknowledgements")
            for source in article.back.acknowledgements:
                paragraph = _add(acknowledgements, "p", id=registry.resolve(source.id))
                self._rich(paragraph, source.content, registry, asset_names)
        for section_type, title, sourced in (
            ("author-contributions", "Author contributions", article.back.contribution_statement),
            ("data-availability", "Data availability", article.back.data_availability),
            ("conflict-of-interest", "Conflicts of interest", article.back.conflicts),
        ):
            if sourced and sourced.value:
                attributes: dict[str, str] = {}
                if section_type == "data-availability":
                    attributes["sec-type"] = section_type
                    if article.back.data_availability_mode:
                        attributes["specific-use"] = article.back.data_availability_mode
                section = _add(back, "sec", **attributes)
                _add(section, "title", title)
                _add(section, "p", sourced.value)
        if article.back.notes:
            note_group = _add(back, "fn-group")
            for position, note in enumerate(article.back.notes, start=1):
                element = _add(
                    note_group,
                    "fn",
                    id=registry.resolve(note.id),
                    **{"fn-type": "other"},
                )
                _add(element, "label", str(position))
                paragraph = _add(element, "p")
                self._rich(paragraph, note.content, registry, asset_names)
        if article.back.references:
            reference_list = _add(back, "ref-list")
            _add(reference_list, "title", "References")
            for position, reference in enumerate(article.back.references, start=1):
                element = _add(reference_list, "ref", id=registry.resolve(reference.id))
                _add(element, "label", str(position))
                citation = _add(element, "mixed-citation")
                self._rich(citation, reference.mixed_citation, registry, asset_names)
                if any(
                    (
                        reference.authors,
                        reference.year and reference.year.value,
                        reference.title and reference.title.value,
                        reference.source and reference.source.value,
                        reference.identifiers,
                    )
                ):
                    structured = _add(
                        element,
                        "element-citation",
                        **{"publication-type": "journal", "specific-use": "machine-readable"},
                    )
                    if reference.authors:
                        authors = _add(
                            structured, "person-group", **{"person-group-type": "author"}
                        )
                        for author in reference.authors:
                            if author.value:
                                _add(authors, "string-name", author.value)
                    if reference.title and reference.title.value:
                        _add(structured, "article-title", reference.title.value)
                    if reference.source and reference.source.value:
                        _add(structured, "source", reference.source.value)
                    if reference.year and reference.year.value:
                        _add(structured, "year", reference.year.value)
                    for identifier in reference.identifiers:
                        if identifier.value.value:
                            _add(
                                structured,
                                "pub-id",
                                identifier.value.value,
                                **{"pub-id-type": identifier.kind},
                            )
