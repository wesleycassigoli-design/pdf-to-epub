"""
docx_processor_caderno.py
Processador DOCX para o template "Caderno de Conceitos Matadores" —
completamente isolado de docx_processor.py (Medcel) e docx_processor_generico.py
(Genérico). Nenhuma função é importada desses módulos, mesmo que duplique
lógica (extração de imagem, runs, controle de alterações) — isolamento total
é intencional aqui, para que os três templates evoluam sem risco de regressão
cruzada.

Mapeamento DOCX → EPUB (engenharia reversa de um exemplo de referência):
1. 1º parágrafo do documento               -> <div class="caderno">
2. 2º parágrafo relevante                  -> <div class="capitulo">, seguido de <hr/>
3. Parágrafo com imagem grande e sem texto  -> <div class="imagem"><img></div>
4. Parágrafo com imagem pequena + texto     -> <div class="destaque"> com ícone
   "ConceitoMatador" (único ícone suportado por enquanto)
5. Estilo "List Paragraph"                 -> <ol><li><b2>marcador</b2>texto</li></ol>
   (marcador por nível: ilvl 0 = "▶", ilvl >=1 = "▷▷")
6. "Heading 3" cujo texto já começa com "N. " -> <h2 id="sigil_toc_id_N">
   (N = contador global sequencial)
7. Parágrafo com sombreado rosa/magenta (fill em PINK_SHADES): olha os
   parágrafos seguintes até o próximo parágrafo rosa (ou fim do documento);
   se houver "Heading 3" numerado nesse intervalo, este título é introdução
   -> <h3 class="sigil_not_in_toc"> sem número; caso contrário, recebe ele
   mesmo o próximo número da sequência -> <h2 id="sigil_toc_id_N">.
8. Parágrafo bold, cor #D31C5B, SEM sombreado -> <h3 class="sigil_not_in_toc">
9. Qualquer outro parágrafo com texto -> <p>texto</p>
"""

import re
import base64
import traceback
from dataclasses import dataclass, field
from datetime import datetime

from docx import Document
from docx.oxml.ns import qn
import structlog

logger = structlog.get_logger()


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def _dbg(tag: str, msg: str) -> None:
    print(f"[DEBUG {_ts()}] [docx_processor_caderno:{tag}] {msg}", flush=True)


# ─── Constantes de detecção ───────────────────────────────────────────────────

# Sombreados rosa/magenta observados no material de referência — qualquer um
# destes marca um "título introdutório" (regra 7).
PINK_SHADES = {"E6257B", "D41C5B", "D31C5B"}
# Cor de texto rosa usada nos títulos bold sem sombreado (regra 8).
PINK_TEXT_COLOR = "D31C5B"
# Acima deste tamanho (em EMU; 1px a 96dpi = 9525 EMU) uma imagem embutida é
# tratada como "grande" (regra 3); abaixo, como ícone pequeno (regra 4).
# Observado: imagem grande real ~567x387px: ícone pequeno real ~36x29px —
# folga ampla dos dois lados pro corte em 150px.
SMALL_IMAGE_MAX_EMU = 150 * 9525
# Marcador de lista por nível de indentação (w:ilvl). Níveis mais profundos
# que os observados reaproveitam o marcador do nível 1 (nunca travar).
LIST_LEVEL_MARKERS = {0: "▶", 1: "▷▷"}
DEFAULT_LIST_MARKER = "▷▷"
ICONE_CONCEITO_MATADOR = "ICONE_ConceitoMatador"

W_DEL = qn("w:del")
W_MOVEFROM = qn("w:moveFrom")
W_T = qn("w:t")
W_R = qn("w:r")
W_RPR = qn("w:rPr")
W_PPR = qn("w:pPr")
W_B = qn("w:b")
W_I = qn("w:i")
W_COLOR = qn("w:color")
W_SHD = qn("w:shd")
W_FILL = qn("w:fill")
W_VAL = qn("w:val")
W_NUMPR = qn("w:numPr")
W_ILVL = qn("w:ilvl")
W_DRAWING = qn("w:drawing")
WP_EXTENT = qn("wp:extent")
A_BLIP = qn("a:blip")
R_EMBED = qn("r:embed")


# ─── Estruturas de dados ──────────────────────────────────────────────────────

@dataclass
class CadernoImage:
    filename: str
    data_b64: str
    media_type: str


