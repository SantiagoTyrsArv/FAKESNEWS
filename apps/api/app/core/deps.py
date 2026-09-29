import uuid
from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import TokenError, decode_token
from app.modules.auth import service as auth_service
from app.modules.auth.models import User

ACCESS_COOKIE = "access_token"
CSRF_COOKIE = "csrf_token"
CSRF_ERROR = "Token CSRF inválido o ausente."


def parse_user_id(sub: str) -> uuid.UUID:
    try:
        return uuid.UUID(sub)
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token inválido o expirado") from exc


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    access_token: Annotated[str | None, Cookie()] = None,
) -> User:
    if access_token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sesión inválida o expirada")

    try:
        payload = decode_token(access_token, expected_scope="access")
    except TokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sesión inválida o expirada") from exc

    user = await auth_service.get_user_by_id(db, parse_user_id(payload.sub))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sesión inválida o expirada")
    return user


async def require_csrf(
    csrf_token: Annotated[str | None, Cookie()] = None,
    x_csrf_token: Annotated[str | None, Header()] = None,
) -> None:
    if not csrf_token or not x_csrf_token or csrf_token != x_csrf_token:
        raise HTTPException(status.HTTP_403_FORBIDDEN, CSRF_ERROR)
