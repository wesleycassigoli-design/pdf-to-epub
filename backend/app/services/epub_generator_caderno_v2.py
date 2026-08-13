"""
epub_generator_caderno_v2.py
Gera EPUB2 no template "Caderno de Conceitos Matadores — v2" a partir de
CadernoV2Structure (produzida por pdf_processor_caderno_v2.py). Completamente
isolado de epub_generator.py, epub_generator_medcel.py e epub_generator_caderno.py
(v1) — nenhuma função é importada desses módulos (fontes/CSS/manifest também
são montados aqui, duplicados de propósito).

Estrutura gerada:
- mimetype
- META-INF/container.xml
- OEBPS/content.opf
- OEBPS/toc.ncx
- OEBPS/Text/Section0001.xhtml   (Sumário gerado — complementar ao toc.ncx)
- OEBPS/Text/Section0002.xhtml   (corpo: INCIDÊNCIA + capítulos)
- OEBPS/Styles/brand_caderno_v2.css
- OEBPS/Fonts/AfyaSans-*.ttf         (4 — completas, reaproveitadas do acervo Medcel)
- OEBPS/Images/ICONE_ConceitoMatador.png

AfyaSansPro NÃO é embutida no EPUB (ver backend/app/assets/fonts/afyasans_caderno_v2/README.md):
o subconjunto extraído do PDF de referência falha a sanitização de fonte de
leitores Chromium/WebKit. INCIDÊNCIA e o Sumário gerado usam AfyaSans-Bold/
Regular como substituto visual.
"""

import os
import uuid
import zipfile
from pathlib import Path
import structlog
from app.services.pdf_processor_caderno_v2 import CadernoV2Structure, CadernoV2Block

logger = structlog.get_logger()

_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
_FONTS_DIR = _ASSETS_DIR / "fonts" / "afyasans_caderno_v2"
_ICONS_DIR = _ASSETS_DIR / "icons" / "caderno"
_CSS_PATH = Path(__file__).resolve().parent / "brand_caderno_v2.css"

_FONT_FILES = [
    "AfyaSans-Regular.ttf",
    "AfyaSans-Bold.ttf",
    "AfyaSans-Italic.ttf",
    "AfyaSans-BoldItalic.ttf",
]
# AfyaSansPro (Light/Regular/Bold/ExtraBold) fica só no acervo de assets
# (backend/app/assets/fonts/afyasans_caderno_v2/), NÃO é embutida no EPUB —
# ver README.md nesse diretório: o subconjunto extraído do PDF de referência
# falha a sanitização de fonte usada por leitores baseado em Chromium/WebKit
# (2 dos 4 pesos não têm tabela 'cmap' e são inutilizáveis; os outros 2 só
# cobrem os caracteres do PDF de exemplo). INCIDÊNCIA e o Sumário gerado
# usam AfyaSans-Bold/Regular como substituto visual até existir um
# AfyaSansPro completo no acervo.

_ICON_FILE = "ICONE_ConceitoMatador.png"

_BODY_XHTML = "Section0002.xhtml"
_SUMARIO_XHTML = "Section0001.xhtml"


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


# ─── Corpo (Section0002) ──────────────────────────────────────────────────────

def _next_edit_id(edit_counter: list[int]) -> str:
    """Contador sequencial global de data-edit-id, usado pelo editor (/reader/[id])
    pra endereçar de forma estável cada elemento editável."""
    edit_counter[0] += 1
    return f"p-{edit_counter[0]}"


def _render_incidencia(block: CadernoV2Block, edit_counter: list[int]) -> str:
    data = block.incidencia
    lines = ['<div class="incidencia">']
    lines.append(f'<h2 class="incidencia-titulo" data-edit-id="{_next_edit_id(edit_counter)}">INCIDÊNCIA</h2>')
    if data.intro:
        lines.append(f'<p class="incidencia-intro" data-edit-id="{_next_edit_id(edit_counter)}">{_escape_xml(data.intro)}</p>')
    for item in data.items:
        lines.append('<div class="incidencia-item">')
        lines.append(f'<span class="incidencia-numero" data-edit-id="{_next_edit_id(edit_counter)}">{_escape_xml(item.number)}</span>')
        lines.append(f'<span class="incidencia-rotulo" data-edit-id="{_next_edit_id(edit_counter)}">{_escape_xml(item.label)}</span>')
        lines.append('</div>')
    lines.append('</div>')
    return "\n".join(lines)


