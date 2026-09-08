from pathlib import Path

import pytest
from lxml import etree

from idml_foundation.domain.canonical import (
    BackMatter,
    CanonicalArticle,
    Contributor,
    ContributorName,
    CrossReference,
    FieldState,
    FormulaBlock,
    FormulaRepresentation,
    FrontMatter,
    FundingStatement,
    Identifier,
    InlineKind,
    InlineNode,
    NoteBlock,
    Paragraph,
    Reference,
    RichText,
    SourcedText,
    TableBlock,
    TableCellSpan,
)
from idml_foundation.pipeline.jats_builder import XLINK_NS, JatsBuilder
from idml_foundation.pipeline.validation import OfflineJatsValidator, ValidationSeverity
from tests.domain_helpers import canonical_article, sourced

VENDOR = Path(__file__).parents[1] / "vendor" / "jats" / "1.3"
EVIDENCE = ("evidence-source-1",)


def rich(identifier: str, value: str) -> RichText:
    return RichText(
        plain=sourced(value),
        inlines=(
            InlineNode(
                id=f"inline-{identifier}",
                kind=InlineKind.TEXT,
                text=value,
                evidence_ids=EVIDENCE,
            ),
        ),
    )


def missing_rich() -> RichText:
    return RichText(plain=SourcedText(state=FieldState.MISSING))


def xref_paragraph(
    identifier: str,
    label: str,
    target_id: str,
    reference_type: str,
) -> Paragraph:
    return Paragraph(
        id=identifier,
        content=RichText(
            plain=sourced(label),
            inlines=(
                InlineNode(
                    id=f"inline-{identifier}",
                    kind=InlineKind.CROSS_REFERENCE,
                    text=label,
                    target_id=target_id,
                    evidence_ids=EVIDENCE,
                ),
            ),
        ),
        cross_references=(
            CrossReference(
                target_id=target_id,
                reference_type=reference_type,  # type: ignore[arg-type]
                evidence_ids=EVIDENCE,
            ),
        ),
        evidence_ids=EVIDENCE,
    )


