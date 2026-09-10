from __future__ import annotations

import hashlib

import pytest
from lxml import etree

from idml_foundation.pipeline.service import DeterministicPipeline
from idml_foundation.release.editorial_enrichment import (
    build_editorial_enrichment_catalog,
)
from tests.phase3_helpers import synthetic_idml


def _approved_xml() -> bytes:
    return b"""<article><front><article-meta>
      <article-id pub-id-type="other">00212</article-id>
      <author-notes>
        <fn><label>Associate editor:</label><p>Bruno Costa  https://orcid.org/0000-0002-1825-0097</p></fn>
        <fn><label>Scientific editor:</label><p>Carla Souza  https://orcid.org/0000-0002-1694-233X</p></fn>
      </author-notes>
    </article-meta></front></article>"""


def test_editorial_catalog_enriches_identifiers_and_orcids_atomically() -> None:
    source = synthetic_idml(include_correspondence=True)
    original = DeterministicPipeline().run(
        source,
        logical_name="ESA_2024001_AOP.idml",
    )
    catalog, report = build_editorial_enrichment_catalog(
        article=original.canonical,
        source_idml_sha256=hashlib.sha256(source).hexdigest(),
        approved_xml=_approved_xml(),
        corpus_id="esa-fixture",
    )

    enriched = DeterministicPipeline(editorial_enrichment_catalog=catalog).run(
        source,
        logical_name="ESA_2024001_AOP.idml",
    )
    root = etree.fromstring(enriched.xml)

    assert enriched.validation.valid is True
    assert root.xpath("string(front/article-meta/article-id[@pub-id-type='other'])") == "00212"
    assert root.xpath("count(front/article-meta/article-id[@pub-id-type='publisher-id'])") == 0.0
    assert root.xpath("string(front/article-meta/elocation-id)") == "e20240001"
    assert root.xpath("count(back/fn-group/fn[contains(., 'orcid.org')])") == 2.0
    assert report["editorial_orcids"] == 2
    assert report["restricted_content_emitted"] is False
    assert "associate_editor_orcid_requires_enrichment" not in enriched.canonical.review_reasons
    assert any(
        reason.startswith("editorial_enrichment_pending_human:")
        for reason in enriched.canonical.review_reasons
    )


def test_editorial_catalog_is_bound_to_exact_source() -> None:
    source = synthetic_idml(include_correspondence=True)
    original = DeterministicPipeline().run(
        source,
        logical_name="ESA_2024001_AOP.idml",
    )
    catalog, _ = build_editorial_enrichment_catalog(
        article=original.canonical,
        source_idml_sha256=hashlib.sha256(source).hexdigest(),
        approved_xml=_approved_xml(),
        corpus_id="esa-fixture",
    )

    with pytest.raises(ValueError, match="source IDML hash mismatch"):
        catalog.apply(original.canonical, source_idml_sha256="0" * 64)
