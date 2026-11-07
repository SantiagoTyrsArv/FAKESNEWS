import logging
import sys

import structlog

_REDACTED_KEYS = {
    "password",
    "totp_secret",
    "totp_secret_encrypted",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "code",
    "recovery_code",
    "jwt_secret_key",
    "totp_secret_encryption_key",
}
# Any provider's key, so that a new one is covered without touching this list.
_REDACTED_SUFFIXES = ("api_key", "api-key")


def _redact_sensitive(_logger: object, _method_name: str, event_dict: dict) -> dict:
    for key in list(event_dict.keys()):
        name = key.lower()
        if name in _REDACTED_KEYS or name.endswith(_REDACTED_SUFFIXES):
            event_dict[key] = "***REDACTED***"
    return event_dict


def configure_logging(log_level: str = "INFO") -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _redact_sensitive,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    return structlog.get_logger(name)
