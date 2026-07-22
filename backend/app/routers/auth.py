from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from app.database import get_db
from app.models.models import User
from app.schemas.schemas import (
    RegisterRequest,
    RegisterResponse,
    LoginRequest,
    TokenResponse,
    UserOut,
    ChangePasswordRequest,
    MessageResponse,
)
from app.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    check_login_rate_limit,
    register_login_attempt,
    reset_login_attempts,
)
from app.dependencies import get_current_approved_user
from app.services.user_service import build_user_out
from app.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])
logger = structlog.get_logger()
settings = get_settings()

ALLOWED_EMAIL_DOMAIN = "@afya.com.br"


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    email = payload.email.strip().lower()

    if not email.endswith(ALLOWED_EMAIL_DOMAIN):
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_DOMAIN", "message": f"Cadastro permitido apenas para e-mails {ALLOWED_EMAIL_DOMAIN}"},
        )
    if not payload.privacy_accepted:
        raise HTTPException(
            status_code=400,
            detail={"code": "PRIVACY_NOT_ACCEPTED", "message": "É necessário aceitar a Política de Privacidade"},
        )

    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail={"code": "EMAIL_TAKEN", "message": "Já existe uma conta com este e-mail"})

    admin_email = settings.admin_email.strip().lower()
    is_bootstrap_admin = bool(admin_email) and email == admin_email

    user = User(
        full_name=payload.full_name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
        status="approved" if is_bootstrap_admin else "pending",
        is_admin=is_bootstrap_admin,
        privacy_accepted_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.commit()

    logger.info("user_registered", email=email, is_bootstrap_admin=is_bootstrap_admin)

    message = (
        "Conta criada como administrador — você já pode fazer login."
        if is_bootstrap_admin
        else "Cadastro recebido! Aguarde a aprovação de um administrador para poder fazer login."
    )
    return RegisterResponse(message=message, status=user.status)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    email = payload.email.strip().lower()

    if not check_login_rate_limit(email):
        raise HTTPException(
            status_code=429,
            detail={"code": "TOO_MANY_ATTEMPTS", "message": "Muitas tentativas de login. Tente novamente em alguns minutos."},
        )

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.password_hash):
        register_login_attempt(email)
        raise HTTPException(status_code=401, detail={"code": "INVALID_CREDENTIALS", "message": "E-mail ou senha inválidos"})

    if user.status == "revoked":
        raise HTTPException(
            status_code=403,
            detail={"code": "ACCESS_REVOKED", "message": "Seu acesso foi revogado. Entre em contato com um administrador."},
        )
    if user.status != "approved":
        raise HTTPException(
            status_code=403,
            detail={"code": "PENDING_APPROVAL", "message": "Seu cadastro ainda está aguardando aprovação de um administrador."},
        )

    reset_login_attempts(email)
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(str(user.id), user.is_admin)
    logger.info("user_login", email=email)
    return TokenResponse(access_token=token, user=await build_user_out(db, user))


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_approved_user), db: AsyncSession = Depends(get_db)):
    return await build_user_out(db, user)


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_approved_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(payload.current_password, user.password_hash):
        # 400, não 401: um 401 aqui dispararia o logout automático do
        # interceptor do axios (qualquer 401 é tratado como sessão inválida),
        # e isso não é um problema de sessão — é só a senha atual errada.
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_CURRENT_PASSWORD", "message": "Senha atual incorreta"},
        )

    user.password_hash = hash_password(payload.new_password)
    await db.commit()
    logger.info("user_password_changed", user_id=str(user.id))
    return MessageResponse(message="Senha alterada com sucesso")
