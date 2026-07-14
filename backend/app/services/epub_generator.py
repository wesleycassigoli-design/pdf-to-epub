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

# ─── Marca Medcel/Afya (modo texto) ───────────────────────────────────────────

_FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "ttf"

# (arquivo, font-family, font-weight, font-style)
_FONT_FACES = [
    ("AfyaSans-Regular.ttf", "AfyaSans-Regular", "normal", "normal"),
    ("AfyaSans-Bold.ttf", "AfyaSans-Bold", "bold", "normal"),
    ("AfyaSans-ExtraBold.ttf", "AfyaSans-ExtraBold", "bold", "normal"),
    ("AfyaSans-Light.ttf", "AfyaSans-Light", "normal", "normal"),
    ("AfyaSans-Italic.ttf", "AfyaSans-Italic", "normal", "italic"),
    ("AfyaSans-BoldItalic.ttf", "AfyaSans-BoldItalic", "bold", "italic"),
    ("AfyaSans-ExtraBoldItalic.ttf", "AfyaSans-ExtraBoldItalic", "bold", "italic"),
    ("AfyaSans-LightItalic.ttf", "AfyaSans-LightItalic", "normal", "italic"),
]

_BRAND_CSS = """.capitulo {
  text-align: left;
  margin-bottom: 10px;
  margin-top: 0px;
  font-size: 30px;
  color: #D31C5B;
  font-family: "AfyaSans-Bold";
}
.nome_autor {
  text-align: left;
  margin-bottom: 10px;
  margin-top: 10px;
  font-size: 10px;
  color: black;
  font-family: "AfyaSans-Regular";
}
h1 {
  font-family: "AfyaSans-Bold";
  color: #D31C5B;
  text-align: right;
}
h2, h3, h4, h5, h6 {
  font-family: "AfyaSans-Regular";
}
h2, h3 {
  color: #D31C5B;
}
h4, h5, h6 {
  color: #363A3D;
}
b {
  color: #363A3D;
  font-family: "AfyaSans-Bold";
}
b2 {
  color: #D31C5B;
  font-family: "AfyaSans-Bold";
}
p {
  color: #363A3D;
  font-family: "AfyaSans-Regular";
  line-height: 160%;
}
ol {
  color: #363A3D;
  font-family: "AfyaSans-Regular";
  list-style-type: none;
  line-height: 140%;
}
li {
  color: #363A3D;
  font-family: "AfyaSans-Regular";
  list-style-type: none;
  margin-left: -35px;
  line-height: 130%;
}
.destaque {
  background-color: #f1f1f1;
  padding-top: 10px;
  padding-bottom: 1px;
  border: 1px solid #ccc;
  border-radius: 5px;
  padding-left: 1em;
  padding-right: 1em;
  color: #D31C5B;
  font-family: "AfyaSans-Bold";
}
"""

# CSS complementar — elementos que não fazem parte do CSS de marca oficial
# (legenda/fonte de imagem, linha divisória, botão, tabela, caixa de alerta),
# mas usam as cores/fontes da marca. Arquivo separado, não mistura no brand.css.
_BRAND_EXTRAS_CSS = """.zoom {
  width: 100%;
  margin-top: 15px;
  margin-bottom: 15px;
}
.zoom img {
  margin-right: 8%;
  margin-left: 5.4%;
  width: 100%;
}
.zoom h5 {
  font-family: "AfyaSans-Regular";
  color: #363A3D;
  margin-top: 10px;
  margin-bottom: 10px;
}
.zoom .fonte {
  font-family: "AfyaSans-Light", "AfyaSans-Regular";
  font-size: 0.8em;
  color: #777;
  text-align: right;
}
hr {
  border: 0;
  height: 2px;
  background-image: linear-gradient(to right, transparent, #ccc, transparent);
}
.button1 {
  background-color: #f1f1f1;
  color: #D31C5B;
  border: 1.4px solid #D31C5B;
  border-radius: 1px;
  padding: 10px 10px;
  text-align: center;
  text-decoration: none;
  display: inline-block;
  font-family: "AfyaSans-Regular";
  font-size: 10px;
  cursor: pointer;
}
.button1:hover {
  background-color: #D31C5B;
  color: white;
}
.sumario {
  text-align: center;
  margin-top: 2em;
}
.medcel-table {
  width: 100%;
  border-collapse: collapse;
  margin: 1em 0;
  font-family: "AfyaSans-Regular";
  font-size: 0.9em;
}
.medcel-table th {
  background: #D31C5B;
  color: #fff;
  padding: 0.4em 0.6em;
  text-align: left;
  font-family: "AfyaSans-Bold";
}
.medcel-table td {
  border: 1px solid #ddd;
  padding: 0.4em 0.6em;
  color: #363A3D;
}
.alert-box {
  background: #f1f1f1;
  border-left: 4px solid #D31C5B;
  padding: 0.6em 1em;
  margin: 1em 0;
  font-family: "AfyaSans-Regular";
  color: #363A3D;
  font-size: 0.95em;
}
"""


def _font_face_css() -> str:
    rules = []
    for filename, family, weight, style in _FONT_FACES:
        rules.append(f"""@font-face {{
  font-family: "{family}";
  font-weight: {weight};
  font-style: {style};
  src: url("../fonts/{filename}");
}}""")
    return "\n".join(rules) + "\n"


def _brand_stylesheet() -> str:
    return _font_face_css() + "\n" + _BRAND_CSS


def _brand_manifest_items() -> str:
    """Itens de manifest OPF pro CSS de marca + extras + 8 fontes (reaproveitado por PDF e DOCX)."""
    items = [
        '<item id="brand-css" href="styles/brand.css" media-type="text/css"/>',
        '<item id="brand-extras-css" href="styles/brand-extras.css" media-type="text/css"/>',
    ]
    items += [
        f'<item id="font-{idx}" href="fonts/{filename}" media-type="application/vnd.ms-opentype"/>'
        for idx, (filename, _, _, _) in enumerate(_FONT_FACES)
    ]
    return "\n    ".join(items)


def _write_brand_assets(zf: zipfile.ZipFile) -> None:
    """Grava OEBPS/styles/brand.css, brand-extras.css e as 8 fontes AfyaSans (reaproveitado por PDF e DOCX)."""
    zf.writestr("OEBPS/styles/brand.css", _brand_stylesheet())
    zf.writestr("OEBPS/styles/brand-extras.css", _BRAND_EXTRAS_CSS)
    for filename, _, _, _ in _FONT_FACES:
        zf.write(_FONTS_DIR / filename, f"OEBPS/fonts/{filename}")


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
    if page.text_blocks:
        parts = []
        for blk in page.text_blocks:
            cls = f' class="{blk.css_class}"' if blk.css_class else ""
            parts.append(f"  <p{cls}>{_escape_xml(blk.text)}</p>")
        body = "\n".join(parts)
    else:
        # Fallback: comportamento antigo (split por linha), caso text_blocks não tenha sido populado
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
  <link rel="stylesheet" type="text/css" href="../styles/brand.css"/>
  <link rel="stylesheet" type="text/css" href="../styles/brand-extras.css"/>
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
    manifest_brand = _brand_manifest_items()
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
    {manifest_brand}
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
        else:
            # No modo texto, embute o CSS de marca e as fontes AfyaSans
            _write_brand_assets(zf)

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
