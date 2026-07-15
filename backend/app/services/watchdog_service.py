"""
watchdog_service.py
Resolve o SINTOMA de conversões travadas para sempre em "processing"
(independente da causa raiz do travamento): qualquer Book com
status="processing" cujo updated_at esteja mais velho que STALE_TIMEOUT_MINUTES
é automaticamente marcado como "error". Chamado no início de cada novo
upload — sem cron, sem infraestrutura nova.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.models import Book, Conversion

logger = structlog.get_logger()

STALE_TIMEOUT_MINUTES = 10
TIMEOUT_MESSAGE = "Timeout - processo pode ter sido interrompido"


async def mark_stale_conversions_as_error(db: AsyncSession, timeout_minutes: int = STALE_TIMEOUT_MINUTES) -> int:
    """
    Marca como "error" todo Book preso em "processing" há mais de
    `timeout_minutes` sem atualização. Também marca a Conversion mais recente
    associada (se ainda estiver "queued"/"running"). Retorna quantos livros
    foram marcados.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
    result = await db.execute(
        select(Book).where(Book.status == "processing", Book.updated_at < cutoff)
    )
    stale_books = result.scalars().all()
    if not stale_books:
        return 0

    for book in stale_books:
        book.status = "error"
        book.error_message = TIMEOUT_MESSAGE

        conv_result = await db.execute(
            select(Conversion)
            .where(Conversion.book_id == book.id)
            .order_by(Conversion.created_at.desc())
        )
        conv = conv_result.scalars().first()
        if conv and conv.status in ("queued", "running"):
            conv.status = "error"
            conv.finished_at = datetime.now(timezone.utc)

        logger.warning(
            "stale_conversion_marked_error",
            book_id=str(book.id),
            timeout_minutes=timeout_minutes,
            last_updated_at=book.updated_at.isoformat() if book.updated_at else None,
        )

    await db.commit()
    return len(stale_books)
