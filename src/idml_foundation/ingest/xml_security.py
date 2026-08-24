from lxml import etree


class UnsafeXmlError(ValueError):
    pass


def parse_untrusted_xml(data: bytes) -> etree._Element:
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
    return etree.fromstring(data, parser=parser)
