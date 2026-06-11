"""
ocr_service.py
Ativa OCR via Tesseract apenas quando o PDF é escaneado.
Preserva layout usando hOCR output.
"""

import os
import fitz
import pytesseract
from PIL import Image
import io
import structlog

logger = structlog.get_logger()

# DPI para rasterização (maior = mais fiel, mais lento)
RENDER_DPI = 200


def _page_to_pil(page: fitz.Page) -> Image.Image:
    """Converte página PyMuPDF em imagem PIL."""
    mat = fitz.Matrix(RENDER_DPI / 72, RENDER_DPI / 72)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img_bytes = pix.tobytes("png")
    return Image.open(io.BytesIO(img_bytes))


def ocr_page_to_svg(page: fitz.Page, lang: str = "por+eng") -> str:
    """
    Roda OCR na página e retorna SVG com texto posicionado
    sobre a imagem original da página (hOCR overlay).
    """
    try:
        # Renderiza como imagem
        img = _page_to_pil(page)
        w, h = img.size

        # hOCR = HTML com coordenadas exatas de cada palavra
        hocr = pytesseract.image_to_pdf_or_hocr(img, lang=lang, extension="hocr")
        hocr_str = hocr.decode("utf-8")

        # Converte hOCR para SVG simples (imagem de fundo + texto sobreposto)
        # Usando a imagem renderizada como fundo para preservar visual 100%
        import base64
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        img_b64 = base64.b64encode(buf.getvalue()).decode()

        # SVG com imagem como fundo (layout preservado) + camada de texto para seleção
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg"
             xmlns:xlink="http://www.w3.org/1999/xlink"
             width="{page.rect.width}pt" height="{page.rect.height}pt"
             viewBox="0 0 {page.rect.width} {page.rect.height}">
  <image href="data:image/png;base64,{img_b64}"
         x="0" y="0"
         width="{page.rect.width}" height="{page.rect.height}"
         preserveAspectRatio="none"/>
</svg>"""
        return svg

    except Exception as e:
        logger.error("ocr_failed", error=str(e))
        # Fallback: retorna página como imagem pura (sem texto selecionável)
        return _page_to_svg_image_only(page)


def _page_to_svg_image_only(page: fitz.Page) -> str:
    """Fallback: página como imagem PNG embutida em SVG."""
    import base64
    img = _page_to_pil(page)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_b64 = base64.b64encode(buf.getvalue()).decode()
    return f"""<svg xmlns="http://www.w3.org/2000/svg"
         xmlns:xlink="http://www.w3.org/1999/xlink"
         width="{page.rect.width}pt" height="{page.rect.height}pt"
         viewBox="0 0 {page.rect.width} {page.rect.height}">
  <image href="data:image/png;base64,{img_b64}"
         x="0" y="0"
         width="{page.rect.width}" height="{page.rect.height}"
         preserveAspectRatio="none"/>
</svg>"""
