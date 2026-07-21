import os
import re
import json
import base64
import uuid
from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models.models import Book, Chapter, Conversion, User
from app.schemas.schemas import BookOut, BookListItem, ChapterOut, StatusResponse, ConversionOut
from app.services.storage_service import download_from_supabase, upload_to_supabase
from app.services.epub_editor_service import apply_edits, TextEdit, ImageEdit, EpubEditError, MAX_IMAGE_BYTES
from app.services.conversion_service import _validate_epub_zip
from app.dependencies import require_app_access
from app.config import get_settings
import structlog

router = APIRouter(tags=["books"])
logger = structlog.get_logger()
settings = get_settings()

_STEP_RE = re.compile(r"\[STEP\]\s*(\w+)")

# Sem isso, o FileResponse só manda Last-Modified/ETag (sem Cache-Control) —
# como o arquivo em /download/{id} agora pode mudar de conteúdo pro MESMO
# book_id (edição via /books/{id}/edits), o navegador pode aplicar cache
# heurístico (RFC 7234) e servir uma versão antiga logo após salvar uma
# edição, mesmo com uma request de rede nova pra mesma URL.
_NO_CACHE_HEADERS = {"Cache-Control": "no-store"}


def _epub_name(original_name: str, suffix: str = "") -> str:
    """Gera nome amigável do EPUB a partir do nome original do PDF."""
    base = os.path.splitext(original_name or "livro")[0]
    return f"{base}{suffix}.epub"


def _last_step(logs: str | None) -> str | None:
    """Extrai a última tag [STEP] xxx gravada em Conversion.logs (progresso incremental)."""
    if not logs:
        return None
    matches = _STEP_RE.findall(logs)
    return matches[-1] if matches else None


# ─── GET /books ──────────────────────────────────────────────────────────────
@router.get("/books", response_model=list[BookListItem])
async def list_books(
    db: AsyncSession = Depends(get_db),
    limit: int = 20,
    offset: int = 0,
    _user: User = Depends(require_app_access("epub")),
):
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
async def get_book(book_id: uuid.UUID, db: AsyncSession = Depends(get_db), _user: User = Depends(require_app_access("epub"))):
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
async def get_status(book_id: uuid.UUID, db: AsyncSession = Depends(get_db), _user: User = Depends(require_app_access("epub"))):
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

    current_step = _last_step(conv.logs) if conv else None

    status_messages = {
        "pending": "Aguardando processamento",
        "processing": f"Convertendo... ({current_step or 'em andamento'})",
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
async def list_chapters(book_id: uuid.UUID, db: AsyncSession = Depends(get_db), _user: User = Depends(require_app_access("epub"))):
    ch_result = await db.execute(
        select(Chapter).where(Chapter.book_id == book_id).order_by(Chapter.chapter_number)
    )
    return ch_result.scalars().all()


# ─── GET /download/{book_id} ─────────────────────────────────────────────────
@router.get("/download/{book_id}")
async def download_full_epub(book_id: uuid.UUID, db: AsyncSession = Depends(get_db), _user: User = Depends(require_app_access("epub"))):
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
        return FileResponse(local_tmp, media_type="application/epub+zip", filename=safe_name, headers=_NO_CACHE_HEADERS)

    if book.full_epub and not book.full_epub.startswith("http") and os.path.exists(book.full_epub):
        return FileResponse(book.full_epub, media_type="application/epub+zip", filename=safe_name, headers=_NO_CACHE_HEADERS)

    raise HTTPException(status_code=404, detail={"code": "FILE_NOT_FOUND", "message": "Arquivo não encontrado"})


# ─── GET /download/{book_id}/chapter/{chapter_id} ───────────────────────────
@router.get("/download/{book_id}/chapter/{chapter_id}")
async def download_chapter_epub(
    book_id: uuid.UUID,
    chapter_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_app_access("epub")),
):
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
        return FileResponse(local_tmp, media_type="application/epub+zip", filename=safe_name, headers=_NO_CACHE_HEADERS)

    if chapter.epub_file and not chapter.epub_file.startswith("http") and os.path.exists(chapter.epub_file):
        return FileResponse(chapter.epub_file, media_type="application/epub+zip", filename=safe_name, headers=_NO_CACHE_HEADERS)

    raise HTTPException(status_code=404, detail={"code": "FILE_NOT_FOUND", "message": "Arquivo não encontrado"})


