"""
docx_processor.py
Processa arquivos .docx no padrão Medcel e monta estrutura para geração de EPUB.

Detecta por heurística:
- Título do capítulo
- Autores
- Seções H2 (padrão: "1 INTRODUÇÃO", "2 FISIOPATOLOGIA" etc.)
- Seções H3
- Parágrafos normais
- Imagens com legendas
- Bloco de referências
- Quadros/figuras com classe zoom
"""

import re
import base64
from io import BytesIO
from dataclasses import dataclass, field
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH
import structlog

logger = structlog.get_logger()


# ─── Estruturas de dados ──────────────────────────────────────────────────────

@dataclass
class DocxImage:
    filename: str        # ex: img001.jpg
    data_b64: str        # imagem em base64
    media_type: str      # image/jpeg ou image/png
    caption: str = ""    # legenda detectada abaixo da imagem
    source: str = ""     # fonte detectada abaixo da legenda


@dataclass
class DocxBlock:
    """Bloco de conteúdo de uma seção."""
    block_type: str      # "paragraph", "h3", "image", "list_item", "alert", "table"
    content: str = ""    # texto HTML-safe
    image: DocxImage = None
    raw_html: str = ""   # HTML já montado (para tabelas)


@dataclass
class DocxSection:
    """Seção H2 do documento."""
    number: int
    title: str           # ex: "1 INTRODUÇÃO"
    blocks: list[DocxBlock] = field(default_factory=list)


@dataclass
class DocxStructure:
    """Estrutura completa do documento Medcel."""
    title: str
    authors: str
    sections: list[DocxSection] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    images: list[DocxImage] = field(default_factory=list)
    original_filename: str = ""


# ─── Padrões de detecção ─────────────────────────────────────────────────────

# "1 INTRODUÇÃO", "2 FISIOPATOLOGIA", "10 TÍTULO"
H2_PATTERN = re.compile(r"^(\d+)\s+([A-ZÁÉÍÓÚÂÊÎÔÛÃÕÀÜÇ][A-ZÁÉÍÓÚÂÊÎÔÛÃÕÀÜÇ\s\-\/\(\)]{2,})$")

# "1.1 Subtítulo", "2.3 Algo"
H3_PATTERN = re.compile(r"^(\d+\.\d+)\s+\S+")

# Padrão de autores: contém • ou múltiplos nomes separados
AUTHOR_PATTERN = re.compile(r"[A-Z][a-záéíóú]+\s+[A-Z][a-záéíóú]+")

# Alertas/destaques: começa com palavra em maiúsculas seguida de :
ALERT_PATTERN = re.compile(r"^(ALERTA|PONTO DE PROVA|ATENÇÃO|IMPORTANTE|DICA|CUIDADO)[:\s]", re.IGNORECASE)

# Referências
REF_PATTERN = re.compile(r"^[A-ZÁÉÍÓÚ]+,\s+[A-Z]|^https?://", re.IGNORECASE)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _escape_html(text: str) -> str:
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def _is_bold(paragraph) -> bool:
    """Verifica se o parágrafo inteiro é negrito."""
    for run in paragraph.runs:
        if run.bold:
            return True
    return False


def _is_large_font(paragraph, min_size: int = 13) -> bool:
    """Verifica se algum run tem fonte grande."""
    for run in paragraph.runs:
        if run.font.size and run.font.size.pt >= min_size:
            return True
    return False


def _get_run_html(run) -> str:
    """Converte um run em HTML inline respeitando bold/italic."""
    text = _escape_html(run.text)
    if not text.strip():
        return text
    if run.bold and run.italic:
        return f"<b><i>{text}</i></b>"
    if run.bold:
        return f"<b>{text}</b>"
    if run.italic:
        return f"<i>{text}</i>"
    return text


def _paragraph_to_html(paragraph) -> str:
    """Converte parágrafo em HTML preservando bold/italic inline."""
    parts = []
    for run in paragraph.runs:
        parts.append(_get_run_html(run))
    return "".join(parts)


def _is_h2_candidate(text: str, paragraph) -> bool:
    """Detecta se é um título H2 (seção numerada)."""
    if H2_PATTERN.match(text.strip()):
        return True
    # Fallback: texto curto, negrito, começa com número
    if _is_bold(paragraph) and re.match(r"^\d+\s+\w", text.strip()) and len(text.strip()) < 80:
        return True
    return False


def _is_h3_candidate(text: str, paragraph) -> bool:
    """Detecta se é um subtítulo H3."""
    if H3_PATTERN.match(text.strip()):
        return True
    return False


def _extract_images_from_paragraph(paragraph, img_counter: list) -> DocxImage | None:
    """Extrai imagem embutida no parágrafo, se houver."""
    for run in paragraph.runs:
        for drawing in run._element.findall('.//' + qn('a:blip')):
            rId = drawing.get(qn('r:embed'))
            if rId and rId in paragraph._element.getroottree()._getroot().nsmap:
                pass  # fallback abaixo

        # Método direto via inline shapes
        drawings = run._element.findall('.//' + qn('wp:inline')) + \
                   run._element.findall('.//' + qn('wp:anchor'))
        for drawing in drawings:
            blip = drawing.find('.//' + qn('a:blip'))
            if blip is not None:
                rId = blip.get(qn('r:embed'))
                if rId:
                    try:
                        part = paragraph.part.related_parts[rId]
                        img_data = part.blob
                        ct = part.content_type  # image/jpeg, image/png etc.
                        ext = "jpg" if "jpeg" in ct else "png"
                        img_counter[0] += 1
                        filename = f"img{img_counter[0]:03d}.{ext}"
                        return DocxImage(
                            filename=filename,
                            data_b64=base64.b64encode(img_data).decode(),
                            media_type=ct,
                        )
                    except Exception:
                        pass
    return None