def _build_body_xhtml(structure: CadernoV2Structure) -> str:
    edit_counter = [0]
    lines: list[str] = []
    lines.append('<?xml version="1.0" encoding="utf-8"?>')
    lines.append('<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"')
    lines.append('  "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">')
    lines.append('<html xmlns="http://www.w3.org/1999/xhtml">')
    lines.append('<head>')
    lines.append(f'  <title>{_escape_xml(structure.title)}</title>')
    lines.append('  <link href="../Styles/brand_caderno_v2.css" type="text/css" rel="stylesheet"/>')
    lines.append('</head>')
    lines.append('<body>')

    # Pilha de níveis de <ul> abertos — cada <li> fica aberto (sem fechar)
    # até o próximo <li> do mesmo nível, um sub-<ul> (nível mais profundo,
    # aninhado DENTRO do <li> ainda aberto) ou o fim da lista, pra produzir
    # aninhamento válido (<ul><li>...<ul><li>...</li></ul></li></ul>).
    list_stack: list[bool] = []  # bool = há um <li> aberto nesse nível

    def close_li_at(depth: int) -> None:
        if list_stack[depth]:
            lines.append('</li>')
            list_stack[depth] = False

    def close_lists_to(target_depth: int) -> None:
        while len(list_stack) > target_depth:
            close_li_at(len(list_stack) - 1)
            lines.append('</ul>')
            list_stack.pop()

    for block in structure.blocks:
        if block.block_type != "list_item":
            close_lists_to(0)
        else:
            level = block.marker_level
            if level >= len(list_stack):
                while len(list_stack) <= level:
                    lines.append('<ul>')
                    list_stack.append(False)
            else:
                close_lists_to(level + 1)
                close_li_at(level)

        if block.block_type == "incidencia":
            lines.append(_render_incidencia(block, edit_counter))

        elif block.block_type == "capitulo_titulo":
            lines.append(f'<h2 id="sigil_toc_id_{block.toc_id}" data-edit-id="{_next_edit_id(edit_counter)}">{_escape_xml(block.content)}</h2>')

        elif block.block_type == "subtitulo":
            lines.append(f'<h3 class="sigil_not_in_toc" data-edit-id="{_next_edit_id(edit_counter)}">{_escape_xml(block.content)}</h3>')

        elif block.block_type == "como_cai_na_prova":
            lines.append(f'<h3 class="sigil_not_in_toc como-cai-na-prova" data-edit-id="{_next_edit_id(edit_counter)}">{_escape_xml(block.content)}</h3>')

        elif block.block_type == "gabarito_comentario":
            lines.append(f'<p class="gabarito-comentario" data-edit-id="{_next_edit_id(edit_counter)}">{block.content}</p>')

        elif block.block_type == "destaque":
            lines.append(
                '<div class="destaque">\n'
                f'<div class="icone"><img data-edit-id="{_next_edit_id(edit_counter)}" alt="ICONE_ConceitoMatador" src="../Images/{_ICON_FILE}"/></div>\n'
                f'<p data-edit-id="{_next_edit_id(edit_counter)}">{block.content}</p>\n'
                '</div>'
            )

        elif block.block_type == "list_item":
            # <li> fica sem fechar de propósito — ver comentário de list_stack
            # acima. É fechado pelo próximo <li> do mesmo nível, por
            # close_li_at/close_lists_to, ou no final do documento.
            lines.append(f'<li data-edit-id="{_next_edit_id(edit_counter)}">{block.content}')
            list_stack[block.marker_level] = True

        elif block.block_type == "paragraph":
            lines.append(f'<p data-edit-id="{_next_edit_id(edit_counter)}">{block.content}</p>')

    close_lists_to(0)

    lines.append('</body>')
    lines.append('</html>')
    return "\n".join(lines)


# ─── Sumário gerado (Section0001) ─────────────────────────────────────────────

