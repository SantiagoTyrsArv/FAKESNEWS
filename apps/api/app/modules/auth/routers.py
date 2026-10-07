from typing import Annotated

import redis.asyncio as redis_asyncio
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.client_ip import client_ip
from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import (
    ACCESS_COOKIE,
    CSRF_COOKIE,
    get_current_user,
    parse_user_id,
    require_csrf,
)
from app.core.rate_limit import RateLimitExceeded, get_redis_dependency
from app.core.security import TokenError, decode_token
from app.modules.auth import service
from app.modules.auth.models import User
from app.modules.auth.schemas import (
    LoginRequest,
    PendingTokenResponse,
    RegisterRequest,
    RegisterResponse,
    SessionResponse,
    TotpConfirmRequest,
    TotpConfirmResponse,
    TotpSetupResponse,
    UserResponse,
    VerifyRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])

GENERIC_AUTH_ERROR = "Credenciales o código inválido."

REFRESH_COOKIE = "refresh_token"


def _cookie_secure() -> bool:
    return get_settings().is_production


def _set_session_cookies(response: Response, session: dict) -> None:
    settings = get_settings()
    secure = _cookie_secure()

    response.set_cookie(
        ACCESS_COOKIE,
        session["access_token"],
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        secure=secure,
        samesite="lax",
        domain=settings.cookie_domain,
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        session["refresh_token"],
        max_age=settings.refresh_token_expire_days * 86400,
        httponly=True,
        secure=secure,
        samesite="lax",
        domain=settings.cookie_domain,
        path=f"{settings.cookie_path_prefix}/auth",
    )
    response.set_cookie(
        CSRF_COOKIE,
        session["csrf_token"],
        max_age=settings.refresh_token_expire_days * 86400,
        httponly=False,
        secure=secure,
        samesite="lax",
        domain=settings.cookie_domain,
        path="/",
    )


def _clear_session_cookies(response: Response) -> None:
    settings = get_settings()
    domain = settings.cookie_domain
    response.delete_cookie(ACCESS_COOKIE, path="/", domain=domain)
    response.delete_cookie(
        REFRESH_COOKIE, path=f"{settings.cookie_path_prefix}/auth", domain=domain
    )
    response.delete_cookie(CSRF_COOKIE, path="/", domain=domain)


async def _get_bearer_token(
    authorization: Annotated[str | None, Header()] = None,
) -> str | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    return authorization.split(" ", 1)[1]


async def require_pending_actor(
    token: Annotated[str | None, Depends(_get_bearer_token)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Resolve the user behind an mfa_setup_pending or mfa_pending bearer
    token, used by /2fa/verify (and as one option for /2fa/setup + confirm).
    """
    if token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "falta token de autenticación")

    try:
        payload = decode_token(token)
    except TokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token inválido o expirado") from exc

    if payload.scope not in ("mfa_setup_pending", "mfa_pending"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "alcance de token inválido")

    user = await service.get_user_by_id(db, parse_user_id(payload.sub))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token inválido o expirado")
    return user


async def require_setup_actor(
    request: Request,
    token: Annotated[str | None, Depends(_get_bearer_token)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Resolve who may enroll an authenticator (/2fa/setup and /2fa/confirm).

    Only two actors qualify:
    - an `mfa_setup_pending` token for a user who has no 2FA yet (first-time
      enrollment right after the password step), or
    - a full session, which already passed 2FA (re-enrollment from settings).

    An `mfa_pending` token is deliberately rejected: it proves only the
    password, and accepting it here would let anyone who knows the password
    swap in their own authenticator and bypass 2FA entirely.
    """
    if token is not None:
        try:
            payload = decode_token(token, expected_scope="mfa_setup_pending")
        except TokenError as exc:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token inválido o expirado") from exc

        user = await service.get_user_by_id(db, parse_user_id(payload.sub))
        if user is None or user.mfa_enabled:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token inválido o expirado")
        return user

    access_cookie = request.cookies.get(ACCESS_COOKIE)
    if access_cookie is not None:
        try:
            payload = decode_token(access_cookie, expected_scope="access")
        except TokenError as exc:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sesión inválida o expirada") from exc

        user = await service.get_user_by_id(db, parse_user_id(payload.sub))
        if user is not None:
            return user

    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "falta token de autenticación")


def _rate_limited() -> HTTPException:
    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS, "Demasiados intentos. Intenta de nuevo más tarde."
    )


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    try:
        user = await service.register_user(db, body.email, body.password)
    except service.WeakPasswordError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, {"violations": exc.violations}) from exc
    except service.EmailAlreadyRegisteredError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ese correo ya está registrado.") from exc

    return RegisterResponse(id=user.id, email=user.email)


