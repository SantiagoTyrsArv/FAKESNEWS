import pytest

from app.modules.pipeline import claims as claims_module
from app.modules.pipeline.claims import ClaimsExtractionResult, ExtractedClaim


class _FakeParseResponse:
    def __init__(self, parsed_output: ClaimsExtractionResult) -> None:
        self.parsed_output = parsed_output


class _FakeMessages:
    def __init__(self, side_effects: list) -> None:
        self._side_effects = list(side_effects)

    async def parse(self, **_kwargs):
        effect = self._side_effects.pop(0)
        if isinstance(effect, Exception):
            raise effect
        return _FakeParseResponse(effect)


class _FakeClient:
    def __init__(self, side_effects: list) -> None:
        self.messages = _FakeMessages(side_effects)


async def test_extract_claims_success(monkeypatch: pytest.MonkeyPatch) -> None:
    result = ClaimsExtractionResult(
        claims=[
            ExtractedClaim(text="La inflación fue del 5%."),
            ExtractedClaim(text="El evento fue el lunes."),
        ]
    )
    fake_client = _FakeClient([result])
    monkeypatch.setattr(claims_module, "get_anthropic_client", lambda: fake_client)

    claims = await claims_module.extract_claims("algún texto de ejemplo")

    assert claims == ["La inflación fue del 5%.", "El evento fue el lunes."]


async def test_extract_claims_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    result = ClaimsExtractionResult(claims=[ExtractedClaim(text="Afirmación válida.")])
    fake_client = _FakeClient([RuntimeError("boom"), result])
    monkeypatch.setattr(claims_module, "get_anthropic_client", lambda: fake_client)

    claims = await claims_module.extract_claims("texto")

    assert claims == ["Afirmación válida."]


async def test_extract_claims_raises_after_exhausting_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _FakeClient([RuntimeError("a"), RuntimeError("b"), RuntimeError("c")])
    monkeypatch.setattr(claims_module, "get_anthropic_client", lambda: fake_client)

    with pytest.raises(claims_module.ClaimsExtractionError):
        await claims_module.extract_claims("texto", max_attempts=3)


async def test_extract_claims_empty_when_no_factual_claims(monkeypatch: pytest.MonkeyPatch) -> None:
    result = ClaimsExtractionResult(claims=[])
    fake_client = _FakeClient([result])
    monkeypatch.setattr(claims_module, "get_anthropic_client", lambda: fake_client)

    claims = await claims_module.extract_claims("esto es pura opinión, no hechos")

    assert claims == []