@dataclass
class CadernoBlock:
    block_type: str  # caderno | capitulo | hr | imagem | destaque | list_item | heading_numbered | heading_not_in_toc | paragraph
    content: str = ""
    image: CadernoImage | None = None
    toc_id: int | None = None
    marker: str = ""


@dataclass
class CadernoStructure:
    title: str
    blocks: list[CadernoBlock] = field(default_factory=list)
    images: list[CadernoImage] = field(default_factory=list)
    toc_entries: list[tuple] = field(default_factory=list)  # [(toc_id, text), ...]
    original_filename: str = ""
    warnings: list[str] = field(default_factory=list)


# ─── Extração robusta de XML (mesma lógica anti track-changes dos outros
#     processadores, duplicada de propósito — isolamento total) ──────────────

def _is_inside_tag(element, tag) -> bool:
    parent = element.getparent()
    while parent is not None:
        if parent.tag == tag:
            return True
        parent = parent.getparent()
    return False


def _run_props(r_element) -> dict:
    bold, italic, color = False, False, None
    rpr = r_element.find(W_RPR)
    if rpr is not None:
        b = rpr.find(W_B)
        i = rpr.find(W_I)
        c = rpr.find(W_COLOR)
        if b is not None and b.get(W_VAL) not in ("0", "false"):
            bold = True
        if i is not None and i.get(W_VAL) not in ("0", "false"):
            italic = True
        if c is not None:
            color = (c.get(W_VAL) or "").upper()
    return {"bold": bold, "italic": italic, "color": color}


def _get_paragraph_runs(paragraph) -> list[dict]:
    runs = []
    for r in paragraph._p.findall(".//" + W_R):
        if _is_inside_tag(r, W_DEL) or _is_inside_tag(r, W_MOVEFROM):
            continue
        text = "".join(t.text or "" for t in r.findall(W_T))
        if not text:
            continue
        runs.append({"text": text, **_run_props(r)})
    return runs


def _paragraph_mark_deleted(paragraph) -> bool:
    """Marca de fim de parágrafo deletada via Track Changes — quando presente,
    este parágrafo físico deve se fundir com o próximo (mesma lógica dos
    outros dois processadores, duplicada aqui de propósito)."""
    ppr = paragraph._p.find(W_PPR)
    if ppr is None:
        return False
    rpr = ppr.find(W_RPR)
    if rpr is None:
        return False
    return rpr.find(W_DEL) is not None


def _merge_tracked_paragraphs(paragraphs: list) -> list[list]:
    groups: list[list] = []
    current: list = []
    for para in paragraphs:
        current.append(para)
        if not _paragraph_mark_deleted(para):
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return groups


def _group_runs(group: list) -> list[dict]:
    runs = []
    for para in group:
        runs.extend(_get_paragraph_runs(para))
    return runs


def _escape_html(text: str) -> str:
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def _runs_to_html(runs: list[dict]) -> str:
    parts = []
    for r in runs:
        text = _escape_html(r["text"])
        if not text.strip():
            parts.append(text)
            continue
        if r["bold"] and r["italic"]:
            parts.append(f"<b><i>{text}</i></b>")
        elif r["bold"]:
            parts.append(f"<b>{text}</b>")
        elif r["italic"]:
            parts.append(f"<i>{text}</i>")
        else:
            parts.append(text)
    return "".join(parts)


def _group_shading_fill(group: list) -> str | None:
    """Sombreado (w:shd/@w:fill) do primeiro parágrafo físico do grupo."""
    ppr = group[0]._p.find(W_PPR)
    if ppr is None:
        return None
    shd = ppr.find(W_SHD)
    if shd is None:
        return None
    fill = shd.get(W_FILL)
    if not fill or fill.lower() == "auto":
        return None
    return fill.upper()


def _group_style_name(group: list) -> str | None:
    style = group[0].style
    return style.name if style else None


def _group_ilvl(group: list) -> int | None:
    ppr = group[0]._p.find(W_PPR)
    if ppr is None:
        return None
    numpr = ppr.find(W_NUMPR)
    if numpr is None:
        return None
    ilvl_el = numpr.find(W_ILVL)
    if ilvl_el is None:
        return 0
    try:
        return int(ilvl_el.get(W_VAL))
    except (TypeError, ValueError):
        return 0


