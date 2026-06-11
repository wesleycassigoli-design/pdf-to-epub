import os
import uuid
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models.models import Book, Chapter, Conversion
from app.schemas.schemas import BookOut, BookListItem, ChapterOut, StatusResponse, ConversionOut
from app.workers.celery_app import celery_app
from app.config import get_settings
import structlog

router = APIRouter(tags=["books"])
logger = structlog.get_logger()
settings = get_settings()


# ─── GET /books ──────────────────────────────────────────────────────────────
@router.get("/books", response_model=list[BookListItem])
async def list_books(
    db: AsyncSession = Depends(get_db),
    limit: int = 20,
    offset: int = 0,
):
    result = await db.execute(
        select(Book).order_by(Book.created_at.desc()).limit(limit).offset(offset)
    )
    books = result.scalars().all()

    items = []
    for book in books:
        ch_result = await db.execute(
            select(func.count(Chapter.id)).where(Chapter.book_id == book.id)
        )
        chapters_count = ch_result.scalar() or 0
        items.append(BookListItem(
            id=book.id,
            original_name=book.original_name,
            file_size_bytes=book.file_size_bytes,
            page_count=book.page_count,
            status=book.status,
            created_at=book.created_at,
            chapters_count=chapters_count,
        ))

    return items


# ─── GET /books/{id} ─────────────────────────────────────────────────────────
@router.get("/books/{book_id}", response_model=BookOut)
async def get_book(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Livro não encontrado"})

    ch_result = await db.execute(select(Chapter).where(Chapter.book_id == book_id).order_by(Chapter.chapter_number))
    book.chapters = ch_result.scalars().all()
    return book


# ─── GET /status/{book_id} ───────────────────────────────────────────────────
@router.get("/status/{book_id}", response_model=StatusResponse)
async def get_status(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Livro não encontrado"})

    conv_result = await db.execute(
        select(Conversion).where(Conversion.book_id == book_id).order_by(Conversion.created_at.desc())
    )
    conv = conv_result.scalar_one_or_none()

    ch_count_result = await db.execute(
        select(func.count(Chapter.id)).where(Chapter.book_id == book_id)
    )
    chapters_count = ch_count_result.scalar() or 0

    # Pega progresso do Celery se ainda rodando
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
async def list_chapters(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    ch_result = await db.execute(
        select(Chapter).where(Chapter.book_id == book_id).order_by(Chapter.chapter_number)
    )
    return ch_result.scalars().all()


# ─── GET /download/{book_id} ─────────────────────────────────────────────────
@router.get("/download/{book_id}")
async def download_full_epub(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Livro não encontrado"})
    if book.status != "done":
        raise HTTPException(status_code=409, detail={"code": "NOT_READY", "message": "EPUB ainda não está pronto"})
    if not book.full_epub:
        raise HTTPException(status_code=404, detail={"code": "NO_EPUB", "message": "Arquivo EPUB não encontrado"})

    # Se é URL Supabase, redireciona
    if book.full_epub.startswith("http"):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=book.full_epub)

    # Se é path local
    if not os.path.exists(book.full_epub):
        raise HTTPException(status_code=404, detail={"code": "FILE_NOT_FOUND", "message": "Arquivo local não encontrado"})

    safe_name = f"{book.original_name.replace('.pdf', '')}_completo.epub"
    return FileResponse(
        path=book.full_epub,
        media_type="application/epub+zip",
        filename=safe_name,
    )


# ─── GET /download/{book_id}/chapter/{chapter_id} ───────────────────────────
@router.get("/download/{book_id}/chapter/{chapter_id}")
async def download_chapter_epub(
    book_id: uuid.UUID,
    chapter_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    ch_result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id, Chapter.book_id == book_id)
    )
    chapter = ch_result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Capítulo não encontrado"})
    if not chapter.epub_file:
        raise HTTPException(status_code=404, detail={"code": "NO_EPUB", "message": "EPUB do capítulo não disponível"})

    if chapter.epub_file.startswith("http"):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=chapter.epub_file)

    if not os.path.exists(chapter.epub_file):
        raise HTTPException(status_code=404, detail={"code": "FILE_NOT_FOUND", "message": "Arquivo não encontrado"})

    safe_name = f"capitulo_{chapter.chapter_number:03d}.epub"
    return FileResponse(
        path=chapter.epub_file,
        media_type="application/epub+zip",
        filename=safe_name,
    )


# ─── GET /conversions/{book_id} ──────────────────────────────────────────────
@router.get("/conversions/{book_id}", response_model=list[ConversionOut])
async def list_conversions(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversion).where(Conversion.book_id == book_id).order_by(Conversion.created_at.desc())
    )
    return result.scalars().all()
