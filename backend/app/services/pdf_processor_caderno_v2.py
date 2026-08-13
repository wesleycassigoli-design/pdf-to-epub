"""
pdf_processor_caderno_v2.py
Extração do template "Caderno de Conceitos Matadores — v2" — fonte PDF.
Completamente isolado de pdf_processor.py (pipeline Fiel/Texto), docx_processor*.py
e epub_generator*.py existentes: nenhuma função é importada desses módulos, mesmo
que duplique lógica (extração de span, heurísticas de heading/bullet/destaque) —
isolamento total é intencional, para este e os demais templates evoluírem sem
risco de regressão cruzada.

Usa pymupdf (fitz) — page.get_text("dict") por página, span a span, com
font/size/color/bbox. Cada "block" (type 0) retornado pelo PyMuPDF já
corresponde, neste documento de referência (InDesign), a um parágrafo ou item
de lista completo (marcador "•"/"◦" como 1ª linha do próprio bloco + linhas
de texto seguintes) — não é necessário agrupar linhas manualmente.

Heurísticas de detecção (engenharia reversa de
_referencia_caderno_v2/00_MODELO_CONCEITOS_MATADORES_2026.pdf via inspeção
span a span; ver comentários de cada função para os valores observados):

1. Cabeçalho/rodapé: bloco de uma linha, AfyaSans-Bold, size~10, color
   #ce0058, posicionado nos ~50pt do topo (cabeçalho: nome do capítulo) OU
   nos ~50pt da base (rodapé: número da página) — descartado sempre.
2. Título de capítulo: bloco Bold, size~15, color #182143 (navy).
   - Texto casa com "^\\d+\\.\\s" → <h2 id="sigil_toc_id_N">
   - Caso contrário → <h3 class="sigil_not_in_toc"> (subtítulo introdutório)
3. "Como cai na prova!": bloco Bold, size~13, color #ce0058 (magenta) →
   <h3 class="sigil_not_in_toc">. O bloco imediatamente seguinte, se
   inteiramente Bold+magenta (ex.: "2023 - HOB"), é o identificador da
   prova → <p><b>texto</b></p>.
4. Bullets: bloco cuja 1ª linha é só o marcador "•" (nível 0) ou "◦" (nível
   1, fonte pode ser ArialMT) → <li>, nível pelo glifo do marcador (não pela
   indentação, que varia).
5. Caixa de destaque ("conceito matador"): bloco (que NÃO é bullet) cujo
   PRIMEIRO span é Bold e cuja cor NÃO é uma das cores de heading (navy
   #182143 / magenta #ce0058) — na prática sempre #333333 (cor do corpo),
   com uma única observação de #464e69 num rótulo com fonte trocada
   (NunitoSans) no PDF de referência, tratada aqui como o mesmo padrão
   editorial (normalizada visualmente, sem tentar reproduzir a fonte
   incidental) — e cujo texto até o primeiro ":" (soma dos spans bold
   iniciais) tem menos de DESTAQUE_LABEL_MAX_CHARS caracteres.
6. "Gabarito: x" / "Comentário(s):": bloco inteiramente Bold+magenta que
   não é o heading "Como cai na prova!" → <p><b>texto</b></p> (mesmo
   tratamento do identificador de prova da regra 3).
7. Itálico: span AfyaSans-Italic (ou *-BoldItalic) dentro de um bloco →
   <i>/<b><i> inline.
8. Continuação entre páginas: quando o PDF quebra um parágrafo/item de
   lista no meio, o texto restante aparece como um bloco novo, sem marcador,
   no topo da página seguinte. Detectado por: bloco sem padrão especial
   (cairia no fallback da regra 11) + página diferente do bloco anterior +
   já existe um bloco de conteúdo aberto para anexar. Anexado ao bloco
   anterior em vez de criar um novo.
9. INCIDÊNCIA: página com um span "INCIDÊNCIA" (Bold, size>=28). Pares
   número-grande (Bold, size>=40, branco) + rótulo (Regular, branco/quase
   branco) pareados por proximidade vertical de bbox. Se o padrão não
   bater, página pulada sem travar a conversão (página opcional).
10. SUMÁRIO: página com um span "SUMÁRIO" (Bold, size>=28) — conteúdo da
    página descartado (o EPUB gera seu próprio sumário a partir dos
    capítulos detectados pela regra 2).
11. Capa: página 1 do PDF, sempre descartada (convenção fixa do template).
    Créditos: página cujo texto contém "direitos reservados" — descartada.
12. Fallback: qualquer bloco que não bata com nenhuma regra acima entra
    como <p> normal (bold/itálico inline preservados). Nunca trava por
    padrão não reconhecido, nunca perde conteúdo — registrado em warnings.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime

import fitz  # PyMuPDF
import structlog

logger = structlog.get_logger()


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def _dbg(tag: str, msg: str) -> None:
    print(f"[DEBUG {_ts()}] [pdf_processor_caderno_v2:{tag}] {msg}", flush=True)


# ─── Constantes de detecção ───────────────────────────────────────────────────

NAVY = "#182143"
MAGENTA = "#ce0058"
HEADING_COLORS = {NAVY, MAGENTA}

# Faixa (em pt) a partir da borda superior/inferior da página onde
# cabeçalho/rodapé de impressão são procurados (rule 1).
HEADER_FOOTER_BAND_PT = 50

# Texto até o primeiro ":" de um possível rótulo de destaque (rule 5) —
# "~60" no material de referência de origem; ajustado com folga após
# validação empírica contra o PDF de exemplo (o rótulo mais longo
# observado, "Notificação ao SINAN (Sistema de Informação de Agravos de
# Notificação)", tem 70 caracteres).
DESTAQUE_LABEL_MAX_CHARS = 90

NUMBERED_HEADING_RE = re.compile(r"^\d+\.\s")

ICONE_CONCEITO_MATADOR = "ICONE_ConceitoMatador"


def _is_bold_span(span: dict) -> bool:
    font = (span.get("font") or "").lower()
    return "bold" in font or bool(span.get("flags", 0) & 2**4)


def _is_italic_span(span: dict) -> bool:
    font = (span.get("font") or "").lower()
    return "italic" in font or bool(span.get("flags", 0) & 2**1)


def _color_hex(color) -> str:
    if color is None:
        return "#000000"
    return "#%06x" % color


def _strip_accents_lower(text: str) -> str:
    norm = unicodedata.normalize("NFKD", text)
    return "".join(c for c in norm if not unicodedata.combining(c)).lower()


# ─── Estruturas de dados ──────────────────────────────────────────────────────

@dataclass
class CadernoV2Image:
    filename: str
    data_b64: str
    media_type: str


@dataclass
class IncidenciaItem:
    number: str
    label: str


@dataclass
class IncidenciaData:
    intro: str
    items: list[IncidenciaItem] = field(default_factory=list)


@dataclass
class CadernoV2Block:
    # capitulo_titulo | subtitulo | como_cai_na_prova | prova_label |
    # gabarito_comentario | destaque | list_item | paragraph | incidencia | hr
    block_type: str
    content: str = ""
    toc_id: int | None = None
    marker_level: int = 0
    incidencia: IncidenciaData | None = None


@dataclass
class CadernoV2Structure:
    title: str
    blocks: list[CadernoV2Block] = field(default_factory=list)
    toc_entries: list[tuple] = field(default_factory=list)  # [(toc_id, text), ...]
    original_filename: str = ""
    warnings: list[str] = field(default_factory=list)
    used_font_fallback: bool = False  # AfyaSansPro subset extraído do PDF (sempre True hoje)


# ─── Runs inline (bold/itálico) ───────────────────────────────────────────────

def _escape_html(text: str) -> str:
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def _line_text(line: dict) -> str:
    return "".join(s.get("text", "") for s in line.get("spans", []))


def _block_text(block: dict, skip_first_line: bool = False) -> str:
    lines = block.get("lines", [])
    if skip_first_line:
        lines = lines[1:]
    return " ".join(_line_text(line).strip() for line in lines if _line_text(line).strip())


def _spans_to_html(spans: list[dict]) -> str:
    parts = []
    for s in spans:
        text = _escape_html(s.get("text", ""))
        if not text.strip():
            parts.append(text)
            continue
        bold = _is_bold_span(s)
        italic = _is_italic_span(s)
        if bold and italic:
            parts.append(f"<b><i>{text}</i></b>")
        elif bold:
            parts.append(f"<b>{text}</b>")
        elif italic:
            parts.append(f"<i>{text}</i>")
        else:
            parts.append(text)
    return "".join(parts)


def _block_html(block: dict, skip_first_line: bool = False) -> str:
    """Concatena o HTML inline (bold/itálico) de todas as linhas do bloco,
    juntando a quebra de linha do PDF (hifenização/wrap) com um espaço."""
    lines = block.get("lines", [])
    if skip_first_line:
        lines = lines[1:]
    parts = []
    for line in lines:
        spans = line.get("spans", [])
        html = _spans_to_html(spans)
        if html.strip():
            parts.append(html.strip())
    return " ".join(parts)


# ─── Classificação de blocos ──────────────────────────────────────────────────

def _first_real_span(block: dict) -> dict | None:
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            if span.get("text", "").strip():
                return span
    return None


def _block_first_line_marker(block: dict) -> str | None:
    """Se a 1ª linha do bloco é só um marcador de bullet ("•"/"◦",
    possivelmente com tab antes), retorna o glifo; caso contrário None."""
    lines = block.get("lines", [])
    if not lines:
        return None
    text = _line_text(lines[0]).strip()
    if text in ("•", "◦"):
        return text
    return None


def _is_header_footer_block(block: dict, page_height: float) -> bool:
    """Rule 1 — numeração de impressão (nome do capítulo no topo, número da
    página na base). Bloco de 1 linha, Bold, size~10, color magenta,
    dentro da faixa de ~50pt do topo OU da base da página."""
    lines = block.get("lines", [])
    if len(lines) != 1:
        return False
    span = _first_real_span(block)
    if span is None:
        return False
    if not _is_bold_span(span):
        return False
    if _color_hex(span.get("color")) != MAGENTA:
        return False
    size = span.get("size", 0)
    if not (9.0 <= size <= 11.0):
        return False
    y0, y1 = block["bbox"][1], block["bbox"][3]
    near_top = y0 < HEADER_FOOTER_BAND_PT
    near_bottom = y1 > page_height - HEADER_FOOTER_BAND_PT
    return near_top or near_bottom


def _is_fully_styled(block: dict, color: str, bold_only: bool = True) -> bool:
    """Todo texto real do bloco é Bold (se bold_only) e da cor dada —
    usado pra 'Como cai na prova!' / prova-id / Gabarito / Comentário,
    que são sempre blocos de uma linha inteiramente na cor de destaque."""
    any_text = False
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            if not span.get("text", "").strip():
                continue
            any_text = True
            if bold_only and not _is_bold_span(span):
                return False
            if _color_hex(span.get("color")) != color:
                return False
    return any_text


def _is_numbered_heading(block: dict) -> tuple[bool, str]:
    """Rule 2 — título de capítulo. Bold, size~15, color navy."""
    span = _first_real_span(block)
    if span is None:
        return False, ""
    if not _is_bold_span(span) or _color_hex(span.get("color")) != NAVY:
        return False, ""
    if not (13.5 <= span.get("size", 0) <= 17.0):
        return False, ""
    text = _block_text(block)
    return True, text


def _is_como_cai_na_prova(block: dict) -> bool:
    span = _first_real_span(block)
    if span is None:
        return False
    text = _block_text(block)
    return (
        _is_bold_span(span)
        and _color_hex(span.get("color")) == MAGENTA
        and _strip_accents_lower(text).strip() == "como cai na prova!"
    )


def _destaque_label_len(block: dict) -> int | None:
    """Soma os spans Bold iniciais do bloco até o primeiro ':' — usado
    pela heurística da rule 5. Retorna None se não houver ':' nos spans
    bold iniciais (não é padrão 'termo: definição')."""
    running = ""
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            text = span.get("text", "")
            if not text.strip():
                continue
            if not _is_bold_span(span):
                return len(running) if ":" in running else None
            running += text
            if ":" in text:
                return len(running.split(":", 1)[0])
    return None


def _is_destaque(block: dict) -> bool:
    """Rule 5 — caixa de destaque. Primeiro span Bold, cor fora do
    conjunto de cores de heading (navy/magenta — na prática sempre
    #333333, com uma exceção observada de #464e69 por troca de fonte no
    PDF de origem, tolerada de propósito), texto-rótulo curto."""
    span = _first_real_span(block)
    if span is None:
        return False
    if not _is_bold_span(span):
        return False
    color = _color_hex(span.get("color"))
    if color in HEADING_COLORS:
        return False
    label_len = _destaque_label_len(block)
    if label_len is None:
        return False
    return label_len < DESTAQUE_LABEL_MAX_CHARS


# ─── Página especial: INCIDÊNCIA ─────────────────────────────────────────────

def _page_has_span_text(page_dict: dict, target: str, min_size: float = 28.0) -> bool:
    for block in page_dict["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if span.get("size", 0) < min_size:
                    continue
                if _strip_accents_lower(span.get("text", "").strip()) == target:
                    return True
    return False


def _extract_incidencia(page_dict: dict) -> IncidenciaData:
    """Rule 9 — pares (número grande Bold branco) + (rótulo Regular
    branco/quase-branco), pareados por proximidade vertical de bbox.
    Texto Regular à esquerda (x0 baixo), antes do primeiro número, é o
    parágrafo introdutório da página (não faz parte do rule 9 original,
    mas melhora a fidelidade visual sem custo de robustez)."""
    numbers = []
    labels = []
    intro_lines = []
    for block in page_dict["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "").strip()
                if not text:
                    continue
                size = span.get("size", 0)
                color = _color_hex(span.get("color"))
                x0, y0, _, y1 = line["bbox"]
                if _is_bold_span(span) and size >= 40 and color == "#ffffff":
                    numbers.append({"text": text, "y0": y0, "y1": y1})
                elif size < 20 and color in ("#ffffff", "#eeeeee") and not _is_bold_span(span) and size >= 10:
                    if x0 < 300:
                        intro_lines.append({"text": text, "y0": y0})
                    else:
                        labels.append({"text": text, "y0": y0, "y1": y1})

    if not numbers:
        return IncidenciaData(intro="", items=[])

    numbers.sort(key=lambda n: n["y0"])
    items = []
    for num in numbers:
        # Rótulos cuja faixa vertical (y0..y1) sobrepõe a do número.
        matched = [l for l in labels if l["y0"] < num["y1"] and l["y1"] > num["y0"]]
        matched.sort(key=lambda l: l["y0"])
        label_text = " ".join(m["text"].strip() for m in matched).strip()
        items.append(IncidenciaItem(number=num["text"], label=label_text))

    intro_lines.sort(key=lambda l: l["y0"])
    intro = " ".join(l["text"] for l in intro_lines).strip()
    return IncidenciaData(intro=intro, items=items)


# ─── Processador principal ───────────────────────────────────────────────────

def analyze_pdf_caderno_v2(pdf_path: str, original_filename: str = "") -> CadernoV2Structure:
    """Analisa o PDF no padrão "Caderno de Conceitos Matadores — v2"."""
    _dbg("analyze_pdf_caderno_v2", f"INICIO pdf_path={pdf_path} original_filename={original_filename}")
    doc = fitz.open(pdf_path)
    filename = original_filename or "Caderno de Conceitos Matadores"
    metadata_title = (doc.metadata or {}).get("title") or ""
    title = metadata_title.strip() or (filename.rsplit(".", 1)[0] if "." in filename else filename)

    blocks: list[CadernoV2Block] = []
    toc_entries: list[tuple] = []
    warnings: list[str] = []
    toc_counter = 0

    last_block_page: int | None = None
    open_block_ref: CadernoV2Block | None = None  # último bloco de conteúdo emitido, pra continuação entre páginas

    total_pages = len(doc)

    for page_index, page in enumerate(doc):
        page_num = page_index + 1

        # Regra 11 — capa (convenção fixa: sempre a primeira página).
        if page_index == 0:
            continue

        page_dict = page.get_text("dict")
        page_height = page.rect.height

        page_text = page.get_text("text")
        if "direitos reservados" in _strip_accents_lower(page_text):
            continue  # Regra 11 — página de créditos/direitos autorais.

        if _page_has_span_text(page_dict, "incidencia"):
            incidencia = _extract_incidencia(page_dict)
            if incidencia.items:
                blocks.append(CadernoV2Block("incidencia", incidencia=incidencia))
            else:
                warnings.append(
                    f"Página {page_num}: título 'INCIDÊNCIA' encontrado, mas o padrão "
                    f"número+rótulo não bateu — página de incidência pulada (não é obrigatória)."
                )
            last_block_page = page_num
            continue

        if _page_has_span_text(page_dict, "sumario"):
            # Regra 10 — sumário nativo do PDF descartado; o EPUB gera o seu.
            last_block_page = page_num
            continue

        content_blocks = [b for b in page_dict["blocks"] if b.get("type") == 0]

        for block in content_blocks:
            if not block.get("lines"):
                continue

            if _is_header_footer_block(block, page_height):
                continue

            text_plain = _block_text(block)
            if not text_plain:
                continue

            marker = _block_first_line_marker(block)

            # Regra 8 — continuação de parágrafo/item de lista quebrado
            # entre páginas: bloco sem marcador, cuja página difere da do
            # último bloco de conteúdo emitido, e que não bate com nenhum
            # padrão especial (título, prova, destaque) — só cai aqui
            # depois de garantir que não é heading/prova/destaque/bullet.
            is_continuation_candidate = (
                marker is None
                and open_block_ref is not None
                and last_block_page is not None
                and page_num != last_block_page
                and not _is_numbered_heading(block)[0]
                and not _is_como_cai_na_prova(block)
                and not _is_fully_styled(block, MAGENTA)
                and not _is_destaque(block)
            )
            if is_continuation_candidate:
                open_block_ref.content = f"{open_block_ref.content} {_block_html(block)}".strip()
                last_block_page = page_num
                continue

            last_block_page = page_num

            if marker is not None:
                level = 0 if marker == "•" else 1
                html = _block_html(block, skip_first_line=True)
                new_block = CadernoV2Block("list_item", content=html, marker_level=level)
                blocks.append(new_block)
                open_block_ref = new_block
                continue

            is_numbered, heading_text = _is_numbered_heading(block)
            if is_numbered:
                if NUMBERED_HEADING_RE.match(heading_text):
                    toc_counter += 1
                    new_block = CadernoV2Block("capitulo_titulo", content=heading_text, toc_id=toc_counter)
                    blocks.append(new_block)
                    toc_entries.append((toc_counter, heading_text))
                else:
                    new_block = CadernoV2Block("subtitulo", content=heading_text)
                    blocks.append(new_block)
                open_block_ref = new_block
                continue

            if _is_como_cai_na_prova(block):
                new_block = CadernoV2Block("como_cai_na_prova", content=_block_text(block))
                blocks.append(new_block)
                open_block_ref = new_block
                continue

            if _is_fully_styled(block, MAGENTA):
                # Regras 3 (identificador de prova) e 6 (Gabarito/Comentário) —
                # mesmo tratamento visual: <p><b>texto</b></p>.
                new_block = CadernoV2Block("gabarito_comentario", content=_block_html(block))
                blocks.append(new_block)
                open_block_ref = new_block
                continue

            if _is_destaque(block):
                new_block = CadernoV2Block("destaque", content=_block_html(block))
                blocks.append(new_block)
                open_block_ref = new_block
                continue

            # Regra 11 — fallback: parágrafo comum.
            new_block = CadernoV2Block("paragraph", content=_block_html(block))
            blocks.append(new_block)
            open_block_ref = new_block

    if not blocks:
        warnings.append("Nenhum bloco de conteúdo reconhecido no PDF — verifique se o arquivo segue o padrão esperado.")

    warnings.append(
        "AfyaSansPro (Light/Regular/Bold/ExtraBold) não está disponível como fonte completa. O "
        "subconjunto extraído do PDF de referência (backend/app/assets/fonts/afyasans_caderno_v2/) "
        "falha a sanitização de fonte usada por leitores baseados em Chromium/WebKit — verificado "
        "empiricamente: 2 dos 4 pesos (Light/ExtraBold) não têm tabela 'cmap' e não renderizam em "
        "nenhum leitor; os outros 2 (Regular/Bold), mesmo reparados, só cobrem os caracteres já "
        "usados no PDF de exemplo. Por isso a página INCIDÊNCIA e o Sumário gerado usam AfyaSans-"
        "Bold/Regular (fonte completa) como substituto visual, não AfyaSansPro. Ver README.md em "
        "backend/app/assets/fonts/afyasans_caderno_v2/ para repor com fontes completas no futuro."
    )

    logger.info(
        "caderno_v2_pdf_analysis_done",
        title=title,
        blocks=len(blocks),
        toc_entries=len(toc_entries),
        warnings=len(warnings),
        total_pages=total_pages,
    )
    _dbg("analyze_pdf_caderno_v2", f"FIM (sucesso) titulo={title!r} blocks={len(blocks)} toc_entries={len(toc_entries)}")

    return CadernoV2Structure(
        title=title,
        blocks=blocks,
        toc_entries=toc_entries,
        original_filename=filename,
        warnings=warnings,
        used_font_fallback=True,
    )
