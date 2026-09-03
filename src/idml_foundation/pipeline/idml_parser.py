from __future__ import annotations

import hashlib
import mimetypes
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
from typing import cast
from urllib.parse import unquote, urlparse
from zipfile import ZipFile

from lxml import etree

from idml_foundation.domain.common import (
    BoundingBox,
    Evidence,
    EvidenceLocator,
    SourceKind,
    stable_id,
)
from idml_foundation.domain.raw import (
    AnchoredPlacement,
    RawAnchoredObject,
    RawArticle,
    RawAsset,
    RawLink,
    RawObjectKind,
    RawParagraph,
    RawSpread,
    RawStory,
    RawStyle,
    RawTable,
    RawTableCell,
    RawTextFrame,
    RawTextRun,
    ReadingOrderIssue,
    StyleKind,
)
from idml_foundation.ingest.safe_zip import inspect_idml
from idml_foundation.ingest.xml_security import parse_untrusted_xml
from idml_foundation.settings import Settings

_STYLE_PREFIX = re.compile(r"^(\d{2}(?:\.\d+)?)")
_NULL_REFERENCE = {"", "n", "$ID/"}


def _local_name(element: etree._Element) -> str:
    return etree.QName(element).localname if isinstance(element.tag, str) else ""


def _elements(root: etree._Element, name: str) -> list[etree._Element]:
    return [element for element in root.iter() if _local_name(element) == name]


def _direct_elements(root: etree._Element, name: str) -> list[etree._Element]:
    return [element for element in root if _local_name(element) == name]


def _normalize_style_name(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).replace("\ufffd", "")
    return " ".join(value.casefold().split())


def style_prefix(value: str) -> str | None:
    """Return the journal-controlled numeric prefix without trusting mojibake text."""
    match = _STYLE_PREFIX.match(value.strip())
    return match.group(1) if match else None


def _reference(value: str | None) -> str | None:
    return None if value is None or value in _NULL_REFERENCE else value


def _numbers(value: str | None, expected: int) -> tuple[float, ...]:
    if value is None:
        return (0.0,) * expected
    parts = tuple(float(item) for item in value.split())
    return parts if len(parts) == expected else (0.0,) * expected


def _sanitized_asset_name(uri: str) -> str:
    parsed = urlparse(uri)
    candidate = PurePosixPath(unquote(parsed.path.replace("\\", "/"))).name
    candidate = "".join(ch for ch in candidate if ch.isprintable() and ch not in {"/", "\\"})
    return candidate[:255] or "unnamed-asset"


def _media_type(name: str, resource_format: str | None) -> str:
    guessed = mimetypes.guess_type(name)[0]
    if guessed:
        return guessed
    normalized = (resource_format or "").casefold()
    if "pdf" in normalized or "portable document" in normalized:
        return "application/pdf"
    return "application/octet-stream"


def _text_of_range(element: etree._Element) -> str:
    pieces: list[str] = []
    range_is_table_cell = any(_local_name(item) == "Cell" for item in element.iterancestors())

    def nested_below(descendant: etree._Element, name: str) -> bool:
        for ancestor in descendant.iterancestors():
            if ancestor is element:
                return False
            if _local_name(ancestor) == name:
                return True
        return False

    for descendant in element.iter():
        name = _local_name(descendant)
        if name == "Content" and descendant.text:
            if nested_below(descendant, "TextVariableInstance"):
                continue
            if not range_is_table_cell and nested_below(descendant, "Table"):
                continue
            pieces.append(descendant.text)
        elif name == "Br":
            pieces.append("\n")
        elif name == "TextVariableInstance":
            result = descendant.get("ResultText")
            if result:
                pieces.append(result)
    return "".join(pieces)


