import pytest

from app.core.config import get_settings
from app.modules.pipeline import ingest as ingest_module
from app.modules.pipeline.ingest import IngestError

settings = get_settings()


@pytest.fixture(autouse=True)
def _skip_ssrf_dns_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    # These tests exercise ingest logic, not SSRF guarding (see
    # test_url_safety.py) — skip the real DNS lookup so they stay hermetic.
    monkeypatch.setattr(ingest_module, "assert_public_http_url", lambda url: None)


async def test_ingest_text_trims_whitespace() -> None:
    result = await ingest_module.ingest_text("   hola mundo   ")
    assert result == "hola mundo"


async def test_ingest_text_rejects_empty() -> None:
    with pytest.raises(IngestError):
        await ingest_module.ingest_text("   ")


async def test_ingest_text_caps_length(monkeypatch: pytest.MonkeyPatch) -> None:
    # `settings` is the lru_cache singleton shared with ingest_module, so
    # mutating this attribute affects the code under test directly.
    monkeypatch.setattr(settings, "max_text_input_chars", 10)
    result = await ingest_module.ingest_text("a" * 100)
    assert len(result) == 10


async def test_ingest_url_success(monkeypatch: pytest.MonkeyPatch) -> None:
    import trafilatura

    monkeypatch.setattr(trafilatura, "fetch_url", lambda url: "<html>raw</html>")
    monkeypatch.setattr(
        trafilatura, "extract", lambda html, favor_recall=True: "Texto extraído del artículo."
    )

    result = await ingest_module.ingest_url("https://example.com/article")

    assert result == "Texto extraído del artículo."


async def test_ingest_url_fetch_failure_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    import trafilatura

    monkeypatch.setattr(trafilatura, "fetch_url", lambda url: None)

    with pytest.raises(IngestError):
        await ingest_module.ingest_url("https://example.com/unreachable")


async def test_ingest_url_extract_failure_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    import trafilatura

    monkeypatch.setattr(trafilatura, "fetch_url", lambda url: "<html></html>")
    monkeypatch.setattr(trafilatura, "extract", lambda html, favor_recall=True: None)

    with pytest.raises(IngestError):
        await ingest_module.ingest_url("https://example.com/empty")


class _FakeYoutubeDL:
    info: dict = {}
    filename: str = "/tmp/fake-audio.webm"

    def __init__(self, opts: dict) -> None:
        self.opts = opts

    def __enter__(self) -> "_FakeYoutubeDL":
        return self

    def __exit__(self, *_args: object) -> bool:
        return False

    def extract_info(self, _url: str, download: bool) -> dict:
        return type(self).info

    def prepare_filename(self, _info: dict) -> str:
        return type(self).filename


class _FakeTranscriber:
    def __init__(self, text: str = "texto transcrito del audio") -> None:
        self.text = text
        self.received_path: str | None = None

    async def transcribe(self, audio_path: str) -> str:
        self.received_path = audio_path
        return self.text


async def test_ingest_video_rejects_too_long(monkeypatch: pytest.MonkeyPatch) -> None:
    import yt_dlp

    _FakeYoutubeDL.info = {"duration": settings.max_video_duration_seconds + 1}
    monkeypatch.setattr(yt_dlp, "YoutubeDL", _FakeYoutubeDL)

    with pytest.raises(IngestError):
        await ingest_module.ingest_video(
            "https://www.youtube.com/watch?v=too-long", _FakeTranscriber()
        )


async def test_ingest_video_success(monkeypatch: pytest.MonkeyPatch) -> None:
    import yt_dlp

    _FakeYoutubeDL.info = {"duration": 60}
    monkeypatch.setattr(yt_dlp, "YoutubeDL", _FakeYoutubeDL)
    transcriber = _FakeTranscriber("Esto dijo el video.")

    result = await ingest_module.ingest_video("https://www.youtube.com/watch?v=ok", transcriber)

    assert result == "Esto dijo el video."
    assert transcriber.received_path == _FakeYoutubeDL.filename