def complete_article() -> CanonicalArticle:
    base = canonical_article()
    affiliation = base.front.affiliations[0].model_copy(
        update={
            "department": sourced("Department of Sanitary Engineering"),
            "city": sourced("Rio de Janeiro"),
            "state_or_province": sourced("RJ"),
            "country": sourced("Brazil"),
            "ror": sourced("https://ror.org/012345678"),
        }
    )
    contributor = Contributor(
        id="contributor-1",
        contributor_type="person",
        name=ContributorName(
            given_names=sourced("Ana"),
            surname=sourced("Silva"),
            prefix=sourced("Dr."),
            suffix=sourced("Jr."),
        ),
        orcid=sourced("0000-0002-1825-0097"),
        affiliation_ids=(affiliation.id,),
        roles=("Conceptualization", "Writing"),
        corresponding=True,
        email=sourced("ana@example.org"),
        evidence_ids=EVIDENCE,
    )
    table = TableBlock(
        id="table-1",
        label=sourced("Table 1"),
        caption=rich("table-caption", "Water quality"),
        rows=(
            (rich("cell-00", "Merged heading"), missing_rich()),
            (rich("cell-10", "A"), rich("cell-11", "B")),
        ),
        cell_spans=(TableCellSpan(row=0, column=0, column_span=2),),
        footnotes=(rich("table-note", "Source: authors."),),
        evidence_ids=EVIDENCE,
    )
    formula = FormulaBlock(
        id="formula-1",
        display=True,
        source=sourced("x=1"),
        representation=FormulaRepresentation.LATEX,
        label=sourced("(1)"),
        evidence_ids=EVIDENCE,
    )
    note = NoteBlock(
        id="note-1",
        note_type="other",
        content=rich("note", "Editorial note."),
        evidence_ids=EVIDENCE,
    )
    reference = Reference(
        id="reference-1",
        mixed_citation=rich(
            "reference",
            "Silva A. Water treatment. Example Journal. 2025. doi:10.1234/example.1",
        ),
        identifiers=(Identifier(kind="doi", value=sourced("10.1234/example.1")),),
        authors=(sourced("Silva A"),),
        year=sourced("2025"),
        title=sourced("Water treatment"),
        source=sourced("Example Journal"),
        evidence_ids=EVIDENCE,
    )
    first_section = base.body[0].model_copy(
        update={
            "blocks": (
                *base.body[0].blocks,
                xref_paragraph("xref-table", "Table 1", table.id, "table"),
                table,
                xref_paragraph("xref-formula", "Equation 1", formula.id, "formula"),
                formula,
                xref_paragraph("xref-note", "Note 1", note.id, "note"),
                xref_paragraph("xref-reference", "[1]", reference.id, "reference"),
            )
        }
    )
    front = FrontMatter(
        journal=base.front.journal.model_copy(
            update={
                "abbreviated_title": sourced("Ex. J."),
                "identifiers": (Identifier(kind="eissn", value=sourced("1234-5678")),),
            }
        ),
        article_identifiers=(
            Identifier(kind="publisher-id", value=sourced("e20260001")),
            Identifier(kind="doi", value=sourced("10.1234/example.article")),
        ),
        article_category=base.front.article_category,
        titles=base.front.titles,
        contributors=(contributor,),
        affiliations=(affiliation,),
        publication_date=sourced("2026-09-08"),
        volume=sourced("31"),
        issue=sourced("1"),
        abstracts=base.front.titles,
        keywords=base.front.titles,
        license_text=sourced("Creative Commons Attribution 4.0 International."),
        funding=(
            FundingStatement(
                agency=sourced("Example Foundation"),
                award_id=sourced("Grant 42"),
                statement=sourced("Funded by Example Foundation."),
            ),
        ),
    )
    return base.model_copy(
        update={
            "front": front,
            "body": (first_section,),
            "back": BackMatter(
                acknowledgements=(
                    Paragraph(
                        id="acknowledgement-1",
                        content=rich("acknowledgement", "We thank the laboratory."),
                        evidence_ids=EVIDENCE,
                    ),
                ),
                contribution_statement=sourced("Ana Silva designed and wrote the study."),
                data_availability=sourced("Data are available in the repository."),
                conflicts=sourced("The authors declare no conflicts."),
                notes=(note,),
                references=(reference,),
            ),
        }
    )


def test_builder_emits_complete_dtd_valid_and_deterministic_jats() -> None:
    article = CanonicalArticle.model_validate(complete_article().model_dump(mode="json"))
    first = JatsBuilder().build(article)
    second = JatsBuilder().build(article)
    report = OfflineJatsValidator(VENDOR).validate(
        first,
        asset_names={asset.logical_name for asset in article.assets},
    )
    root = etree.fromstring(first)

    assert first == second
    assert report.valid, report.issues
    assert root.xpath("string(front/article-meta/contrib-group/contrib/contrib-id)").endswith(
        "0000-0002-1825-0097"
    )
    assert root.xpath("string(front/article-meta/pub-date/@iso-8601-date)") == "2026-09-08"
    assert root.xpath("string(front/article-meta/volume)") == "31"
    assert root.xpath("string(front/article-meta/issue)") == "1"
    assert root.xpath("count(front/article-meta/permissions/license/license-p)") == 1.0
    assert root.xpath("count(front/article-meta/funding-group/award-group)") == 1.0
    assert root.xpath("count(back/ack)") == 1.0
    assert root.xpath("count(back/sec)") == 3.0
    assert root.xpath("count(back/ref-list/ref/element-citation/pub-id)") == 1.0


def test_builder_preserves_table_spans_and_infers_every_xref_type() -> None:
    xml = JatsBuilder().build(complete_article())
    root = etree.fromstring(xml)

    assert root.xpath("string(body//table-wrap/table/tbody/tr[1]/td/@colspan)") == "2"
    assert root.xpath("count(body//table-wrap/table/tbody/tr[1]/td)") == 1.0
    assert set(root.xpath("body//xref/@ref-type")) >= {
        "fig",
        "table",
        "disp-formula",
        "fn",
        "bibr",
    }