def _range_events(element: etree._Element) -> list[tuple[str, str]]:
    events: list[tuple[str, str]] = []
    range_is_table_cell = any(_local_name(item) == "Cell" for item in element.iterancestors())

    def nested_below(descendant: etree._Element, name: str) -> bool:
        for ancestor in descendant.iterancestors():
            if ancestor is element:
                return False
            if _local_name(ancestor) == name:
                return True
        return False

    for descendant in element.iter():
        name = _local_name(descendant)
        if name == "Content" and descendant.text:
            if nested_below(descendant, "TextVariableInstance"):
                continue
            if not range_is_table_cell and nested_below(descendant, "Table"):
                continue
            events.append(("text", descendant.text))
        elif name == "Br":
            events.append(("text", "\n"))
        elif name == "TextVariableInstance":
            if result := descendant.get("ResultText"):
                events.append(("text", result))
        elif name == "Link" and (link_self := descendant.get("Self")):
            events.append(("link", link_self))
    return events


def _anchor_context(
    events: list[tuple[str, str]],
    position: int,
) -> tuple[AnchoredPlacement, str | None]:
    left = ""
    for kind, value in reversed(events[:position]):
        if kind == "link":
            break
        left = value + left
        if "\n" in value:
            left = left.rsplit("\n", maxsplit=1)[-1]
            break
    right = ""
    for kind, value in events[position + 1 :]:
        if kind == "link":
            break
        right += value
        if "\n" in value:
            right = right.split("\n", maxsplit=1)[0]
            break
    label_match = re.fullmatch(r"\s*(\(\d+\))\s*", right)
    if not left.strip() and (not right.strip() or label_match):
        return AnchoredPlacement.BLOCK, label_match.group(1) if label_match else None
    return AnchoredPlacement.INLINE, None


@dataclass(frozen=True)
class _StoryResult:
    story: RawStory
    tables: tuple[RawTable, ...]
    objects: tuple[RawAnchoredObject, ...]
    assets: tuple[RawAsset, ...]
    links: tuple[RawLink, ...]
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True)
class _LayoutResult:
    frames: tuple[RawTextFrame, ...]
    spreads: tuple[RawSpread, ...]
    objects: tuple[RawAnchoredObject, ...]
    assets: tuple[RawAsset, ...]
    links: tuple[RawLink, ...]
    evidence: tuple[Evidence, ...]


