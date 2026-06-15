import os
import uuid
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models.models import Book, Chapter, Conversion
from app.schemas.schemas import BookOut, BookListItem, ChapterOut, StatusResponse, ConversionOut
from app.services.storage_service import download_from_supabase
from app.workers.celery_app import celery_app
from app.config import get_settings
import structlog

router = APIRouter(tags=["books"])
logger = structlog.get_logger()
settings = get_settings()


def _epub_name(original_name: str, suffix: str = "") -> str:
    """Gera nome amigável do EPUB a partir do nome original do PDF."""
    base = os.path.splitext(original_name or "livro")[0]
    return f"{base}{suffix}.epub"


# ─── GET /books ──────────────────────────────────────────────────────────────
@router.get("/books", response_model=list[BookListItem])
async def list_books(db: AsyncSession = Depends(get_db), limit: int = 20, offset: int = 0):
    result = await db.execute(
        select(Book).order_by(Book.created_at.desc()).limit(limit).offset(offset)
    )
    books = result.scalars().all()
    items = []
    for book in books:
        ch_result = await db.execute(select(func.count(Chapter.id)).where(Chapter.book_id == book.id))
        items.append(BookListItem(
            id=book.id,
            original_name=book.original_name,
            file_size_bytes=book.file_size_bytes,
            page_count=book.page_count,
            status=book.status,
            created_at=book.created_at,
            chapters_count=ch_result.scalar() or 0,
        ))
    return items


# ─── GET /books/{id} ─────────────────────────────────────────────────────────
@router.get("/books/{book_id}", response_model=BookOut)
async def get_book(book_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Livro não encontrado"})

    ch_result = await db.execute(
        select(Chapter).where(Chapter.book_id == book_id).order_by(Chapter.chapter_number)
    )
    chapters = ch_result.scalars().all()

    return BookOut(
        id=book.id,
        filename=book.filename,
        original_name=book.original_name,
        file_size_bytes=book.file_size_bytes,
        page_count=book.page_count,
        original_pdf=book.original_pdf,
        full_epub=book.full_epub,
        status=book.status,
        error_message=book.error_message,
        created_at=book.created_at,
        updated_at=book.updated_at,
        chapters=[ChapterOut.model_validate(c) for c in chapters],
    )


# ─── GET /status/{book_id} ───────────────────────────────────────────────────
@router.get("/status/{book_id}", response_model=StatusResponse)
async def get_status(book_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Livro não encontrado"})

    conv_result = await db.execute(
        select(Conversion).where(Conversion.book_id == book_id).order_by(Conversion.created_at.desc())
    )
    conv = conv_result.scalar_one_or_none()

    ch_count = await db.execute(select(func.count(Chapter.id)).where(Chapter.book_id == book_id))
    chapters_count = ch_count.scalar() or 0

    celery_progress = None
    if conv and conv.task_id and book.status == "processing":
        try:
            task = celery_app.AsyncResult(conv.task_id)
            if task.info and isinstance(task.info, dict):
                celery_progress = task.info.get("step")
        except Exception:
            pass

    status_messages = {
        "pending": "Aguardando processamento",
        "processing": f"Convertendo... ({celery_progress or 'em andamento'})",
        "done": "Conversão concluída",
        "error": f"Erro na conversão: {book.error_message or 'desconhecido'}",
    }

    return StatusResponse(
        book_id=book.id,
        book_status=book.status,
        conversion_status=conv.status if conv else None,
        task_id=conv.task_id if conv else None,
        progress_message=status_messages.get(book.status, book.status),
        chapters_count=chapters_count,
        full_epub_ready=bool(book.full_epub and book.status == "done"),
    )


# ─── GET /chapters/{book_id} ─────────────────────────────────────────────────
@router.get("/chapters/{book_id}", response_model=list[ChapterOut])
async def list_chapters(book_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    ch_result = await db.execute(
        select(Chapter).where(Chapter.book_id == book_id).order_by(Chapter.chapter_number)
    )
    return ch_result.scalars().all()


# ─── GET /download/{book_id} ─────────────────────────────────────────────────
@router.get("/download/{book_id}")
async def download_full_epub(book_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Livro não encontrado"})
    if book.status != "done" or not book.full_epub:
        raise HTTPException(status_code=409, detail={"code": "NOT_READY", "message": "EPUB ainda não está pronto"})

    safe_name = _epub_name(book.original_name)
    storage_path = f"epubs/{book_id}/full.epub"
    local_tmp = os.path.join(settings.temp_dir, f"dl_{book_id}_full.epub")

    if download_from_supabase(storage_path, local_tmp):
        return FileResponse(local_tmp, media_type="application/epub+zip", filename=safe_name)

    if book.full_epub and not book.full_epub.startswith("http") and os.path.exists(book.full_epub):
        return FileResponse(book.full_epub, media_type="application/epub+zip", filename=safe_name)

    raise HTTPException(status_code=404, detail={"code": "FILE_NOT_FOUND", "message": "Arquivo não encontrado"})


# ─── GET /download/{book_id}/chapter/{chapter_id} ───────────────────────────
@router.get("/download/{book_id}/chapter/{chapter_id}")
async def download_chapter_epub(book_id: uuid.UUID, chapter_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()

    ch_result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id, Chapter.book_id == book_id)
    )
    chapter = ch_result.scalar_one_or_none()
    if not chapter or not chapter.epub_file:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Capítulo não encontrado"})

    orig = book.original_name if book else "livro"
    safe_name = _epub_name(orig, suffix=f"_cap{chapter.chapter_number:02d}")
    storage_path = f"epubs/{book_id}/chapters/ch{chapter.chapter_number:03d}.epub"
    local_tmp = os.path.join(settings.temp_dir, f"dl_{book_id}_ch{chapter.chapter_number:03d}.epub")

    if download_from_supabase(storage_path, local_tmp):
        return FileResponse(local_tmp, media_type="application/epub+zip", filename=safe_name)

    if chapter.epub_file and not chapter.epub_file.startswith("http") and os.path.exists(chapter.epub_file):
        return FileResponse(chapter.epub_file, media_type="application/epub+zip", filename=safe_name)

    raise HTTPException(status_code=404, detail={"code": "FILE_NOT_FOUND", "message": "Arquivo não encontrado"})


# ─── GET /conversions/{book_id} ──────────────────────────────────────────────
@router.get("/conversions/{book_id}", response_model=list[ConversionOut])
async def list_conversions(book_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Conversion).where(Conversion.book_id == book_id).order_by(Conversion.created_at.desc())
    )
    return result.scalars().all()
