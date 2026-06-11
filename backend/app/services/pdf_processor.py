"""
pdf_processor.py
Responsável por toda a análise do PDF:
- Detecção de estrutura (capítulos, títulos, subtítulos)
- Extração de páginas como SVG/HTML
- Extração de imagens
- Detecção de PDF escaneado (ativa OCR)
"""

import os
import re
import fitz  # PyMuPDF
from dataclasses import dataclass, field
from pathlib import Path
import structlog

logger = structlog.get_logger()


@dataclass
class PageContent:
    page_number: int          # 1-indexed
    width: float
    height: float
    svg_content: str          # SVG da página (preserva layout exato)
    text_content: str         # texto puro para análise
    is_scanned: bool = False


@dataclass
class ChapterInfo:
    number: int
    title: str
    start_page: int           # 1-indexed
    end_page: int = 0         # preenchido depois


@dataclass
class BookStructure:
    title: str
    total_pages: int
    chapters: list[ChapterInfo] = field(default_factory=list)
    pages: list[PageContent] = field(default_factory=list)
    has_toc: bool = False
    is_scanned: bool = False
    images_dir: str = ""


# ─── Padrões para detectar início de capítulo ───────────────────────────────
CHAPTER_PATTERNS = [
    re.compile(r"^(cap[íi]tulo|chapter|cap\.?)\s+(\d+|[ivxlc]+)", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^(unidade|unit|aula|lição|módulo|module)\s+(\d+|[ivxlc]+)", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^(\d+)\s*[\.–\-]\s+\w+", re.MULTILINE),
    re.compile(r"^(parte|part)\s+(\d+|[ivxlc]+)", re.IGNORECASE | re.MULTILINE),
]


def _is_scanned_page(page: fitz.Page) -> bool:
    """Página escaneada = tem imagem grande cobrindo quase tudo e texto mínimo."""
    text = page.get_text("text").strip()
    if len(text) > 50:
        return False
    images = page.get_images(full=True)
    if not images:
        return False
    for img in images:
        xref = img[0]
        img_info = page.parent.extract_image(xref)
        if img_info:
            # imagem maior que 50% da área da página = provavelmente escaneada
            w, h = img_info["width"], img_info["height"]
            if w * h > (page.rect.width * page.rect.height * 0.5):
                return True
    return False


def _is_chapter_start(page: fitz.Page, page_num: int) -> tuple[bool, str]:
    """
    Analisa fontes e posicionamento para detectar início de capítulo.
    Retorna (is_chapter, title_text)
    """
    blocks = page.get_text("dict")["blocks"]
    if not blocks:
        return False, ""

    page_width = page.rect.width
    page_height = page.rect.height

    # Coleta spans com fonte grande (títulos)
    large_spans = []
    for block in blocks:
        if block.get("type") != 0:  # type 0 = texto
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                size = span.get("size", 0)
                text = span.get("text", "").strip()
                if not text:
                    continue

                # Span grande ou em negrito
                is_bold = "bold" in span.get("font", "").lower() or span.get("flags", 0) & 2**4
                if size >= 14 or (size >= 12 and is_bold):
                    x0, y0, x1, y1 = span["bbox"]
                    center_x = (x0 + x1) / 2
                    is_centered = abs(center_x - page_width / 2) < page_width * 0.2
                    is_top_half = y0 < page_height * 0.4
                    large_spans.append({
                        "text": text,
                        "size": size,
                        "centered": is_centered,
                        "top_half": is_top_half,
                    })

    if not large_spans:
        return False, ""

    # Analisa o texto completo da página contra os padrões
    full_text = page.get_text("text")
    for pattern in CHAPTER_PATTERNS:
        m = pattern.search(full_text)
        if m:
            # Pega o maior span como título
            best = max(large_spans, key=lambda s: s["size"])
            return True, best["text"]

    # Heurística: se >50% da página for fundo branco e único bloco de texto grande + centralizado
    if large_spans:
        best = large_spans[0]
        if best["centered"] and best["top_half"] and len(large_spans) <= 3:
            word_count = len(page.get_text("text").split())
            if word_count < 80:  # página com pouco texto = capa de capítulo
                return True, best["text"]

    return False, ""


