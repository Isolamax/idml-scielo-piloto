import re

from idml_foundation.pipeline.canonical_mapper import (
    _AFFILIATION,
    _AFFILIATION_NO_DEPARTMENT,
    _split_trailing_country,
    _strip_affiliation_label,
)
from idml_foundation.pipeline.country_codes import iso_country_code


def test_country_names_in_three_languages_map_to_iso_codes() -> None:
    assert [
        iso_country_code(name)
        for name in ("Portugal", "United States", "Estados Unidos", "EUA", "Alemanha", "España")
    ] == ["PT", "US", "US", "US", "DE", "ES"]
    assert iso_country_code("Brazil.") == "BR"
    assert iso_country_code("Atlantis") is None


def test_affiliation_labels_are_stripped_only_when_they_are_labels() -> None:
    assert _strip_affiliation_label("1Universidade Federal", 1) == "Universidade Federal"
    assert _strip_affiliation_label("II Universidade Federal", 2) == "Universidade Federal"
    assert _strip_affiliation_label("IVNTS Electronic Control", 4) == "NTS Electronic Control"
    # Not the expected ordinal: an institution that merely starts with roman letters is kept.
    assert _strip_affiliation_label("IVNTS Electronic Control", 2) == "IVNTS Electronic Control"
    assert _strip_affiliation_label("Instituto Federal", 1) == "Instituto Federal"


def test_multi_segment_city_and_affiliation_without_department() -> None:
    match = _AFFILIATION.fullmatch(
        "Universidad Exemplo, School of X \u2013 Santander, Bucaramanga, Colombia."
    )
    assert isinstance(match, re.Match)
    parts = _split_trailing_country(match).groupdict()
    assert (parts["city"], parts["country"]) == ("Santander, Bucaramanga", "Colombia")
    plain = _AFFILIATION_NO_DEPARTMENT.fullmatch("NTS Electronic Control \u2013 Bogotá, Colombia.")
    assert plain is not None and plain.group("country") == "Colombia"
