"""Content-free comprehensive Canonical Article fixture for the V-05 gate."""

from idml_foundation.domain.canonical import (
    BackMatter,
    CanonicalArticle,
    Contributor,
    ContributorName,
    CrossReference,
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
from tests.domain_helpers import canonical_article, sourced

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
    from idml_foundation.domain.canonical import FieldState

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
