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
    real_url = "https://colombiacheck.com/article1"
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
        "La afirmación X ocurrió.", allowed_domains=["colombiacheck.com"]
    )

    assert result.verdict == "SUPPORTED"
    assert len(result.evidence) == 1
    assert result.evidence[0].url == real_url
    assert result.evidence[0].domain == "colombiacheck.com"
    assert result.evidence[0].published_at == "April 30, 2025"


async def test_verify_claim_drops_hallucinated_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    real_url = "https://colombiacheck.com/real"
    invented_url = "https://colombiacheck.com/invented-by-the-model"
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

    result = await verify_module.verify_claim("afirmación", allowed_domains=["colombiacheck.com"])

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

    result = await verify_module.verify_claim("afirmación", allowed_domains=["colombiacheck.com"])

    assert result.verdict == "INSUFFICIENT"
    assert result.evidence == []


def _contradicting_evidence_content(url: str) -> list:
    return [
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


async def test_verify_claim_keeps_evidence_from_trusted_subdomain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "https://archivo.lasillavacia.com/historia/123"
    fake_client = _FakeClient([_response(content=_contradicting_evidence_content(url))])
    monkeypatch.setattr(verify_module, "get_anthropic_client", lambda: fake_client)

    result = await verify_module.verify_claim("afirmación", allowed_domains=["lasillavacia.com"])

    assert result.verdict == "CONTRADICTED"
    assert result.evidence[0].url == url
    # The trusted source's own domain, so the orchestrator finds its row.
    assert result.evidence[0].domain == "lasillavacia.com"


@pytest.mark.parametrize(
    "url", ["https://notlasillavacia.com/page", "https://lasillavacia.com.evil.example/page"]
)
async def test_verify_claim_drops_lookalike_domains(
    monkeypatch: pytest.MonkeyPatch, url: str
) -> None:
    fake_client = _FakeClient([_response(content=_contradicting_evidence_content(url))])
    monkeypatch.setattr(verify_module, "get_anthropic_client", lambda: fake_client)

    result = await verify_module.verify_claim("afirmación", allowed_domains=["lasillavacia.com"])

    assert result.verdict == "INSUFFICIENT"
    assert result.evidence == []


async def test_verify_claim_retries_on_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    url = "https://colombiacheck.com/a"
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
        "afirmación", allowed_domains=["colombiacheck.com"], max_attempts=2
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
        "afirmación", allowed_domains=["colombiacheck.com"], max_attempts=2
    )

    assert result.verdict == "INSUFFICIENT"
    assert result.verification_failed is True


async def test_verify_claim_without_evidence_is_not_a_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answer = {"verdict": "INSUFFICIENT", "rationale": "Nada concluyente.", "evidence": []}
    content = [_search_tool_result_block([]), _text_block(json.dumps(answer))]
    monkeypatch.setattr(
        verify_module, "get_anthropic_client", lambda: _FakeClient([_response(content)])
    )

    result = await verify_module.verify_claim("afirmación", allowed_domains=["colombiacheck.com"])

    assert result.verdict == "INSUFFICIENT"
    assert result.verification_failed is False


def _verdict_with_evidence(verdict: str, stances: list[str]) -> list:
    urls = [f"https://colombiacheck.com/a{i}" for i in range(len(stances))]
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

    result = await verify_module.verify_claim("afirmación", allowed_domains=["colombiacheck.com"])

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

    result = await verify_module.verify_claim("afirmación", allowed_domains=["colombiacheck.com"])

    assert result.verdict == verdict


