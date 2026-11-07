import httpx
import pytest
import respx
from pydantic import BaseModel

from app.core import llm
from app.core.llm import LLMError, LLMQuotaError, generate_structured

URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-test:generateContent"


class _Answer(BaseModel):
    verdict: str


def _ok(text: str = '{"verdict": "SUPPORTED"}') -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5},
        },
    )


async def _generate() -> _Answer:
    return await generate_structured(
        step="verify", system="s", user="u", schema=_Answer, model="gemini-test"
    )


@pytest.fixture(autouse=True)
def _settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm.settings, "gemini_api_key", "secret-key")
    monkeypatch.setattr(llm, "RETRY_WAIT_SECONDS", 0)


@respx.mock
async def test_generate_structured_returns_the_parsed_schema() -> None:
    respx.post(URL).mock(return_value=_ok())

    assert await _generate() == _Answer(verdict="SUPPORTED")


@respx.mock
async def test_generate_structured_sends_the_key_in_a_header_and_the_schema() -> None:
    route = respx.post(URL).mock(return_value=_ok())

    await _generate()

    request = route.calls.last.request
    assert request.headers["x-goog-api-key"] == "secret-key"
    assert "secret-key" not in str(request.url)
    body = request.content.decode()
    assert '"responseMimeType":"application/json"' in body
    assert '"responseJsonSchema"' in body


@respx.mock
async def test_generate_structured_joins_the_text_parts() -> None:
    response = _ok()
    payload = response.json()
    payload["candidates"][0]["content"]["parts"] = [
        {"text": '{"verdict"'},
        {"text": ': "SUPPORTED"}'},
    ]
    respx.post(URL).mock(return_value=httpx.Response(200, json=payload))

    assert (await _generate()).verdict == "SUPPORTED"


@respx.mock
async def test_generate_structured_retries_once_on_503() -> None:
    route = respx.post(URL).mock(side_effect=[httpx.Response(503), _ok()])

    await _generate()

    assert route.call_count == 2


@respx.mock
async def test_generate_structured_gives_up_after_one_retry() -> None:
    route = respx.post(URL).mock(return_value=httpx.Response(503))

    with pytest.raises(LLMError):
        await _generate()

    assert route.call_count == 2


@respx.mock
async def test_generate_structured_honours_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    waits: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr(llm.asyncio, "sleep", fake_sleep)
    respx.post(URL).mock(side_effect=[httpx.Response(429, headers={"Retry-After": "7"}), _ok()])

    await _generate()

    assert waits == [7]


@respx.mock
async def test_generate_structured_caps_a_long_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    waits: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr(llm.asyncio, "sleep", fake_sleep)
    respx.post(URL).mock(side_effect=[httpx.Response(429, headers={"Retry-After": "900"}), _ok()])

    await _generate()

    assert waits == [llm.MAX_RETRY_WAIT_SECONDS]


@respx.mock
async def test_repeated_429_is_a_quota_error() -> None:
    route = respx.post(URL).mock(return_value=httpx.Response(429))

    with pytest.raises(LLMQuotaError):
        await _generate()

    assert route.call_count == 2


@respx.mock
async def test_prepayment_depleted_is_a_quota_error_without_retrying() -> None:
    route = respx.post(URL).mock(return_value=httpx.Response(402))

    with pytest.raises(LLMQuotaError):
        await _generate()

    assert route.call_count == 1


@respx.mock
async def test_bad_schema_raises_without_retrying() -> None:
    route = respx.post(URL).mock(return_value=_ok('{"otro": 1}'))

    with pytest.raises(LLMError):
        await _generate()

    assert route.call_count == 1


@respx.mock
async def test_truncated_answer_raises() -> None:
    response = _ok()
    payload = response.json()
    payload["candidates"][0]["finishReason"] = "MAX_TOKENS"
    respx.post(URL).mock(return_value=httpx.Response(200, json=payload))

    with pytest.raises(LLMError):
        await _generate()


@respx.mock
async def test_answer_without_candidates_raises() -> None:
    respx.post(URL).mock(return_value=httpx.Response(200, json={"candidates": []}))

    with pytest.raises(LLMError):
        await _generate()


@respx.mock
async def test_network_errors_are_retried_then_raised() -> None:
    route = respx.post(URL).mock(side_effect=httpx.ConnectError("boom"))

    with pytest.raises(LLMError):
        await _generate()

    assert route.call_count == 2


@respx.mock
async def test_llm_errors_never_contain_the_api_key() -> None:
    respx.post(URL).mock(return_value=httpx.Response(400, json={"error": "secret-key"}))

    with pytest.raises(LLMError) as exc:
        await _generate()

    assert "secret-key" not in str(exc.value)