@router.post("/login", response_model=PendingTokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[redis_asyncio.Redis, Depends(get_redis_dependency)],
):
    try:
        user = await service.authenticate_password(
            db, redis_client, ip=client_ip(request), email=body.email, password=body.password
        )
    except RateLimitExceeded:
        raise _rate_limited() from None
    except service.AccountLockedError as exc:
        raise HTTPException(status.HTTP_423_LOCKED, GENERIC_AUTH_ERROR) from exc
    except service.InvalidCredentialsError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, GENERIC_AUTH_ERROR) from exc

    token, scope, expires_in = service.issue_pending_token(user)
    return PendingTokenResponse(token=token, token_type=scope, expires_in=expires_in)


@router.post("/2fa/setup", response_model=TotpSetupResponse)
async def setup_totp(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_setup_actor)],
):
    uri, qr_b64 = await service.start_totp_setup(db, user)
    return TotpSetupResponse(otpauth_uri=uri, qr_code_base64=qr_b64)


@router.post("/2fa/confirm", response_model=TotpConfirmResponse)
async def confirm_totp(
    body: TotpConfirmRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[redis_asyncio.Redis, Depends(get_redis_dependency)],
    user: Annotated[User, Depends(require_setup_actor)],
):
    try:
        codes = await service.confirm_totp_setup(
            db, redis_client, ip=client_ip(request), user=user, code=body.code
        )
    except RateLimitExceeded:
        raise _rate_limited() from None
    except service.AccountLockedError as exc:
        raise HTTPException(status.HTTP_423_LOCKED, GENERIC_AUTH_ERROR) from exc
    except service.TotpSetupNotStartedError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Primero debes iniciar el enrolamiento de 2FA."
        ) from exc
    except service.InvalidCodeError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, GENERIC_AUTH_ERROR) from exc

    return TotpConfirmResponse(recovery_codes=codes)


@router.post("/2fa/verify", response_model=SessionResponse)
async def verify_totp(
    body: VerifyRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[redis_asyncio.Redis, Depends(get_redis_dependency)],
    user: Annotated[User, Depends(require_pending_actor)],
):
    if not body.code and not body.recovery_code:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Debes enviar 'code' o 'recovery_code'.")

    try:
        user = await service.verify_login(
            db,
            redis_client,
            ip=client_ip(request),
            user=user,
            code=body.code,
            recovery_code=body.recovery_code,
        )
    except RateLimitExceeded:
        raise _rate_limited() from None
    except service.AccountLockedError as exc:
        raise HTTPException(status.HTTP_423_LOCKED, GENERIC_AUTH_ERROR) from exc
    except service.MfaNotEnabledError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Primero debes completar el enrolamiento de 2FA."
        ) from exc
    except service.InvalidCodeError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, GENERIC_AUTH_ERROR) from exc

    session = await service.issue_session(db, user)
    _set_session_cookies(response, session)

    return SessionResponse(
        user=UserResponse(id=user.id, email=user.email, mfa_enabled=user.mfa_enabled)
    )


@router.post("/refresh", response_model=SessionResponse)
async def refresh(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
    refresh_token: Annotated[str | None, Cookie()] = None,
):
    if refresh_token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sesión inválida o expirada")

    try:
        session = await service.rotate_refresh_token(db, refresh_token)
    except service.RefreshReuseDetectedError as exc:
        _clear_session_cookies(response)
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "sesión inválida: se detectó reutilización de token"
        ) from exc
    except service.InvalidRefreshTokenError as exc:
        _clear_session_cookies(response)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sesión inválida o expirada") from exc

    _set_session_cookies(response, session)

    user = session["user"]
    return SessionResponse(
        user=UserResponse(id=user.id, email=user.email, mfa_enabled=user.mfa_enabled)
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
    refresh_token: Annotated[str | None, Cookie()] = None,
):
    if refresh_token is not None:
        await service.revoke_refresh_token(db, refresh_token)
    _clear_session_cookies(response)


@router.get("/me", response_model=UserResponse)
async def me(user: Annotated[User, Depends(get_current_user)]):
    return UserResponse(id=user.id, email=user.email, mfa_enabled=user.mfa_enabled)
