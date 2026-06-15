import uuid
import os
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
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
    mode: str = Form("fiel"),   # "fiel" (imagem) ou "texto" (reflow)
    db: AsyncSession = Depends(get_db),
):
    """
    Recebe PDF, valida, salva no Supabase e enfileira conversão.
    mode: "fiel" = imagem por página (idêntico ao PDF)
          "texto" = texto reflow (selecionável)
    """
    if mode not in ("fiel", "texto"):
        mode = "fiel"

    temp_path, sanitized_name, file_size = await validate_and_save_upload(file)

    book = Book(
        filename=sanitized_name,
        original_name=file.filename or sanitized_name,
        file_size_bytes=file_size,
        status="pending",
    )
    db.add(book)
    await db.flush()

    storage_path = f"pdfs/{book.id}/{sanitized_name}"
    supabase_url = await upload_to_supabase(temp_path, storage_path)
    book.original_pdf = supabase_url or temp_path

    conv = Conversion(book_id=book.id, status="queued")
    db.add(conv)
    await db.commit()
    await db.refresh(book)

    task = convert_pdf_to_epub.apply_async(
        args=[str(book.id), storage_path, sanitized_name, mode],
        task_id=str(uuid.uuid4()),
    )

    conv.task_id = task.id
    await db.commit()

    logger.info("upload_queued", book_id=str(book.id), task_id=task.id, mode=mode)

    return UploadResponse(
        book_id=book.id,
        task_id=task.id,
        message=f"PDF recebido e enfileirado (modo {mode})",
    )

# limpa temp local
    try:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    except Exception:
        pass
