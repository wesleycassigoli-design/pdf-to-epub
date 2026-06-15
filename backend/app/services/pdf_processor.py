"""
pdf_processor.py
Análise do PDF:
- Detecção de estrutura (capítulos, títulos)
- Rasterização de cada página em alta resolução (modo fiel)
- Extração de texto (modo texto)
- Detecção de PDF escaneado
"""

import os
import re
import base64
import fitz  # PyMuPDF
from io import BytesIO
from dataclasses import dataclass, field
from pathlib import Path
import structlog

logger = structlog.get_logger()

# DPI da rasterização das páginas (modo fiel)
RENDER_DPI = 200


@dataclass
class PageContent:
    page_number: int
    width: float
    height: float
    text_content: str = ""
    page_image_b64: str = ""   # PNG da página inteira em base64 (modo fiel)
    is_scanned: bool = False


@dataclass
class ChapterInfo:
    number: int
    title: str
    start_page: int
    end_page: int = 0


@dataclass
class BookStructure:
    title: str
    total_pages: int
    chapters: list[ChapterInfo] = field(default_factory=list)
    pages: list[PageContent] = field(default_factory=list)
    has_toc: bool = False
    is_scanned: bool = False
    images_dir: str = ""


CHAPTER_PATTERNS = [
    re.compile(r"^(cap[íi]tulo|chapter|cap\.?)\s+(\d+|[ivxlc]+)", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^(unidade|unit|aula|lição|módulo|module)\s+(\d+|[ivxlc]+)", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^(\d+)\s*[\.–\-]\s+\w+", re.MULTILINE),
    re.compile(r"^(parte|part)\s+(\d+|[ivxlc]+)", re.IGNORECASE | re.MULTILINE),
]


def _is_scanned_page(page: fitz.Page) -> bool:
    text = page.get_text("text").strip()
    if len(text) > 50:
        return False
    images = page.get_images(full=True)
    if not images:
        return False
    for img in images:
        xref = img[0]
        info = page.parent.extract_image(xref)
        if info:
            w, h = info["width"], info["height"]
            if w * h > (page.rect.width * page.rect.height * 0.5):
                return True
    return False


def _is_chapter_start(page: fitz.Page, page_num: int) -> tuple[bool, str]:
    blocks = page.get_text("dict")["blocks"]
    if not blocks:
        return False, ""
    page_width = page.rect.width
    page_height = page.rect.height
    large_spans = []
    for block in blocks:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                size = span.get("size", 0)
                text = span.get("text", "").strip()
                if not text:
                    continue
                is_bold = "bold" in span.get("font", "").lower() or span.get("flags", 0) & 2**4
                if size >= 14 or (size >= 12 and is_bold):
                    x0, y0, x1, y1 = span["bbox"]
                    center_x = (x0 + x1) / 2
                    large_spans.append({
                        "text": text, "size": size,
                        "centered": abs(center_x - page_width / 2) < page_width * 0.2,
                        "top_half": y0 < page_height * 0.4,
                    })
    if not large_spans:
        return False, ""
    full_text = page.get_text("text")
    for pattern in CHAPTER_PATTERNS:
        if pattern.search(full_text):
            best = max(large_spans, key=lambda s: s["size"])
            return True, best["text"]
    best = large_spans[0]
    if best["centered"] and best["top_half"] and len(large_spans) <= 3:
        if len(full_text.split()) < 80:
            return True, best["text"]
    return False, ""


def _render_page_png(page: fitz.Page) -> str:
    """Rasteriza a página em RENDER_DPI e retorna PNG em base64."""
    mat = fitz.Matrix(RENDER_DPI / 72, RENDER_DPI / 72)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    return base64.b64encode(pix.tobytes("png")).decode()


def analyze_pdf(pdf_path: str, images_dir: str, mode: str = "fiel") -> BookStructure:
    """
    Analisa o PDF.
    mode="fiel"  → rasteriza cada página (gera imagem)
    mode="texto" → extrai apenas texto
    """
    os.makedirs(images_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    metadata = doc.metadata or {}
    book_title = metadata.get("title") or Path(pdf_path).stem

    toc = doc.get_toc()
    has_toc = len(toc) > 0

    chapters: list[ChapterInfo] = []
    pages: list[PageContent] = []
    scanned_pages = 0

    logger.info("pdf_analysis_start", path=pdf_path, total_pages=len(doc), mode=mode, has_toc=has_toc)

    if has_toc:
        for level, title, page_num in toc:
            if level == 1:
                chapters.append(ChapterInfo(number=len(chapters) + 1, title=title, start_page=page_num))

    for i, page in enumerate(doc):
        page_num = i + 1
        is_scanned = _is_scanned_page(page)
        if is_scanned:
            scanned_pages += 1

        pc = PageContent(
            page_number=page_num,
            width=page.rect.width,
            height=page.rect.height,
            text_content=page.get_text("text"),
            is_scanned=is_scanned,
        )

        # No modo fiel, rasteriza a página inteira
        if mode == "fiel":
            pc.page_image_b64 = _render_page_png(page)

        pages.append(pc)

        if not has_toc and page_num > 1:
            is_chapter, title_text = _is_chapter_start(page, page_num)
            if is_chapter and title_text:
                chapters.append(ChapterInfo(number=len(chapters) + 1, title=title_text, start_page=page_num))
                logger.info("chapter_detected", page=page_num, title=title_text)

    for idx, ch in enumerate(chapters):
        ch.end_page = (chapters[idx + 1].start_page - 1) if idx + 1 < len(chapters) else len(doc)

    if not chapters:
        chapters.append(ChapterInfo(number=1, title=book_title, start_page=1, end_page=len(doc)))

    is_scanned = scanned_pages > len(doc) * 0.5
    doc.close()

    logger.info("pdf_analysis_done", total_pages=len(pages), chapters=len(chapters), is_scanned=is_scanned)

    return BookStructure(
        title=book_title,
        total_pages=len(pages),
        chapters=chapters,
        pages=pages,
        has_toc=has_toc,
        is_scanned=is_scanned,
        images_dir=images_dir,
    )
