import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import structlog

from app.database import get_db
from app.models.models import User
from app.schemas.schemas import UserOut
from app.dependencies import require_admin

router = APIRouter(prefix="/admin", tags=["admin"])
logger = structlog.get_logger()


async def _get_user_or_404(db: AsyncSession, user_id: uuid.UUID) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Usuário não encontrado"})
    return user


@router.get("/users", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return result.scalars().all()


@router.post("/users/{user_id}/approve", response_model=UserOut)
async def approve_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    user = await _get_user_or_404(db, user_id)
    user.status = "approved"
    await db.commit()
    await db.refresh(user)
    logger.info("user_approved", user_id=str(user_id), by=str(admin.id))
    return user


@router.post("/users/{user_id}/revoke", response_model=UserOut)
async def revoke_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    user = await _get_user_or_404(db, user_id)

    if user.is_admin:
        count_result = await db.execute(
            select(func.count(User.id)).where(
                User.is_admin.is_(True), User.status == "approved", User.id != user.id
            )
        )
        remaining_admins = count_result.scalar() or 0
        if remaining_admins == 0:
            raise HTTPException(
                status_code=409,
                detail={"code": "LAST_ADMIN", "message": "Não é possível revogar o único administrador aprovado restante"},
            )

    user.status = "revoked"
    await db.commit()
    await db.refresh(user)
    logger.info("user_revoked", user_id=str(user_id), by=str(admin.id))
    return user


@router.post("/users/{user_id}/promote", response_model=UserOut)
async def promote_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    user = await _get_user_or_404(db, user_id)
    user.is_admin = True
    await db.commit()
    await db.refresh(user)
    logger.info("user_promoted", user_id=str(user_id), by=str(admin.id))
    return user
