"""
celery_app.py
Configura o Celery e define a task de conversão PDF → EPUB.
"""

import os
import time
import uuid
from datetime import datetime, timezone
from celery import Celery
from app.config import get_settings
import structlog

logger = structlog.get_logger()
settings = get_settings()

# ─── Celery App ──────────────────────────────────────────────────────────────
celery_app = Celery(
    "pdf_epub_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Sao_Paulo",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=1800,
    task_time_limit=2100,
)


def _get_db_sync():
    """Cria sessão síncrona para uso dentro do worker Celery."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    url = settings.database_url
    engine = create_engine(url, pool_size=2)
    Session = sessionmaker(bind=engine)
    return Session()


@celery_app.task(bind=True, name="convert_pdf_to_epub")
def convert_pdf_to_epub(
    self,
    book_id: str,
    pdf_path: str,
    original_name: str,
) -> dict:
    """
    Task principal. Recebe o caminho do PDF no Supabase Storage,
    baixa, processa e gera os EPUBs.
    """
    from app.models.models import Book, Chapter, Conversion
    from app.services.pdf_processor import analyze_pdf
    from app.services.epub_generator import build_epub, build_chapter_epub
    from app.services.ocr_service import ocr_page_to_svg
    from app.services.storage_service import upload_to_supabase, get_epub_output_path, download_from_supabase

    start_time = time.time()
    log_lines = []

    def log(msg: str):
        log_lines.append(f"[{datetime.now(timezone.utc).isoformat()}] {msg}")
        logger.info(msg, book_id=book_id)

    db = _get_db_sync()

    try:
        # ── 1. Atualiza status no banco ───────────────────────────────────────
        book = db.query(Book).filter_by(id=book_id).first()
        if not book:
            raise ValueError(f"Book {book_id} não encontrado no banco")

        conv = db.query(Conversion).filter_by(book_id=book_id).first()
        if conv:
            conv.status = "running"
            conv.started_at = datetime.now(timezone.utc)
            conv.task_id = self.request.id
            db.commit()

        book.status = "processing"
        db.commit()

        self.update_state(state="PROGRESS", meta={"step": "analyzing", "progress": 10})
        log("Baixando PDF do storage")

        # ── 1.5 Baixa o PDF do Supabase para o disco local do worker ──────────
        local_pdf = os.path.join(settings.temp_dir, f"{book_id}_source.pdf")
        ok = download_from_supabase(pdf_path, local_pdf)
        if not ok:
            raise FileNotFoundError(f"Não foi possível baixar o PDF do storage: {pdf_path}")

        log("Iniciando análise do PDF")

        # ── 2. Análise estrutural ─────────────────────────────────────────────
        images_dir = os.path.join(settings.temp_dir, f"{book_id}_images")
        structure = analyze_pdf(local_pdf, images_dir)

        book.page_count = structure.total_pages
        db.commit()
        log(f"PDF analisado: {structure.total_pages} páginas, {len(structure.chapters)} capítulos")

        # ── 3. OCR se necessário ─────────────────────────────────────────────
        if structure.is_scanned:
            import fitz
            log("PDF escaneado detectado — ativando OCR")
            self.update_state(state="PROGRESS", meta={"step": "ocr", "progress": 25})
            doc = fitz.open(local_pdf)
            for page_content in structure.pages:
                page = doc[page_content.page_number - 1]
                if page_content.is_scanned:
                    page_content.svg_content = ocr_page_to_svg(page)
            doc.close()
            log("OCR concluído")

        # ── 4. Gera EPUB completo ─────────────────────────────────────────────
        self.update_state(state="PROGRESS", meta={"step": "building_epub", "progress": 50})
        log("Gerando EPUB completo")

        full_epub_local = get_epub_output_path(book_id, f"{book_id}_full.epub")
        os.makedirs(os.path.dirname(full_epub_local), exist_ok=True)
        build_epub(structure, full_epub_local)
        log(f"EPUB completo gerado: {full_epub_local}")

        full_epub_url = await_upload(full_epub_local, f"epubs/{book_id}/full.epub")

        book.full_epub = full_epub_url or full_epub_local
        db.commit()

        # ── 5. Gera EPUBs por capítulo ────────────────────────────────────────
        self.update_state(state="PROGRESS", meta={"step": "building_chapters", "progress": 70})
        log(f"Gerando {len(structure.chapters)} EPUBs de capítulos")

        for ch_info in structure.chapters:
            chapter_epub_path = get_epub_output_path(
                book_id, f"{book_id}_ch{ch_info.number:03d}.epub"
            )
            build_chapter_epub(structure, ch_info, chapter_epub_path)

            chapter_url = await_upload(
                chapter_epub_path,
                f"epubs/{book_id}/chapters/ch{ch_info.number:03d}.epub"
            )

            chapter = Chapter(
                book_id=uuid.UUID(book_id),
                title=ch_info.title,
                chapter_number=ch_info.number,
                start_page=ch_info.start_page,
                end_page=ch_info.end_page,
                epub_file=chapter_url or chapter_epub_path,
            )
            db.add(chapter)
            log(f"Capítulo {ch_info.number}: {ch_info.title} (p.{ch_info.start_page}-{ch_info.end_page})")

        db.commit()

        # ── 6. Finaliza ───────────────────────────────────────────────────────
        duration_ms = int((time.time() - start_time) * 1000)
        log(f"Concluído em {duration_ms}ms")

        book.status = "done"
        db.commit()

        if conv:
            conv.status = "done"
            conv.finished_at = datetime.now(timezone.utc)
            conv.duration_ms = duration_ms
            conv.logs = "\n".join(log_lines)
            db.commit()

        _cleanup_temp(local_pdf, images_dir)

        self.update_state(state="SUCCESS", meta={"step": "done", "progress": 100})
        return {"status": "done", "book_id": book_id, "chapters": len(structure.chapters)}

    except Exception as e:
        logger.error("conversion_failed", book_id=book_id, error=str(e), exc_info=True)
        log(f"ERRO: {str(e)}")

        try:
            book = db.query(Book).filter_by(id=book_id).first()
            if book:
                book.status = "error"
                book.error_message = str(e)
                db.commit()

            conv = db.query(Conversion).filter_by(book_id=book_id).first()
            if conv:
                conv.status = "error"
                conv.finished_at = datetime.now(timezone.utc)
                conv.logs = "\n".join(log_lines)
                db.commit()
        except Exception:
            pass

        raise

    finally:
        db.close()


def await_upload(local_path: str, storage_path: str) -> str | None:
    """Wrapper síncrono para upload_to_supabase (Celery é síncrono)."""
    import asyncio
    from app.services.storage_service import upload_to_supabase
    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(upload_to_supabase(local_path, storage_path))
        loop.close()
        return result
    except Exception as e:
        logger.warning("upload_skipped", error=str(e))
        return None


def _cleanup_temp(pdf_path: str, images_dir: str) -> None:
    """Remove arquivos temporários após conclusão."""
    import shutil
    try:
        if os.path.exists(pdf_path):
            os.unlink(pdf_path)
        if os.path.isdir(images_dir):
            shutil.rmtree(images_dir)
    except Exception as e:
        logger.warning("cleanup_failed", error=str(e))
