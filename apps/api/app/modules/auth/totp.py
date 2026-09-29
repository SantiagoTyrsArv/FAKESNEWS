import base64
import time
from io import BytesIO

import pyotp
import qrcode

from app.core.config import get_settings

settings = get_settings()

_STEP_SECONDS = 30
_WINDOW = 1


def generate_secret() -> str:
    return pyotp.random_base32()


def build_provisioning_uri(secret: str, account_email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(
        name=account_email, issuer_name=settings.totp_issuer_name
    )


def generate_qr_code_base64(otpauth_uri: str) -> str:
    img = qrcode.make(otpauth_uri)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def current_step(for_time: float | None = None) -> int:
    return int((for_time if for_time is not None else time.time()) // _STEP_SECONDS)


def verify_totp_code_any(secret: str, code: str) -> bool:
    """Verify `code` is currently valid within a +/-1 step window, with no
    replay tracking. Used only during enrollment (/2fa/confirm), where the
    goal is proving the authenticator app is set up correctly rather than
    guarding an active session.
    """
    return pyotp.TOTP(secret).verify(code, valid_window=_WINDOW)


def verify_totp_code(
    secret: str, code: str, last_used_step: int | None, for_time: float | None = None
) -> int | None:
    """Verify `code` against `secret` within a +/-1 step window.

    Returns the matched step if the code is valid and strictly newer than
    `last_used_step` (replay protection); returns None otherwise.
    """
    totp = pyotp.TOTP(secret)
    now = for_time if for_time is not None else time.time()

    for offset in range(-_WINDOW, _WINDOW + 1):
        step_time = now + offset * _STEP_SECONDS
        step = current_step(step_time)
        if last_used_step is not None and step <= last_used_step:
            continue
        if totp.verify(code, for_time=step_time, valid_window=0):
            return step

    return None
