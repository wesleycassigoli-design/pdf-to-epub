"""
epub_generator_caderno.py
Gera EPUB2 no template "Caderno de Conceitos Matadores" a partir de
CadernoStructure. Completamente isolado de epub_generator.py e
epub_generator_medcel.py — nenhuma função é importada desses módulos
(inclusive fontes/CSS/manifest são montados aqui, duplicados de propósito).

Estrutura gerada (fixa, idêntica em todo caderno, independente do conteúdo):
- mimetype
- META-INF/container.xml
- OEBPS/content.opf
- OEBPS/toc.ncx
- OEBPS/Text/Section0001.xhtml   (documento único)
- OEBPS/Styles/brand_caderno.css
- OEBPS/Fonts/Montserrat-*.ttf   (8 fontes)
- OEBPS/Images/ICONE_*.png       (6 ícones — só ConceitoMatador é usado hoje)
- OEBPS/Images/imagem_NNN.*      (imagens grandes extraídas do docx, se houver)
"""

import os
import uuid
import base64
import zipfile
from pathlib import Path
import structlog
from app.services.docx_processor_caderno import CadernoStructure, CadernoBlock, CadernoImage

logger = structlog.get_logger()

_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
_FONTS_DIR = _ASSETS_DIR / "fonts" / "montserrat"
_ICONS_DIR = _ASSETS_DIR / "icons" / "caderno"
_CSS_PATH = Path(__file__).resolve().parent / "brand_caderno.css"

_FONT_FILES = [
    "Montserrat-Light.ttf",
    "Montserrat-LightItalic.ttf",
    "Montserrat-Regular.ttf",
    "Montserrat-Italic.ttf",
    "Montserrat-Bold.ttf",
    "Montserrat-BoldItalic.ttf",
    "Montserrat-SemiBold.ttf",
    "Montserrat-SemiBoldItalic.ttf",
]

_ICON_FILES = [
    "ICONE_ConceitoMatador.png",
    "ICONE_Descomplica.png",
    "ICONE_Importante.png",
    "ICONE_Memorize.png",
    "ICONE_Pegadinha.png",
    "ICONE_Update.png",
]


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
</container>
"""


# ─── HTML do documento ────────────────────────────────────────────────────────

def _next_edit_id(edit_counter: list[int]) -> str:
    """Contador sequencial global de data-edit-id, usado pelo editor (/reader/[id])
    pra endereçar de forma estável cada elemento editável (p/h2/h3/li/img)."""
    edit_counter[0] += 1
    return f"p-{edit_counter[0]}"


def _block_to_html(block: CadernoBlock, edit_counter: list[int]) -> str:
    if block.block_type == "caderno":
        return f'<div class="caderno">{_escape_xml(block.content)}</div>\n'

    if block.block_type == "capitulo":
        return f'<div class="capitulo">{_escape_xml(block.content)}</div>\n'

    if block.block_type == "hr":
        return "<hr/>\n"

    if block.block_type == "imagem" and block.image:
        stem = block.image.filename.rsplit(".", 1)[0]
        return (
            f'<div class="imagem">\n'
            f'<img data-edit-id="{_next_edit_id(edit_counter)}" alt="{_escape_xml(stem)}" src="../Images/{block.image.filename}"/>\n'
            f'</div>\n'
        )

    if block.block_type == "destaque":
        return (
            f'<div class="destaque">\n'
            f'<div class="icone"><img data-edit-id="{_next_edit_id(edit_counter)}" alt="ICONE_ConceitoMatador" src="../Images/ICONE_ConceitoMatador.png"/></div>\n'
            f'<p data-edit-id="{_next_edit_id(edit_counter)}">{block.content}</p>\n'
            f'</div>\n'
        )

    if block.block_type == "list_item":
        return f'<ol><li data-edit-id="{_next_edit_id(edit_counter)}"><b2>{block.marker}</b2>{block.content}</li></ol>\n'

    if block.block_type == "heading_numbered":
        return f'<h2 id="sigil_toc_id_{block.toc_id}" data-edit-id="{_next_edit_id(edit_counter)}">{_escape_xml(block.content)}</h2>\n'

    if block.block_type == "heading_not_in_toc":
        return f'<h3 class="sigil_not_in_toc" data-edit-id="{_next_edit_id(edit_counter)}">{_escape_xml(block.content)}</h3>\n'

    if block.block_type == "paragraph":
        return f'<p data-edit-id="{_next_edit_id(edit_counter)}">{block.content}</p>\n'

    return ""


def _build_section_xhtml(structure: CadernoStructure) -> str:
    edit_counter = [0]
    lines = []
    lines.append('<?xml version="1.0" encoding="utf-8"?>')
    lines.append('<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"')
    lines.append('  "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">')
    lines.append('<html xmlns="http://www.w3.org/1999/xhtml">')
    lines.append('<head>')
    lines.append(f'  <title>{_escape_xml(structure.title)}</title>')
    lines.append('  <link href="../Styles/brand_caderno.css" type="text/css" rel="stylesheet"/>')
    lines.append('</head>')
    lines.append('<body>')
    for block in structure.blocks:
        lines.append(_block_to_html(block, edit_counter))
    lines.append('</body>')
    lines.append('</html>')
    return "\n".join(lines)


# ─── OPF / NCX ────────────────────────────────────────────────────────────────

def _make_content_opf(book_id: str, title: str, images: list[CadernoImage]) -> str:
    uid = f"urn:uuid:{book_id}"

    manifest_items = [
        '<item id="Section0001.xhtml" href="Text/Section0001.xhtml" media-type="application/xhtml+xml"/>',
        '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
        '<item id="brand-caderno-css" href="Styles/brand_caderno.css" media-type="text/css"/>',
    ]
    manifest_items += [
        f'<item id="{fname.rsplit(".", 1)[0]}.ttf" href="Fonts/{fname}" media-type="font/ttf"/>'
        for fname in _FONT_FILES
    ]
    manifest_items += [
        f'<item id="{fname.rsplit(".", 1)[0]}.png" href="Images/{fname}" media-type="image/png"/>'
        for fname in _ICON_FILES
    ]
    manifest_items += [
        f'<item id="{img.filename.rsplit(".", 1)[0]}" href="Images/{img.filename}" media-type="{img.media_type}"/>'
        for img in images
    ]
    manifest = "\n    ".join(manifest_items)

    return f"""<?xml version="1.0" encoding="utf-8"?>