def extract_page_as_svg(page: fitz.Page) -> str:
    """Extrai página inteira como SVG, preservando layout exato."""
    svg = page.get_svg_image(text_as_path=False)
    return svg


def extract_images_from_page(page: fitz.Page, output_dir: str, page_num: int) -> list[str]:
    """Extrai todas as imagens da página e salva como arquivos. Retorna lista de paths."""
    saved = []
    images = page.get_images(full=True)

    for idx, img in enumerate(images):
        xref = img[0]
        try:
            base_image = page.parent.extract_image(xref)
            if not base_image:
                continue
            ext = base_image["ext"]
            img_bytes = base_image["image"]
            fname = f"page{page_num:04d}_img{idx:03d}.{ext}"
            fpath = os.path.join(output_dir, fname)
            with open(fpath, "wb") as f:
                f.write(img_bytes)
            saved.append(fpath)
        except Exception as e:
            logger.warning("image_extract_failed", page=page_num, idx=idx, error=str(e))

    return saved


def analyze_pdf(pdf_path: str, images_dir: str) -> BookStructure:
    """
    Analisa completamente o PDF.
    Retorna BookStructure com capítulos detectados e conteúdo de cada página.
    """
    os.makedirs(images_dir, exist_ok=True)
    doc = fitz.open(pdf_path)

    # Título: tenta metadados, depois primeira página
    metadata = doc.metadata or {}
    book_title = metadata.get("title") or Path(pdf_path).stem

    # Verifica se tem sumário digital (TOC)
    toc = doc.get_toc()
    has_toc = len(toc) > 0

    chapters: list[ChapterInfo] = []
    pages: list[PageContent] = []
    scanned_pages = 0

    logger.info("pdf_analysis_start", path=pdf_path, total_pages=len(doc), has_toc=has_toc)

    # Se tem TOC, usa diretamente
    if has_toc:
        for level, title, page_num in toc:
            if level == 1:  # apenas capítulos de nível 1
                chapters.append(ChapterInfo(
                    number=len(chapters) + 1,
                    title=title,
                    start_page=page_num,
                ))

    # Processa cada página
    for i, page in enumerate(doc):
        page_num = i + 1
        is_scanned = _is_scanned_page(page)
        if is_scanned:
            scanned_pages += 1

        svg = extract_page_as_svg(page)
        text = page.get_text("text")

        # Extrai imagens desta página
        extract_images_from_page(page, images_dir, page_num)

        pages.append(PageContent(
            page_number=page_num,
            width=page.rect.width,
            height=page.rect.height,
            svg_content=svg,
            text_content=text,
            is_scanned=is_scanned,
        ))

        # Detecção de capítulo por análise tipográfica (só se não tem TOC)
        if not has_toc and page_num > 1:
            is_chapter, title_text = _is_chapter_start(page, page_num)
            if is_chapter and title_text:
                chapters.append(ChapterInfo(
                    number=len(chapters) + 1,
                    title=title_text,
                    start_page=page_num,
                ))
                logger.info("chapter_detected", page=page_num, title=title_text)

    # Preenche end_page de cada capítulo
    for idx, ch in enumerate(chapters):
        if idx + 1 < len(chapters):
            ch.end_page = chapters[idx + 1].start_page - 1
        else:
            ch.end_page = len(doc)

    # Se não detectou nenhum capítulo, trata o livro inteiro como um capítulo
    if not chapters:
        chapters.append(ChapterInfo(
            number=1,
            title=book_title,
            start_page=1,
            end_page=len(doc),
        ))

    is_scanned = scanned_pages > len(doc) * 0.5
    doc.close()

    logger.info(
        "pdf_analysis_done",
        total_pages=len(pages),
        chapters=len(chapters),
        is_scanned=is_scanned,
    )

    return BookStructure(
        title=book_title,
        total_pages=len(pages),
        chapters=chapters,
        pages=pages,
        has_toc=has_toc,
        is_scanned=is_scanned,
        images_dir=images_dir,
    )
