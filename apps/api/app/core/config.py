from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = Field(default="development", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    database_url: str = Field(
        default="postgresql+asyncpg://fakesnews:fakesnews@postgres:5432/fakesnews",
        alias="DATABASE_URL",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def use_asyncpg_driver(cls, value: str) -> str:
        # Managed Postgres providers commonly expose a plain postgres:// or
        # postgresql:// URL. This app uses SQLAlchemy's asyncpg driver.
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+asyncpg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    redis_url: str = Field(default="redis://redis:6379/0", alias="REDIS_URL")

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    # Parent domain for session cookies (e.g. ".example.com") when web and API
    # live on different subdomains: the web needs to read csrf_token and the
    # proxy needs to see the session cookies. Empty = host-only cookies.
    cookie_domain: str | None = Field(default=None, alias="COOKIE_DOMAIN")

    @field_validator("cookie_domain", mode="before")
    @classmethod
    def empty_cookie_domain_is_none(cls, value: str | None) -> str | None:
        return value or None

    jwt_secret_key: str = Field(default="dev-insecure-change-me", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=15, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=30, alias="REFRESH_TOKEN_EXPIRE_DAYS")
    mfa_pending_token_expire_minutes: int = Field(
        default=5, alias="MFA_PENDING_TOKEN_EXPIRE_MINUTES"
    )

    totp_secret_encryption_key: str = Field(
        default="MvSmxncXq52PBWdowkbPhAN6d_-YFDdWLvT3GIwtQL0=",
        alias="TOTP_SECRET_ENCRYPTION_KEY",
    )
    totp_issuer_name: str = Field(default="FakesNews", alias="TOTP_ISSUER_NAME")

    max_login_attempts: int = Field(default=5, alias="MAX_LOGIN_ATTEMPTS")
    lockout_minutes: int = Field(default=15, alias="LOCKOUT_MINUTES")
    rate_limit_login_per_minute: int = Field(default=10, alias="RATE_LIMIT_LOGIN_PER_MINUTE")
    rate_limit_verify_per_minute: int = Field(default=10, alias="RATE_LIMIT_VERIFY_PER_MINUTE")

    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-sonnet-5", alias="ANTHROPIC_MODEL")

    whisper_model_size: str = Field(default="small", alias="WHISPER_MODEL_SIZE")
    max_video_duration_seconds: int = Field(default=600, alias="MAX_VIDEO_DURATION_SECONDS")
    max_text_input_chars: int = Field(default=20000, alias="MAX_TEXT_INPUT_CHARS")
    # SSRF hardening: yt-dlp's generic extractor will scrape *any* URL for
    # embedded media, so video submissions are restricted to these hosts.
    allowed_video_hosts: list[str] = Field(
        default_factory=lambda: [
            "youtube.com",
            "www.youtube.com",
            "m.youtube.com",
            "youtu.be",
            "vimeo.com",
            "www.vimeo.com",
            "dailymotion.com",
            "www.dailymotion.com",
            "tiktok.com",
            "www.tiktok.com",
        ]
    )

    max_claims_per_submission: int = Field(default=8, alias="MAX_CLAIMS_PER_SUBMISSION")
    verify_concurrency_limit: int = Field(default=4, alias="VERIFY_CONCURRENCY_LIMIT")
    verify_timeout_seconds: int = Field(default=30, alias="VERIFY_TIMEOUT_SECONDS")

    trusted_sources_path: str = Field(
        default="app/data/trusted_sources.json", alias="TRUSTED_SOURCES_PATH"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
