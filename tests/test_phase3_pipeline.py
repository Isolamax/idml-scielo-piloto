import hashlib
import json
from pathlib import Path

import pytest
from lxml import etree

from idml_foundation.domain.common import canonical_bytes
from idml_foundation.pipeline.canonical_mapper import CanonicalMapper
from idml_foundation.pipeline.idml_parser import IdmlParser, style_prefix
from idml_foundation.pipeline.jats_builder import IdRegistry, IdRegistryError, JatsBuilder
from idml_foundation.pipeline.profile import load_profile
from idml_foundation.pipeline.service import DeterministicPipeline
from idml_foundation.pipeline.validation import OfflineJatsValidator, ValidationSeverity
from tests.phase3_helpers import synthetic_idml


def test_parser_reconstructs_raw_graph_and_sanitizes_external_paths() -> None:
    raw = IdmlParser().parse(synthetic_idml(), logical_name="ESA_2024001_AOP.idml")

    assert len(raw.stories) == 4
    assert len(raw.frames) == 4
    assert len(raw.reading_order) == 4
    assert not raw.reading_order_issues
    assert raw.assets[0].logical_path == "Figure 1.jpg"
    assert "private" not in canonical_bytes(raw).decode()
    assert style_prefix("05.0.texto") == "05.0"
    assert style_prefix("unknown") is None


def test_mapper_records_missing_and_ambiguities_without_using_gold_xml() -> None:
    raw = IdmlParser().parse(synthetic_idml(), logical_name="ESA_2024001_AOP.idml")
    article = CanonicalMapper(load_profile()).map(raw)

    assert article.article_id == "e20240001"
    assert article.front.publication_date.value is None
    assert len(article.front.contributors) == 1
    assert len(article.back.references) == 2
    assert "external_assets_require_package_resolution" in article.review_reasons


def test_mapper_nests_level_two_sections_under_the_preceding_level_one() -> None:
    raw = IdmlParser().parse(
        synthetic_idml(include_subsection=True),
        logical_name="ESA_2024001_AOP.idml",
    )
    article = CanonicalMapper(load_profile()).map(raw)

    assert len(article.body) == 2
    introduction = article.body[0]
    assert introduction.title.value == "Introduction"
    assert len(introduction.children) == 1
    assert introduction.children[0].level == 2
    assert introduction.children[0].title.value == "Nested method details"
    assert introduction.children[0].blocks[0].content.plain.value == "Nested content"


def test_pipeline_preserves_anchored_pdf_formula_as_reviewable_image() -> None:
    result = DeterministicPipeline().run(
        synthetic_idml(include_formula=True),
        logical_name="ESA_2024001_AOP.idml",
    )
    root = etree.fromstring(result.xml)

    formula = result.canonical.body[0].blocks[-1]
    assert formula.kind == "formula"
    assert formula.representation == "image"
    assert formula.source.value == "Equations.pdf"
    assert any(
        reason.startswith("formula_requires_mathml_transcription:")
        for reason in result.canonical.review_reasons
    )
    assert root.xpath("count(body//disp-formula/graphic)") == 1.0
    assert result.validation.valid


def test_pipeline_is_byte_deterministic_and_offline_dtd_valid() -> None:
    pipeline = DeterministicPipeline()
    first = pipeline.run(synthetic_idml(), logical_name="ESA_2024001_AOP.idml")
    second = pipeline.run(synthetic_idml(), logical_name="ESA_2024001_AOP.idml")

    assert first.xml == second.xml
    assert canonical_bytes(first.raw) == canonical_bytes(second.raw)
    assert canonical_bytes(first.canonical) == canonical_bytes(second.canonical)
    assert first.validation == second.validation
    assert first.validation.valid
    assert first.validation.issues
    assert all(
        item.code == "uncited-reference" and item.severity == ValidationSeverity.WARNING
        for item in first.validation.issues
    )


def test_id_registry_rejects_duplicates_and_orphans() -> None:
    registry = IdRegistry()
    registry.register("known")
    with pytest.raises(IdRegistryError, match="duplicate"):
        registry.register("known")
    with pytest.raises(IdRegistryError, match="orphan"):
        registry.resolve("missing")


def test_validator_normalizes_malformed_xml_and_unsafe_assets() -> None:
    vendor = Path(__file__).parents[1] / "vendor" / "jats" / "1.3"
    validator = OfflineJatsValidator(vendor)
    malformed = validator.validate(b"<article>")
    assert not malformed.valid
    assert malformed.issues[0].code == "xml-not-well-formed"

    raw = IdmlParser().parse(synthetic_idml(), logical_name="ESA_2024001_AOP.idml")
    article = CanonicalMapper(load_profile()).map(raw)
    xml = JatsBuilder().build(article).replace(b"Figure 1.jpg", b"https://bad.invalid/x")
    report = validator.validate(xml)
    assert not report.valid
    assert any(
        item.code == "unsafe-asset-reference" and item.severity == ValidationSeverity.ERROR
        for item in report.issues
    )


def test_validator_checks_bibliography_reference_semantics() -> None:
    vendor = Path(__file__).parents[1] / "vendor" / "jats" / "1.3"
    validator = OfflineJatsValidator(vendor)
    xml = DeterministicPipeline().run(
        synthetic_idml(), logical_name="ESA_2024001_AOP.idml"
    ).xml
    root = etree.fromstring(xml)
    reference_ids = [item.get("id") for item in root.xpath("//ref")]
    cited = xml.replace(
        b"</p>",
        (
            f'<xref ref-type="bibr" rid="{" ".join(reference_ids)}">[1,2]</xref></p>'
        ).encode(),
        1,
    )
    cited_report = validator.validate(cited)
    assert not any(item.code in {"orphan-rid", "uncited-reference"} for item in cited_report.issues)

    figure_id = str(root.xpath("//fig/@id")[0])
    wrong_target = xml.replace(
        b"</p>",
        f'<xref ref-type="bibr" rid="{figure_id}">[x]</xref></p>'.encode(),
        1,
    )
    wrong_report = validator.validate(wrong_target)
    assert any(item.code == "invalid-bibliography-rid-target" for item in wrong_report.issues)


def test_vendored_jats_files_match_pinned_provenance() -> None:
    vendor = Path(__file__).parents[1] / "vendor" / "jats" / "1.3"
    provenance = json.loads((vendor / "SOURCE.json").read_text(encoding="utf-8"))
    assert provenance["archive_sha256"] == (
        "41ddeaf6eeb04eb64244e9894212e0aaeafdbb9114d20602da2d855ad39b9b7b"
    )
    for name, expected in provenance["files"].items():
        assert hashlib.sha256((vendor / name).read_bytes()).hexdigest() == expected
