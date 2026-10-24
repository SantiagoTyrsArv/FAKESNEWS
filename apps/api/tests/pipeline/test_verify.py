import json
from types import SimpleNamespace

import pytest

from app.modules.pipeline import verify as verify_module


def _web_search_result(url: str, title: str = "Title", page_age: str | None = "April 30, 2025"):
    return SimpleNamespace(type="web_search_result", url=url, title=title, page_age=page_age)


def _search_tool_result_block(results: list):
    return SimpleNamespace(type="web_search_tool_result", content=results)


def _text_block(text: str):
    return SimpleNamespace(type="text", text=text)


def _response(content: list, stop_reason: str = "end_turn"):
    usage = SimpleNamespace(input_tokens=10, output_tokens=5, server_tool_use=None)
    return SimpleNamespace(content=content, stop_reason=stop_reason, usage=usage)


class _FakeMessages:
    def __init__(self, side_effects: list) -> None:
        self._side_effects = list(side_effects)
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        effect = self._side_effects.pop(0)
        if isinstance(effect, Exception):
            raise effect
        return effect


class _FakeClient:
    def __init__(self, side_effects: list) -> None:
        self.messages = _FakeMessages(side_effects)


async def test_verify_claim_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    real_url = "https://reuters.com/article1"
    content = [
        _text_block("Voy a buscar sobre esto."),
        _search_tool_result_block([_web_search_result(real_url, page_age="April 30, 2025")]),
        _text_block(
            json.dumps(
                {
                    "verdict": "SUPPORTED",
                    "rationale": "La fuente confirma el hecho.",
                    "evidence": [
                        {
                            "url": real_url,
                            "snippet": "texto citado de la fuente",
                            "published_at": None,
                            "stance": "supports",
                        }
                    ],
                }
            )
        ),
    ]
    fake_client = _FakeClient([_response(content=content)])
    monkeypatch.setattr(verify_module, "get_anthropic_client", lambda: fake_client)

    result = await verify_module.verify_claim(
        "La afirmación X ocurrió.", allowed_domains=["reuters.com"]
    )

    assert result.verdict == "SUPPORTED"
    assert len(result.evidence) == 1
    assert result.evidence[0].url == real_url
    assert result.evidence[0].domain == "reuters.com"
    assert result.evidence[0].published_at == "April 30, 2025"


async def test_verify_claim_drops_hallucinated_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    real_url = "https://reuters.com/real"
    invented_url = "https://reuters.com/invented-by-the-model"
    content = [
        _search_tool_result_block([_web_search_result(real_url)]),
        _text_block(
            json.dumps(
                {
                    "verdict": "SUPPORTED",
                    "rationale": "...",
                    "evidence": [
                        {
                            "url": invented_url,
                            "snippet": "...",
                            "published_at": None,
                            "stance": "supports",
                        }
                    ],
                }
            )
        ),
    ]
    fake_client = _FakeClient([_response(content=content)])
    monkeypatch.setattr(verify_module, "get_anthropic_client", lambda: fake_client)

    result = await verify_module.verify_claim("afirmación", allowed_domains=["reuters.com"])

    assert result.verdict == "INSUFFICIENT"
    assert result.evidence == []


async def test_verify_claim_drops_evidence_outside_whitelist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "https://not-trusted.com/page"
    content = [
        _search_tool_result_block([_web_search_result(url)]),
        _text_block(
            json.dumps(
                {
                    "verdict": "CONTRADICTED",
                    "rationale": "...",
                    "evidence": [
                        {
                            "url": url,
                            "snippet": "...",
                            "published_at": None,
                            "stance": "contradicts",
                        }
                    ],
                }
            )
        ),
    ]
    fake_client = _FakeClient([_response(content=content)])
    monkeypatch.setattr(verify_module, "get_anthropic_client", lambda: fake_client)

    result = await verify_module.verify_claim("afirmación", allowed_domains=["reuters.com"])

    assert result.verdict == "INSUFFICIENT"
    assert result.evidence == []


async def test_verify_claim_retries_on_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    url = "https://reuters.com/a"
    bad_response = _response(
        content=[_search_tool_result_block([_web_search_result(url)]), _text_block("no es json")]
    )
    good_response = _response(
        content=[
            _search_tool_result_block([_web_search_result(url)]),
            _text_block(
                json.dumps(
                    {
                        "verdict": "SUPPORTED",
                        "rationale": "ok",
                        "evidence": [
                            {"url": url, "snippet": "x", "published_at": None, "stance": "supports"}
                        ],
                    }
                )
            ),
        ]
    )
    fake_client = _FakeClient([bad_response, good_response])
    monkeypatch.setattr(verify_module, "get_anthropic_client", lambda: fake_client)

    result = await verify_module.verify_claim(
        "afirmación", allowed_domains=["reuters.com"], max_attempts=2
    )

    assert result.verdict == "SUPPORTED"


