import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
import structlog

from app.database import get_db
from app.models.models import User, UserAppAccess
from app.schemas.schemas import UserOut, AppAccessUpdate
from app.dependencies import require_admin
from app.services.user_service import build_user_out, ALL_APP_KEYS

router = APIRouter(prefix="/admin", tags=["admin"])
logger = structlog.get_logger()


async def _get_user_or_404(db: AsyncSession, user_id: uuid.UUID) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Usuário não encontrado"})
    return user


async def _count_other_approved_admins(db: AsyncSession, user: User) -> int:
    """Quantos outros admins aprovados existem além de `user` — usado pra
    travar ações (revogar/remover admin/excluir) que deixariam o sistema
    sem nenhum admin."""
    result = await db.execute(
        select(func.count(User.id)).where(
            User.is_admin.is_(True), User.status == "approved", User.deleted_at.is_(None), User.id != user.id
        )
    )
    return result.scalar() or 0


@router.get("/users", response_model=list[UserOut])
async def list_users(
    show_deleted: bool = False,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = select(User).order_by(User.created_at.desc())
    if not show_deleted:
        query = query.where(User.deleted_at.is_(None))
    result = await db.execute(query)
    users = result.scalars().all()

    reused_result = await db.execute(
        select(User.original_email).where(User.deleted_at.is_not(None), User.original_email.is_not(None))
    )
    reused_emails = {row[0] for row in reused_result.all()}

    out = []
    for u in users:
        user_out = await build_user_out(db, u)
        if u.deleted_at is None and u.email in reused_emails:
            user_out = user_out.model_copy(update={"reused_deleted_email": True})
        out.append(user_out)
    return out


@router.post("/users/{user_id}/approve", response_model=UserOut)
async def approve_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    user = await _get_user_or_404(db, user_id)
    user.status = "approved"
    await db.commit()
    await db.refresh(user)
    logger.info("user_approved", user_id=str(user_id), by=str(admin.id))
    return await build_user_out(db, user)


@router.post("/users/{user_id}/revoke", response_model=UserOut)
async def revoke_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    user = await _get_user_or_404(db, user_id)

    if user.is_admin and await _count_other_approved_admins(db, user) == 0:
        raise HTTPException(
            status_code=409,
            detail={"code": "LAST_ADMIN", "message": "Não é possível revogar o único administrador aprovado restante"},
        )

    user.status = "revoked"
    await db.commit()
    await db.refresh(user)
    logger.info("user_revoked", user_id=str(user_id), by=str(admin.id))
    return await build_user_out(db, user)


@router.post("/users/{user_id}/promote", response_model=UserOut)
async def promote_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    user = await _get_user_or_404(db, user_id)
    user.is_admin = True
    await db.commit()
    await db.refresh(user)
    logger.info("user_promoted", user_id=str(user_id), by=str(admin.id))
    return await build_user_out(db, user)


@router.post("/users/{user_id}/demote", response_model=UserOut)
async def demote_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    user = await _get_user_or_404(db, user_id)

    if not user.is_admin:
        return await build_user_out(db, user)

    if user.status == "approved" and await _count_other_approved_admins(db, user) == 0:
        raise HTTPException(
            status_code=409,
            detail={"code": "LAST_ADMIN", "message": "Não é possível remover o único administrador aprovado restante"},
        )

    user.is_admin = False
    await db.commit()
    await db.refresh(user)
    logger.info("user_demoted", user_id=str(user_id), by=str(admin.id))
    return await build_user_out(db, user)


@router.post("/users/{user_id}/delete", response_model=UserOut)
async def delete_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    """Exclusão lógica: marca deleted_at e anonimiza o email (liberando-o pra
    um cadastro novo). Nada é apagado de verdade — histórico de livros
    continua vinculado ao mesmo user_id. Login é bloqueado imediatamente
    (checado em get_current_user via deleted_at)."""
    user = await _get_user_or_404(db, user_id)

    if user.deleted_at is not None:
        return await build_user_out(db, user)

    if user.is_admin and await _count_other_approved_admins(db, user) == 0:
        raise HTTPException(
            status_code=409,
            detail={"code": "LAST_ADMIN", "message": "Não é possível excluir o único administrador aprovado restante"},
        )

    user.original_email = user.email
    user.email = f"deleted_{uuid.uuid4()}@deleted.local"
    user.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    logger.info("user_deleted", user_id=str(user_id), by=str(admin.id))
    return await build_user_out(db, user)


@router.patch("/users/{user_id}/app-access", response_model=UserOut)
async def update_app_access(
    user_id: uuid.UUID,
    payload: AppAccessUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Define exatamente quais apps o usuário tem liberado (substitui o
    conjunto anterior). Não faz sentido pra admin — eles já têm acesso a
    tudo sempre, independente do que estiver gravado aqui."""
    user = await _get_user_or_404(db, user_id)

    desired = {key for key, granted in payload.model_dump().items() if granted and key in ALL_APP_KEYS}

    result = await db.execute(select(UserAppAccess).where(UserAppAccess.user_id == user.id))
    current_rows = {row.app_key: row for row in result.scalars().all()}

    for app_key in desired - current_rows.keys():
        db.add(UserAppAccess(user_id=user.id, app_key=app_key))

    to_remove = current_rows.keys() - desired
    if to_remove:
        await db.execute(
            delete(UserAppAccess).where(UserAppAccess.user_id == user.id, UserAppAccess.app_key.in_(to_remove))
        )

    await db.commit()
    await db.refresh(user)
    logger.info("user_app_access_updated", user_id=str(user_id), apps=sorted(desired), by=str(admin.id))
    return await build_user_out(db, user)