def _group_is_bold_pink_unshaded(group: list, runs: list[dict]) -> bool:
    if _group_shading_fill(group) is not None:
        return False
    return any(r["bold"] and r["color"] == PINK_TEXT_COLOR for r in runs)


def _group_images(group: list, img_counter: list) -> list[dict]:
    """Extrai imagens embutidas no grupo (bytes, media_type, extensão, extent
    em EMU). Ignora imagens dentro de w:del/w:moveFrom (Track Changes)."""
    found = []
    for para in group:
        p_element = para._p
        drawings = p_element.findall(".//" + W_DRAWING)
        for drawing in drawings:
            if _is_inside_tag(drawing, W_DEL) or _is_inside_tag(drawing, W_MOVEFROM):
                continue
            blip = drawing.find(".//" + A_BLIP)
            if blip is None:
                continue
            rId = blip.get(R_EMBED)
            if not rId:
                continue
            extent = drawing.find(".//" + WP_EXTENT)
            cx = int(extent.get("cx")) if extent is not None and extent.get("cx") else 0
            cy = int(extent.get("cy")) if extent is not None and extent.get("cy") else 0
            try:
                part = para.part.related_parts[rId]
                img_data = part.blob
                ct = part.content_type
                ext = "jpg" if "jpeg" in ct else "png"
                img_counter[0] += 1
                found.append({
                    "data": img_data,
                    "media_type": ct,
                    "ext": ext,
                    "cx": cx,
                    "cy": cy,
                })
            except Exception as e:
                _dbg("_group_images", f"EXCEPTION: {e!r}")
                print(traceback.format_exc(), flush=True)
                logger.warning("caderno_image_extraction_failed", error=str(e))
    return found


_NUMBERED_RE = re.compile(r"^\d+\.\s")


def _is_numbered_heading3(style_name: str | None, text: str) -> bool:
    return style_name == "Heading 3" and bool(_NUMBERED_RE.match(text))


# ─── Processador principal ───────────────────────────────────────────────────

