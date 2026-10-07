from urllib.parse import parse_qs, urlparse

import pyotp
from httpx import AsyncClient

from app.core.config import get_settings

settings = get_settings()

EMAIL = "demo@example.com"
PASSWORD = "Str0ngPassw0rd!"


def _totp_secret_from_uri(otpauth_uri: str) -> str:
    query = parse_qs(urlparse(otpauth_uri).query)
    return query["secret"][0]


async def _register_and_login(client: AsyncClient) -> None:
    """Register and log in with the password alone: without 2FA that is a
    full session."""
    register_resp = await client.post("/auth/register", json={"email": EMAIL, "password": PASSWORD})
    assert register_resp.status_code == 201

    login_resp = await client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert login_resp.status_code == 200
    assert login_resp.json()["status"] == "authenticated"


def _csrf(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("csrf_token")}


async def _enroll_mfa(client: AsyncClient) -> tuple[str, list[str]]:
    """Enroll an authenticator from the current full session (settings)."""
    setup_resp = await client.post("/auth/2fa/setup", headers=_csrf(client))
    assert setup_resp.status_code == 200
    secret = _totp_secret_from_uri(setup_resp.json()["otpauth_uri"])

    code = pyotp.TOTP(secret).now()
    confirm_resp = await client.post(
        "/auth/2fa/confirm", json={"code": code}, headers=_csrf(client)
    )
    assert confirm_resp.status_code == 200
    recovery_codes = confirm_resp.json()["recovery_codes"]
    assert len(recovery_codes) == 10

    return secret, recovery_codes


async def _login_with_password_only(client: AsyncClient) -> str:
    """Log in again (fresh cookies) as a user with 2FA: returns the pending token."""
    client.cookies.clear()
    resp = await client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "mfa_required"
    assert body["token_type"] == "mfa_pending"
    assert "access_token" not in resp.cookies
    return body["token"]


async def _register_with_mfa(client: AsyncClient) -> tuple[str, list[str], str]:
    """A user with 2FA enrolled, logged out, holding a pending token."""
    await _register_and_login(client)
    secret, recovery_codes = await _enroll_mfa(client)
    pending = await _login_with_password_only(client)
    return secret, recovery_codes, pending


async def test_register_rejects_weak_password(app_client: AsyncClient) -> None:
    resp = await app_client.post("/auth/register", json={"email": EMAIL, "password": "short"})
    assert resp.status_code == 400


async def test_register_rejects_duplicate_email(app_client: AsyncClient) -> None:
    await app_client.post("/auth/register", json={"email": EMAIL, "password": PASSWORD})
    resp = await app_client.post("/auth/register", json={"email": EMAIL, "password": PASSWORD})
    assert resp.status_code == 409


async def test_login_unknown_email_returns_generic_error(app_client: AsyncClient) -> None:
    resp = await app_client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": PASSWORD}
    )
    assert resp.status_code == 401
    assert "inválid" in resp.json()["detail"].lower()


async def test_login_wrong_password_returns_generic_error(app_client: AsyncClient) -> None:
    await app_client.post("/auth/register", json={"email": EMAIL, "password": PASSWORD})
    resp = await app_client.post(
        "/auth/login", json={"email": EMAIL, "password": "wrong-password-123"}
    )
    assert resp.status_code == 401


