from __future__ import annotations

import re
from dataclasses import dataclass, field

from lxml import etree

from idml_foundation.domain.canonical import (
    CanonicalArticle,
    FieldState,
    FigureBlock,
    FormulaBlock,
    InlineKind,
    ListBlock,
    NoteBlock,
    Paragraph,
    QuoteBlock,
    RichText,
    Section,
    TableBlock,
)

XLINK_NS = "http://www.w3.org/1999/xlink"
XML_NS = "http://www.w3.org/XML/1998/namespace"
JATS_DTD_NAME = "JATS-journalpublishing1-3-mathml3.dtd"
_INVALID_NCNAME = re.compile(r"[^A-Za-z0-9_.-]+")


class IdRegistryError(ValueError):
    pass


@dataclass
class IdRegistry:
    _by_source: dict[str, str] = field(default_factory=dict)
    _used: set[str] = field(default_factory=set)

    def register(self, source_id: str) -> str:
        if source_id in self._by_source:
            raise IdRegistryError(f"duplicate canonical ID: {source_id}")
        candidate = _INVALID_NCNAME.sub("-", source_id).strip("-.") or "id"
        if not candidate[0].isalpha() and candidate[0] != "_":
            candidate = f"id-{candidate}"
        if candidate in self._used:
            raise IdRegistryError(f"normalized XML ID collision: {candidate}")
        self._by_source[source_id] = candidate
        self._used.add(candidate)
        return candidate

    def resolve(self, source_id: str) -> str:
        try:
            return self._by_source[source_id]
        except KeyError as exc:
            raise IdRegistryError(f"orphan cross-reference target: {source_id}") from exc


def _add(
    parent: etree._Element,
    tag: str,
    text: str | None = None,
    **attributes: str,
) -> etree._Element:
    element = etree.SubElement(parent, tag, attrib=attributes)
    if text is not None:
        element.text = text
    return element


