"""
epub_generator_generico.py
Gera EPUB3 simples a partir de GenericStructure — sem identidade visual
Medcel, layout limpo e neutro, com navegação baseada nos headings reais
do Word (Heading 1/2/3), quando existirem.
"""

import os
import uuid
import base64
import zipfile
import structlog
from app.services.docx_processor_generico import GenericStructure, GenericBlock, GenericImage

logger = structlog.get_logger()


GENERIC_CSS = """
@charset "UTF-8";

body {
    font-family: Georgia, "Times New Roman", serif;
    font-size: 1em;
    line-height: 1.6;
    margin: 1em 1.5em;
    color: #1a1a1a;
}

h1.doc-title {
    font-size: 1.5em;
    font-weight: bold;
    margin-bottom: 1em;
    padding-bottom: 0.4em;
    border-bottom: 1px solid #ccc;
}

h1 { font-size: 1.3em; font-weight: bold; margin-top: 1.4em; margin-bottom: 0.5em; }
h2 { font-size: 1.15em; font-weight: bold; margin-top: 1.2em; margin-bottom: 0.4em; }
h3 { font-size: 1.05em; font-weight: bold; margin-top: 1em; margin-bottom: 0.3em; }

p { margin: 0 0 0.8em 0; text-align: justify; }

ol, ul { margin: 0.3em 0 0.3em 1.5em; padding: 0; }
li { margin-bottom: 0.3em; }

img { max-width: 100%; height: auto; display: block; margin: 1em auto; }

.generic-table {
    width: 100%;
    border-collapse: collapse;
    margin: 1em 0;
    font-size: 0.9em;
}
.generic-table th { background: #e5e5e5; padding: 0.4em 0.6em; text-align: left; }
.generic-table td { border: 1px solid #ddd; padding: 0.4em 0.6em; }
"""


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


def _block_to_html(block: GenericBlock, heading_ids: dict) -> str:
    if block.block_type == "paragraph":
        return f"<p>{block.content}</p>\n"
    if block.block_type == "list_item":
        return f"<ul><li>{block.content}</li></ul>\n"
    if block.block_type == "table":
        return block.raw_html + "\n"
    if block.block_type in ("heading1", "heading2", "heading3"):
        tag = {"heading1": "h1", "heading2": "h2", "heading3": "h3"}[block.block_type]
        anchor_id = heading_ids.get(id(block), "")
        id_attr = f' id="{anchor_id}"' if anchor_id else ""
        return f"<{tag}{id_attr}>{_escape_xml(block.content)}</{tag}>\n"
    if block.block_type == "image" and block.image:
        return f'<img src="../Images/{block.image.filename}" alt=""/>\n'
    return ""


def _build_chapter_xhtml(structure: GenericStructure, heading_ids: dict) -> str:
    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<!DOCTYPE html>')
    lines.append('<html xmlns="http://www.w3.org/1999/xhtml">')
    lines.append('<head>')
    lines.append(f'  <title>{_escape_xml(structure.title)}</title>')
    lines.append('  <link href="../Styles/generic.css" type="text/css" rel="stylesheet"/>')
    lines.append('</head>')
    lines.append('<body>')
    lines.append(f'<h1 class="doc-title">{_escape_xml(structure.title)}</h1>')
    for block in structure.blocks:
        lines.append(_block_to_html(block, heading_ids))
    lines.append('</body>')
    lines.append('</html>')
    return "\n".join(lines)


def _make_content_opf(book_id: str, title: str, images: list[GenericImage]) -> str:
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
    <item id="css" href="Styles/generic.css" media-type="text/css"/>
    <item id="chapter" href="Text/chapter.xhtml" media-type="application/xhtml+xml"/>
    {img_manifest}
  </manifest>
  <spine toc="ncx">
    <itemref idref="chapter"/>
  </spine>
</package>"""


def _make_nav_xhtml(title: str, structure: GenericStructure, heading_ids: dict) -> str:
    items = []
    for block in structure.blocks:
        if block.block_type in ("heading1", "heading2") and id(block) in heading_ids:
            items.append(
                f'<li><a href="Text/chapter.xhtml#{heading_ids[id(block)]}">{_escape_xml(block.content)}</a></li>'
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


def _make_toc_ncx(book_id: str, title: str, structure: GenericStructure, heading_ids: dict) -> str:
    points = []
    order = 1
    for block in structure.blocks:
        if block.block_type in ("heading1", "heading2") and id(block) in heading_ids:
            points.append(f"""  <navPoint id="nav{order}" playOrder="{order}">
    <navLabel><text>{_escape_xml(block.content)}</text></navLabel>
    <content src="Text/chapter.xhtml#{heading_ids[id(block)]}"/>
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


def build_epub_generico(structure: GenericStructure, output_path: str) -> str:
    """Gera EPUB3 genérico a partir de GenericStructure. Retorna o caminho do arquivo."""
    book_id = str(uuid.uuid4())
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # IDs de âncora só para headings 1 e 2 (viram entradas de sumário)
    heading_ids = {}
    counter = 0
    for block in structure.blocks:
        if block.block_type in ("heading1", "heading2"):
            counter += 1
            heading_ids[id(block)] = f"sec{counter:02d}"

    chapter_xhtml = _build_chapter_xhtml(structure, heading_ids)
    nav_xhtml = _make_nav_xhtml(structure.title, structure, heading_ids)
    toc_ncx = _make_toc_ncx(book_id, structure.title, structure, heading_ids)
    content_opf = _make_content_opf(book_id, structure.title, structure.images)

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", _make_container_xml())
        zf.writestr("OEBPS/content.opf", content_opf)
        zf.writestr("OEBPS/nav.xhtml", nav_xhtml)
        zf.writestr("OEBPS/toc.ncx", toc_ncx)
        zf.writestr("OEBPS/Styles/generic.css", GENERIC_CSS)
        zf.writestr("OEBPS/Text/chapter.xhtml", chapter_xhtml)
        for img in structure.images:
            img_bytes = base64.b64decode(img.data_b64)
            zf.writestr(f"OEBPS/Images/{img.filename}", img_bytes)

    logger.info("epub_generico_built", path=output_path, title=structure.title, blocks=len(structure.blocks))
    return output_path