async def test_login_without_mfa_issues_session(app_client: AsyncClient) -> None:
    await app_client.post("/auth/register", json={"email": EMAIL, "password": PASSWORD})

    resp = await app_client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "authenticated"
    assert body["user"]["mfa_enabled"] is False
    assert body["token"] is None
    assert "access_token" in resp.cookies
    assert "csrf_token" in resp.cookies

    me_resp = await app_client.get("/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["mfa_enabled"] is False


async def test_full_enrollment_and_verify_happy_path(app_client: AsyncClient) -> None:
    secret, _codes, pending = await _register_with_mfa(app_client)

    code = pyotp.TOTP(secret).now()
    verify_resp = await app_client.post(
        "/auth/2fa/verify",
        json={"code": code},
        headers={"Authorization": f"Bearer {pending}"},
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["user"]["email"] == EMAIL

    assert "access_token" in verify_resp.cookies
    assert "refresh_token" in verify_resp.cookies
    assert "csrf_token" in verify_resp.cookies

    me_resp = await app_client.get("/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == EMAIL
    assert me_resp.json()["mfa_enabled"] is True


async def test_verify_rejects_reused_code(app_client: AsyncClient) -> None:
    secret, _codes, pending = await _register_with_mfa(app_client)
    headers = {"Authorization": f"Bearer {pending}"}

    code = pyotp.TOTP(secret).now()
    first = await app_client.post("/auth/2fa/verify", json={"code": code}, headers=headers)
    assert first.status_code == 200

    second = await app_client.post("/auth/2fa/verify", json={"code": code}, headers=headers)
    assert second.status_code == 401


async def test_verify_rejects_invalid_code(app_client: AsyncClient) -> None:
    _secret, _codes, pending = await _register_with_mfa(app_client)

    resp = await app_client.post(
        "/auth/2fa/verify",
        json={"code": "000000"},
        headers={"Authorization": f"Bearer {pending}"},
    )
    assert resp.status_code == 401


async def test_pending_token_cannot_access_protected_route(app_client: AsyncClient) -> None:
    _secret, _codes, pending = await _register_with_mfa(app_client)

    app_client.cookies.set("access_token", pending)
    resp = await app_client.get("/auth/me")
    assert resp.status_code == 401


async def test_recovery_code_login_and_single_use(app_client: AsyncClient) -> None:
    secret, recovery_codes, pending = await _register_with_mfa(app_client)
    headers = {"Authorization": f"Bearer {pending}"}

    recovery_code = recovery_codes[0]
    resp = await app_client.post(
        "/auth/2fa/verify", json={"recovery_code": recovery_code}, headers=headers
    )
    assert resp.status_code == 200

    reuse_resp = await app_client.post(
        "/auth/2fa/verify", json={"recovery_code": recovery_code}, headers=headers
    )
    assert reuse_resp.status_code == 401

    # A never-used code (and a fresh TOTP code) should still work afterwards.
    fresh_code = pyotp.TOTP(secret).now()
    ok_resp = await app_client.post("/auth/2fa/verify", json={"code": fresh_code}, headers=headers)
    assert ok_resp.status_code == 200


async def test_lockout_after_max_failed_attempts(app_client: AsyncClient) -> None:
    await app_client.post("/auth/register", json={"email": EMAIL, "password": PASSWORD})

    for _ in range(settings.max_login_attempts):
        resp = await app_client.post(
            "/auth/login", json={"email": EMAIL, "password": "wrong-password-123"}
        )
        assert resp.status_code == 401

    locked_resp = await app_client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert locked_resp.status_code == 423


async def test_refresh_rotation_and_reuse_detection(app_client: AsyncClient) -> None:
    await _register_and_login(app_client)

    old_refresh = app_client.cookies.get("refresh_token")
    csrf_1 = app_client.cookies.get("csrf_token")

    refresh_resp = await app_client.post("/auth/refresh", headers={"X-CSRF-Token": csrf_1})
    assert refresh_resp.status_code == 200

    new_refresh = app_client.cookies.get("refresh_token")
    csrf_2 = app_client.cookies.get("csrf_token")
    assert new_refresh != old_refresh

    # Present the OLD (already-rotated) refresh token again: this is reuse
    # and must revoke the whole family, including the new token. The CSRF
    # cookie was rotated by the successful refresh above, so use its current
    # value here — we're deliberately testing stale *refresh* token reuse,
    # not CSRF.
    app_client.cookies.set("refresh_token", old_refresh)
    reuse_resp = await app_client.post("/auth/refresh", headers={"X-CSRF-Token": csrf_2})
    assert reuse_resp.status_code == 401

    app_client.cookies.set("refresh_token", new_refresh)
    after_reuse_resp = await app_client.post("/auth/refresh", headers={"X-CSRF-Token": csrf_2})
    assert after_reuse_resp.status_code == 401


async def test_refresh_requires_csrf_header(app_client: AsyncClient) -> None:
    await _register_and_login(app_client)

    resp = await app_client.post("/auth/refresh")
    assert resp.status_code == 403


async def test_logout_revokes_refresh_token(app_client: AsyncClient) -> None:
    await _register_and_login(app_client)

    csrf = app_client.cookies.get("csrf_token")
    refresh_token_value = app_client.cookies.get("refresh_token")

    logout_resp = await app_client.post("/auth/logout", headers={"X-CSRF-Token": csrf})
    assert logout_resp.status_code == 204

    # Logout clears the cookies client-side, but the point of this test is
    # that the token itself was revoked server-side: replay it explicitly.
    app_client.cookies.set("refresh_token", refresh_token_value)
    app_client.cookies.set("csrf_token", csrf)
    refresh_resp = await app_client.post("/auth/refresh", headers={"X-CSRF-Token": csrf})
    assert refresh_resp.status_code == 401


async def test_email_is_case_insensitive(app_client: AsyncClient) -> None:
    resp = await app_client.post(
        "/auth/register", json={"email": "Demo@Example.COM", "password": PASSWORD}
    )
    assert resp.status_code == 201
    assert resp.json()["email"] == "demo@example.com"

    duplicate = await app_client.post(
        "/auth/register", json={"email": "DEMO@example.com", "password": PASSWORD}
    )
    assert duplicate.status_code == 409

    login = await app_client.post(
        "/auth/login", json={"email": "  demo@EXAMPLE.com ", "password": PASSWORD}
    )
    assert login.status_code == 200