@pytest.mark.parametrize(
    ("mutation", "code"),
    (
        (lambda xml: xml.replace(b" encoding='UTF-8'", b"", 1), "invalid-xml-declaration"),
        (lambda xml: xml.replace(b"sps-1.10", b"sps-9.99", 1), "unsupported-sps-version"),
        (lambda xml: xml.replace(b"1234-5678", b"invalid"), "invalid-issn"),
        (
            lambda xml: xml.replace(b"https://example.org", b"javascript:alert(1)", 1),
            "unsafe-external-link",
        ),
        (
            lambda xml: xml.replace(b"article-gf01.jpg", b"../escape.jpg", 1),
            "unsafe-asset-reference",
        ),
        (lambda xml: xml.replace(b'rid="figure-1"', b'rid="missing"', 1), "orphan-rid"),
        (
            lambda xml: xml.replace(b"Synthetic title", "Synthetic\u200b title".encode(), 1),
            "forbidden-invisible-character",
        ),
    ),
)
def test_validator_rejects_invalid_xml_contracts(mutation: object, code: str) -> None:
    article = complete_article()
    xml = JatsBuilder().build(article)
    if code == "unsafe-external-link":
        xml = xml.replace(
            b"</p>",
            (
                b'<ext-link xmlns:xlink="http://www.w3.org/1999/xlink" '
                b'ext-link-type="uri" xlink:href="https://example.org">link</ext-link></p>'
            ),
            1,
        )
    report = OfflineJatsValidator(VENDOR).validate(
        mutation(xml),  # type: ignore[operator]
        asset_names={asset.logical_name for asset in article.assets},
    )

    assert not report.valid
    assert any(
        issue.code == code and issue.severity == ValidationSeverity.ERROR for issue in report.issues
    )


def test_builder_rejects_an_unimplemented_sps_contract() -> None:
    with pytest.raises(ValueError, match=r"only SPS 1\.10"):
        JatsBuilder(sps_version="sps-2.0")


def test_validator_checks_inline_assets_too() -> None:
    article = complete_article()
    xml = (
        JatsBuilder()
        .build(article)
        .replace(
            b"</p>",
            (f'<inline-graphic xmlns:xlink="{XLINK_NS}" xlink:href="unknown.png"/></p>'.encode()),
            1,
        )
    )
    report = OfflineJatsValidator(VENDOR).validate(
        xml,
        asset_names={asset.logical_name for asset in article.assets},
    )

    assert any(issue.code == "unknown-asset-reference" for issue in report.issues)


def test_table_span_contract_rejects_overlap_and_out_of_bounds() -> None:
    rows = ((rich("a", "A"), rich("b", "B")), (rich("c", "C"), rich("d", "D")))
    with pytest.raises(ValueError, match="overlap"):
        TableBlock(
            id="table-overlap",
            label=sourced("Table"),
            caption=rich("caption-overlap", "Caption"),
            rows=rows,
            cell_spans=(
                TableCellSpan(row=0, column=0, column_span=2),
                TableCellSpan(row=0, column=1, row_span=2),
            ),
        )
    with pytest.raises(ValueError, match="exceeds"):
        TableBlock(
            id="table-bounds",
            label=sourced("Table"),
            caption=rich("caption-bounds", "Caption"),
            rows=rows,
            cell_spans=(TableCellSpan(row=1, column=0, row_span=2),),
        )
    with pytest.raises(ValueError, match="covered"):
        TableBlock(
            id="table-covered-content",
            label=sourced("Table"),
            caption=rich("caption-covered", "Caption"),
            rows=rows,
            cell_spans=(TableCellSpan(row=0, column=0, column_span=2),),
        )


def test_non_present_back_fields_do_not_create_an_empty_back() -> None:
    base = canonical_article()
    missing = SourcedText(state=FieldState.MISSING)
    article = base.model_copy(
        update={
            "back": BackMatter(
                contribution_statement=missing,
                data_availability=missing,
                conflicts=missing,
            )
        }
    )

    assert etree.fromstring(JatsBuilder().build(article)).find("back") is None
