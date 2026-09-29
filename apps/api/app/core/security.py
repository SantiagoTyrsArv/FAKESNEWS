import contextlib
import hashlib
import re
import secrets
import time
import uuid
from dataclasses import dataclass
from functools import lru_cache

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

settings = get_settings()

_password_hasher = PasswordHasher()

# A valid argon2id hash of a random, never-used password. Verifying against
# it keeps the "user not found" and "wrong password" code paths doing the
# same expensive work, so responses take similar time either way.
_DUMMY_PASSWORD_HASH = _password_hasher.hash(str(uuid.uuid4()))


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def verify_password_or_dummy(password: str, password_hash: str | None) -> bool:
    """Verify `password` against `password_hash`, or against a dummy hash of
    matching cost when `password_hash` is None (user not found). Used so that
    login timing doesn't leak whether an email is registered.
    """
    if password_hash is None:
        with contextlib.suppress(VerifyMismatchError):
            _password_hasher.verify(_DUMMY_PASSWORD_HASH, password)
        return False
    return verify_password(password, password_hash)


_PASSWORD_MIN_LENGTH = 10


def validate_password_strength(password: str) -> list[str]:
    """Return a list of human-readable violations; empty list means OK."""
    violations = []
    if len(password) < _PASSWORD_MIN_LENGTH:
        violations.append(f"Debe tener al menos {_PASSWORD_MIN_LENGTH} caracteres.")
    if not re.search(r"[a-z]", password):
        violations.append("Debe incluir al menos una letra minúscula.")
    if not re.search(r"[A-Z]", password):
        violations.append("Debe incluir al menos una letra mayúscula.")
    if not re.search(r"\d", password):
        violations.append("Debe incluir al menos un número.")
    return violations


class TokenError(Exception):
    pass


@dataclass(frozen=True)
class TokenPayload:
    sub: str
    scope: str
    exp: int
    jti: str


def create_token(subject: str, scope: str, expires_minutes: int) -> str:
    now = int(time.time())
    payload = {
        "sub": subject,
        "scope": scope,
        "iat": now,
        "exp": now + expires_minutes * 60,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str, expected_scope: str | None = None) -> TokenPayload:
    try:
        raw = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("token expirado") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("token inválido") from exc

    payload = TokenPayload(sub=raw["sub"], scope=raw["scope"], exp=raw["exp"], jti=raw["jti"])
    if expected_scope is not None and payload.scope != expected_scope:
        raise TokenError("alcance de token inválido")
    return payload


@lru_cache
def _fernet() -> Fernet:
    return Fernet(settings.totp_secret_encryption_key.encode())


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise TokenError("no se pudo descifrar el secreto") from exc


def generate_opaque_token() -> str:
    return secrets.token_urlsafe(48)


def hash_opaque_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
