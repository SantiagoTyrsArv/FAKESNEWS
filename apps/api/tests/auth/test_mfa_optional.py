"""2FA is optional: enabled and disabled from settings with a full session.

Disabling needs a current second factor, so a hijacked or unattended session
alone can't strip the protection off an account.
"""

import time

import pyotp
from httpx import AsyncClient

from tests.auth.test_auth_flow import (
    EMAIL,
    PASSWORD,
    _csrf,
    _enroll_mfa,
    _login_with_password_only,
    _register_and_login,
)


def _next_code(secret: str) -> str:
    # The current step's code was already accepted while enrolling.
    return pyotp.TOTP(secret).at(time.time() + 30)


async def test_setup_requires_session(app_client: AsyncClient) -> None:
    resp = await app_client.post("/auth/2fa/setup")
    assert resp.status_code == 401


async def test_setup_and_confirm_require_csrf(app_client: AsyncClient) -> None:
    await _register_and_login(app_client)

    setup = await app_client.post("/auth/2fa/setup")
    assert setup.status_code == 403

    confirm = await app_client.post("/auth/2fa/confirm", json={"code": "123456"})
    assert confirm.status_code == 403


async def test_pending_token_cannot_enroll(app_client: AsyncClient) -> None:
    await _register_and_login(app_client)
    await _enroll_mfa(app_client)
    pending = await _login_with_password_only(app_client)

    resp = await app_client.post("/auth/2fa/setup", headers={"Authorization": f"Bearer {pending}"})
    assert resp.status_code == 401


async def test_disable_with_code_turns_mfa_off(app_client: AsyncClient) -> None:
    await _register_and_login(app_client)
    secret, _codes = await _enroll_mfa(app_client)

    resp = await app_client.post(
        "/auth/2fa/disable", json={"code": _next_code(secret)}, headers=_csrf(app_client)
    )
    assert resp.status_code == 200
    assert resp.json()["mfa_enabled"] is False

    app_client.cookies.clear()
    login = await app_client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert login.json()["status"] == "authenticated"


async def test_disable_with_recovery_code(app_client: AsyncClient) -> None:
    await _register_and_login(app_client)
    _secret, recovery_codes = await _enroll_mfa(app_client)

    resp = await app_client.post(
        "/auth/2fa/disable",
        json={"recovery_code": recovery_codes[0]},
        headers=_csrf(app_client),
    )
    assert resp.status_code == 200
    assert resp.json()["mfa_enabled"] is False


async def test_disable_rejects_invalid_code(app_client: AsyncClient) -> None:
    await _register_and_login(app_client)
    await _enroll_mfa(app_client)

    resp = await app_client.post(
        "/auth/2fa/disable", json={"code": "000000"}, headers=_csrf(app_client)
    )
    assert resp.status_code == 401

    me = await app_client.get("/auth/me")
    assert me.json()["mfa_enabled"] is True


async def test_disable_requires_a_code(app_client: AsyncClient) -> None:
    await _register_and_login(app_client)
    await _enroll_mfa(app_client)

    resp = await app_client.post("/auth/2fa/disable", json={}, headers=_csrf(app_client))
    assert resp.status_code == 400


async def test_disable_requires_csrf(app_client: AsyncClient) -> None:
    await _register_and_login(app_client)
    secret, _codes = await _enroll_mfa(app_client)

    resp = await app_client.post("/auth/2fa/disable", json={"code": _next_code(secret)})
    assert resp.status_code == 403


async def test_disable_requires_session(app_client: AsyncClient) -> None:
    await _register_and_login(app_client)
    secret, _codes = await _enroll_mfa(app_client)
    pending = await _login_with_password_only(app_client)

    resp = await app_client.post(
        "/auth/2fa/disable",
        json={"code": _next_code(secret)},
        headers={"Authorization": f"Bearer {pending}"},
    )
    assert resp.status_code == 401


async def test_disable_when_not_enabled_is_rejected(app_client: AsyncClient) -> None:
    await _register_and_login(app_client)

    resp = await app_client.post(
        "/auth/2fa/disable", json={"code": "123456"}, headers=_csrf(app_client)
    )
    assert resp.status_code == 400


async def test_reenable_after_disable_issues_new_recovery_codes(app_client: AsyncClient) -> None:
    await _register_and_login(app_client)
    secret, old_codes = await _enroll_mfa(app_client)
    await app_client.post(
        "/auth/2fa/disable", json={"code": _next_code(secret)}, headers=_csrf(app_client)
    )

    new_secret, new_codes = await _enroll_mfa(app_client)
    assert new_secret != secret
    assert set(new_codes).isdisjoint(old_codes)

    pending = await _login_with_password_only(app_client)
    stale = await app_client.post(
        "/auth/2fa/verify",
        json={"recovery_code": old_codes[1]},
        headers={"Authorization": f"Bearer {pending}"},
    )
    assert stale.status_code == 401
