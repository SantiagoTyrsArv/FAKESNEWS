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
