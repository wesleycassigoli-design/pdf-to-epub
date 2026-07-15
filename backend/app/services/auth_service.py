"""
auth_service.py
Hash/verificação de senha, criação/decodificação de JWT, e rate limiting simples
do login (tudo em memória — sem Redis, adequado ao volume baixo de um app interno).
"""

import time
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
import structlog

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: str, is_admin: bool) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expires_minutes)
    payload = {"sub": user_id, "is_admin": is_admin, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as e:
        logger.warning("jwt_decode_failed", error=str(e))
        return None


# ─── Rate limiting do login (em memória) ─────────────────────────────────────

_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_WINDOW_SECONDS = 15 * 60
_login_attempts: dict[str, list[float]] = {}


def check_login_rate_limit(email: str) -> bool:
    """Retorna True se o e-mail ainda pode tentar logar (dentro do limite)."""
    now = time.time()
    attempts = _login_attempts.get(email, [])
    attempts = [t for t in attempts if now - t < _LOGIN_WINDOW_SECONDS]
    _login_attempts[email] = attempts
    return len(attempts) < _LOGIN_MAX_ATTEMPTS


def register_login_attempt(email: str) -> None:
    _login_attempts.setdefault(email, []).append(time.time())


def reset_login_attempts(email: str) -> None:
    _login_attempts.pop(email, None)
