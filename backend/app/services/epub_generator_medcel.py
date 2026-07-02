"""
epub_generator_medcel.py
Gera EPUB3 no padrão Medcel a partir de DocxStructure.

Estrutura gerada:
- mimetype
- META-INF/container.xml
- OEBPS/content.opf
- OEBPS/nav.xhtml
- OEBPS/toc.ncx
- OEBPS/Styles/medcel.css
- OEBPS/Text/chapter.xhtml  (documento único)
- OEBPS/Images/img001.jpg   (imagens extraídas)
"""

import os
import uuid
import base64
import zipfile
from pathlib import Path
import structlog
from app.services.docx_processor import DocxStructure, DocxSection, DocxBlock, DocxImage

logger = structlog.get_logger()


# ─── CSS Medcel ───────────────────────────────────────────────────────────────

MEDCEL_CSS = """
@charset "UTF-8";

body {
    font-family: "Georgia", serif;
    font-size: 1em;
    line-height: 1.6;
    margin: 1em 2em;
    color: #222;
}

.capitulo {
    font-size: 1.4em;
    font-weight: bold;
    color: #D31C5B;
    text-transform: uppercase;
    margin-bottom: 0.3em;
    border-bottom: 2px solid #D31C5B;
    padding-bottom: 0.3em;
}

.nome_autor {
    font-size: 0.95em;
    color: #555;
    margin-bottom: 1.2em;
}

hr {
    border: none;
    border-top: 1px solid #ccc;
    margin: 1.5em 0;
}

h2 {
    font-size: 1.15em;
    font-weight: bold;
    color: #1a1a1a;
    margin-top: 1.5em;
    margin-bottom: 0.5em;
    text-transform: uppercase;
}

h3 {
    font-size: 1.05em;
    font-weight: bold;
    color: #333;
    margin-top: 1.2em;
    margin-bottom: 0.4em;
}

p {
    margin: 0 0 0.8em 0;
    text-align: justify;
}

ol {
    margin: 0.3em 0 0.3em 1.5em;
    padding: 0;
}

ol li {
    margin-bottom: 0.3em;
}

.alert-box {
    background: #fff8e1;
    border-left: 4px solid #D31C5B;
    padding: 0.6em 1em;
    margin: 1em 0;
    font-size: 0.95em;
}

.zoom {
    margin: 1em 0;
    text-align: center;
}

.zoom img {
    max-width: 100%;
    height: auto;
}

.zoom h5 {
    font-size: 0.9em;
    font-weight: bold;
    color: #444;
    margin: 0.4em 0 0.2em 0;
    text-align: left;
}

.zoom .fonte {
    font-size: 0.8em;
    color: #777;
    text-align: right;
    margin-top: 0.2em;
}

.medcel-table {
    width: 100%;
    border-collapse: collapse;
    margin: 1em 0;
    font-size: 0.9em;
}

.medcel-table th {
    background: #D31C5B;
    color: #fff;
    padding: 0.4em 0.6em;
    text-align: left;
}

.medcel-table td {
    border: 1px solid #ddd;
    padding: 0.4em 0.6em;
}

.medcel-table tr:nth-child(even) td {
    background: #f9f9f9;
}

h3.referencias {
    font-size: 1em;
    text-transform: uppercase;
    margin-top: 2em;
    border-top: 1px solid #ccc;
    padding-top: 1em;
}

p.referencia {
    font-size: 0.85em;
    text-align: left;
    margin-bottom: 0.6em;
    color: #444;
}

.sumario {
    text-align: center;
    margin-top: 2em;
}

.button1 {
    background: #D31C5B;
    color: #fff;
    border: none;
    padding: 0.5em 1.5em;
    font-size: 0.95em;
    cursor: pointer;
    border-radius: 4px;
}
"""


# ─── Helpers XML ─────────────────────────────────────────────────────────────

def _escape_xml(text: str) -> str:
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def _make_container_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""


# ─── HTML do capítulo ─────────────────────────────────────────────────────────

def _block_to_html(block: DocxBlock) -> str:
    if block.block_type == "paragraph":
        return f"<p>{block.content}</p>\n"

    if block.block_type == "h3":
        return f"<h3>{_escape_xml(block.content)}</h3>\n"

    if block.block_type == "list_item":
        return f"<ol><li>{block.content}</li></ol>\n"

    if block.block_type == "alert":
        return f'<div class="alert-box">{block.content}</div>\n'

    if block.block_type == "table":
        return block.raw_html + "\n"

    if block.block_type == "image" and block.image:
        img = block.image
        caption_html = f'<h5 class="sigil_not_in_toc">{_escape_xml(img.caption)}</h5>\n' if img.caption else ""
        source_html = f'<p class="fonte">{_escape_xml(img.source)}</p>\n' if img.source else ""
        return (
            f'<div class="zoom">\n'
            f'{caption_html}'
            f'  <img src="../Images/{img.filename}" alt="{_escape_xml(img.caption or img.filename)}"/>\n'
            f'{source_html}'
            f'</div>\n'
        )

    return ""


