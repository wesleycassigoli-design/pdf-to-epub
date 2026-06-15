"""
celery_app.py
Configura o Celery e define a task de conversão PDF → EPUB.
Suporta modo "fiel" (imagem) e "texto" (reflow).
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
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(settings.database_url, pool_size=2)
    Session = sessionmaker(bind=engine)
    return Session()


@celery_app.task(bind=True, name="convert_pdf_to_epub")
def convert_pdf_to_epub(self, book_id: str, pdf_path: str, original_name: str, mode: str = "fiel") -> dict:
    """Task principal: baixa PDF do Supabase, processa e gera EPUBs no modo escolhido."""
    from app.models.models import Book, Chapter, Conversion
    from app.services.pdf_processor import analyze_pdf
    from app.services.epub_generator import build_epub, build_chapter_epub
    from app.services.storage_service import get_epub_output_path, download_from_supabase

    start_time = time.time()
    log_lines = []

    def log(msg: str):
        log_lines.append(f"[{datetime.now(timezone.utc).isoformat()}] {msg}")
        logger.info(msg, book_id=book_id)

    db = _get_db_sync()

    try:
        book = db.query(Book).filter_by(id=book_id).first()
        if not book:
            raise ValueError(f"Book {book_id} não encontrado")

        conv = db.query(Conversion).filter_by(book_id=book_id).first()
        if conv:
            conv.status = "running"
            conv.started_at = datetime.now(timezone.utc)
            conv.task_id = self.request.id
            db.commit()

        book.status = "processing"
        db.commit()

        self.update_state(state="PROGRESS", meta={"step": "downloading", "progress": 10})
        log(f"Baixando PDF do storage (modo {mode})")

        local_pdf = os.path.join(settings.temp_dir, f"{book_id}_source.pdf")
        if not download_from_supabase(pdf_path, local_pdf):
            raise FileNotFoundError(f"Não foi possível baixar o PDF: {pdf_path}")

        log("Analisando PDF")
        self.update_state(state="PROGRESS", meta={"step": "analyzing", "progress": 25})
        images_dir = os.path.join(settings.temp_dir, f"{book_id}_images")
        structure = analyze_pdf(local_pdf, images_dir, mode=mode)

        book.page_count = structure.total_pages
        db.commit()
        log(f"{structure.total_pages} páginas, {len(structure.chapters)} capítulos")

        self.update_state(state="PROGRESS", meta={"step": "building_epub", "progress": 50})
        log("Gerando EPUB completo")
        full_epub_local = get_epub_output_path(book_id, f"{book_id}_full.epub")
        os.makedirs(os.path.dirname(full_epub_local), exist_ok=True)
        build_epub(structure, full_epub_local, mode=mode)

        full_epub_url = await_upload(full_epub_local, f"epubs/{book_id}/full.epub")
        book.full_epub = full_epub_url or full_epub_local
        db.commit()

        self.update_state(state="PROGRESS", meta={"step": "building_chapters", "progress": 70})
        log(f"Gerando {len(structure.chapters)} EPUBs de capítulos")

        for ch_info in structure.chapters:
            chapter_epub_path = get_epub_output_path(book_id, f"{book_id}_ch{ch_info.number:03d}.epub")
            build_chapter_epub(structure, ch_info, chapter_epub_path, mode=mode)
            chapter_url = await_upload(chapter_epub_path, f"epubs/{book_id}/chapters/ch{ch_info.number:03d}.epub")
            chapter = Chapter(
                book_id=uuid.UUID(book_id),
                title=ch_info.title,
                chapter_number=ch_info.number,
                start_page=ch_info.start_page,
                end_page=ch_info.end_page,
                epub_file=chapter_url or chapter_epub_path,
            )
            db.add(chapter)
            log(f"Cap {ch_info.number}: {ch_info.title}")

        db.commit()

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
        return {"status": "done", "book_id": book_id, "chapters": len(structure.chapters), "mode": mode}

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
    import shutil
    try:
        if os.path.exists(pdf_path):
            os.unlink(pdf_path)
        if os.path.isdir(images_dir):
            shutil.rmtree(images_dir)
    except Exception as e:
        logger.warning("cleanup_failed", error=str(e))
