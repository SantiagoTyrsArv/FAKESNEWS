"""Regression tests for MFA enrollment hardening.

A password alone must never be enough to change which authenticator protects
an account, and starting a re-enrollment must not break the current device.
"""

import time

import pyotp
from httpx import AsyncClient

from tests.auth.test_auth_flow import (
    _csrf,
    _login_with_password_only,
    _register_with_mfa,
    _totp_secret_from_uri,
)


def _next_code(secret: str) -> str:
    # The current step's code was already spent by _full_session (replay
    # protection), so use the next step, which the +/-1 window still accepts.
    return pyotp.TOTP(secret).at(time.time() + 30)


async def _full_session(client: AsyncClient) -> str:
    secret, _codes, pending = await _register_with_mfa(client)
    verify = await client.post(
        "/auth/2fa/verify",
        json={"code": pyotp.TOTP(secret).now()},
        headers={"Authorization": f"Bearer {pending}"},
    )
    assert verify.status_code == 200
    return secret


async def test_password_only_token_cannot_start_enrollment(app_client: AsyncClient) -> None:
    await _full_session(app_client)

    pending = await _login_with_password_only(app_client)
    resp = await app_client.post("/auth/2fa/setup", headers={"Authorization": f"Bearer {pending}"})

    assert resp.status_code == 401


async def test_password_only_token_cannot_replace_authenticator(app_client: AsyncClient) -> None:
    """The full takeover chain: an attacker with the password must not be able
    to enroll their own authenticator and then pass /2fa/verify with it."""
    victim_secret = await _full_session(app_client)

    pending = await _login_with_password_only(app_client)
    headers = {"Authorization": f"Bearer {pending}"}
    attacker_secret = pyotp.random_base32()

    confirm = await app_client.post(
        "/auth/2fa/confirm", json={"code": pyotp.TOTP(attacker_secret).now()}, headers=headers
    )
    assert confirm.status_code == 401

    attacker_verify = await app_client.post(
        "/auth/2fa/verify", json={"code": pyotp.TOTP(attacker_secret).now()}, headers=headers
    )
    assert attacker_verify.status_code == 401

    # The victim's own authenticator still works.
    pending = await _login_with_password_only(app_client)
    victim_verify = await app_client.post(
        "/auth/2fa/verify",
        json={"code": _next_code(victim_secret)},
        headers={"Authorization": f"Bearer {pending}"},
    )
    assert victim_verify.status_code == 200


async def test_reenrollment_keeps_current_device_until_confirmed(app_client: AsyncClient) -> None:
    old_secret = await _full_session(app_client)

    # Start re-enrollment from the full session, then abandon it.
    setup = await app_client.post("/auth/2fa/setup", headers=_csrf(app_client))
    assert setup.status_code == 200
    new_secret = _totp_secret_from_uri(setup.json()["otpauth_uri"])
    assert new_secret != old_secret

    pending = await _login_with_password_only(app_client)
    resp = await app_client.post(
        "/auth/2fa/verify",
        json={"code": _next_code(old_secret)},
        headers={"Authorization": f"Bearer {pending}"},
    )
    assert resp.status_code == 200


async def test_reenrollment_switches_device_once_confirmed(app_client: AsyncClient) -> None:
    old_secret = await _full_session(app_client)

    setup = await app_client.post("/auth/2fa/setup", headers=_csrf(app_client))
    new_secret = _totp_secret_from_uri(setup.json()["otpauth_uri"])
    confirm = await app_client.post(
        "/auth/2fa/confirm",
        json={"code": pyotp.TOTP(new_secret).now()},
        headers=_csrf(app_client),
    )
    assert confirm.status_code == 200
    assert len(confirm.json()["recovery_codes"]) == 10

    pending = await _login_with_password_only(app_client)
    headers = {"Authorization": f"Bearer {pending}"}

    old = await app_client.post(
        "/auth/2fa/verify", json={"code": _next_code(old_secret)}, headers=headers
    )
    assert old.status_code == 401

    new = await app_client.post(
        "/auth/2fa/verify", json={"code": pyotp.TOTP(new_secret).now()}, headers=headers
    )
    assert new.status_code == 200
