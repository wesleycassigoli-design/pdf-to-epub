"""
epub_generator.py
Gera EPUB3 a partir da estrutura analisada do PDF.

Dois modos:
- mode="fiel"  → EPUB3 Fixed Layout com IMAGEM de cada página (idêntico ao PDF)
- mode="texto" → EPUB3 Reflowable com texto extraído (selecionável, ajustável)

NÃO altera conteúdo textual de forma alguma.
"""

import os
import uuid
import base64
import zipfile
from io import BytesIO
from pathlib import Path
import structlog
from app.services.pdf_processor import BookStructure, ChapterInfo, PageContent

logger = structlog.get_logger()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _escape_xml(text: str) -> str:
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def _pt_to_px(pt: float) -> int:
    return round(pt * (96 / 72))


def _make_container_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""


# ─── MODO FIEL: página como imagem ───────────────────────────────────────────

def _make_page_xhtml_image(page: PageContent, img_filename: str) -> str:
    """XHTML de uma página com a imagem da página inteira (Fixed Layout)."""
    w_px = _pt_to_px(page.width)
    h_px = _pt_to_px(page.height)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width={w_px}, height={h_px}"/>
  <title>Page {page.page_number}</title>
  <style>
    html, body {{ margin:0; padding:0; width:{w_px}px; height:{h_px}px; }}
    img {{ width:{w_px}px; height:{h_px}px; display:block; }}
  </style>
</head>
<body>
  <div epub:type="bodymatter">
    <img src="../images/{img_filename}" alt="Página {page.page_number}"/>
  </div>
</body>
</html>"""


def _make_content_opf_image(book_id: str, title: str, spine_items: list[dict]) -> str:
    uid = f"urn:uuid:{book_id}"
    manifest_pages = "\n    ".join([
        f'<item id="{i["id"]}" href="{i["href"]}" media-type="application/xhtml+xml"/>'
        for i in spine_items
    ])
    manifest_imgs = "\n    ".join([
        f'<item id="img{i["id"]}" href="images/{i["img"]}" media-type="image/png"/>'
        for i in spine_items
    ])
    spine = "\n    ".join([f'<itemref idref="{i["id"]}"/>' for i in spine_items])
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid">
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
    {manifest_pages}
    {manifest_imgs}
  </manifest>
  <spine toc="ncx">
    {spine}
  </spine>
</package>"""


# ─── MODO TEXTO: reflow ───────────────────────────────────────────────────────

def _make_page_xhtml_text(page: PageContent) -> str:
    """XHTML reflowable com o texto da página (preserva quebras de parágrafo)."""
    # Preserva o texto EXATO, apenas escapando XML e mantendo quebras de linha
    raw = page.text_content or ""
    paragraphs = [p for p in raw.split("\n") if p.strip()]
    body = "\n".join(f"  <p>{_escape_xml(p)}</p>" for p in paragraphs)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
  <meta charset="UTF-8"/>
  <title>Página {page.page_number}</title>
  <style>
    body {{ font-family: serif; line-height: 1.5; margin: 1em; }}
    p {{ margin: 0 0 0.6em 0; }}
  </style>
</head>
<body epub:type="bodymatter">
{body}
</body>
</html>"""


def _make_content_opf_text(book_id: str, title: str, spine_items: list[dict]) -> str:
    uid = f"urn:uuid:{book_id}"
    manifest_pages = "\n    ".join([
        f'<item id="{i["id"]}" href="{i["href"]}" media-type="application/xhtml+xml"/>'
        for i in spine_items
    ])
    spine = "\n    ".join([f'<itemref idref="{i["id"]}"/>' for i in spine_items])
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
    {manifest_pages}
  </manifest>
  <spine toc="ncx">
    {spine}
  </spine>
</package>"""


# ─── NAV e NCX (comuns) ───────────────────────────────────────────────────────

def _make_nav_xhtml(title: str, spine_items: list[dict]) -> str:
    items = "\n      ".join([
        f'<li><a href="{i["href"]}">{_escape_xml(i["label"])}</a></li>'
        for i in spine_items
    ])
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><meta charset="UTF-8"/><title>{_escape_xml(title)}</title></head>
<body>
  <nav epub:type="toc"><h1>Conteúdo</h1><ol>
      {items}
  </ol></nav>
</body>
</html>"""


def _make_toc_ncx(book_id: str, title: str, spine_items: list[dict]) -> str:
    points = "\n  ".join([
        f"""<navPoint id="nav{idx+1}" playOrder="{idx+1}">
    <navLabel><text>{_escape_xml(i["label"])}</text></navLabel>
    <content src="{i["href"]}"/>
  </navPoint>"""
        for idx, i in enumerate(spine_items)
    ])
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN" "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head><meta name="dtb:uid" content="urn:uuid:{book_id}"/></head>
  <docTitle><text>{_escape_xml(title)}</text></docTitle>
  <navMap>
  {points}
  </navMap>
</ncx>"""


# ─── Build principal ──────────────────────────────────────────────────────────

def build_epub(
    structure: BookStructure,
    output_path: str,
    mode: str = "fiel",
    pages_subset: list[PageContent] | None = None,
    chapter_title: str | None = None,
) -> str:
    """
    Gera EPUB3.
    mode="fiel"  → imagem por página (Fixed Layout, idêntico ao PDF)
    mode="texto" → texto reflowable (selecionável)
    """
    pages = pages_subset if pages_subset is not None else structure.pages
    title = chapter_title or structure.title
    book_id = str(uuid.uuid4())
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    spine_items = []
    page_files: dict[str, str] = {}

    for page in pages:
        item_id = f"page{page.page_number:04d}"
        href = f"pages/{item_id}.xhtml"
        label = f"Página {page.page_number}"
        entry = {"id": item_id, "href": href, "label": label}

        if mode == "fiel":
            img_name = f"{item_id}.png"
            entry["img"] = img_name
            page_files[href] = _make_page_xhtml_image(page, img_name)
        else:
            page_files[href] = _make_page_xhtml_text(page)

        spine_items.append(entry)

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", _make_container_xml())

        if mode == "fiel":
            zf.writestr("OEBPS/content.opf", _make_content_opf_image(book_id, title, spine_items))
        else:
            zf.writestr("OEBPS/content.opf", _make_content_opf_text(book_id, title, spine_items))

        zf.writestr("OEBPS/nav.xhtml", _make_nav_xhtml(title, spine_items))
        zf.writestr("OEBPS/toc.ncx", _make_toc_ncx(book_id, title, spine_items))

        for href, content in page_files.items():
            zf.writestr(f"OEBPS/{href}", content)

        # No modo fiel, grava as imagens das páginas (PNG em base64 armazenado na PageContent)
        if mode == "fiel":
            for page in pages:
                if page.page_image_b64:
                    img_bytes = base64.b64decode(page.page_image_b64)
                    zf.writestr(f"OEBPS/images/page{page.page_number:04d}.png", img_bytes)

    logger.info("epub_built", path=output_path, pages=len(pages), mode=mode, title=title)
    return output_path


def build_chapter_epub(
    structure: BookStructure,
    chapter: ChapterInfo,
    output_path: str,
    mode: str = "fiel",
) -> str:
    chapter_pages = [
        p for p in structure.pages
        if chapter.start_page <= p.page_number <= chapter.end_page
    ]
    return build_epub(
        structure=structure,
        output_path=output_path,
        mode=mode,
        pages_subset=chapter_pages,
        chapter_title=chapter.title,
    )
