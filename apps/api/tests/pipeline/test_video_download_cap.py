"""The cap on what a video may download, with real yt-dlp over real HTTP: the
stream sends no Content-Length, which is what yt-dlp's own max_filesize needs."""

import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.modules.pipeline import ingest as ingest_module

MEGABYTE = 1024 * 1024
STREAM_MEGABYTES = 8


class _EndlessAudio(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self.end_headers()
        try:
            for _ in range(STREAM_MEGABYTES):
                self.wfile.write(b"\0" * MEGABYTE)
        except OSError:
            return  # the client hung up, as it should

    def log_message(self, *_args) -> None:
        return


@pytest.fixture
def audio_url(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    # The URL is on loopback: the SSRF checks would rightly reject it.
    monkeypatch.setattr(ingest_module, "assert_allowed_video_host", lambda *_: None)
    monkeypatch.setattr(ingest_module, "assert_public_http_url", lambda *_: None)
    server = ThreadingHTTPServer(("127.0.0.1", 0), _EndlessAudio)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/audio.mp3"
    server.shutdown()
    server.server_close()


def test_download_stops_at_the_cap(audio_url: str, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ingest_module.settings, "max_video_download_mb", 2)

    with pytest.raises(ingest_module.IngestError, match="2 MB"):
        ingest_module._download_audio(audio_url, str(tmp_path))


def test_download_under_the_cap_finishes(audio_url: str, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ingest_module.settings, "max_video_download_mb", STREAM_MEGABYTES + 1)

    path = ingest_module._download_audio(audio_url, str(tmp_path))

    assert (tmp_path / path.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]).exists()
