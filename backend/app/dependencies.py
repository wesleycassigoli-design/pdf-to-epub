"""
dependencies.py
Dependencies do FastAPI para autenticação/autorização. `get_current_user` sempre
busca o usuário fresco no banco (não confia só nas claims do JWT) — é isso que
garante que revogar acesso de alguém funciona imediatamente, mesmo que o token
ainda não tenha expirado.
"""

import uuid
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.models import User
from app.services.auth_service import decode_access_token

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail={"code": "NOT_AUTHENTICATED", "message": "Faça login para continuar"})

    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail={"code": "INVALID_TOKEN", "message": "Sessão inválida ou expirada, faça login novamente"})

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=401, detail={"code": "INVALID_TOKEN", "message": "Sessão inválida, faça login novamente"})

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail={"code": "INVALID_TOKEN", "message": "Sessão inválida, faça login novamente"})

    return user


async def get_current_approved_user(user: User = Depends(get_current_user)) -> User:
    if user.status == "revoked":
        raise HTTPException(status_code=403, detail={"code": "ACCESS_REVOKED", "message": "Seu acesso foi revogado"})
    if user.status != "approved":
        raise HTTPException(status_code=403, detail={"code": "PENDING_APPROVAL", "message": "Seu cadastro ainda está aguardando aprovação"})
    return user


async def require_admin(user: User = Depends(get_current_approved_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail={"code": "ADMIN_REQUIRED", "message": "Acesso restrito a administradores"})
    return user