def _build_chapter_xhtml(structure: DocxStructure) -> str:
    """Monta o XHTML completo do capítulo no padrão Medcel."""
    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"')
    lines.append('  "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">')
    lines.append('<html xmlns="http://www.w3.org/1999/xhtml">')
    lines.append('<head>')
    lines.append(f'  <title>{_escape_xml(structure.title)}</title>')
    lines.append('  <link href="../Styles/medcel.css" type="text/css" rel="stylesheet"/>')
    lines.append('</head>')
    lines.append('<body>')

    # Cabeçalho
    lines.append(f'<div class="capitulo">{_escape_xml(structure.title)}</div>')
    if structure.authors:
        lines.append(f'<div class="nome_autor">{_escape_xml(structure.authors)}</div>')
    lines.append('<hr/>')

    # Seções
    for section in structure.sections:
        if section.title:
            section_id = f"sec{section.number:02d}"
            lines.append(f'<h2 id="{section_id}">{_escape_xml(section.title)}</h2>')

        for block in section.blocks:
            lines.append(_block_to_html(block))

    # Referências
    if structure.references:
        lines.append('<hr/>')
        lines.append('<h3 class="referencias sigil_not_in_toc">REFERÊNCIAS</h3>')
        for ref in structure.references:
            lines.append(f'<p class="referencia">{_escape_xml(ref)}</p>')

    # Botão voltar
    lines.append('<hr/>')
    lines.append('<div class="sumario">')
    lines.append('  <a href="#">')
    lines.append('    <h3 style="text-align: center;" class="sigil_not_in_toc">')
    lines.append('      <button class="button1">VOLTAR AO INÍCIO</button>')
    lines.append('    </h3>')
    lines.append('  </a>')
    lines.append('</div>')

    lines.append('</body>')
    lines.append('</html>')

    return "\n".join(lines)


# ─── OPF ─────────────────────────────────────────────────────────────────────

def _make_content_opf(book_id: str, title: str, images: list[DocxImage]) -> str:
    uid = f"urn:uuid:{book_id}"

    img_manifest = "\n    ".join([
        f'<item id="img{i+1:03d}" href="Images/{img.filename}" media-type="{img.media_type}"/>'
        for i, img in enumerate(images)
    ])

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="uid">{uid}</dc:identifier>
    <dc:title>{_escape_xml(title)}</dc:title>
    <dc:language>pt</dc:language>
  </metadata>
  <manifest>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="css" href="Styles/medcel.css" media-type="text/css"/>
    <item id="chapter" href="Text/chapter.xhtml" media-type="application/xhtml+xml"/>
    {img_manifest}
  </manifest>
  <spine toc="ncx">
    <itemref idref="chapter"/>
  </spine>
</package>"""


def _make_nav_xhtml(title: str, sections: list[DocxSection]) -> str:
    items = []
    for sec in sections:
        if sec.title and sec.number > 0:
            sec_id = f"sec{sec.number:02d}"
            items.append(
                f'<li><a href="Text/chapter.xhtml#{sec_id}">{_escape_xml(sec.title)}</a></li>'
            )

    nav_items = "\n      ".join(items) if items else '<li><a href="Text/chapter.xhtml">Início</a></li>'

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><meta charset="UTF-8"/><title>{_escape_xml(title)}</title></head>
<body>
  <nav epub:type="toc"><h1>Conteúdo</h1>
    <ol>
      {nav_items}
    </ol>
  </nav>
</body>
</html>"""


def _make_toc_ncx(book_id: str, title: str, sections: list[DocxSection]) -> str:
    points = []
    order = 1
    for sec in sections:
        if sec.title and sec.number > 0:
            sec_id = f"sec{sec.number:02d}"
            points.append(f"""  <navPoint id="nav{order}" playOrder="{order}">
    <navLabel><text>{_escape_xml(sec.title)}</text></navLabel>
    <content src="Text/chapter.xhtml#{sec_id}"/>
  </navPoint>""")
            order += 1

    if not points:
        points.append(f"""  <navPoint id="nav1" playOrder="1">
    <navLabel><text>{_escape_xml(title)}</text></navLabel>
    <content src="Text/chapter.xhtml"/>
  </navPoint>""")

    nav_map = "\n".join(points)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN" "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head><meta name="dtb:uid" content="urn:uuid:{book_id}"/></head>
  <docTitle><text>{_escape_xml(title)}</text></docTitle>
  <navMap>
{nav_map}
  </navMap>
</ncx>"""


# ─── Build principal ──────────────────────────────────────────────────────────

def build_epub_medcel(structure: DocxStructure, output_path: str) -> str:
    """
    Gera EPUB3 no padrão Medcel a partir de DocxStructure.
    Retorna o caminho do arquivo gerado.
    """
    book_id = str(uuid.uuid4())
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    chapter_xhtml = _build_chapter_xhtml(structure)
    nav_xhtml = _make_nav_xhtml(structure.title, structure.sections)
    toc_ncx = _make_toc_ncx(book_id, structure.title, structure.sections)
    content_opf = _make_content_opf(book_id, structure.title, structure.images)

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # mimetype deve ser o primeiro e sem compressão
        zf.writestr(
            zipfile.ZipInfo("mimetype"),
            "application/epub+zip",
            compress_type=zipfile.ZIP_STORED,
        )
        zf.writestr("META-INF/container.xml", _make_container_xml())
        zf.writestr("OEBPS/content.opf", content_opf)
        zf.writestr("OEBPS/nav.xhtml", nav_xhtml)
        zf.writestr("OEBPS/toc.ncx", toc_ncx)
        zf.writestr("OEBPS/Styles/medcel.css", MEDCEL_CSS)
        zf.writestr("OEBPS/Text/chapter.xhtml", chapter_xhtml)

        # Imagens
        for img in structure.images:
            img_bytes = base64.b64decode(img.data_b64)
            zf.writestr(f"OEBPS/Images/{img.filename}", img_bytes)

    logger.info(
        "epub_medcel_built",
        path=output_path,
        title=structure.title,
        sections=len(structure.sections),
        images=len(structure.images),
    )
    return output_path
