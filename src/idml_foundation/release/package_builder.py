from __future__ import annotations

import hashlib
import mimetypes
from enum import StrEnum
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from lxml import etree
from pydantic import Field, model_validator

from idml_foundation.domain.common import SHA256_PATTERN, StrictModel, canonical_bytes

_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)
_XLINK_HREF = "{http://www.w3.org/1999/xlink}href"


class PackageRole(StrEnum):
    XML = "xml"
    PDF = "pdf"
    ASSET = "asset"


class PackageInput(StrictModel):
    name: str
    role: PackageRole
    media_type: str
    data: bytes = Field(repr=False)

    @model_validator(mode="after")
    def package_local_name(self) -> PackageInput:
        path = PurePosixPath(self.name.replace("\\", "/"))
        if path.name != self.name or self.name in {"", ".", ".."}:
            raise ValueError("package files must use a safe basename")
        return self


class ManifestFile(StrictModel):
    name: str
    role: PackageRole
    media_type: str
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=SHA256_PATTERN)


class ConversionManifest(StrictModel):
    manifest_version: str = "1.0.0"
    article_id: str
    profile_id: str
    source_idml_sha256: str = Field(pattern=SHA256_PATTERN)
    candidate_set_sha256: str = Field(pattern=SHA256_PATTERN)
    files: tuple[ManifestFile, ...]
    validator_versions: dict[str, str]


class PackageBuild(StrictModel):
    package_sha256: str = Field(pattern=SHA256_PATTERN)
    package_size_bytes: int = Field(ge=0)
    manifest: ConversionManifest
    archive: bytes = Field(repr=False)


class AssetPayload(StrictModel):
    source_name: str
    data: bytes = Field(repr=False)
    media_type: str | None = None


class PackageBuilder:
    def scielo_files(
        self,
        *,
        package_stem: str,
        xml: bytes,
        pdf: bytes,
        assets: tuple[AssetPayload, ...],
    ) -> tuple[PackageInput, ...]:
        if PurePosixPath(package_stem).name != package_stem:
            raise ValueError("package stem must be a safe basename")
        parser = etree.XMLParser(
            resolve_entities=False,
            load_dtd=False,
            no_network=True,
            recover=False,
            huge_tree=False,
        )
        root = etree.fromstring(xml, parser=parser)
        by_source = {item.source_name: item for item in assets}
        if len(by_source) != len(assets):
            raise ValueError("asset source names must be unique")
        package_assets: list[PackageInput] = []
        used: set[str] = set()
        for position, graphic in enumerate(root.iter("graphic"), start=1):
            source_name = graphic.get(_XLINK_HREF, "")
            payload = by_source.get(source_name)
            if payload is None:
                raise ValueError(f"missing package asset: {source_name}")
            suffix = PurePosixPath(source_name).suffix.casefold() or ".bin"
            target_name = f"{package_stem}-gf{position:02}{suffix}"
            graphic.set(_XLINK_HREF, target_name)
            used.add(source_name)
            package_assets.append(
                PackageInput(
                    name=target_name,
                    role=PackageRole.ASSET,
                    media_type=(
                        payload.media_type
                        or mimetypes.guess_type(target_name)[0]
                        or "application/octet-stream"
                    ),
                    data=payload.data,
                )
            )
        if used != set(by_source):
            raise ValueError("package contains assets not referenced by the XML")
        doctype = str(getattr(root.getroottree().docinfo, "doctype", ""))
        resolved_xml = etree.tostring(
            root,
            encoding="UTF-8",
            xml_declaration=True,
            doctype=doctype,
            pretty_print=False,
        )
        if not isinstance(resolved_xml, bytes):
            raise TypeError("XML serialization did not return bytes")
        return (
            PackageInput(
                name=f"{package_stem}.xml",
                role=PackageRole.XML,
                media_type="application/xml",
                data=resolved_xml,
            ),
            PackageInput(
                name=f"{package_stem}.pdf",
                role=PackageRole.PDF,
                media_type="application/pdf",
                data=pdf,
            ),
            *package_assets,
        )

    def build(
        self,
        *,
        article_id: str,
        profile_id: str,
        source_idml_sha256: str,
        files: tuple[PackageInput, ...],
        validator_versions: dict[str, str],
    ) -> PackageBuild:
        if len({item.name.casefold() for item in files}) != len(files):
            raise ValueError("package filenames must be unique ignoring case")
        roles = [item.role for item in files]
        if roles.count(PackageRole.XML) != 1 or roles.count(PackageRole.PDF) != 1:
            raise ValueError("package requires exactly one XML and one PDF")
        manifest_files = tuple(
            ManifestFile(
                name=item.name,
                role=item.role,
                media_type=item.media_type,
                size_bytes=len(item.data),
                sha256=hashlib.sha256(item.data).hexdigest(),
            )
            for item in sorted(files, key=lambda entry: entry.name.casefold())
        )
        candidate_set_sha = hashlib.sha256(
            b"".join(
                item.name.encode("utf-8") + b"\0" + item.sha256.encode("ascii") + b"\0"
                for item in manifest_files
            )
        ).hexdigest()
        manifest = ConversionManifest(
            article_id=article_id,
            profile_id=profile_id,
            source_idml_sha256=source_idml_sha256,
            candidate_set_sha256=candidate_set_sha,
            files=manifest_files,
            validator_versions=dict(sorted(validator_versions.items())),
        )
        entries = [(item.name, item.data) for item in files]
        entries.append(("conversion-manifest.json", canonical_bytes(manifest)))
        buffer = BytesIO()
        with ZipFile(buffer, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
            for name, data in sorted(entries, key=lambda entry: entry[0].casefold()):
                info = ZipInfo(name, date_time=_ZIP_EPOCH)
                info.compress_type = ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                info.flag_bits = 0x800
                archive.writestr(info, data, compresslevel=9)
        payload = buffer.getvalue()
        return PackageBuild(
            package_sha256=hashlib.sha256(payload).hexdigest(),
            package_size_bytes=len(payload),
            manifest=manifest,
            archive=payload,
        )
