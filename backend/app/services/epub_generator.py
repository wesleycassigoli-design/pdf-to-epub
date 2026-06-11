"""
epub_generator.py
Gera EPUB3 Fixed Layout a partir da estrutura analisada do PDF.
Prioridade máxima: fidelidade visual ao PDF original.
NÃO altera conteúdo textual de forma alguma.
"""

import os
import uuid
import zipfile
from io import BytesIO
from pathlib import Path
from dataclasses import dataclass
import structlog
from app.services.pdf_processor import BookStructure, ChapterInfo, PageContent

logger = structlog.get_logger()


# ─── Helpers de template ─────────────────────────────────────────────────────

def _pt_to_px(pt: float) -> int:
    """Converte pontos PDF em pixels CSS (96dpi)."""
    return round(pt * (96 / 72))


def _make_container_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""


def _make_page_xhtml(page: PageContent, svg_content: str) -> str:
    """Gera XHTML de uma página com o SVG embutido (Fixed Layout)."""
    w_px = _pt_to_px(page.width)
    h_px = _pt_to_px(page.height)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:epub="http://www.idpf.org/2007/ops">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width={w_px}, height={h_px}"/>
  <title>Page {page.page_number}</title>
  <style>
    html, body {{
      margin: 0;
      padding: 0;
      width: {w_px}px;
      height: {h_px}px;
      overflow: hidden;
      background: white;
    }}
    .page-container {{
      width: {w_px}px;
      height: {h_px}px;
      position: relative;
      overflow: hidden;
    }}
    .page-container svg {{
      width: 100%;
      height: 100%;
      display: block;
    }}
  </style>
</head>
<body>
  <div class="page-container" epub:type="bodymatter">
{svg_content}
  </div>
</body>
</html>"""


def _make_content_opf(
    book_id: str,
    title: str,
    spine_items: list[dict],
) -> str:
    """Gera o content.opf principal do EPUB3 Fixed Layout."""
    uid = f"urn:uuid:{book_id}"

    manifest_items = "\n    ".join([
        f'<item id="{item["id"]}" href="{item["href"]}" media-type="application/xhtml+xml" properties="svg"/>'
        for item in spine_items
    ])

    spine_items_xml = "\n    ".join([
        f'<itemref idref="{item["id"]}"/>'
        for item in spine_items
    ])

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf"
         xmlns:dc="http://purl.org/dc/elements/1.1/"
         version="3.0"
         unique-identifier="uid">

  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="uid">{uid}</dc:identifier>
    <dc:title>{_escape_xml(title)}</dc:title>
    <dc:language>pt</dc:language>
    <meta property="rendition:layout">pre-paginated</meta>
    <meta property="rendition:orientation">auto</meta>
    <meta property="rendition:spread">none</meta>
  </metadata>

  <manifest>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    {manifest_items}
  </manifest>

  <spine toc="ncx">
    {spine_items_xml}
  </spine>

</package>"""


def _make_nav_xhtml(title: str, spine_items: list[dict]) -> str:
    nav_items = "\n      ".join([
        f'<li><a href="{item["href"]}">{item["label"]}</a></li>'
        for item in spine_items
    ])
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><meta charset="UTF-8"/><title>{_escape_xml(title)}</title></head>
<body>
  <nav epub:type="toc">
    <h1>Conteúdo</h1>
    <ol>
      {nav_items}
    </ol>
  </nav>
</body>
</html>"""


def _make_toc_ncx(book_id: str, title: str, spine_items: list[dict]) -> str:
    nav_points = "\n  ".join([
        f"""<navPoint id="nav{i+1}" playOrder="{i+1}">
    <navLabel><text>{_escape_xml(item["label"])}</text></navLabel>
    <content src="{item["href"]}"/>
  </navPoint>"""
        for i, item in enumerate(spine_items)
    ])
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN" "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="urn:uuid:{book_id}"/>
  </head>
  <docTitle><text>{_escape_xml(title)}</text></docTitle>
  <navMap>
  {nav_points}
  </navMap>
</ncx>"""


def _escape_xml(text: str) -> str:
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


# ─── Geração do EPUB ─────────────────────────────────────────────────────────

def build_epub(
    structure: BookStructure,
    output_path: str,
    pages_subset: list[PageContent] | None = None,
    chapter_title: str | None = None,
) -> str:
    """
    Gera um arquivo EPUB3 Fixed Layout.
    
    - output_path: caminho completo do arquivo .epub a criar
    - pages_subset: se informado, gera EPUB apenas com essas páginas
    - chapter_title: título a usar no EPUB (capítulo individual)
    """
    pages = pages_subset if pages_subset is not None else structure.pages
    title = chapter_title or structure.title
    book_id = str(uuid.uuid4())

    spine_items = []
    page_xhtmls: dict[str, str] = {}

    for page in pages:
        item_id = f"page{page.page_number:04d}"
        href = f"pages/{item_id}.xhtml"
        label = f"Página {page.page_number}"

        spine_items.append({"id": item_id, "href": href, "label": label})
        page_xhtmls[href] = _make_page_xhtml(page, page.svg_content)

    # Monta o ZIP (estrutura EPUB)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # mimetype deve ser o primeiro e sem compressão
        zf.writestr(
            zipfile.ZipInfo("mimetype"),
            "application/epub+zip",
            compress_type=zipfile.ZIP_STORED,
        )

        # META-INF/container.xml
        zf.writestr("META-INF/container.xml", _make_container_xml())

        # OEBPS/content.opf
        zf.writestr("OEBPS/content.opf", _make_content_opf(book_id, title, spine_items))

        # OEBPS/nav.xhtml
        zf.writestr("OEBPS/nav.xhtml", _make_nav_xhtml(title, spine_items))

        # OEBPS/toc.ncx
        zf.writestr("OEBPS/toc.ncx", _make_toc_ncx(book_id, title, spine_items))

        # Páginas XHTML
        for href, content in page_xhtmls.items():
            zf.writestr(f"OEBPS/{href}", content)

        # Imagens (se existirem)
        images_dir = structure.images_dir
        if images_dir and os.path.isdir(images_dir):
            for img_file in Path(images_dir).iterdir():
                if img_file.is_file():
                    zf.write(img_file, f"OEBPS/images/{img_file.name}")

    logger.info("epub_built", path=output_path, pages=len(pages), title=title)
    return output_path


def build_chapter_epub(
    structure: BookStructure,
    chapter: ChapterInfo,
    output_path: str,
) -> str:
    """Gera EPUB de um único capítulo."""
    chapter_pages = [
        p for p in structure.pages
        if chapter.start_page <= p.page_number <= chapter.end_page
    ]
    return build_epub(
        structure=structure,
        output_path=output_path,
        pages_subset=chapter_pages,
        chapter_title=chapter.title,
    )
