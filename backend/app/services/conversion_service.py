"""
conversion_service.py
Lógica de conversão executada em background (FastAPI BackgroundTasks), sem worker/broker
separado. Substitui as antigas tasks Celery.

- convert_pdf_to_epub  → PDF, modo "fiel" (imagem) ou "texto" (reflow)
- convert_docx_to_epub → DOCX, template escolhido ("medcel" ou "generico")
"""

import asyncio
import os
import time
import uuid
from datetime import datetime, timezone
from app.config import get_settings
from app.database import AsyncSessionLocal
import structlog

logger = structlog.get_logger()
settings = get_settings()


def _fmt_log(msg: str) -> str:
    return f"[{datetime.now(timezone.utc).isoformat()}] {msg}"


async def _append_step(db, conv, step: str, msg: str) -> None:
    """Registra o passo atual em Conversion.logs (usado pelo /status para granularidade)."""
    line = f"{_fmt_log(msg)} [STEP] {step}"
    conv.logs = f"{conv.logs}\n{line}" if conv.logs else line
    await db.commit()


async def convert_pdf_to_epub(conversion_id: str, book_id: str, pdf_path: str, original_name: str, mode: str = "fiel") -> None:
    """Baixa PDF do Supabase, processa e gera EPUBs no modo escolhido."""
    from app.models.models import Book, Chapter, Conversion
    from app.services.pdf_processor import analyze_pdf
    from app.services.epub_generator import build_epub, build_chapter_epub
    from app.services.storage_service import get_epub_output_path, download_from_supabase, upload_to_supabase
    from sqlalchemy import select

    start_time = time.time()

    async with AsyncSessionLocal() as db:
        book = (await db.execute(select(Book).where(Book.id == book_id))).scalar_one_or_none()
        conv = (await db.execute(select(Conversion).where(Conversion.id == conversion_id))).scalar_one_or_none()

        if not book or not conv:
            logger.error("conversion_target_missing", book_id=book_id, conversion_id=conversion_id)
            return

        try:
            conv.status = "running"
            conv.started_at = datetime.now(timezone.utc)
            book.status = "processing"
            await db.commit()

            await _append_step(db, conv, "downloading", f"Baixando PDF do storage (modo {mode})")
            local_pdf = os.path.join(settings.temp_dir, f"{book_id}_source.pdf")
            os.makedirs(settings.temp_dir, exist_ok=True)
            ok = await asyncio.to_thread(download_from_supabase, pdf_path, local_pdf)
            if not ok:
                raise FileNotFoundError(f"Não foi possível baixar o PDF: {pdf_path}")

            await _append_step(db, conv, "analyzing", "Analisando PDF")
            images_dir = os.path.join(settings.temp_dir, f"{book_id}_images")
            structure = await asyncio.to_thread(analyze_pdf, local_pdf, images_dir, mode=mode, original_filename=original_name)

            book.page_count = structure.total_pages
            await db.commit()
            await _append_step(db, conv, "building_epub", f"{structure.total_pages} páginas, {len(structure.chapters)} capítulos. Gerando EPUB completo")

            full_epub_local = get_epub_output_path(book_id, f"{book_id}_full.epub")
            os.makedirs(os.path.dirname(full_epub_local), exist_ok=True)
            await asyncio.to_thread(build_epub, structure, full_epub_local, mode=mode)

            full_epub_url = await upload_to_supabase(full_epub_local, f"epubs/{book_id}/full.epub")
            book.full_epub = full_epub_url or full_epub_local
            await db.commit()

            await _append_step(db, conv, "building_chapters", f"Gerando {len(structure.chapters)} EPUBs de capítulos")

            for ch_info in structure.chapters:
                chapter_epub_path = get_epub_output_path(book_id, f"{book_id}_ch{ch_info.number:03d}.epub")
                await asyncio.to_thread(build_chapter_epub, structure, ch_info, chapter_epub_path, mode=mode)
                chapter_url = await upload_to_supabase(chapter_epub_path, f"epubs/{book_id}/chapters/ch{ch_info.number:03d}.epub")
                chapter = Chapter(
                    book_id=uuid.UUID(book_id),
                    title=ch_info.title,
                    chapter_number=ch_info.number,
                    start_page=ch_info.start_page,
                    end_page=ch_info.end_page,
                    epub_file=chapter_url or chapter_epub_path,
                )
                db.add(chapter)

            await db.commit()

            duration_ms = int((time.time() - start_time) * 1000)
            book.status = "done"
            conv.status = "done"
            conv.finished_at = datetime.now(timezone.utc)
            conv.duration_ms = duration_ms
            await _append_step(db, conv, "done", f"Concluído em {duration_ms}ms")

            await asyncio.to_thread(_cleanup_temp, local_pdf, images_dir)

        except Exception as e:
            logger.error("conversion_failed", book_id=book_id, error=str(e), exc_info=True)
            try:
                book.status = "error"
                book.error_message = str(e)
                conv.status = "error"
                conv.finished_at = datetime.now(timezone.utc)
                await _append_step(db, conv, "error", f"ERRO: {str(e)}")
            except Exception:
                logger.error("conversion_error_persist_failed", book_id=book_id, exc_info=True)


