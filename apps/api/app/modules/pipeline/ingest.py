import asyncio
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.pipeline.transcribe import Transcriber
from app.modules.pipeline.url_safety import (
    UnsafeUrlError,
    assert_allowed_video_host,
    assert_public_http_url,
    fetch_public_page,
)

settings = get_settings()
logger = get_logger(__name__)


class IngestError(Exception):
    pass


async def ingest_text(raw_text: str) -> str:
    sanitized = raw_text.strip()
    if not sanitized:
        raise IngestError("El texto enviado está vacío.")
    return sanitized[: settings.max_text_input_chars]


def _fetch_and_extract_url(url: str) -> str | None:
    import trafilatura

    # Our own SSRF-safe download (every redirect checked, validated IP
    # pinned); trafilatura only extracts the text.
    try:
        downloaded = fetch_public_page(url)
    except httpx.HTTPError:
        return None
    if not downloaded:
        return None
    return trafilatura.extract(downloaded, favor_recall=True)


def _log_blocked(url: str, exc: UnsafeUrlError) -> None:
    # The host only: a path or query string can carry a user's tokens.
    logger.warning("ssrf.blocked", host=urlparse(url).hostname, reason=exc.reason)


async def ingest_url(url: str) -> str:
    try:
        text = await asyncio.to_thread(_fetch_and_extract_url, url)
    except UnsafeUrlError as exc:
        _log_blocked(url, exc)
        raise IngestError(str(exc)) from exc
    if not text or not text.strip():
        raise IngestError("No se pudo extraer contenido del artículo en esa URL.")
    return text.strip()[: settings.max_text_input_chars]


def _extract_video_info(video_url: str) -> dict:
    import yt_dlp

    assert_allowed_video_host(video_url, set(settings.allowed_video_hosts))
    assert_public_http_url(video_url)
    opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(video_url, download=False)


def _download_audio(video_url: str, out_dir: str) -> str:
    import yt_dlp

    assert_allowed_video_host(video_url, set(settings.allowed_video_hosts))
    assert_public_http_url(video_url)
    opts = {
        "quiet": True,
        "no_warnings": True,
        "format": "bestaudio/best",
        "outtmpl": str(Path(out_dir) / "%(id)s.%(ext)s"),
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(video_url, download=True)
        return ydl.prepare_filename(info)


async def ingest_video(video_url: str, transcriber: Transcriber) -> str:
    try:
        info = await asyncio.to_thread(_extract_video_info, video_url)
    except UnsafeUrlError as exc:
        _log_blocked(video_url, exc)
        raise IngestError(str(exc)) from exc
    duration = info.get("duration")
    if duration is not None and duration > settings.max_video_duration_seconds:
        raise IngestError(
            f"El video dura {int(duration)}s, el máximo permitido es "
            f"{settings.max_video_duration_seconds}s."
        )

    try:
        with tempfile.TemporaryDirectory(prefix="fakesnews-video-") as tmp_dir:
            audio_path = await asyncio.to_thread(_download_audio, video_url, tmp_dir)
            text = await transcriber.transcribe(audio_path)
    except UnsafeUrlError as exc:
        _log_blocked(video_url, exc)
        raise IngestError(str(exc)) from exc

    if not text or not text.strip():
        raise IngestError("No se pudo transcribir audio del video.")
    return text.strip()[: settings.max_text_input_chars]
