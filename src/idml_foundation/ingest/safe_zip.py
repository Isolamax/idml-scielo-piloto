import stat
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile, ZipInfo

from idml_foundation.settings import Settings

NESTED_ARCHIVE_SUFFIXES = {
    ".7z",
    ".bz2",
    ".gz",
    ".idml",
    ".rar",
    ".tar",
    ".tgz",
    ".xz",
    ".zip",
}


class UnsafeArchiveError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ArchiveInspection:
    entry_count: int
    total_uncompressed_bytes: int
    max_compression_ratio: float


def _validate_name(name: str) -> PurePosixPath:
    if "\x00" in name or "\\" in name:
        raise UnsafeArchiveError("invalid_path", "archive contains an invalid path")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise UnsafeArchiveError("path_traversal", "archive contains path traversal")
    if path.parts[0].endswith(":"):
        raise UnsafeArchiveError("absolute_path", "archive contains an absolute path")
    return path


def _validate_entry_type(info: ZipInfo) -> None:
    mode = (info.external_attr >> 16) & 0xFFFF
    if not mode:
        return
    kind = stat.S_IFMT(mode)
    if kind not in {0, stat.S_IFREG, stat.S_IFDIR}:
        raise UnsafeArchiveError("special_entry", "symlinks and special entries are forbidden")


def inspect_idml(data: bytes, settings: Settings) -> ArchiveInspection:
    if len(data) > settings.upload_max_bytes:
        raise UnsafeArchiveError("upload_too_large", "upload exceeds configured size limit")
    try:
        archive = ZipFile(BytesIO(data))
    except BadZipFile as exc:
        raise UnsafeArchiveError("invalid_zip", "IDML is not a valid ZIP package") from exc

    with archive:
        infos = archive.infolist()
        if len(infos) > settings.zip_max_entries:
            raise UnsafeArchiveError("too_many_entries", "archive has too many entries")

        names: set[str] = set()
        total = 0
        max_ratio = 1.0
        for info in infos:
            path = _validate_name(info.filename)
            normalized = path.as_posix().casefold()
            if normalized in names:
                raise UnsafeArchiveError("duplicate_entry", "archive has duplicate entry names")
            names.add(normalized)
            _validate_entry_type(info)
            if info.flag_bits & 0x1:
                raise UnsafeArchiveError("encrypted_entry", "encrypted entries are forbidden")
            total += info.file_size
            if total > settings.zip_max_uncompressed_bytes:
                raise UnsafeArchiveError("expanded_too_large", "expanded archive exceeds limit")
            ratio = info.file_size / max(info.compress_size, 1)
            max_ratio = max(max_ratio, ratio)
            if ratio > settings.zip_max_ratio and info.file_size > 1024:
                raise UnsafeArchiveError("compression_ratio", "suspicious compression ratio")
            if path.suffix.casefold() in NESTED_ARCHIVE_SUFFIXES:
                raise UnsafeArchiveError("nested_archive", "nested archives are forbidden")

        required = {"mimetype", "designmap.xml"}
        if not required.issubset(names):
            raise UnsafeArchiveError("invalid_idml", "required IDML entries are missing")
        mime = archive.read("mimetype")
        if mime != b"application/vnd.adobe.indesign-idml-package":
            raise UnsafeArchiveError("invalid_mimetype", "unexpected IDML mimetype")

    return ArchiveInspection(
        entry_count=len(infos),
        total_uncompressed_bytes=total,
        max_compression_ratio=max_ratio,
    )