class JatsBuilder:
    def build(self, article: CanonicalArticle) -> bytes:
        registry = IdRegistry()
        self._register_ids(article, registry)
        root = etree.Element(
            "article",
            nsmap={"xlink": XLINK_NS},
            attrib={
                "article-type": article.front.article_category.value or "research-article",
                "dtd-version": "1.3",
                f"{{{XML_NS}}}lang": self._primary_language(article),
            },
        )
        self._front(root, article, registry)
        self._body(root, article, registry)
        self._back(root, article, registry)
        tree = etree.ElementTree(root)
        return etree.tostring(
            tree,
            encoding="UTF-8",
            xml_declaration=True,
            pretty_print=False,
            doctype=f'<!DOCTYPE article SYSTEM "{JATS_DTD_NAME}">',
        )

    def _register_ids(self, article: CanonicalArticle, registry: IdRegistry) -> None:
        for contributor in article.front.contributors:
            registry.register(contributor.id)
        for affiliation in article.front.affiliations:
            registry.register(affiliation.id)
        for section in article.body:
            self._register_section(section, registry)
        for note in article.back.notes:
            registry.register(note.id)
        for reference in article.back.references:
            registry.register(reference.id)

    def _register_section(self, section: Section, registry: IdRegistry) -> None:
        registry.register(section.id)
        for block in section.blocks:
            registry.register(block.id)
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
            group = _add(article_meta, "contrib-group", **{"content-type": "author"})
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
                if contributor.name:
                    name = _add(contrib, "name", **{"name-style": "western"})
                    _add(name, "surname", contributor.name.surname.value or "")
                    _add(name, "given-names", contributor.name.given_names.value or "")
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
        for position, affiliation in enumerate(article.front.affiliations, start=1):
            aff = _add(article_meta, "aff", id=registry.resolve(affiliation.id))
            _add(aff, "label", str(position))
            _add(
                aff,
                "institution",
                affiliation.institution.value or "",
                **{"content-type": "orgname"},
            )

        if article.front.publication_date.state == FieldState.PRESENT:
            pub_date = _add(article_meta, "pub-date", **{"pub-type": "epub"})
            _add(pub_date, "string-date", article.front.publication_date.value or "")
        for abstract in article.front.abstracts:
            if abstract.text.value:
                element = _add(
                    article_meta,
                    "abstract",
                    **{f"{{{XML_NS}}}lang": abstract.language},
                )
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

    def _body(
        self,
        root: etree._Element,
        article: CanonicalArticle,
        registry: IdRegistry,
    ) -> None:
        body = _add(root, "body")
        asset_names = {asset.id: asset.logical_name for asset in article.assets}
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
                self._rich(paragraph, block.content, registry)
            elif isinstance(block, FigureBlock):
                figure = _add(element, "fig", id=registry.resolve(block.id))
                if block.label.value:
                    _add(figure, "label", block.label.value)
                caption = _add(figure, "caption")
                caption_paragraph = _add(caption, "p")
                self._rich(caption_paragraph, block.caption, registry)
                if block.asset_id:
                    _add(
                        figure,
                        "graphic",
                        **{f"{{{XLINK_NS}}}href": asset_names[block.asset_id]},
                    )
            elif isinstance(block, TableBlock):
                wrapper = _add(element, "table-wrap", id=registry.resolve(block.id))
                if block.label.value:
                    _add(wrapper, "label", block.label.value)
                caption = _add(wrapper, "caption")
                caption_paragraph = _add(caption, "p")
                self._rich(caption_paragraph, block.caption, registry)
                table = _add(wrapper, "table")
                tbody = _add(table, "tbody")
                for row in block.rows:
                    tr = _add(tbody, "tr")
                    for cell in row:
                        td = _add(tr, "td")
                        if cell.plain.value:
                            self._rich(td, cell, registry)
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
                    self._rich(paragraph, item.content, registry)
            elif isinstance(block, QuoteBlock):
                quote = _add(element, "disp-quote", id=registry.resolve(block.id))
                paragraph = _add(quote, "p")
                self._rich(paragraph, block.content, registry)
            elif isinstance(block, FormulaBlock):
                formula = _add(element, "disp-formula", id=registry.resolve(block.id))
                _add(formula, "tex-math", block.source.value or "")
            elif isinstance(block, NoteBlock):
                note = _add(element, "boxed-text", id=registry.resolve(block.id))
                paragraph = _add(note, "p")
                self._rich(paragraph, block.content, registry)
        for child in section.children:
            self._section(element, child, registry, asset_names)

    def _rich(
        self,
        parent: etree._Element,
        rich_text: RichText,
        registry: IdRegistry,
    ) -> None:
        if not rich_text.inlines:
            parent.text = rich_text.plain.value or ""
            return
        previous: etree._Element | None = None
        for inline in rich_text.inlines:
            if inline.kind == InlineKind.TEXT:
                if previous is None:
                    parent.text = (parent.text or "") + inline.text
                else:
                    previous.tail = (previous.tail or "") + inline.text
                continue
            tag = {
                InlineKind.EMPHASIS: "italic",
                InlineKind.STRONG: "bold",
                InlineKind.SUBSCRIPT: "sub",
                InlineKind.SUPERSCRIPT: "sup",
                InlineKind.EXTERNAL_LINK: "ext-link",
                InlineKind.CROSS_REFERENCE: "xref",
                InlineKind.INLINE_FORMULA: "inline-formula",
                InlineKind.NAMED_CONTENT: "named-content",
            }[inline.kind]
            attributes: dict[str, str] = {}
            if inline.kind == InlineKind.EXTERNAL_LINK and inline.href:
                attributes[f"{{{XLINK_NS}}}href"] = inline.href
                attributes["ext-link-type"] = "uri"
            elif inline.kind == InlineKind.CROSS_REFERENCE and inline.target_id:
                attributes["rid"] = registry.resolve(inline.target_id)
                attributes["ref-type"] = "other"
            elif inline.kind == InlineKind.NAMED_CONTENT and inline.name:
                attributes["content-type"] = inline.name
            previous = _add(parent, tag, inline.text, **attributes)

    def _back(
        self,
        root: etree._Element,
        article: CanonicalArticle,
        registry: IdRegistry,
    ) -> None:
        if not article.back.references and not article.back.notes:
            return
        back = _add(root, "back")
        if article.back.references:
            reference_list = _add(back, "ref-list")
            _add(reference_list, "title", "References")
            for position, reference in enumerate(article.back.references, start=1):
                element = _add(reference_list, "ref", id=registry.resolve(reference.id))
                _add(element, "label", str(position))
                citation = _add(element, "mixed-citation")
                self._rich(citation, reference.mixed_citation, registry)
