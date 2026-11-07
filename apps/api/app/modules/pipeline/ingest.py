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


def ingest_text(raw_text: str) -> str:
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


_LIVE_STATUSES = ("is_live", "is_upcoming", "post_live")
_SINGLE_VIDEO_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "playlistend": 1,
    "socket_timeout": 30,
}


def _extract_video_info(video_url: str) -> dict:
    import yt_dlp

    assert_allowed_video_host(video_url, set(settings.allowed_video_hosts))
    assert_public_http_url(video_url)
    opts = {"skip_download": True, **_SINGLE_VIDEO_OPTS}
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(video_url, download=False)


def _check_video_is_bounded(info: dict) -> None:
    """Only a finished video of known length gets downloaded. Live streams go
    through ffmpeg, which reports no progress for the size cap to act on, and
    a playlist has no duration of its own."""
    if info.get("is_live") or info.get("live_status") in _LIVE_STATUSES:
        raise IngestError("No se pueden analizar videos en directo.")
    duration = info.get("duration")
    if duration is None:
        raise IngestError("No se pudo saber cuánto dura el video.")
    if duration > settings.max_video_duration_seconds:
        raise IngestError(
            f"El video dura {int(duration)}s, el máximo permitido es "
            f"{settings.max_video_duration_seconds}s."
        )


def _reject_unbounded_video(info: dict, *, incomplete: bool) -> None:
    """Downloading resolves the URL again, so this checks the video actually
    about to be fetched. `incomplete` entries don't have their data yet."""
    if not incomplete:
        _check_video_is_bounded(info)


def _stop_oversized_download(progress: dict) -> None:
    """A hook and not yt-dlp's max_filesize, which needs a Content-Length and
    so lets through streams that don't send one."""
    cap_mb = settings.max_video_download_mb
    if (progress.get("downloaded_bytes") or 0) > cap_mb * 1024 * 1024:
        raise IngestError(f"El video pesa más de {cap_mb} MB, el máximo permitido.")


def _download_audio(video_url: str, out_dir: str) -> str:
    import yt_dlp

    assert_allowed_video_host(video_url, set(settings.allowed_video_hosts))
    assert_public_http_url(video_url)
    opts = {
        **_SINGLE_VIDEO_OPTS,
        "format": "bestaudio/best",
        "outtmpl": str(Path(out_dir) / "%(id)s.%(ext)s"),
        "match_filter": _reject_unbounded_video,
        "progress_hooks": [_stop_oversized_download],
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
    _check_video_is_bounded(info)

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