def _is_reference_block(text: str) -> bool:
    """Detecta início do bloco de referências."""
    clean = text.strip().upper()
    return clean in ("REFERÊNCIAS", "REFERENCIAS", "REFERÊNCIAS BIBLIOGRÁFICAS", "BIBLIOGRAPHY")


def _is_list_item(paragraph) -> bool:
    """Detecta item de lista (estilo ou marcador ▶ ▷)."""
    text = paragraph.text.strip()
    if text.startswith(("▶", "▷", "•", "-", "–")):
        return True
    if paragraph.style and "list" in paragraph.style.name.lower():
        return True
    return False


# ─── Processador principal ───────────────────────────────────────────────────

def analyze_docx(docx_path: str, original_filename: str = "") -> DocxStructure:
    """
    Analisa o .docx e retorna DocxStructure no padrão Medcel.
    """
    doc = Document(docx_path)
    filename = original_filename or Path(docx_path).name

    paragraphs = doc.paragraphs
    images_all: list[DocxImage] = []
    img_counter = [0]

    # ── Passo 1: detectar título e autores (primeiros parágrafos não vazios) ──
    title = ""
    authors = ""
    title_found = False
    authors_found = False
    start_idx = 0

    for idx, para in enumerate(paragraphs):
        text = para.text.strip()
        if not text:
            continue

        if not title_found:
            title = text
            title_found = True
            start_idx = idx + 1
            continue

        if not authors_found:
            # Autores: linha curta com nomes ou bullet • entre eles
            if "•" in text or (AUTHOR_PATTERN.search(text) and len(text) < 300):
                authors = text
                authors_found = True
                start_idx = idx + 1
            else:
                # Não tem linha de autores — já é conteúdo
                start_idx = idx
                authors_found = True
            break

    logger.info("docx_header", title=title, authors=authors[:80] if authors else "")

    # ── Passo 2: processar corpo do documento ─────────────────────────────────
    sections: list[DocxSection] = []
    references: list[str] = []
    current_section: DocxSection | None = None
    in_references = False
    pending_caption = ""
    pending_source = ""

    def flush_pending_to_last_image():
        """Aplica legenda/fonte pendente à última imagem da seção atual."""
        nonlocal pending_caption, pending_source
        if not current_section or not current_section.blocks:
            return
        for block in reversed(current_section.blocks):
            if block.block_type == "image" and block.image:
                if pending_caption:
                    block.image.caption = pending_caption
                if pending_source:
                    block.image.source = pending_source
                break
        pending_caption = ""
        pending_source = ""

    for para in paragraphs[start_idx:]:
        text = para.text.strip()

        # Extrai imagem do parágrafo, se houver
        img = _extract_images_from_paragraph(para, img_counter)
        if img:
            flush_pending_to_last_image()
            images_all.append(img)
            if current_section:
                current_section.blocks.append(DocxBlock(block_type="image", image=img))
            pending_caption = ""
            pending_source = ""
            continue

        if not text:
            continue

        # ── Referências ──
        if _is_reference_block(text):
            in_references = True
            continue

        if in_references:
            references.append(text)
            continue

        # ── Legenda de figura (Figura X / Quadro X) ──
        if re.match(r"^(Figura|Quadro|Imagem|Tabela)\s+\d+", text, re.IGNORECASE):
            pending_caption = text
            continue

        # ── Fonte (Fonte: / Legenda:) ──
        if re.match(r"^(Fonte|Legenda|Source):", text, re.IGNORECASE):
            pending_source = text
            flush_pending_to_last_image()
            continue

        # ── H2: nova seção ──
        if _is_h2_candidate(text, para):
            flush_pending_to_last_image()
            section_num = len(sections) + 1
            current_section = DocxSection(number=section_num, title=text)
            sections.append(current_section)
            logger.info("section_detected", number=section_num, title=text[:60])
            continue

        if current_section is None:
            # Conteúdo antes da primeira seção — cria seção genérica
            current_section = DocxSection(number=0, title="")
            sections.append(current_section)

        # ── H3 ──
        if _is_h3_candidate(text, para):
            current_section.blocks.append(DocxBlock(block_type="h3", content=text))
            continue

        # ── Item de lista ──
        if _is_list_item(para):
            html_content = _paragraph_to_html(para)
            current_section.blocks.append(DocxBlock(block_type="list_item", content=html_content))
            continue

        # ── Alerta/destaque ──
        if ALERT_PATTERN.match(text):
            html_content = _paragraph_to_html(para)
            current_section.blocks.append(DocxBlock(block_type="alert", content=html_content))
            continue

        # ── Parágrafo normal ──
        html_content = _paragraph_to_html(para)
        if html_content.strip():
            current_section.blocks.append(DocxBlock(block_type="paragraph", content=html_content))

    # Processa tabelas
    for table in doc.tables:
        html = _table_to_html(table)
        if sections:
            sections[-1].blocks.append(DocxBlock(block_type="table", raw_html=html))

    logger.info(
        "docx_analysis_done",
        title=title,
        sections=len(sections),
        images=len(images_all),
        references=len(references),
    )

    return DocxStructure(
        title=title,
        authors=authors,
        sections=sections,
        references=references,
        images=images_all,
        original_filename=filename,
    )


def _table_to_html(table) -> str:
    """Converte tabela do Word em HTML simples."""
    rows_html = []
    for i, row in enumerate(table.rows):
        cells = []
        for cell in row.cells:
            text = _escape_html(cell.text.strip())
            tag = "th" if i == 0 else "td"
            cells.append(f"<{tag}>{text}</{tag}>")
        rows_html.append(f"<tr>{''.join(cells)}</tr>")
    return f'<table class="medcel-table">{"".join(rows_html)}</table>'
