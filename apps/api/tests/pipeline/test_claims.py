from types import SimpleNamespace

import pytest

from app.modules.pipeline import claims as claims_module
from app.modules.pipeline.claims import ClaimsExtractionResult, ExtractedClaim


class _FakeParseResponse:
    def __init__(
        self, parsed_output: ClaimsExtractionResult | None, stop_reason: str = "end_turn"
    ) -> None:
        self.parsed_output = parsed_output
        self.stop_reason = stop_reason
        self.usage = SimpleNamespace(input_tokens=10, output_tokens=5, server_tool_use=None)


class _FakeMessages:
    def __init__(self, side_effects: list) -> None:
        self._side_effects = list(side_effects)
        self.calls: list[dict] = []

    async def parse(self, **kwargs):
        self.calls.append(kwargs)
        effect = self._side_effects.pop(0)
        if isinstance(effect, Exception):
            raise effect
        if isinstance(effect, _FakeParseResponse):
            return effect
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


@pytest.mark.parametrize("stop_reason", ["max_tokens", "refusal"])
async def test_truncated_or_refused_extraction_fails_without_retrying(
    monkeypatch: pytest.MonkeyPatch, stop_reason: str
) -> None:
    fake_client = _FakeClient([_FakeParseResponse(None, stop_reason=stop_reason)])
    monkeypatch.setattr(claims_module, "get_anthropic_client", lambda: fake_client)

    with pytest.raises(claims_module.ClaimsExtractionError):
        await claims_module.extract_claims("texto", max_attempts=3)
    assert len(fake_client.messages.calls) == 1


async def test_extraction_leaves_room_for_adaptive_thinking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _FakeClient([ClaimsExtractionResult(claims=[])])
    monkeypatch.setattr(claims_module, "get_anthropic_client", lambda: fake_client)

    await claims_module.extract_claims("texto")

    assert fake_client.messages.calls[0]["max_tokens"] >= 16000
