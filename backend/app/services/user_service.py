"""
user_service.py
Helper compartilhado entre admin.py e auth.py pra montar o UserOut com a
lista de apps liberados (app_access) — admin sempre "tem tudo" sem
depender da tabela user_app_access; usuário comum só o que estiver
gravado lá.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import User, UserAppAccess
from app.schemas.schemas import UserOut

ALL_APP_KEYS = ["epub", "thumbs"]


async def get_app_access(db: AsyncSession, user: User) -> list[str]:
    if user.is_admin:
        return list(ALL_APP_KEYS)
    result = await db.execute(
        select(UserAppAccess.app_key).where(UserAppAccess.user_id == user.id)
    )
    return [row[0] for row in result.all()]


async def build_user_out(db: AsyncSession, user: User) -> UserOut:
    access = await get_app_access(db, user)
    return UserOut.model_validate(user).model_copy(update={"app_access": access})