class IdmlParser:
    """Parse an untrusted IDML package into the loss-aware Raw Article model."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()

    def parse(self, data: bytes, *, logical_name: str) -> RawArticle:
        inspect_idml(data, self.settings)
        artifact_sha = hashlib.sha256(data).hexdigest()
        article_key = PurePosixPath(logical_name.replace("\\", "/")).stem

        with ZipFile(BytesIO(data)) as archive:
            roots = {
                name: parse_untrusted_xml(archive.read(name))
                for name in archive.namelist()
                if name.casefold().endswith(".xml")
            }

        design = roots["designmap.xml"]
        document_self_id = design.get("Self", "document")
        styles, style_evidence = self._parse_styles(roots, article_key, artifact_sha)
        story_results = [
            self._parse_story(path, root, article_key, artifact_sha)
            for path, root in sorted(roots.items())
            if path.startswith("Stories/")
        ]
        layout = self._parse_layout(roots, article_key, artifact_sha)
        frames, spreads = layout.frames, layout.spreads
        stories = tuple(result.story for result in story_results)
        known_story_ids = {story.id for story in stories}
        frames = tuple(frame for frame in frames if frame.parent_story_id in known_story_ids)
        known_frame_ids = {frame.id for frame in frames}
        frames = tuple(
            frame.model_copy(
                update={
                    "previous_frame_id": (
                        frame.previous_frame_id
                        if frame.previous_frame_id in known_frame_ids
                        else None
                    ),
                    "next_frame_id": (
                        frame.next_frame_id if frame.next_frame_id in known_frame_ids else None
                    ),
                }
            )
            for frame in frames
        )
        spreads = tuple(
            spread.model_copy(
                update={
                    "frame_ids": tuple(
                        frame_id for frame_id in spread.frame_ids if frame_id in known_frame_ids
                    )
                }
            )
            for spread in spreads
        )
        order, issues = self._reading_order(
            stories,
            frames,
            tuple(design.get("StoryList", "").split()),
        )

        return RawArticle(
            article_id=article_key,
            source_artifact_sha256=artifact_sha,
            document_self_id=document_self_id,
            adobe_dom_version=design.get("DOMVersion"),
            stories=stories,
            frames=frames,
            spreads=spreads,
            styles=styles,
            tables=tuple(table for result in story_results for table in result.tables),
            anchored_objects=tuple(item for result in story_results for item in result.objects)
            + layout.objects,
            assets=tuple(asset for result in story_results for asset in result.assets)
            + layout.assets,
            links=tuple(link for result in story_results for link in result.links) + layout.links,
            reading_order=order,
            reading_order_issues=issues,
            evidence=tuple(
                [*style_evidence, *layout.evidence]
                + [item for result in story_results for item in result.evidence]
            ),
        )

    def _evidence(
        self,
        article_key: str,
        artifact_sha: str,
        logical_path: str,
        element_id: str,
        description: str,
    ) -> Evidence:
        evidence_id = stable_id(article_key, "evidence", f"{logical_path}#{element_id}")
        return Evidence(
            id=evidence_id,
            source_kind=SourceKind.IDML,
            locator=EvidenceLocator(
                artifact_sha256=artifact_sha,
                logical_path=logical_path,
                element_id=element_id,
            ),
            description=description,
        )

    def _parse_styles(
        self,
        roots: dict[str, etree._Element],
        article_key: str,
        artifact_sha: str,
    ) -> tuple[tuple[RawStyle, ...], tuple[Evidence, ...]]:
        kind_by_name = {
            "ParagraphStyle": StyleKind.PARAGRAPH,
            "CharacterStyle": StyleKind.CHARACTER,
            "TableStyle": StyleKind.TABLE,
            "CellStyle": StyleKind.CELL,
        }
        styles: list[RawStyle] = []
        evidence: list[Evidence] = []
        for path, root in sorted(roots.items()):
            if not path.startswith("Resources/"):
                continue
            for element in root.iter():
                kind = kind_by_name.get(_local_name(element))
                source_self = element.get("Self")
                if kind is None or source_self is None:
                    continue
                source_name = element.get("Name", source_self.rsplit("/", 1)[-1])
                evidence_item = self._evidence(
                    article_key, artifact_sha, path, source_self, "IDML style definition"
                )
                evidence.append(evidence_item)
                parent = next(
                    (
                        child.text
                        for child in element.iter()
                        if _local_name(child) == "BasedOn" and child.text
                    ),
                    None,
                )
                properties: dict[str, str | int | float | bool | None] = {}
                prefix = style_prefix(source_name)
                if prefix:
                    properties["journal_prefix"] = prefix
                for key in ("FontStyle", "Position", "PointSize"):
                    if key in element.attrib:
                        properties[key] = cast(str, element.attrib[key])
                styles.append(
                    RawStyle(
                        id=stable_id(article_key, "style", source_self),
                        source_name=source_name,
                        normalized_name=_normalize_style_name(source_name),
                        kind=kind,
                        parent_style_id=(
                            stable_id(article_key, "style", parent) if parent else None
                        ),
                        properties=properties,
                        evidence_ids=(evidence_item.id,),
                    )
                )
        known = {item.id for item in styles}
        styles = [
            item.model_copy(
                update={
                    "parent_style_id": (
                        item.parent_style_id if item.parent_style_id in known else None
                    )
                }
            )
            for item in styles
        ]
        return tuple(styles), tuple(evidence)

    def _parse_story(
        self,
        path: str,
        root: etree._Element,
        article_key: str,
        artifact_sha: str,
    ) -> _StoryResult:
        story_element = next(element for element in _elements(root, "Story") if element.get("Self"))
        source_self = story_element.get("Self", PurePosixPath(path).stem)
        story_id = stable_id(article_key, "story", source_self)
        story_evidence = self._evidence(article_key, artifact_sha, path, source_self, "IDML story")
        evidence: list[Evidence] = [story_evidence]
        runs: list[RawTextRun] = []
        paragraphs: list[RawParagraph] = []
        run_ids_by_cell: defaultdict[str, list[str]] = defaultdict(list)
        anchor_run_by_link: dict[str, str] = {}
        anchor_placement_by_link: dict[str, AnchoredPlacement] = {}
        anchor_label_by_link: dict[str, str] = {}

        def cell_key(cell: etree._Element) -> str:
            table = next(
                (ancestor for ancestor in cell.iterancestors() if _local_name(ancestor) == "Table"),
                None,
            )
            table_self = table.get("Self", "table") if table is not None else "table"
            return f"{table_self}:{cell.get('Name', 'cell')}"

        paragraph_ranges = _elements(story_element, "ParagraphStyleRange")
        for paragraph_position, paragraph_range in enumerate(paragraph_ranges):
            paragraph_locator = f"{source_self}:paragraph:{paragraph_position}"
            paragraph_evidence = self._evidence(
                article_key, artifact_sha, path, paragraph_locator, "IDML paragraph range"
            )
            evidence.append(paragraph_evidence)
            paragraph_style = paragraph_range.get("AppliedParagraphStyle")
            paragraph_style_id = (
                stable_id(article_key, "style", paragraph_style) if paragraph_style else None
            )
            paragraph_run_ids: list[str] = []
            cell = next(
                (
                    ancestor
                    for ancestor in paragraph_range.iterancestors()
                    if _local_name(ancestor) == "Cell"
                ),
                None,
            )
            character_ranges = [
                child for child in paragraph_range if _local_name(child) == "CharacterStyleRange"
            ]
            range_events = [
                (character_range, _range_events(character_range))
                for character_range in character_ranges
            ]
            paragraph_events = [event for _, events in range_events for event in events]
            for event_position, (kind, value) in enumerate(paragraph_events):
                if kind != "link":
                    continue
                placement, label = _anchor_context(paragraph_events, event_position)
                anchor_placement_by_link[value] = placement
                if label is not None:
                    anchor_label_by_link[value] = label

            def append_run(
                text: str,
                character_range: etree._Element,
                *,
                anchor_link_self: str | None = None,
                paragraph_style_id: str | None = paragraph_style_id,
                paragraph_evidence: Evidence = paragraph_evidence,
                paragraph_run_ids: list[str] = paragraph_run_ids,
                cell: etree._Element | None = cell,
            ) -> None:
                position = len(runs)
                run_id = stable_id(article_key, "run", f"{source_self}:{position}")
                character_style = character_range.get("AppliedCharacterStyle")
                runs.append(
                    RawTextRun(
                        id=run_id,
                        text=text,
                        paragraph_style_id=paragraph_style_id,
                        character_style_id=(
                            stable_id(article_key, "style", character_style)
                            if character_style
                            else None
                        ),
                        position=position,
                        evidence_ids=(paragraph_evidence.id,),
                    )
                )
                paragraph_run_ids.append(run_id)
                if cell is not None:
                    run_ids_by_cell[cell_key(cell)].append(run_id)
                if anchor_link_self is not None:
                    anchor_run_by_link[anchor_link_self] = run_id

            for character_range, events in range_events:
                buffered_text = ""
                pending_label: str | None = None
                for kind, value in events:
                    if kind == "text":
                        if pending_label is not None:
                            value = re.sub(
                                rf"^\s*{re.escape(pending_label)}\s*",
                                "",
                                value,
                                count=1,
                            )
                            pending_label = None
                        buffered_text += value
                        continue
                    if buffered_text:
                        append_run(buffered_text, character_range)
                        buffered_text = ""
                    append_run("", character_range, anchor_link_self=value)
                    pending_label = anchor_label_by_link.get(value)
                if buffered_text:
                    append_run(buffered_text, character_range)
            paragraph_id = stable_id(article_key, "paragraph", paragraph_locator)
            cell_id = (
                stable_id(
                    article_key,
                    "cell",
                    f"{source_self}:{cell_key(cell)}",
                )
                if cell is not None
                else None
            )
            paragraphs.append(
                RawParagraph(
                    id=paragraph_id,
                    position=paragraph_position,
                    paragraph_style_id=paragraph_style_id,
                    text_run_ids=tuple(paragraph_run_ids),
                    table_cell_id=cell_id,
                    evidence_ids=(paragraph_evidence.id,),
                )
            )

        tables: list[RawTable] = []
        for table_position, table_element in enumerate(_elements(story_element, "Table")):
            source_table_id = table_element.get("Self", f"{source_self}:table:{table_position}")
            table_evidence = self._evidence(
                article_key, artifact_sha, path, source_table_id, "IDML table"
            )
            evidence.append(table_evidence)
            cells: list[RawTableCell] = []
            max_row = max_column = 0
            for cell in _elements(table_element, "Cell"):
                coordinates = cell.get("Name", "0:0").split(":", 1)
                column, row = (int(value) for value in coordinates)
                row_span = int(cell.get("RowSpan", "1"))
                column_span = int(cell.get("ColumnSpan", "1"))
                max_row = max(max_row, row + row_span)
                max_column = max(max_column, column + column_span)
                cells.append(
                    RawTableCell(
                        row=row,
                        column=column,
                        row_span=row_span,
                        column_span=column_span,
                        text_run_ids=tuple(run_ids_by_cell[cell_key(cell)]),
                        evidence_ids=(table_evidence.id,),
                    )
                )
            row_count = int(table_element.get("BodyRowCount", str(max_row or 1)))
            row_count += int(table_element.get("HeaderRowCount", "0"))
            row_count += int(table_element.get("FooterRowCount", "0"))
            column_count = int(table_element.get("ColumnCount", str(max_column or 1)))
            tables.append(
                RawTable(
                    id=stable_id(article_key, "table", source_table_id),
                    source_self_id=source_table_id,
                    row_count=max(row_count, max_row, 1),
                    column_count=max(column_count, max_column, 1),
                    cells=tuple(cells),
                    style_id=(
                        stable_id(article_key, "style", table_element.get("AppliedTableStyle", ""))
                        if table_element.get("AppliedTableStyle")
                        else None
                    ),
                    evidence_ids=(table_evidence.id,),
                )
            )

        assets: list[RawAsset] = []
        links: list[RawLink] = []
        objects: list[RawAnchoredObject] = []
        for link_position, link in enumerate(_elements(story_element, "Link")):
            link_self = link.get("Self", f"{source_self}:link:{link_position}")
            name = _sanitized_asset_name(link.get("LinkResourceURI", ""))
            asset_id = stable_id(article_key, "asset", link_self)
            link_evidence = self._evidence(
                article_key, artifact_sha, path, link_self, "Sanitized external asset link"
            )
            evidence.append(link_evidence)
            assets.append(
                RawAsset(
                    id=asset_id,
                    logical_path=name,
                    media_type=_media_type(name, link.get("LinkResourceFormat")),
                    external=True,
                    evidence_ids=(link_evidence.id,),
                )
            )
            links.append(
                RawLink(
                    id=stable_id(article_key, "link", link_self),
                    source_id=story_id,
                    target=asset_id,
                    relationship="external-asset",
                    evidence_ids=(link_evidence.id,),
                )
            )
            objects.append(
                RawAnchoredObject(
                    id=stable_id(article_key, "object", link_self),
                    source_self_id=link_self,
                    kind=(
                        RawObjectKind.FORMULA
                        if name.casefold().endswith(".pdf")
                        else RawObjectKind.FIGURE
                    ),
                    placement=anchor_placement_by_link.get(link_self, AnchoredPlacement.UNKNOWN),
                    label=anchor_label_by_link.get(link_self),
                    anchor_run_id=anchor_run_by_link.get(link_self),
                    asset_ids=(asset_id,),
                    evidence_ids=(link_evidence.id,),
                )
            )

        return _StoryResult(
            story=RawStory(
                id=story_id,
                source_self_id=source_self,
                runs=tuple(runs),
                paragraphs=tuple(paragraphs),
                table_ids=tuple(item.id for item in tables),
                anchored_object_ids=tuple(item.id for item in objects),
                evidence_ids=(story_evidence.id,),
            ),
            tables=tuple(tables),
            objects=tuple(objects),
            assets=tuple(assets),
            links=tuple(links),
            evidence=tuple(evidence),
        )

    def _parse_layout(
        self,
        roots: dict[str, etree._Element],
        article_key: str,
        artifact_sha: str,
    ) -> _LayoutResult:
        frames: list[RawTextFrame] = []
        spreads: list[RawSpread] = []
        objects: list[RawAnchoredObject] = []
        assets: list[RawAsset] = []
        links: list[RawLink] = []
        evidence: list[Evidence] = []
        page_counter = 0
        for path, root in sorted(roots.items()):
            if not path.startswith("Spreads/"):
                continue
            spread_element = next(
                element for element in _elements(root, "Spread") if element.get("Self")
            )
            spread_self = spread_element.get("Self", PurePosixPath(path).stem)
            pages = _elements(spread_element, "Page")
            page_indices = tuple(range(page_counter, page_counter + len(pages)))
            page_counter += len(pages)
            spread_frame_ids: list[str] = []
            for frame_element in _elements(spread_element, "TextFrame"):
                source_self = frame_element.get("Self")
                parent_story = frame_element.get("ParentStory")
                if source_self is None or parent_story is None:
                    continue
                transform = _numbers(frame_element.get("ItemTransform"), 6)
                anchors = [
                    _numbers(item.get("Anchor"), 2)
                    for item in _elements(frame_element, "PathPointType")
                ]
                first = transform[4] + min((point[0] for point in anchors), default=0.0)
                second = transform[5] + min((point[1] for point in anchors), default=0.0)
                first_max = transform[4] + max((point[0] for point in anchors), default=0.0)
                second_max = transform[5] + max((point[1] for point in anchors), default=0.0)
                local_page = 0 if len(pages) < 2 or transform[4] < 0 else 1
                page_index = page_indices[min(local_page, len(page_indices) - 1)]
                frame_evidence = self._evidence(
                    article_key, artifact_sha, path, source_self, "IDML text frame"
                )
                evidence.append(frame_evidence)
                frame_id = stable_id(article_key, "frame", source_self)
                spread_frame_ids.append(frame_id)
                frames.append(
                    RawTextFrame(
                        id=frame_id,
                        source_self_id=source_self,
                        parent_story_id=stable_id(article_key, "story", parent_story),
                        page_index=page_index,
                        box=BoundingBox(
                            x=first,
                            y=second,
                            width=max(0.0, first_max - first),
                            height=max(0.0, second_max - second),
                        ),
                        transform=transform,
                        previous_frame_id=(
                            stable_id(article_key, "frame", previous)
                            if (previous := _reference(frame_element.get("PreviousTextFrame")))
                            else None
                        ),
                        next_frame_id=(
                            stable_id(article_key, "frame", following)
                            if (following := _reference(frame_element.get("NextTextFrame")))
                            else None
                        ),
                        evidence_ids=(frame_evidence.id,),
                    )
                )
            spread_evidence = self._evidence(
                article_key, artifact_sha, path, spread_self, "IDML spread"
            )
            evidence.append(spread_evidence)
            for link_position, link in enumerate(_elements(spread_element, "Link")):
                link_self = link.get("Self", f"{spread_self}:link:{link_position}")
                name = _sanitized_asset_name(link.get("LinkResourceURI", ""))
                asset_id = stable_id(article_key, "layout-asset", link_self)
                link_evidence = self._evidence(
                    article_key,
                    artifact_sha,
                    path,
                    link_self,
                    "Sanitized spread asset link",
                )
                evidence.append(link_evidence)
                media_type = _media_type(name, link.get("LinkResourceFormat"))
                assets.append(
                    RawAsset(
                        id=asset_id,
                        logical_path=name,
                        media_type=media_type,
                        external=True,
                        evidence_ids=(link_evidence.id,),
                    )
                )
                links.append(
                    RawLink(
                        id=stable_id(article_key, "layout-link", link_self),
                        source_id=stable_id(article_key, "spread", spread_self),
                        target=asset_id,
                        relationship="external-layout-asset",
                        evidence_ids=(link_evidence.id,),
                    )
                )
                objects.append(
                    RawAnchoredObject(
                        id=stable_id(article_key, "layout-object", link_self),
                        source_self_id=link_self,
                        kind=(
                            RawObjectKind.FORMULA
                            if media_type == "application/pdf"
                            else RawObjectKind.FIGURE
                        ),
                        asset_ids=(asset_id,),
                        page_index=page_indices[0] if page_indices else None,
                        evidence_ids=(link_evidence.id,),
                    )
                )
            spreads.append(
                RawSpread(
                    id=stable_id(article_key, "spread", spread_self),
                    source_self_id=spread_self,
                    page_indices=page_indices,
                    frame_ids=tuple(spread_frame_ids),
                    evidence_ids=(spread_evidence.id,),
                )
            )
        return _LayoutResult(
            frames=tuple(frames),
            spreads=tuple(spreads),
            objects=tuple(objects),
            assets=tuple(assets),
            links=tuple(links),
            evidence=tuple(evidence),
        )

    def _reading_order(
        self,
        stories: tuple[RawStory, ...],
        frames: tuple[RawTextFrame, ...],
        story_list: tuple[str, ...],
    ) -> tuple[tuple[str, ...], tuple[ReadingOrderIssue, ...]]:
        frames_by_story: defaultdict[str, list[RawTextFrame]] = defaultdict(list)
        for frame in frames:
            frames_by_story[frame.parent_story_id].append(frame)
        source_hint = {source_id: index for index, source_id in enumerate(story_list)}
        issues: list[ReadingOrderIssue] = []
        first_positions: dict[str, tuple[int, float, float, int]] = {}
        for story in stories:
            story_frames = frames_by_story[story.id]
            starts = [item for item in story_frames if item.previous_frame_id is None]
            if not story_frames:
                issues.append(ReadingOrderIssue(code="story_without_frame", story_id=story.id))
                first_positions[story.id] = (
                    10**9,
                    0.0,
                    0.0,
                    source_hint.get(story.source_self_id, 10**9),
                )
                continue
            if len(starts) != 1:
                issues.append(
                    ReadingOrderIssue(
                        code="invalid_thread_start_count",
                        story_id=story.id,
                        details={"start_count": len(starts)},
                    )
                )
            frame_by_id = {frame.id: frame for frame in story_frames}
            for frame in story_frames:
                if frame.next_frame_id:
                    following = frame_by_id.get(frame.next_frame_id)
                    if following is None or following.previous_frame_id != frame.id:
                        issues.append(
                            ReadingOrderIssue(
                                code="non_reciprocal_thread_link",
                                story_id=story.id,
                                frame_id=frame.id,
                            )
                        )
            visited: set[str] = set()
            cursor = starts[0] if len(starts) == 1 else None
            while cursor is not None and cursor.id not in visited:
                visited.add(cursor.id)
                cursor = frame_by_id.get(cursor.next_frame_id or "")
            if cursor is not None:
                issues.append(
                    ReadingOrderIssue(
                        code="thread_cycle",
                        story_id=story.id,
                        frame_id=cursor.id,
                    )
                )
            if len(starts) == 1 and len(visited) != len(story_frames):
                issues.append(
                    ReadingOrderIssue(
                        code="thread_disconnected",
                        story_id=story.id,
                        details={
                            "visited_frames": len(visited),
                            "story_frames": len(story_frames),
                        },
                    )
                )
            first = min(
                starts or story_frames,
                key=lambda item: (item.page_index, item.box.y, item.box.x),
            )
            first_positions[story.id] = (
                first.page_index,
                first.box.y,
                first.box.x,
                source_hint.get(story.source_self_id, 10**9),
            )
        ordered = tuple(sorted((story.id for story in stories), key=first_positions.__getitem__))
        return ordered, tuple(issues)