async def convert_docx_to_epub(conversion_id: str, book_id: str, docx_path: str, original_name: str, template: str = "medcel") -> None:
    """
    Baixa DOCX do Supabase, processa e gera EPUB no template escolhido.

    Roteamento de template: "medcel" (heurística editorial específica) e
    "generico" (fallback simples, sem padrão fixo). Para adicionar um novo
    template no futuro, criar seu próprio módulo de processamento/geração
    e adicionar um novo branch abaixo — sem tocar nos existentes.
    """
    from app.models.models import Book, Chapter, Conversion
    from app.services.storage_service import get_epub_output_path, download_from_supabase, upload_to_supabase
    from sqlalchemy import select

    if template == "medcel":
        from app.services.docx_processor import analyze_docx
        from app.services.epub_generator_medcel import build_epub_medcel
    elif template == "generico":
        from app.services.docx_processor_generico import analyze_docx_generico as analyze_docx
        from app.services.epub_generator_generico import build_epub_generico as build_epub_medcel
    else:
        raise ValueError(f"Template DOCX não suportado: {template}")

    start_time = time.time()

    async with AsyncSessionLocal() as db:
        book = (await db.execute(select(Book).where(Book.id == book_id))).scalar_one_or_none()
        conv = (await db.execute(select(Conversion).where(Conversion.id == conversion_id))).scalar_one_or_none()

        if not book or not conv:
            logger.error("conversion_target_missing", book_id=book_id, conversion_id=conversion_id)
            return

        try:
            conv.status = "running"
            conv.started_at = datetime.now(timezone.utc)
            book.status = "processing"
            await db.commit()

            await _append_step(db, conv, "downloading", "Baixando DOCX do storage")
            local_docx = os.path.join(settings.temp_dir, f"{book_id}_source.docx")
            os.makedirs(settings.temp_dir, exist_ok=True)
            ok = await asyncio.to_thread(download_from_supabase, docx_path, local_docx)
            if not ok:
                raise FileNotFoundError(f"Não foi possível baixar o DOCX: {docx_path}")

            await _append_step(db, conv, "analyzing", f"Analisando DOCX (template {template})")
            structure = await asyncio.to_thread(analyze_docx, local_docx, original_filename=original_name)

            book.page_count = None
            await db.commit()

            await _append_step(db, conv, "building_epub", f"Gerando EPUB (template {template}), título: {structure.title}")
            full_epub_local = get_epub_output_path(book_id, f"{book_id}_full.epub")
            os.makedirs(os.path.dirname(full_epub_local), exist_ok=True)
            await asyncio.to_thread(build_epub_medcel, structure, full_epub_local)

            full_epub_url = await upload_to_supabase(full_epub_local, f"epubs/{book_id}/full.epub")
            book.full_epub = full_epub_url or full_epub_local
            book.status = "done"
            await db.commit()

            # Registra a estrutura como capítulo único (documento não é fatiado por capítulo)
            chapter = Chapter(
                book_id=uuid.UUID(book_id),
                title=structure.title,
                chapter_number=1,
                start_page=1,
                end_page=1,
                epub_file=full_epub_url or full_epub_local,
            )
            db.add(chapter)
            await db.commit()

            duration_ms = int((time.time() - start_time) * 1000)
            conv.status = "done"
            conv.finished_at = datetime.now(timezone.utc)
            conv.duration_ms = duration_ms
            await _append_step(db, conv, "done", f"Concluído em {duration_ms}ms")

            await asyncio.to_thread(_cleanup_temp, local_docx, None)

        except Exception as e:
            logger.error("docx_conversion_failed", book_id=book_id, error=str(e), exc_info=True)
            try:
                book.status = "error"
                book.error_message = str(e)
                conv.status = "error"
                conv.finished_at = datetime.now(timezone.utc)
                await _append_step(db, conv, "error", f"ERRO: {str(e)}")
            except Exception:
                logger.error("conversion_error_persist_failed", book_id=book_id, exc_info=True)


def _cleanup_temp(source_path: str, images_dir: str | None) -> None:
    import shutil
    try:
        if os.path.exists(source_path):
            os.unlink(source_path)
        if images_dir and os.path.isdir(images_dir):
            shutil.rmtree(images_dir)
    except Exception as e:
        logger.warning("cleanup_failed", error=str(e))
