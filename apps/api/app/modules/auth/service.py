import uuid
from datetime import UTC, datetime, timedelta

import redis.asyncio as redis_asyncio
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.rate_limit import RateLimitExceeded, check_rate_limit
from app.core.security import (
    create_token,
    decrypt_secret,
    encrypt_secret,
    generate_opaque_token,
    hash_opaque_token,
    hash_password,
    validate_password_strength,
    verify_password_or_dummy,
)
from app.modules.auth import totp as totp_module
from app.modules.auth.models import MfaRecoveryCode, RefreshToken, User
from app.modules.auth.recovery_codes import (
    generate_recovery_codes,
    hash_recovery_code,
    verify_recovery_code,
)

settings = get_settings()


class AuthError(Exception):
    """Base class for auth errors mapped to HTTP responses by the router."""


class EmailAlreadyRegisteredError(AuthError):
    pass


class WeakPasswordError(AuthError):
    def __init__(self, violations: list[str]) -> None:
        self.violations = violations
        super().__init__("password does not meet strength requirements")


class InvalidCredentialsError(AuthError):
    pass


class AccountLockedError(AuthError):
    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__("account temporarily locked")


class TotpSetupNotStartedError(AuthError):
    pass


class MfaNotEnabledError(AuthError):
    pass


class InvalidCodeError(AuthError):
    pass


class InvalidRefreshTokenError(AuthError):
    pass


class RefreshReuseDetectedError(AuthError):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime) -> datetime:
    """Normalize a datetime read back from the DB to timezone-aware UTC.

    Postgres (TIMESTAMPTZ) round-trips aware datetimes as-is; SQLite (used in
    tests) drops tzinfo on read, so naive values are assumed to already be
    UTC and tagged accordingly before comparing against `_now()`.
    """
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


async def _check_not_locked(user: User) -> None:
    if user.locked_until is not None and _aware(user.locked_until) > _now():
        retry_after = int((_aware(user.locked_until) - _now()).total_seconds())
        raise AccountLockedError(retry_after_seconds=max(retry_after, 1))


async def _register_failed_attempt(db: AsyncSession, user: User) -> None:
    user.failed_attempts += 1
    if user.failed_attempts >= settings.max_login_attempts:
        user.locked_until = _now() + timedelta(minutes=settings.lockout_minutes)
    await db.commit()