async def test_api_error_rationale_hides_provider_details(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _FakeClient([RuntimeError("Error code: 400 credit balance too low")] * 2)
    monkeypatch.setattr(verify_module, "get_anthropic_client", lambda: fake_client)

    result = await verify_module.verify_claim("afirmación", allowed_domains=["colombiacheck.com"])

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
    url = "https://colombiacheck.com/a"
    paused_content = [_search_tool_result_block([_web_search_result(url)])]
    paused = _response(content=paused_content, stop_reason="pause_turn")
    final = _response(content=[_text_block(_supported_json(url))])
    fake_client = _FakeClient([paused, final])
    monkeypatch.setattr(verify_module, "get_anthropic_client", lambda: fake_client)

    result = await verify_module.verify_claim("afirmación", allowed_domains=["colombiacheck.com"])

    # The search results from the paused turn still count as real results.
    assert result.verdict == "SUPPORTED"
    assert [e.url for e in result.evidence] == [url]
    resumed = fake_client.messages.calls[1]["messages"]
    assert resumed[-1] == {"role": "assistant", "content": paused_content}


@pytest.mark.parametrize("stop_reason", ["max_tokens", "refusal"])
async def test_truncated_or_refused_answer_is_insufficient_without_retrying(
    monkeypatch: pytest.MonkeyPatch, stop_reason: str
) -> None:
    url = "https://colombiacheck.com/a"
    content = [
        _search_tool_result_block([_web_search_result(url)]),
        _text_block(_supported_json(url)),
    ]
    fake_client = _FakeClient([_response(content=content, stop_reason=stop_reason)])
    monkeypatch.setattr(verify_module, "get_anthropic_client", lambda: fake_client)

    result = await verify_module.verify_claim("afirmación", allowed_domains=["colombiacheck.com"])

    assert result.verdict == "INSUFFICIENT"
    assert result.evidence == []
    assert len(fake_client.messages.calls) == 1


async def test_requests_leave_room_for_adaptive_thinking(monkeypatch: pytest.MonkeyPatch) -> None:
    url = "https://colombiacheck.com/a"
    content = [
        _search_tool_result_block([_web_search_result(url)]),
        _text_block(_supported_json(url)),
    ]
    fake_client = _FakeClient([_response(content=content)])
    monkeypatch.setattr(verify_module, "get_anthropic_client", lambda: fake_client)

    await verify_module.verify_claim("afirmación", allowed_domains=["colombiacheck.com"])

    assert fake_client.messages.calls[0]["max_tokens"] >= 16000


async def test_verify_claim_drops_evidence_with_non_http_scheme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The host is whitelisted, but the link would run script when clicked.
    script_url = "javascript://colombiacheck.com/%0Aalert(1)"
    content = [
        _search_tool_result_block([_web_search_result(script_url)]),
        _text_block(
            json.dumps(
                {
                    "verdict": "SUPPORTED",
                    "rationale": "...",
                    "evidence": [
                        {
                            "url": script_url,
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

    result = await verify_module.verify_claim("afirmación", allowed_domains=["colombiacheck.com"])

    assert result.verdict == "INSUFFICIENT"
    assert result.evidence == []


def test_evidence_item_rejects_non_http_url() -> None:
    with pytest.raises(ValueError):
        verify_module.EvidenceItem(
            url="javascript:alert(1)", domain="colombiacheck.com", snippet="...", stance="neutral"
        )


async def test_verify_claim_does_not_send_unsearchable_domains(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _FakeClient([_response(content=[_text_block("no es json")])] * 2)
    monkeypatch.setattr(verify_module, "get_anthropic_client", lambda: fake_client)

    await verify_module.verify_claim(
        "afirmación", allowed_domains=["reuters.com", "colombiacheck.com", "bbc.com"]
    )

    sent = fake_client.messages.calls[0]["tools"][0]["allowed_domains"]
    assert sent == ["colombiacheck.com"]


async def test_verify_claim_with_only_unsearchable_domains_skips_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _FakeClient([])
    monkeypatch.setattr(verify_module, "get_anthropic_client", lambda: fake_client)

    result = await verify_module.verify_claim("afirmación", allowed_domains=["reuters.com"])

    assert result.verdict == "INSUFFICIENT"
    assert fake_client.messages.calls == []


async def test_verify_claim_logs_domains_blocked_for_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from structlog.testing import capture_logs

    blocked = Exception(
        "Error code: 400 - The following domains are not accessible to our user agent: "
        "['newsite.com']"
    )
    fake_client = _FakeClient([blocked, blocked])
    monkeypatch.setattr(verify_module, "get_anthropic_client", lambda: fake_client)

    with capture_logs() as logs:
        result = await verify_module.verify_claim(
            "afirmación", allowed_domains=["colombiacheck.com"]
        )

    assert result.verdict == "INSUFFICIENT"
    assert any(log["event"] == "verify_claim_domains_blocked" for log in logs)


def _layout_of_a_real_answer(url: str, answer: str) -> list:
    """How Claude answered in production: prose split by citations, with the
    JSON at the end of the last text block."""
    return [
        _search_tool_result_block([_web_search_result(url)]),
        _text_block("La búsqueda confirma la afirmación. "),
        _text_block("El Banco Central ordenó el cierre"),
        _text_block(answer),
    ]


@pytest.mark.parametrize(
    "answer",
    [
        ".\n\nLa afirmación está respaldada.\n\n```json\n{json}\n```",
        ".\n\nLa afirmación está respaldada.\n\n{json}",
        "Usé el formato {{}} pedido.\n{json}",
    ],
)
async def test_verify_claim_reads_json_surrounded_by_text(
    monkeypatch: pytest.MonkeyPatch, answer: str
) -> None:
    url = "https://colombiacheck.com/a"
    content = _layout_of_a_real_answer(url, answer.replace("{json}", _supported_json(url)))
    fake = _FakeClient([_response(content)])
    monkeypatch.setattr(verify_module, "get_anthropic_client", lambda: fake)

    result = await verify_module.verify_claim("c", allowed_domains=["colombiacheck.com"])

    assert result.verdict == "SUPPORTED"
    assert len(fake.messages.calls) == 1


async def test_verify_claim_reads_json_split_across_text_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "https://colombiacheck.com/a"
    answer = _supported_json(url)
    middle = len(answer) // 2
    content = [
        _search_tool_result_block([_web_search_result(url)]),
        _text_block(answer[:middle]),
        _text_block(answer[middle:]),
    ]
    fake = _FakeClient([_response(content)])
    monkeypatch.setattr(verify_module, "get_anthropic_client", lambda: fake)

    result = await verify_module.verify_claim("c", allowed_domains=["colombiacheck.com"])

    assert result.verdict == "SUPPORTED"


@pytest.mark.parametrize(
    "answer",
    [
        pytest.param("{draft}\nCorrijo:\n{json}", id="two-verdicts-that-disagree"),
        pytest.param("{json}\n\nEso es todo.", id="text-after-the-json"),
    ],
)
async def test_verify_claim_rejects_a_verdict_it_cannot_trust(
    monkeypatch: pytest.MonkeyPatch, answer: str
) -> None:
    url = "https://colombiacheck.com/a"
    draft = json.dumps({"verdict": "CONTRADICTED", "rationale": "borrador", "evidence": []})
    answer = answer.replace("{draft}", draft).replace("{json}", _supported_json(url))
    content = _layout_of_a_real_answer(url, answer)
    fake = _FakeClient([_response(content), _response(content)])
    monkeypatch.setattr(verify_module, "get_anthropic_client", lambda: fake)

    result = await verify_module.verify_claim("c", allowed_domains=["colombiacheck.com"])

    assert result.verdict == "INSUFFICIENT"


async def test_verify_claim_ignores_verdicts_written_before_the_last_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "https://colombiacheck.com/a"
    content = [
        _text_block(_supported_json(url)),
        _search_tool_result_block([_web_search_result(url)]),
        _text_block("No encontré nada concluyente."),
    ]
    fake = _FakeClient([_response(content), _response(content)])
    monkeypatch.setattr(verify_module, "get_anthropic_client", lambda: fake)

    result = await verify_module.verify_claim("c", allowed_domains=["colombiacheck.com"])

    assert result.verdict == "INSUFFICIENT"
