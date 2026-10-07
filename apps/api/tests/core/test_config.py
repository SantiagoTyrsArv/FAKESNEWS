import pytest

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


def _production_env(monkeypatch, **overrides: str) -> None:
    from cryptography.fernet import Fernet

    values = {
        "ENVIRONMENT": "production",
        "JWT_SECRET_KEY": "x" * 48,
        "TOTP_SECRET_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "CORS_ORIGINS": '["https://app.example.com"]',
    }
    values.update(overrides)
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def test_production_accepts_strong_secrets(monkeypatch) -> None:
    _production_env(monkeypatch)
    assert Settings(_env_file=None).is_production


@pytest.mark.parametrize(
    "overrides",
    [
        {"JWT_SECRET_KEY": "dev-insecure-change-me"},
        {"JWT_SECRET_KEY": "change-me-to-a-long-random-string"},
        {"JWT_SECRET_KEY": "too-short"},
        {"TOTP_SECRET_ENCRYPTION_KEY": "MvSmxncXq52PBWdowkbPhAN6d_-YFDdWLvT3GIwtQL0="},
        {"TOTP_SECRET_ENCRYPTION_KEY": "change-me-fernet-key-32-bytes-b64=="},
        {"TOTP_SECRET_ENCRYPTION_KEY": "not-a-fernet-key"},
        {"CORS_ORIGINS": '["*"]'},
        {"API_PROXY_SECRET": "too-short"},
        {"API_PROXY_SECRET": "change-me-to-a-long-random-string-for-the-proxy"},
    ],
)
def test_production_refuses_insecure_settings(monkeypatch, overrides) -> None:
    from pydantic import ValidationError

    _production_env(monkeypatch, **overrides)
    with pytest.raises(ValidationError, match="Refusing to start"):
        Settings(_env_file=None)


def test_development_tolerates_dev_defaults(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    assert Settings(_env_file=None).jwt_secret_key == "dev-insecure-change-me"


def test_production_accepts_a_strong_proxy_secret(monkeypatch) -> None:
    _production_env(monkeypatch, API_PROXY_SECRET="p" * 48)
    assert Settings(_env_file=None).api_proxy_secret == "p" * 48


def test_empty_proxy_secret_is_none(monkeypatch) -> None:
    monkeypatch.setenv("API_PROXY_SECRET", "")
    assert Settings(_env_file=None).api_proxy_secret is None
