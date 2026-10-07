from app.core.config import Settings


def test_settings_load_with_defaults(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    settings = Settings(_env_file=None)

    assert settings.environment == "development"
    assert settings.anthropic_model == "claude-sonnet-5"
    assert settings.access_token_expire_minutes == 15
    assert settings.mfa_pending_token_expire_minutes == 5


def test_settings_override_from_env(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-5")
    monkeypatch.setenv("MAX_CLAIMS_PER_SUBMISSION", "3")

    settings = Settings(_env_file=None)

    assert settings.anthropic_model == "claude-opus-5"
    assert settings.max_claims_per_submission == 3


def test_cookie_domain_defaults_to_host_only(monkeypatch) -> None:
    monkeypatch.setenv("COOKIE_DOMAIN", "")
    assert Settings(_env_file=None).cookie_domain is None


def test_session_cookies_use_configured_domain(monkeypatch) -> None:
    from fastapi import Response

    from app.modules.auth import routers

    settings = Settings(_env_file=None, COOKIE_DOMAIN=".example.com")
    monkeypatch.setattr(routers, "get_settings", lambda: settings)

    response = Response()
    routers._set_session_cookies(
        response, {"access_token": "a", "refresh_token": "r", "csrf_token": "c"}
    )
    set_cookies = response.headers.getlist("set-cookie")
    assert len(set_cookies) == 3
    assert all("Domain=.example.com" in header for header in set_cookies)

    cleared = Response()
    routers._clear_session_cookies(cleared)
    assert all("Domain=.example.com" in h for h in cleared.headers.getlist("set-cookie"))