<package version="2.0" unique-identifier="BookId" xmlns="http://www.idpf.org/2007/opf">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:identifier id="BookId" opf:scheme="UUID">{uid}</dc:identifier>
    <dc:language>pt</dc:language>
    <dc:title>{_escape_xml(title)}</dc:title>
  </metadata>
  <manifest>
    {manifest}
  </manifest>
  <spine toc="ncx">
    <itemref idref="Section0001.xhtml"/>
  </spine>
</package>"""


def _make_toc_ncx(book_id: str, title: str, toc_entries: list[tuple]) -> str:
    points = []
    for order, (toc_id, text) in enumerate(toc_entries, start=1):
        points.append(f"""    <navPoint id="navPoint-{order}" playOrder="{order}">
      <navLabel>
        <text>{_escape_xml(text)}</text>
      </navLabel>
      <content src="Text/Section0001.xhtml#sigil_toc_id_{toc_id}"/>
    </navPoint>""")

    if not points:
        points.append(f"""    <navPoint id="navPoint-1" playOrder="1">
      <navLabel>
        <text>{_escape_xml(title)}</text>
      </navLabel>
      <content src="Text/Section0001.xhtml"/>
    </navPoint>""")

    nav_map = "\n".join(points)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN"
   "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">

<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="urn:uuid:{book_id}"/>
    <meta name="dtb:depth" content="1"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle>
    <text>{_escape_xml(title)}</text>
  </docTitle>
  <navMap>
{nav_map}
  </navMap>
</ncx>"""


# ─── Build principal ──────────────────────────────────────────────────────────

def build_epub_caderno(structure: CadernoStructure, output_path: str) -> str:
    """Gera o EPUB do template Caderno de Conceitos Matadores. Retorna o caminho gerado."""
    book_id = str(uuid.uuid4())
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    section_xhtml = _build_section_xhtml(structure)
    content_opf = _make_content_opf(book_id, structure.title, structure.images)
    toc_ncx = _make_toc_ncx(book_id, structure.title, structure.toc_entries)
    css = _CSS_PATH.read_text(encoding="utf-8")

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            zipfile.ZipInfo("mimetype"),
            "application/epub+zip",
            compress_type=zipfile.ZIP_STORED,
        )
        zf.writestr("META-INF/container.xml", _make_container_xml())
        zf.writestr("OEBPS/content.opf", content_opf)
        zf.writestr("OEBPS/toc.ncx", toc_ncx)
        zf.writestr("OEBPS/Text/Section0001.xhtml", section_xhtml)
        zf.writestr("OEBPS/Styles/brand_caderno.css", css)

        for fname in _FONT_FILES:
            zf.write(_FONTS_DIR / fname, f"OEBPS/Fonts/{fname}")
        for fname in _ICON_FILES:
            zf.write(_ICONS_DIR / fname, f"OEBPS/Images/{fname}")

        for img in structure.images:
            img_bytes = base64.b64decode(img.data_b64)
            zf.writestr(f"OEBPS/Images/{img.filename}", img_bytes)

    logger.info(
        "epub_caderno_built",
        path=output_path,
        title=structure.title,
        blocks=len(structure.blocks),
        images=len(structure.images),
        toc_entries=len(structure.toc_entries),
    )
    return output_path
