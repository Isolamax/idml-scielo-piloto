from idml_foundation.pipeline.vancouver import numeric_citation_spans, parse_vancouver


def test_journal_reference_with_supplement_and_elocation() -> None:
    ref = parse_vancouver(
        "2. Gomes CS, Souza RPF, Silva AG, et al. Fatores associados: pesquisa, 2019. "
        "Rev Bras Epidemiol. 2021;24(Supl. 2):e210013. https://doi.org/10.1590/x"
    )
    assert ref.label == 2
    assert ref.authors == ("Gomes, CS", "Souza, RPF", "Silva, AG") and ref.et_al
    assert ref.title == "Fatores associados: pesquisa, 2019"
    assert (ref.source, ref.year, ref.volume, ref.issue) == (
        "Rev Bras Epidemiol",
        "2021",
        "24",
        "Supl. 2",
    )
    assert ref.elocation_id == "e210013" and ref.publication_type == "journal"


def test_source_without_period_spaced_pages_and_abbreviated_last_page() -> None:
    ref = parse_vancouver("7. Karasek RA. Job demands. Adm Sci Q 1979; 24(2): 285-308.")
    assert (ref.source, ref.volume, ref.issue, ref.first_page, ref.last_page) == (
        "Adm Sci Q",
        "24",
        "2",
        "285",
        "308",
    )
    assert parse_vancouver("1. Lima AB. T. J Ex. 2020;12:100-5.").last_page == "105"


def test_group_author_webpage_keeps_only_certain_fields() -> None:
    ref = parse_vancouver(
        "1. World Health Organization. Cardiovascular diseases [Internet]. "
        "World Health Organization [accessed on Apr 24, 2024]. Available at: https://x"
    )
    assert ref.collab and ref.authors == ("World Health Organization",)
    assert ref.publication_type == "webpage" and ref.source is None


def test_numeric_citation_spans() -> None:
    assert numeric_citation_spans("1") == [(0, 1, 1)]
    assert [n for _, _, n in numeric_citation_spans("2,3")] == [2, 3]
    assert [n for _, _, n in numeric_citation_spans("4-6")] == [4, 6]
    assert numeric_citation_spans("a") == [] and numeric_citation_spans("2b") == []
