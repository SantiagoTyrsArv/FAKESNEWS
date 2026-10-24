"""Security-relevant auth events are logged, structured and without secrets,
so brute force, account lockouts, stolen refresh tokens and 2FA changes can
be investigated and alerted on (OWASP A09)."""

import time

import pyotp
from httpx import AsyncClient
from structlog.testing import capture_logs

from app.core.config import get_settings
from tests.auth.test_auth_flow import EMAIL, PASSWORD, _csrf, _enroll_mfa, _register_and_login

settings = get_settings()


def _events(logs: list[dict], name: str) -> list[dict]:
    return [entry for entry in logs if entry["event"] == name]


def _no_secrets(logs: list[dict]) -> None:
    text = repr(logs)
    assert EMAIL not in text
    assert PASSWORD not in text


async def test_failed_logins_and_the_lockout_are_logged(app_client: AsyncClient) -> None:
    await app_client.post("/auth/register", json={"email": EMAIL, "password": PASSWORD})

    with capture_logs() as logs:
        for _ in range(settings.max_login_attempts):
            await app_client.post(
                "/auth/login", json={"email": EMAIL, "password": "Wrong-pass-123"}
            )

    failed = _events(logs, "auth.login_failed")
    assert len(failed) == settings.max_login_attempts
    assert failed[0]["reason"] == "wrong_password"
    assert failed[0]["user_id"]
    assert failed[0]["ip"]
    lockouts = _events(logs, "auth.lockout")
    assert len(lockouts) == 1
    assert lockouts[0]["minutes"] == settings.lockout_minutes
    _no_secrets(logs)


async def test_a_login_for_an_unknown_email_is_logged_without_the_email(
    app_client: AsyncClient,
) -> None:
    with capture_logs() as logs:
        await app_client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})

    [event] = _events(logs, "auth.login_failed")
    assert event["reason"] == "unknown_email"
    assert len(event["email_hash"]) == 16  # correlates attempts, reveals nothing
    _no_secrets(logs)


async def test_refresh_token_reuse_is_logged(app_client: AsyncClient) -> None:
    await _register_and_login(app_client)
    old_refresh = app_client.cookies.get("refresh_token")
    await app_client.post("/auth/refresh", headers=_csrf(app_client))

    app_client.cookies.set("refresh_token", old_refresh)
    with capture_logs() as logs:
        await app_client.post("/auth/refresh", headers=_csrf(app_client))

    [event] = _events(logs, "auth.refresh_reuse_detected")
    assert event["user_id"]
    assert event["family_id"]


async def test_enabling_and_disabling_2fa_are_logged(app_client: AsyncClient) -> None:
    await _register_and_login(app_client)

    with capture_logs() as logs:
        secret, _codes = await _enroll_mfa(app_client)
        await app_client.post(
            "/auth/2fa/disable",
            json={"code": pyotp.TOTP(secret).at(time.time() + 30)},
            headers=_csrf(app_client),
        )

    assert len(_events(logs, "auth.mfa_enabled")) == 1
    assert len(_events(logs, "auth.mfa_disabled")) == 1
    _no_secrets(logs)