async def test_verify_claim_no_allowed_domains_skips_call(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail_if_called():
        raise AssertionError("get_anthropic_client should not be called")

    monkeypatch.setattr(verify_module, "get_anthropic_client", _fail_if_called)

    result = await verify_module.verify_claim("afirmación", allowed_domains=[])

    assert result.verdict == "INSUFFICIENT"


async def test_verify_claim_api_error_returns_insufficient(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _FakeClient([RuntimeError("network down"), RuntimeError("network down")])
    monkeypatch.setattr(verify_module, "get_anthropic_client", lambda: fake_client)

    result = await verify_module.verify_claim(
        "afirmación", allowed_domains=["reuters.com"], max_attempts=2
    )

    assert result.verdict == "INSUFFICIENT"


def _verdict_with_evidence(verdict: str, stances: list[str]) -> list:
    urls = [f"https://reuters.com/a{i}" for i in range(len(stances))]
    return [
        _search_tool_result_block([_web_search_result(u) for u in urls]),
        _text_block(
            json.dumps(
                {
                    "verdict": verdict,
                    "rationale": "explicación del modelo",
                    "evidence": [
                        {"url": u, "snippet": "cita", "published_at": None, "stance": s}
                        for u, s in zip(urls, stances, strict=True)
                    ],
                }
            )
        ),
    ]


@pytest.mark.parametrize(
    ("verdict", "stances"),
    [
        ("SUPPORTED", ["neutral"]),
        ("SUPPORTED", ["contradicts"]),
        ("CONTRADICTED", ["neutral", "neutral"]),
        ("CONTRADICTED", ["supports"]),
    ],
)
async def test_directional_verdict_needs_matching_evidence(
    monkeypatch: pytest.MonkeyPatch, verdict: str, stances: list[str]
) -> None:
    content = _verdict_with_evidence(verdict, stances)
    fake_client = _FakeClient([_response(content=content)])
    monkeypatch.setattr(verify_module, "get_anthropic_client", lambda: fake_client)

    result = await verify_module.verify_claim("afirmación", allowed_domains=["reuters.com"])

    assert result.verdict == "INSUFFICIENT"
    # The real, validated citations are still shown, just not as proof.
    assert len(result.evidence) == len(stances)


@pytest.mark.parametrize(
    ("verdict", "stances"),
    [("SUPPORTED", ["supports", "neutral"]), ("CONTRADICTED", ["contradicts", "supports"])],
)
async def test_directional_verdict_kept_with_matching_evidence(
    monkeypatch: pytest.MonkeyPatch, verdict: str, stances: list[str]
) -> None:
    content = _verdict_with_evidence(verdict, stances)
    fake_client = _FakeClient([_response(content=content)])
    monkeypatch.setattr(verify_module, "get_anthropic_client", lambda: fake_client)

    result = await verify_module.verify_claim("afirmación", allowed_domains=["reuters.com"])

    assert result.verdict == verdict


async def test_api_error_rationale_hides_provider_details(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _FakeClient([RuntimeError("Error code: 400 credit balance too low")] * 2)
    monkeypatch.setattr(verify_module, "get_anthropic_client", lambda: fake_client)

    result = await verify_module.verify_claim("afirmación", allowed_domains=["reuters.com"])

    assert result.verdict == "INSUFFICIENT"
    assert "credit" not in result.rationale
    assert "400" not in result.rationale


def _supported_json(url: str) -> str:
    return json.dumps(
        {
            "verdict": "SUPPORTED",
            "rationale": "La fuente confirma el hecho.",
            "evidence": [{"url": url, "snippet": "x", "published_at": None, "stance": "supports"}],
        }
    )


async def test_pause_turn_is_resumed_with_the_paused_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "https://reuters.com/a"
    paused_content = [_search_tool_result_block([_web_search_result(url)])]
    paused = _response(content=paused_content, stop_reason="pause_turn")
    final = _response(content=[_text_block(_supported_json(url))])
    fake_client = _FakeClient([paused, final])
    monkeypatch.setattr(verify_module, "get_anthropic_client", lambda: fake_client)

    result = await verify_module.verify_claim("afirmación", allowed_domains=["reuters.com"])

    # The search results from the paused turn still count as real results.
    assert result.verdict == "SUPPORTED"
    assert [e.url for e in result.evidence] == [url]
    resumed = fake_client.messages.calls[1]["messages"]
    assert resumed[-1] == {"role": "assistant", "content": paused_content}


@pytest.mark.parametrize("stop_reason", ["max_tokens", "refusal"])
async def test_truncated_or_refused_answer_is_insufficient_without_retrying(
    monkeypatch: pytest.MonkeyPatch, stop_reason: str
) -> None:
    url = "https://reuters.com/a"
    content = [
        _search_tool_result_block([_web_search_result(url)]),
        _text_block(_supported_json(url)),
    ]
    fake_client = _FakeClient([_response(content=content, stop_reason=stop_reason)])
    monkeypatch.setattr(verify_module, "get_anthropic_client", lambda: fake_client)

    result = await verify_module.verify_claim("afirmación", allowed_domains=["reuters.com"])

    assert result.verdict == "INSUFFICIENT"
    assert result.evidence == []
    assert len(fake_client.messages.calls) == 1


async def test_requests_leave_room_for_adaptive_thinking(monkeypatch: pytest.MonkeyPatch) -> None:
    url = "https://reuters.com/a"
    content = [
        _search_tool_result_block([_web_search_result(url)]),
        _text_block(_supported_json(url)),
    ]
    fake_client = _FakeClient([_response(content=content)])
    monkeypatch.setattr(verify_module, "get_anthropic_client", lambda: fake_client)

    await verify_module.verify_claim("afirmación", allowed_domains=["reuters.com"])

    assert fake_client.messages.calls[0]["max_tokens"] >= 16000
