"""
epub_generator_medcel.py
Gera EPUB3 no padrão Medcel a partir de DocxStructure.

Estrutura gerada:
- mimetype
- META-INF/container.xml
- OEBPS/content.opf
- OEBPS/nav.xhtml
- OEBPS/toc.ncx
- OEBPS/styles/brand.css        (CSS de marca oficial Medcel/Afya — mesmo arquivo do pipeline PDF)
- OEBPS/styles/brand-extras.css (zoom/hr/botão/tabela/alerta — complementar, cores da marca)
- OEBPS/fonts/*.ttf             (fontes AfyaSans embutidas — mesmo esquema do pipeline PDF)
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
from app.services.epub_generator import _brand_manifest_items, _write_brand_assets

logger = structlog.get_logger()


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

def _next_edit_id(edit_counter: list[int]) -> str:
    """Contador sequencial global de data-edit-id, usado pelo editor (/reader/[id])
    pra endereçar de forma estável cada elemento editável (p/h2/h3/li/img)."""
    edit_counter[0] += 1
    return f"p-{edit_counter[0]}"


def _block_to_html(block: DocxBlock, edit_counter: list[int]) -> str:
    if block.block_type == "paragraph":
        return f'<p data-edit-id="{_next_edit_id(edit_counter)}">{block.content}</p>\n'

    if block.block_type == "h3":
        return f'<h3 data-edit-id="{_next_edit_id(edit_counter)}">{_escape_xml(block.content)}</h3>\n'

    if block.block_type == "list_item":
        return f'<ol><li data-edit-id="{_next_edit_id(edit_counter)}"><b2>▶</b2> {block.content}</li></ol>\n'

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
            f'  <img data-edit-id="{_next_edit_id(edit_counter)}" src="../Images/{img.filename}" alt="{_escape_xml(img.caption or img.filename)}"/>\n'
            f'{source_html}'
            f'</div>\n'
        )

    return ""


def _build_chapter_xhtml(structure: DocxStructure) -> str:
    """Monta o XHTML completo do capítulo no padrão Medcel."""
    edit_counter = [0]
    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"')
    lines.append('  "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">')
    lines.append('<html xmlns="http://www.w3.org/1999/xhtml">')
    lines.append('<head>')
    lines.append(f'  <title>{_escape_xml(structure.title)}</title>')
    lines.append('  <link href="../styles/brand.css" type="text/css" rel="stylesheet"/>')
    lines.append('  <link href="../styles/brand-extras.css" type="text/css" rel="stylesheet"/>')
    lines.append('</head>')
    lines.append('<body>')

    # Cabeçalho — texto em CAIXA ALTA real (não confiamos só no CSS text-transform,
    # pois alguns leitores de EPUB — ex: Google Play Books — ignoram essa propriedade
    # e aplicam o tema próprio do app por cima da formatação original)
    lines.append(f'<div class="capitulo">{_escape_xml(structure.title).upper()}</div>')
    if structure.authors:
        lines.append(f'<div class="nome_autor">{_escape_xml(structure.authors)}</div>')
    lines.append('<hr/>')

    # Seções
    for section in structure.sections:
        if section.title:
            section_id = f"sec{section.number:02d}"
            lines.append(f'<h2 id="{section_id}" data-edit-id="{_next_edit_id(edit_counter)}">{_escape_xml(section.title).upper()}</h2>')

        for block in section.blocks:
            lines.append(_block_to_html(block, edit_counter))

    # Referências
    if structure.references:
        lines.append('<hr/>')
        lines.append('<h3 class="referencias sigil_not_in_toc">REFERÊNCIAS</h3>')
        for ref in structure.references:
            lines.append(f'<p class="referencia" data-edit-id="{_next_edit_id(edit_counter)}">{_escape_xml(ref)}</p>')

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
    <item id="chapter" href="Text/chapter.xhtml" media-type="application/xhtml+xml"/>
    {img_manifest}
    {_brand_manifest_items()}
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
                f'<li><a href="Text/chapter.xhtml#{sec_id}">{_escape_xml(sec.title).upper()}</a></li>'
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
    <navLabel><text>{_escape_xml(sec.title).upper()}</text></navLabel>
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
        zf.writestr("OEBPS/Text/chapter.xhtml", chapter_xhtml)
        _write_brand_assets(zf)

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