# ─── POST /books/{id}/edits — edição enxuta (texto + imagem) do EPUB já
#     gerado. NÃO reprocessa o DOCX original, que permanece intocado no
#     Storage — só baixa o EPUB atual, aplica as edições e sobe substituindo,
#     com a mesma validação de zip do pipeline de conversão antes de
#     persistir (se a remontagem corromper, o EPUB anterior fica intacto). ──
@router.post("/books/{book_id}/edits")
async def apply_book_edits(
    book_id: uuid.UUID,
    edits: str = Form(...),
    files: list[UploadFile] = File(default=[]),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_app_access("epub")),
):
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Livro não encontrado"})
    if book.status != "done" or not book.full_epub:
        raise HTTPException(status_code=409, detail={"code": "NOT_READY", "message": "EPUB ainda não está pronto"})

    try:
        edits_list = json.loads(edits)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail={"code": "INVALID_EDITS", "message": "Lista de edições em formato inválido"})

    if not isinstance(edits_list, list) or not edits_list:
        raise HTTPException(status_code=400, detail={"code": "INVALID_EDITS", "message": "Nenhuma edição enviada"})

    text_edits: list[TextEdit] = []
    image_edits: list[ImageEdit] = []
    for item in edits_list:
        if not isinstance(item, dict) or "type" not in item or "edit_id" not in item:
            raise HTTPException(status_code=400, detail={"code": "INVALID_EDITS", "message": "Edição com formato inválido"})

        if item["type"] == "text":
            html = item.get("html")
            if not isinstance(html, str):
                raise HTTPException(status_code=400, detail={"code": "INVALID_EDITS", "message": "Edição de texto sem conteúdo"})
            text_edits.append(TextEdit(edit_id=item["edit_id"], html=html))

        elif item["type"] == "image":
            # O nome do arquivo de imagem NÃO vem do frontend (o <img> renderizado
            # tem o src reescrito pelo epub.js pra uma blob: URL) — o backend
            # resolve o arquivo real a partir do data-edit-id, direto no XHTML
            # armazenado (ver epub_editor_service.apply_edits).
            file_index = item.get("file_index")
            if not isinstance(file_index, int) or not (0 <= file_index < len(files)):
                raise HTTPException(status_code=400, detail={"code": "INVALID_EDITS", "message": "Edição de imagem sem arquivo correspondente"})
            upload_file = files[file_index]
            if upload_file.content_type not in ("image/png", "image/jpeg"):
                raise HTTPException(status_code=400, detail={"code": "INVALID_IMAGE_TYPE", "message": "Apenas PNG ou JPG são aceitos para substituir imagens"})
            data = await upload_file.read()
            if len(data) > MAX_IMAGE_BYTES:
                raise HTTPException(status_code=413, detail={"code": "IMAGE_TOO_LARGE", "message": f"Imagem excede o limite de {MAX_IMAGE_BYTES // (1024*1024)}MB"})
            image_edits.append(ImageEdit(edit_id=item["edit_id"], data=data, content_type=upload_file.content_type))

        else:
            raise HTTPException(status_code=400, detail={"code": "INVALID_EDITS", "message": f"Tipo de edição desconhecido: {item['type']}"})

    storage_path = f"epubs/{book_id}/full.epub"
    local_current = os.path.join(settings.temp_dir, f"edit_{book_id}_current.epub")
    os.makedirs(settings.temp_dir, exist_ok=True)
    if not download_from_supabase(storage_path, local_current):
        raise HTTPException(status_code=404, detail={"code": "FILE_NOT_FOUND", "message": "Não foi possível baixar o EPUB atual para editar"})

    with open(local_current, "rb") as f:
        current_bytes = f.read()

    try:
        new_bytes = apply_edits(current_bytes, text_edits, image_edits)
    except EpubEditError as e:
        raise HTTPException(status_code=400, detail={"code": "EDIT_FAILED", "message": str(e)})

    local_new = os.path.join(settings.temp_dir, f"edit_{book_id}_new.epub")
    with open(local_new, "wb") as f:
        f.write(new_bytes)

    try:
        _validate_epub_zip(local_new)
    except ValueError as e:
        # Nunca substitui o EPUB anterior se a remontagem corrompeu o zip —
        # o arquivo já salvo no Storage continua exatamente como estava.
        logger.error("epub_edit_validation_failed", book_id=str(book_id), error=str(e))
        raise HTTPException(
            status_code=500,
            detail={
                "code": "EDIT_CORRUPTED_OUTPUT",
                "message": "A edição gerou um EPUB inválido — nenhuma alteração foi salva, o arquivo anterior continua disponível.",
            },
        )

    new_url = await upload_to_supabase(local_new, storage_path)
    if not new_url:
        raise HTTPException(status_code=502, detail={"code": "STORAGE_UPLOAD_FAILED", "message": "Falha ao salvar o EPUB editado no storage"})

    book.full_epub = new_url
    await db.commit()

    for tmp_path in (local_current, local_new):
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    logger.info("book_edits_saved", book_id=str(book_id), text_edits=len(text_edits), image_edits=len(image_edits))
    return {
        "status": "ok",
        "message": "Alterações salvas com sucesso",
        "text_edits_applied": len(text_edits),
        "image_edits_applied": len(image_edits),
        # O EPUB editado vai direto na resposta (base64) pro frontend recarregar
        # o visualizador sem precisar de um novo GET /download logo em seguida —
        # o Storage às vezes leva alguns segundos pra refletir uma sobrescrita
        # recém-feita numa leitura imediata (CDN na frente do bucket), então
        # depender de reler do Storage bem na hora de salvar arrisca mostrar a
        # versão anterior por engano.
        "epub_base64": base64.b64encode(new_bytes).decode("ascii"),
    }


# ─── GET /conversions/{book_id} ──────────────────────────────────────────────
@router.get("/conversions/{book_id}", response_model=list[ConversionOut])
async def list_conversions(book_id: uuid.UUID, db: AsyncSession = Depends(get_db), _user: User = Depends(require_app_access("epub"))):
    result = await db.execute(
        select(Conversion).where(Conversion.book_id == book_id).order_by(Conversion.created_at.desc())
    )
    return result.scalars().all()
