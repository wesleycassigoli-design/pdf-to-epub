import os
import uuid
import hashlib
import aiofiles
from pathlib import Path
from fastapi import UploadFile, HTTPException
from supabase import create_client, Client
from app.config import get_settings
import structlog

logger = structlog.get_logger()
settings = get_settings()


def _get_supabase() -> Client | None:
    if settings.supabase_url and settings.supabase_service_key:
        return create_client(settings.supabase_url, settings.supabase_service_key)
    return None


def _sanitize_filename(name: str) -> str:
    """Remove caracteres perigosos do nome do arquivo."""
    import re
    # Mantém apenas alfanuméricos, pontos, hífens e underscores
    safe = re.sub(r"[^\w\-.]", "_", name)
    # Evita path traversal
    safe = Path(safe).name
    return safe[:200]  # limite de tamanho


async def validate_and_save_upload(file: UploadFile) -> tuple[str, str, int]:
    """
    Valida o arquivo, salva temporariamente e retorna:
    (temp_path, sanitized_name, file_size)
    """
    # Validação de extensão
    original_name = file.filename or "unnamed.pdf"
    ext = Path(original_name).suffix.lower()
    if ext != ".pdf":
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_FILE_TYPE", "message": "Apenas arquivos PDF são aceitos"}
        )

    # Lê o arquivo em chunks para validar tamanho
    os.makedirs(settings.temp_dir, exist_ok=True)
    temp_filename = f"{uuid.uuid4()}.pdf"
    temp_path = os.path.join(settings.temp_dir, temp_filename)

    total_size = 0
    async with aiofiles.open(temp_path, "wb") as out:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            total_size += len(chunk)
            if total_size > settings.max_upload_bytes:
                os.unlink(temp_path)
                raise HTTPException(
                    status_code=413,
                    detail={
                        "code": "FILE_TOO_LARGE",
                        "message": f"Arquivo excede o limite de {settings.max_upload_mb}MB"
                    }
                )
            await out.write(chunk)

    # Valida magic bytes (PDF começa com %PDF)
    with open(temp_path, "rb") as f:
        header = f.read(4)
    if header != b"%PDF":
        os.unlink(temp_path)
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_PDF", "message": "O arquivo não é um PDF válido"}
        )

    sanitized_name = _sanitize_filename(original_name)
    logger.info("upload_validated", filename=sanitized_name, size_bytes=total_size)
    return temp_path, sanitized_name, total_size


async def upload_to_supabase(local_path: str, storage_path: str) -> str | None:
    """Faz upload para Supabase Storage. Retorna URL pública ou None se não configurado."""
    supabase = _get_supabase()
    if not supabase:
        logger.warning("supabase_not_configured", action="skipping_upload")
        return None

    try:
        with open(local_path, "rb") as f:
            data = f.read()

        result = supabase.storage.from_(settings.supabase_storage_bucket).upload(
            path=storage_path,
            file=data,
            file_options={"content-type": "application/octet-stream", "upsert": "true"}
        )

        url = supabase.storage.from_(settings.supabase_storage_bucket).get_public_url(storage_path)
        logger.info("supabase_upload_ok", path=storage_path)
        return url
    except Exception as e:
        logger.error("supabase_upload_failed", error=str(e), path=storage_path)
        return None


def get_epub_output_path(book_id: str, filename: str) -> str:
    """Retorna caminho local para salvar EPUB gerado."""
    os.makedirs(settings.output_dir, exist_ok=True)
    safe_name = _sanitize_filename(filename)
    return os.path.join(settings.output_dir, f"{book_id}_{safe_name}")

def download_from_supabase(storage_path: str, local_path: str) -> bool:
    """Baixa um arquivo do Supabase Storage para o disco local. Retorna True se OK."""
    supabase = _get_supabase()
    if not supabase:
        logger.warning("supabase_not_configured", action="skipping_download")
        return False
    try:
        data = supabase.storage.from_(settings.supabase_storage_bucket).download(storage_path)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(data)
        logger.info("supabase_download_ok", path=storage_path)
        return True
    except Exception as e:
        logger.error("supabase_download_failed", error=str(e), path=storage_path)
        return False
