import pytest

from app.core.logging import _redact_sensitive


@pytest.mark.parametrize(
    "key", ["gemini_api_key", "TAVILY_API_KEY", "anthropic_api_key", "api_key", "x-goog-api-key"]
)
def test_api_keys_are_redacted(key: str) -> None:
    event = _redact_sensitive(None, "info", {key: "secret-value"})

    assert event[key] == "***REDACTED***"


def test_other_fields_are_kept() -> None:
    event = _redact_sensitive(None, "info", {"step": "verify"})

    assert event["step"] == "verify"
