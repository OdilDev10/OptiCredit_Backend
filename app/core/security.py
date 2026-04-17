"""Security helpers for password hashing and JWT handling."""

from datetime import datetime, timedelta, timezone
import hashlib
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.config import settings
from app.core.exceptions import UnauthorizedException


ALGORITHM = "HS256"


def _normalize_password(password: str) -> bytes:
    """Normalize password bytes to avoid bcrypt's 72-byte limitation errors."""
    encoded = password.encode("utf-8")
    if len(encoded) <= 72:
        return encoded
    return hashlib.sha256(encoded).hexdigest().encode("utf-8")


def hash_password(password: str) -> str:
    """Hash a plain password using bcrypt."""
    normalized = _normalize_password(password)
    return bcrypt.hashpw(normalized, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    try:
        normalized = _normalize_password(password)
        return bcrypt.checkpw(normalized, hashed_password.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(data: dict[str, Any]) -> str:
    """Create a signed access token."""
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes,
    )
    payload = {**data, "exp": expires_at, "type": "access"}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def create_refresh_token(data: dict[str, Any]) -> str:
    """Create a signed refresh token."""
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days,
    )
    payload = {**data, "exp": expires_at}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Decode a JWT and raise a domain exception when invalid."""
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise UnauthorizedException("Invalid or expired token") from exc
