from lxml import etree

MAX_UNTRUSTED_XML_BYTES = 32 * 1024 * 1024


class UnsafeXmlError(ValueError):
    pass


def parse_untrusted_xml(data: bytes) -> etree._Element:
    if len(data) > MAX_UNTRUSTED_XML_BYTES:
        raise UnsafeXmlError("XML exceeds the ingestion size limit")
    if b"<!ENTITY" in data.upper() or b"<!DOCTYPE" in data.upper():
        raise UnsafeXmlError("DOCTYPE and entity declarations are forbidden at ingestion")
    parser = etree.XMLParser(
        resolve_entities=False,
        load_dtd=False,
        no_network=True,
        recover=False,
        huge_tree=False,
        remove_comments=False,
    )
    try:
        root = etree.fromstring(data, parser=parser)
    except (etree.XMLSyntaxError, ValueError) as exc:
        raise UnsafeXmlError("XML is malformed or uses a forbidden construct") from exc
    document = root.getroottree().docinfo
    if (
        bool(getattr(document, "doctype", ""))
        or getattr(document, "internalDTD", None) is not None
        or getattr(document, "externalDTD", None) is not None
    ):
        raise UnsafeXmlError("DOCTYPE and entity declarations are forbidden at ingestion")
    if any(isinstance(element, etree._Entity) for element in root.iter()):
        raise UnsafeXmlError("unresolved entities are forbidden at ingestion")
    return root
