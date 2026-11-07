import pytest
from pydantic import ValidationError

from app.core.llm import LLMError
from app.modules.pipeline import claims as claims_module
from app.modules.pipeline.claims import (
    ClaimsExtractionError,
    ClaimsExtractionResult,
    ExtractedClaim,
)


def _fake(monkeypatch: pytest.MonkeyPatch, result: ClaimsExtractionResult | Exception) -> list:
    calls: list[dict] = []

    async def generate(**kwargs) -> ClaimsExtractionResult:
        calls.append(kwargs)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(claims_module, "generate_structured", generate)
    return calls


def _claims(*texts: str) -> ClaimsExtractionResult:
    return ClaimsExtractionResult(claims=[ExtractedClaim(text=t) for t in texts])


async def test_extract_claims_success(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _fake(monkeypatch, _claims("Uno.", "Dos."))

    assert await claims_module.extract_claims("texto") == ["Uno.", "Dos."]
    assert calls[0]["step"] == "claims"
    assert calls[0]["schema"] is ClaimsExtractionResult
    assert "<document>\ntexto\n</document>" in calls[0]["user"]


async def test_extract_claims_drops_blank_claims(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake(monkeypatch, _claims("  ", " Uno. "))

    assert await claims_module.extract_claims("texto") == ["Uno."]


async def test_extract_claims_empty_when_no_factual_claims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake(monkeypatch, _claims())

    assert await claims_module.extract_claims("texto") == []


async def test_extract_claims_respects_the_configured_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake(monkeypatch, _claims("a", "b", "c"))
    monkeypatch.setattr(claims_module.settings, "max_claims_per_submission", 2)

    assert await claims_module.extract_claims("texto") == ["a", "b"]


async def test_extract_claims_raises_on_llm_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake(monkeypatch, LLMError("Gemini respondió 500"))

    with pytest.raises(ClaimsExtractionError):
        await claims_module.extract_claims("texto")


def test_extraction_schema_allows_four_claims() -> None:
    claims = [ExtractedClaim(text="x")] * 5

    with pytest.raises(ValidationError):
        ClaimsExtractionResult(claims=claims)


def test_prompt_asks_for_at_most_four_claims() -> None:
    assert "como máximo 4 afirmaciones" in claims_module.SYSTEM_PROMPT