def analyze_docx_caderno(docx_path: str, original_filename: str = "") -> CadernoStructure:
    """Analisa o .docx no padrão "Caderno de Conceitos Matadores"."""
    _dbg("analyze_docx_caderno", f"INICIO docx_path={docx_path} original_filename={original_filename}")
    doc = Document(docx_path)
    filename = original_filename or "Caderno de Conceitos Matadores"

    groups_raw = _merge_tracked_paragraphs(doc.paragraphs)
    _dbg("analyze_docx_caderno", f"_merge_tracked_paragraphs OK -> {len(groups_raw)} grupos")

    img_counter = [0]

    # Primeira passada: metadados de cada grupo (necessário pro lookahead da regra 7)
    meta = []
    for group in groups_raw:
        runs = _group_runs(group)
        text_plain = "".join(r["text"] for r in runs).strip()
        images = _group_images(group, img_counter)
        if not text_plain and not images:
            continue  # grupo vazio, sem efeito visual
        meta.append({
            "group": group,
            "runs": runs,
            "text_plain": text_plain,
            "text_html_raw": _runs_to_html(runs),
            "images": images,
            "style_name": _group_style_name(group),
            "shading_fill": _group_shading_fill(group),
            "ilvl": _group_ilvl(group),
        })

    _dbg("analyze_docx_caderno", f"grupos relevantes (com texto ou imagem): {len(meta)}")

    blocks: list[CadernoBlock] = []
    images_all: list[CadernoImage] = []
    toc_entries: list[tuple] = []
    warnings: list[str] = []
    toc_counter = 0

    caderno_found = False
    capitulo_found = False
    title = ""

    i = 0
    n = len(meta)
    while i < n:
        m = meta[i]

        # Regras 1 e 2 — são estritamente posicionais: o 1º e o 2º grupo com
        # texto do documento, independente de estilo específico.
        if not caderno_found:
            if not m["text_plain"]:
                i += 1
                continue
            blocks.append(CadernoBlock("caderno", content=m["text_plain"]))
            caderno_found = True
            i += 1
            continue

        if not capitulo_found:
            if not m["text_plain"]:
                i += 1
                continue
            blocks.append(CadernoBlock("capitulo", content=m["text_plain"]))
            title = m["text_plain"]
            blocks.append(CadernoBlock("hr"))
            capitulo_found = True
            i += 1
            continue

        # Regras 3/4 — imagem no parágrafo, checada ANTES de estilo/sombreado
        # (uma imagem+texto num parágrafo estilo "Heading 3", por exemplo,
        # ainda vira caixa de destaque, não um heading).
        if m["images"]:
            if len(m["images"]) > 1:
                warnings.append(
                    f"Parágrafo com {len(m['images'])} imagens — usada apenas a primeira "
                    f"(texto: {m['text_plain'][:60]!r})"
                )
            img = m["images"][0]
            is_small = max(img["cx"], img["cy"]) <= SMALL_IMAGE_MAX_EMU
            if is_small:
                # Regra 4 — ícone pequeno + texto = caixa de destaque. Usa
                # sempre o ícone ConceitoMatador (único suportado por ora),
                # descartando os bytes da imagem realmente embutida no docx.
                blocks.append(CadernoBlock("destaque", content=m["text_html_raw"]))
            else:
                # Regra 3 — imagem grande, standalone.
                if m["text_plain"]:
                    warnings.append(
                        f"Imagem grande com texto no mesmo parágrafo — texto descartado "
                        f"(imagem preservada): {m['text_plain'][:60]!r}"
                    )
                idx = len(images_all) + 1
                cad_img = CadernoImage(
                    filename=f"imagem_{idx:03d}.{img['ext']}",
                    data_b64=base64.b64encode(img["data"]).decode(),
                    media_type=img["media_type"],
                )
                images_all.append(cad_img)
                blocks.append(CadernoBlock("imagem", image=cad_img))
            i += 1
            continue

        # Regra 5 — "List Paragraph"
        if m["style_name"] == "List Paragraph":
            level = m["ilvl"] or 0
            marker = LIST_LEVEL_MARKERS.get(level, DEFAULT_LIST_MARKER)
            blocks.append(CadernoBlock("list_item", content=m["text_html_raw"], marker=marker))
            i += 1
            continue

        # Regra 6 — "Heading 3" numerado ("N. texto")
        if _is_numbered_heading3(m["style_name"], m["text_plain"]):
            toc_counter += 1
            blocks.append(CadernoBlock("heading_numbered", content=m["text_plain"], toc_id=toc_counter))
            toc_entries.append((toc_counter, m["text_plain"]))
            i += 1
            continue

        # Regra 7 — parágrafo com sombreado rosa/magenta: decide por lookahead
        if m["shading_fill"] in PINK_SHADES:
            has_numbered_ahead = False
            j = i + 1
            while j < n and meta[j]["shading_fill"] not in PINK_SHADES:
                if _is_numbered_heading3(meta[j]["style_name"], meta[j]["text_plain"]):
                    has_numbered_ahead = True
                    break
                j += 1
            if has_numbered_ahead:
                blocks.append(CadernoBlock("heading_not_in_toc", content=m["text_plain"]))
            else:
                toc_counter += 1
                text = m["text_plain"]
                numbered_text = text if _NUMBERED_RE.match(text) else f"{toc_counter}. {text}"
                blocks.append(CadernoBlock("heading_numbered", content=numbered_text, toc_id=toc_counter))
                toc_entries.append((toc_counter, numbered_text))
            i += 1
            continue

        # Regra 8 — bold, cor #D31C5B, sem sombreado
        if _group_is_bold_pink_unshaded(m["group"], m["runs"]):
            blocks.append(CadernoBlock("heading_not_in_toc", content=m["text_plain"]))
            i += 1
            continue

        # Regra 9 — fallback
        if m["text_plain"]:
            blocks.append(CadernoBlock("paragraph", content=m["text_html_raw"]))
        i += 1

    if not title:
        title = filename.rsplit(".", 1)[0] if "." in filename else filename

    if warnings:
        logger.warning("caderno_docx_analysis_warnings", count=len(warnings), warnings=warnings)

    logger.info(
        "caderno_docx_analysis_done",
        title=title,
        blocks=len(blocks),
        images=len(images_all),
        toc_entries=len(toc_entries),
        warnings=len(warnings),
    )
    _dbg("analyze_docx_caderno", f"FIM (sucesso) titulo={title!r} blocks={len(blocks)} imagens={len(images_all)}")

    return CadernoStructure(
        title=title,
        blocks=blocks,
        images=images_all,
        toc_entries=toc_entries,
        original_filename=filename,
        warnings=warnings,
    )