async def _reset_failed_attempts(db: AsyncSession, user: User) -> None:
    user.failed_attempts = 0
    user.locked_until = None
    await db.commit()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await db.get(User, user_id)


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def register_user(db: AsyncSession, email: str, password: str) -> User:
    violations = validate_password_strength(password)
    if violations:
        raise WeakPasswordError(violations)

    existing = await get_user_by_email(db, email)
    if existing is not None:
        raise EmailAlreadyRegisteredError()

    user = User(email=email, password_hash=hash_password(password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_password(
    db: AsyncSession,
    redis_client: redis_asyncio.Redis,
    *,
    ip: str,
    email: str,
    password: str,
) -> User:
    try:
        await check_rate_limit(
            f"login:ip:{ip}", settings.rate_limit_login_per_minute, client=redis_client
        )
        await check_rate_limit(
            f"login:email:{email}", settings.rate_limit_login_per_minute, client=redis_client
        )
    except RateLimitExceeded:
        raise

    user = await get_user_by_email(db, email)

    if user is not None:
        await _check_not_locked(user)

    password_matches = verify_password_or_dummy(
        password, user.password_hash if user is not None else None
    )

    if user is None or not password_matches:
        if user is not None:
            await _register_failed_attempt(db, user)
        raise InvalidCredentialsError()

    await _reset_failed_attempts(db, user)
    return user


def issue_pending_token(user: User) -> tuple[str, str, int]:
    scope = "mfa_pending" if user.mfa_enabled else "mfa_setup_pending"
    expires_minutes = settings.mfa_pending_token_expire_minutes
    token = create_token(str(user.id), scope, expires_minutes)
    return token, scope, expires_minutes * 60


async def start_totp_setup(db: AsyncSession, user: User) -> tuple[str, str]:
    secret = totp_module.generate_secret()
    user.totp_secret_encrypted = encrypt_secret(secret)
    await db.commit()

    uri = totp_module.build_provisioning_uri(secret, user.email)
    qr_b64 = totp_module.generate_qr_code_base64(uri)
    return uri, qr_b64


async def confirm_totp_setup(
    db: AsyncSession,
    redis_client: redis_asyncio.Redis,
    *,
    ip: str,
    user: User,
    code: str,
) -> list[str]:
    await check_rate_limit(
        f"verify:ip:{ip}", settings.rate_limit_verify_per_minute, client=redis_client
    )
    await check_rate_limit(
        f"verify:user:{user.id}", settings.rate_limit_verify_per_minute, client=redis_client
    )

    await _check_not_locked(user)

    if user.totp_secret_encrypted is None:
        raise TotpSetupNotStartedError()

    secret = decrypt_secret(user.totp_secret_encrypted)

    if not totp_module.verify_totp_code_any(secret, code):
        await _register_failed_attempt(db, user)
        raise InvalidCodeError()

    user.mfa_enabled = True
    await _reset_failed_attempts(db, user)

    await db.execute(delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.id))
    plaintext_codes = generate_recovery_codes()
    for code_value in plaintext_codes:
        db.add(MfaRecoveryCode(user_id=user.id, code_hash=hash_recovery_code(code_value)))
    await db.commit()

    return plaintext_codes


async def verify_login(
    db: AsyncSession,
    redis_client: redis_asyncio.Redis,
    *,
    ip: str,
    user: User,
    code: str | None,
    recovery_code: str | None,
) -> User:
    await check_rate_limit(
        f"verify:ip:{ip}", settings.rate_limit_verify_per_minute, client=redis_client
    )
    await check_rate_limit(
        f"verify:user:{user.id}", settings.rate_limit_verify_per_minute, client=redis_client
    )

    await _check_not_locked(user)

    if not user.mfa_enabled:
        raise MfaNotEnabledError()

    success = False

    if code is not None:
        secret = decrypt_secret(user.totp_secret_encrypted)
        step = totp_module.verify_totp_code(secret, code, user.totp_last_used_step)
        if step is not None:
            user.totp_last_used_step = step
            success = True
    elif recovery_code is not None:
        result = await db.execute(
            select(MfaRecoveryCode).where(
                MfaRecoveryCode.user_id == user.id,
                MfaRecoveryCode.used_at.is_(None),
            )
        )
        for recovery in result.scalars().all():
            if verify_recovery_code(recovery_code, recovery.code_hash):
                recovery.used_at = _now()
                success = True
                break

    if not success:
        await _register_failed_attempt(db, user)
        raise InvalidCodeError()

    await _reset_failed_attempts(db, user)
    return user


async def issue_session(db: AsyncSession, user: User) -> dict:
    access_token = create_token(str(user.id), "access", settings.access_token_expire_minutes)

    refresh_plain = generate_opaque_token()
    family_id = uuid.uuid4()
    refresh_row = RefreshToken(
        user_id=user.id,
        family_id=family_id,
        token_hash=hash_opaque_token(refresh_plain),
        expires_at=_now() + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(refresh_row)
    await db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_plain,
        "csrf_token": generate_opaque_token(),
    }


async def _get_refresh_token_by_plain(db: AsyncSession, refresh_plain: str) -> RefreshToken | None:
    token_hash = hash_opaque_token(refresh_plain)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    return result.scalar_one_or_none()


async def rotate_refresh_token(db: AsyncSession, refresh_plain: str) -> dict:
    row = await _get_refresh_token_by_plain(db, refresh_plain)

    if row is None:
        raise InvalidRefreshTokenError()

    if row.revoked_at is not None or row.replaced_by is not None:
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == row.family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=_now())
        )
        await db.commit()
        raise RefreshReuseDetectedError()

    if _aware(row.expires_at) < _now():
        raise InvalidRefreshTokenError()

    new_plain = generate_opaque_token()
    new_row = RefreshToken(
        user_id=row.user_id,
        family_id=row.family_id,
        token_hash=hash_opaque_token(new_plain),
        expires_at=_now() + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(new_row)
    await db.flush()

    row.replaced_by = new_row.id
    row.revoked_at = _now()

    user = await get_user_by_id(db, row.user_id)
    if user is None:
        raise InvalidRefreshTokenError()

    access_token = create_token(str(user.id), "access", settings.access_token_expire_minutes)
    await db.commit()

    return {
        "access_token": access_token,
        "refresh_token": new_plain,
        "csrf_token": generate_opaque_token(),
        "user": user,
    }


async def revoke_refresh_token(db: AsyncSession, refresh_plain: str) -> None:
    row = await _get_refresh_token_by_plain(db, refresh_plain)
    if row is not None and row.revoked_at is None:
        row.revoked_at = _now()
        await db.commit()
