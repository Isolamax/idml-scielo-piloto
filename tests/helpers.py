from io import BytesIO
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile


def make_idml(*, extra_name: str | None = None, extra_data: bytes = b"x") -> bytes:
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr(
            "mimetype",
            b"application/vnd.adobe.indesign-idml-package",
            compress_type=ZIP_STORED,
        )
        archive.writestr("designmap.xml", b"<Document/>", compress_type=ZIP_DEFLATED)
        if extra_name:
            archive.writestr(extra_name, extra_data, compress_type=ZIP_DEFLATED)
    return output.getvalue()
