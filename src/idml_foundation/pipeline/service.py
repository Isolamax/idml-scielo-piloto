from dataclasses import dataclass
from pathlib import Path

from idml_foundation.ai.formula_catalog import FormulaTranscriptionCatalog
from idml_foundation.domain.canonical import CanonicalArticle
from idml_foundation.domain.raw import RawArticle
from idml_foundation.pipeline.canonical_mapper import CanonicalMapper
from idml_foundation.pipeline.idml_parser import IdmlParser
from idml_foundation.pipeline.jats_builder import JatsBuilder
from idml_foundation.pipeline.profile import JournalProfile, load_profile
from idml_foundation.pipeline.validation import OfflineJatsValidator, ValidationReport
from idml_foundation.release.editorial_enrichment import EditorialEnrichmentCatalog
from idml_foundation.settings import Settings


@dataclass(frozen=True)
class PipelineResult:
    raw: RawArticle
    canonical: CanonicalArticle
    xml: bytes
    validation: ValidationReport


class DeterministicPipeline:
    def __init__(
        self,
        *,
        profile: JournalProfile | None = None,
        vendor_directory: Path | None = None,
        settings: Settings | None = None,
        formula_catalog: FormulaTranscriptionCatalog | None = None,
        editorial_enrichment_catalog: EditorialEnrichmentCatalog | None = None,
    ) -> None:
        repository_root = Path(__file__).resolve().parents[3]
        self._parser = IdmlParser(settings)
        selected_profile = profile or load_profile()
        self._mapper = CanonicalMapper(selected_profile)
        self._formula_catalog = formula_catalog
        self._editorial_enrichment_catalog = editorial_enrichment_catalog
        self._builder = JatsBuilder(sps_version=selected_profile.sps_version)
        self._validator = OfflineJatsValidator(
            vendor_directory or repository_root / "vendor" / "jats" / "1.3"
        )

    def run(self, data: bytes, *, logical_name: str) -> PipelineResult:
        raw = self._parser.parse(data, logical_name=logical_name)
        canonical = self._mapper.map(raw)
        if self._formula_catalog is not None:
            canonical = self._formula_catalog.apply(
                canonical,
                source_idml_sha256=raw.source_artifact_sha256,
            )
        if self._editorial_enrichment_catalog is not None:
            canonical = self._editorial_enrichment_catalog.apply(
                canonical,
                source_idml_sha256=raw.source_artifact_sha256,
            )
        xml = self._builder.build(canonical)
        report = self._validator.validate(
            xml,
            asset_names={item.logical_name for item in canonical.assets},
        )
        return PipelineResult(raw=raw, canonical=canonical, xml=xml, validation=report)
