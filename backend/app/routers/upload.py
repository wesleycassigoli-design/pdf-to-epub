import uuid
import os
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.models import Book, Conversion
from app.schemas.schemas import UploadResponse
from app.services.storage_service import validate_and_save_upload, upload_to_supabase
from app.workers.celery_app import convert_pdf_to_epub
from app.config import get_settings
import structlog

router = APIRouter(prefix="/upload", tags=["upload"])
logger = structlog.get_logger()
settings = get_settings()


@router.post("/", response_model=UploadResponse, status_code=202)
async def upload_pdf(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Recebe PDF, valida, salva temporariamente e enfileira conversão.
    Retorna book_id + task_id para polling de status.
    """
    # Validação + save temp
    temp_path, sanitized_name, file_size = await validate_and_save_upload(file)

    # Cria registro no banco
    book = Book(
        filename=sanitized_name,
        original_name=file.filename or sanitized_name,
        file_size_bytes=file_size,
        status="pending",
    )
    db.add(book)
    await db.flush()  # garante o book.id antes do upload

    # Upload para Supabase Storage (async)
    storage_path = f"pdfs/{book.id}/{sanitized_name}"
    supabase_url = await upload_to_supabase(temp_path, storage_path)
    book.original_pdf = supabase_url or temp_path  # fallback: path local

    # Cria registro de conversão
    conv = Conversion(book_id=book.id, status="queued")
    db.add(conv)
    await db.commit()
    await db.refresh(book)

    # Enfileira task Celery
    task = convert_pdf_to_epub.apply_async(
        args=[str(book.id), temp_path, sanitized_name],
        task_id=str(uuid.uuid4()),
    )

    # Salva task_id
    conv.task_id = task.id
    await db.commit()

    logger.info("upload_queued", book_id=str(book.id), task_id=task.id)

    return UploadResponse(
        book_id=book.id,
        task_id=task.id,
        message="PDF recebido e enfileirado para conversão",
    )
