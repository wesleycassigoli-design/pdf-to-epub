import uuid
import os
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.models import Book, Conversion
from app.schemas.schemas import UploadResponse
from app.services.storage_service import validate_and_save_upload, upload_to_supabase
from app.services.conversion_service import convert_pdf_to_epub, convert_docx_to_epub
from app.config import get_settings
import structlog

router = APIRouter(prefix="/upload", tags=["upload"])
logger = structlog.get_logger()
settings = get_settings()


@router.post("/", response_model=UploadResponse, status_code=202)
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    mode: str = Form("fiel"),        # "fiel" (imagem) ou "texto" (reflow) — ignorado para DOCX
    template: str = Form("medcel"),  # template editorial usado para DOCX — ignorado para PDF
    db: AsyncSession = Depends(get_db),
):
    """
    Recebe PDF ou DOCX, valida, salva no Supabase e enfileira conversão.
    PDF:
      mode: "fiel" = imagem por página (idêntico ao PDF)
            "texto" = texto reflow (selecionável)
    DOCX:
      template: "medcel" (padrão editorial Medcel) ou "generico" (conversão
      simples sem padrão fixo). Outros templates serão adicionados conforme
      surgirem novos padrões editoriais.
    """
    if mode not in ("fiel", "texto"):
        mode = "fiel"

    SUPPORTED_DOCX_TEMPLATES = ("medcel", "generico")  # adicionar novos templates aqui conforme forem implementados

    temp_path, sanitized_name, file_size, file_type = await validate_and_save_upload(file)

    if file_type == "docx" and template not in SUPPORTED_DOCX_TEMPLATES:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise HTTPException(
            status_code=400,
            detail={
                "code": "TEMPLATE_NOT_SUPPORTED",
                "message": f"Template '{template}' ainda não está disponível. Templates suportados: {', '.join(SUPPORTED_DOCX_TEMPLATES)}.",
            },
        )

    book = Book(
        filename=sanitized_name,
        original_name=file.filename or sanitized_name,
        file_size_bytes=file_size,
        status="pending",
    )
    db.add(book)
    await db.flush()

    storage_path = f"{file_type}s/{book.id}/{sanitized_name}"
    supabase_url = await upload_to_supabase(temp_path, storage_path)
    book.original_pdf = supabase_url or temp_path

    conv = Conversion(book_id=book.id, status="queued")
    db.add(conv)
    await db.commit()
    await db.refresh(book)
    await db.refresh(conv)

    task_id = str(uuid.uuid4())
    conv.task_id = task_id
    await db.commit()

    if file_type == "docx":
        background_tasks.add_task(
            convert_docx_to_epub, str(conv.id), str(book.id), storage_path, sanitized_name, template
        )
    else:
        background_tasks.add_task(
            convert_pdf_to_epub, str(conv.id), str(book.id), storage_path, sanitized_name, mode
        )

    logger.info("upload_queued", book_id=str(book.id), task_id=task_id, mode=mode, file_type=file_type, template=template if file_type == "docx" else None)

    # Só remove o staging local se o upload pro Supabase deu certo — caso contrário
    # `book.original_pdf` aponta pro próprio temp_path como fallback (ver acima).
    if supabase_url:
        try:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        except Exception:
            pass

    return UploadResponse(
        book_id=book.id,
        task_id=task_id,
        message=(
            f"Arquivo DOCX recebido e enfileirado (template {template})"
            if file_type == "docx"
            else f"Arquivo PDF recebido e enfileirado (modo {mode})"
        ),
    )
