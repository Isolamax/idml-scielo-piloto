from io import BytesIO
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile


def synthetic_idml(*, include_table: bool = False) -> bytes:
    design = b"""<?xml version="1.0" encoding="UTF-8"?>
<Document Self="doc" DOMVersion="20.3" StoryList="u1 u2 u3 u4"/>"""
    styles = b"""<?xml version="1.0" encoding="UTF-8"?>
<idPkg:Styles xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging">
  <RootParagraphStyleGroup>
    <ParagraphStyle Self="ParagraphStyle/01.0.title" Name="01.0.title"/>
    <ParagraphStyle Self="ParagraphStyle/02.0.author" Name="02.0.author"/>
    <ParagraphStyle Self="ParagraphStyle/04.0.section" Name="04.0.section"/>
    <ParagraphStyle Self="ParagraphStyle/05.0.text" Name="05.0.text"/>
    <ParagraphStyle Self="ParagraphStyle/06.1.references" Name="06.1.references"/>
    <ParagraphStyle Self="ParagraphStyle/07.0.caption" Name="07.0.caption"/>
  </RootParagraphStyleGroup>
  <RootCharacterStyleGroup>
    <CharacterStyle Self="CharacterStyle/none" Name="none"/>
    <CharacterStyle Self="CharacterStyle/italico" Name="italico"/>
  </RootCharacterStyleGroup>
</idPkg:Styles>"""

    def story(story_id: str, paragraphs: str, extra: str = "") -> bytes:
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<idPkg:Story xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging">
  <Story Self="{story_id}">{paragraphs}{extra}</Story>
</idPkg:Story>'''.encode()

    def paragraph(style: str, text: str, character: str = "none") -> str:
        return (
            f'<ParagraphStyleRange AppliedParagraphStyle="ParagraphStyle/{style}">'
            f'<CharacterStyleRange AppliedCharacterStyle="CharacterStyle/{character}">'
            f"<Content>{text}</Content></CharacterStyleRange></ParagraphStyleRange>"
        )

    table = (
        '<Table Self="table-1" BodyRowCount="1" ColumnCount="2">'
        '<Cell Name="0:0"><ParagraphStyleRange AppliedParagraphStyle="ParagraphStyle/05.0.text">'
        '<CharacterStyleRange AppliedCharacterStyle="CharacterStyle/none">'
        '<Content>Alpha</Content></CharacterStyleRange></ParagraphStyleRange></Cell>'
        '<Cell Name="1:0"><ParagraphStyleRange AppliedParagraphStyle="ParagraphStyle/05.0.text">'
        '<CharacterStyleRange AppliedCharacterStyle="CharacterStyle/none">'
        '<Content>Beta</Content></CharacterStyleRange></ParagraphStyleRange></Cell>'
        "</Table>"
        if include_table
        else ""
    )
    stories = {
        "Stories/Story_u1.xml": story(
            "u1",
            paragraph("01.0.title", "Deterministic conversion")
            + paragraph("02.0.author", "Ana Silva"),
        ),
        "Stories/Story_u2.xml": story(
            "u2",
            paragraph("04.0.section", "Introduction")
            + paragraph("05.0.text", "Plain ")
            + paragraph("05.0.text", "emphasis", "italico"),
            table,
        ),
        "Stories/Story_u3.xml": story(
            "u3",
            '<ParagraphStyleRange AppliedParagraphStyle="ParagraphStyle/06.1.references">'
            '<CharacterStyleRange AppliedCharacterStyle="CharacterStyle/none">'
            "<Content>Reference one.</Content><Br/><Content>Reference two.</Content>"
            "</CharacterStyleRange></ParagraphStyleRange>",
        ),
        "Stories/Story_u4.xml": story(
            "u4",
            paragraph("07.0.caption", "Figure 1. Figure caption"),
            '<Rectangle Self="rectangle-1"><Image><Link Self="link-1" '
            'LinkResourceURI="file:C:/private/source/Figure%201.jpg" '
            'LinkResourceFormat="$ID/JPEG"/></Image></Rectangle>',
        ),
    }
    frames = "".join(
        f"""<TextFrame Self="f{index}" ParentStory="u{index}" PreviousTextFrame="n"
        NextTextFrame="n" ItemTransform="1 0 0 1 {index * 10} {index * 20}">
        <Properties><PathGeometry><GeometryPathType><PathPointArray>
        <PathPointType Anchor="0 0"/><PathPointType Anchor="100 200"/>
        </PathPointArray></GeometryPathType></PathGeometry></Properties></TextFrame>"""
        for index in range(1, 5)
    )
    spread = f"""<?xml version="1.0" encoding="UTF-8"?>
<idPkg:Spread xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging">
  <Spread Self="spread-1"><Page Self="page-1" Name="1"/>{frames}</Spread>
</idPkg:Spread>""".encode()

    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("mimetype", "application/vnd.adobe.indesign-idml-package", ZIP_STORED)
        archive.writestr("designmap.xml", design, ZIP_DEFLATED)
        archive.writestr("Resources/Styles.xml", styles, ZIP_DEFLATED)
        archive.writestr("Spreads/Spread_spread-1.xml", spread, ZIP_DEFLATED)
        for name, value in stories.items():
            archive.writestr(name, value, ZIP_DEFLATED)
    return buffer.getvalue()
