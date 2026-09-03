from __future__ import annotations

from copy import deepcopy

from lxml import etree

MATHML_NS = "http://www.w3.org/1998/Math/MathML"
MAX_MATHML_BYTES = 32_000
_ALLOWED_ELEMENTS = {
    "math",
    "menclose",
    "merror",
    "mfenced",
    "mfrac",
    "mi",
    "mmultiscripts",
    "mn",
    "mo",
    "mover",
    "mpadded",
    "mphantom",
    "mprescripts",
    "mroot",
    "mrow",
    "ms",
    "mspace",
    "msqrt",
    "mstyle",
    "msub",
    "msubsup",
    "msup",
    "mtable",
    "mtd",
    "mtext",
    "mtr",
    "munder",
    "munderover",
    "none",
    "semantics",
    "annotation",
}
_FORBIDDEN_ATTRIBUTE_NAMES = {"href", "src", "actiontype"}


def parse_mathml_fragment(value: str, *, display: bool) -> etree._Element:
    encoded = value.encode("utf-8")
    if not encoded or len(encoded) > MAX_MATHML_BYTES:
        raise ValueError("MathML fragment size is outside the allowed range")
    if b"<!doctype" in encoded.lower():
        raise ValueError("MathML fragment must not contain DTD declarations")
    parser = etree.XMLParser(
        resolve_entities=False,
        load_dtd=False,
        no_network=True,
        recover=False,
        huge_tree=False,
        remove_comments=True,
        remove_pis=True,
    )
    try:
        root = etree.fromstring(encoded, parser=parser)
    except etree.XMLSyntaxError as exc:
        raise ValueError("MathML fragment is not well-formed") from exc
    if root.tag != f"{{{MATHML_NS}}}math":
        raise ValueError("MathML fragment must have mml:math as its root")
    expected_display = "block" if display else "inline"
    observed_display = root.get("display")
    if observed_display not in {None, expected_display}:
        raise ValueError(f"MathML display must be {expected_display}")
    for element in root.iter():
        if not isinstance(element.tag, str):
            raise ValueError("MathML fragment contains an unsupported node")
        qname = etree.QName(element)
        if qname.namespace != MATHML_NS or qname.localname not in _ALLOWED_ELEMENTS:
            raise ValueError("MathML fragment contains an unsupported element")
        for attribute in element.attrib:
            attribute_name = etree.QName(attribute)
            if attribute_name.localname.casefold() in _FORBIDDEN_ATTRIBUTE_NAMES:
                raise ValueError("MathML fragment contains an unsafe attribute")
            if attribute_name.namespace not in {None, MATHML_NS}:
                raise ValueError("MathML fragment contains an unsupported attribute namespace")
    normalized = deepcopy(root)
    normalized.set("display", expected_display)
    etree.cleanup_namespaces(normalized, top_nsmap={"mml": MATHML_NS})
    normalized.tail = None
    return normalized


def canonical_mathml(value: str, *, display: bool) -> str:
    element = parse_mathml_fragment(value, display=display)
    return etree.tostring(element, encoding="unicode", pretty_print=False)