def _build_sumario_xhtml(structure: CadernoV2Structure) -> str:
    lines: list[str] = []
    lines.append('<?xml version="1.0" encoding="utf-8"?>')
    lines.append('<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"')
    lines.append('  "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">')
    lines.append('<html xmlns="http://www.w3.org/1999/xhtml">')
    lines.append('<head>')
    lines.append(f'  <title>Sumário — {_escape_xml(structure.title)}</title>')
    lines.append('  <link href="../Styles/brand_caderno_v2.css" type="text/css" rel="stylesheet"/>')
    lines.append('</head>')
    lines.append('<body>')
    lines.append('<h1 class="sumario-titulo">SUMÁRIO</h1>')
    lines.append('<ul class="sumario-lista">')
    for toc_id, text in structure.toc_entries:
        lines.append(f'<li><a href="{_BODY_XHTML}#sigil_toc_id_{toc_id}">{_escape_xml(text)}</a></li>')
    lines.append('</ul>')
    lines.append('</body>')
    lines.append('</html>')
    return "\n".join(lines)


# ─── OPF / NCX ────────────────────────────────────────────────────────────────

def _make_content_opf(book_id: str, title: str) -> str:
    uid = f"urn:uuid:{book_id}"

    manifest_items = [
        f'<item id="{_SUMARIO_XHTML}" href="Text/{_SUMARIO_XHTML}" media-type="application/xhtml+xml"/>',
        f'<item id="{_BODY_XHTML}" href="Text/{_BODY_XHTML}" media-type="application/xhtml+xml"/>',
        '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
        '<item id="brand-caderno-v2-css" href="Styles/brand_caderno_v2.css" media-type="text/css"/>',
        f'<item id="{_ICON_FILE.rsplit(".", 1)[0]}" href="Images/{_ICON_FILE}" media-type="image/png"/>',
    ]
    manifest_items += [
        f'<item id="{fname.rsplit(".", 1)[0]}.ttf" href="Fonts/{fname}" media-type="font/ttf"/>'
        for fname in _FONT_FILES
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
    <itemref idref="{_SUMARIO_XHTML}"/>
    <itemref idref="{_BODY_XHTML}"/>
  </spine>
</package>"""


def _make_toc_ncx(book_id: str, title: str, toc_entries: list[tuple]) -> str:
    points = [f"""    <navPoint id="navPoint-1" playOrder="1">
      <navLabel>
        <text>Sumário</text>
      </navLabel>
      <content src="Text/{_SUMARIO_XHTML}"/>
    </navPoint>"""]

    for order, (toc_id, text) in enumerate(toc_entries, start=2):
        points.append(f"""    <navPoint id="navPoint-{order}" playOrder="{order}">
      <navLabel>
        <text>{_escape_xml(text)}</text>
      </navLabel>
      <content src="Text/{_BODY_XHTML}#sigil_toc_id_{toc_id}"/>
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

def build_epub_caderno_v2(structure: CadernoV2Structure, output_path: str) -> str:
    """Gera o EPUB do template Caderno de Conceitos Matadores — v2. Retorna o caminho gerado."""
    if structure.used_font_fallback:
        logger.warning(
            "caderno_v2_afyasanspro_unavailable",
            detail=(
                "AfyaSansPro não está disponível como fonte completa — o subconjunto extraído do PDF "
                "de referência falha a sanitização de fonte de leitores Chromium/WebKit (2 dos 4 pesos "
                "sem tabela 'cmap', inutilizáveis; os outros 2 só cobrem os caracteres do PDF de "
                "exemplo). INCIDÊNCIA e o Sumário gerado usam AfyaSans-Bold/Regular como substituto."
            ),
        )

    book_id = str(uuid.uuid4())
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    body_xhtml = _build_body_xhtml(structure)
    sumario_xhtml = _build_sumario_xhtml(structure)
    content_opf = _make_content_opf(book_id, structure.title)
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
        zf.writestr(f"OEBPS/Text/{_SUMARIO_XHTML}", sumario_xhtml)
        zf.writestr(f"OEBPS/Text/{_BODY_XHTML}", body_xhtml)
        zf.writestr("OEBPS/Styles/brand_caderno_v2.css", css)

        for fname in _FONT_FILES:
            zf.write(_FONTS_DIR / fname, f"OEBPS/Fonts/{fname}")
        zf.write(_ICONS_DIR / _ICON_FILE, f"OEBPS/Images/{_ICON_FILE}")

    logger.info(
        "epub_caderno_v2_built",
        path=output_path,
        title=structure.title,
        blocks=len(structure.blocks),
        toc_entries=len(structure.toc_entries),
        warnings=len(structure.warnings),
    )
    return output_path
