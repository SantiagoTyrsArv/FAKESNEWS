import ipaddress
import socket
import time
import zlib
from urllib.parse import ParseResult, urljoin, urlparse

import httpx

_ALLOWED_SCHEMES = {"http", "https"}
_MAX_REDIRECTS = 5
_MAX_BYTES = 5_000_000
_TIMEOUT_SECONDS = 15.0  # the whole download, redirects included
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_USER_AGENT = "Mozilla/5.0 (compatible; FakesNewsBot/1.0)"


class UnsafeUrlError(Exception):
    """`reason` is a fixed code, safe to log; the message may name the host."""

    def __init__(self, message: str, reason: str = "unsafe") -> None:
        super().__init__(message)
        self.reason = reason


def _is_public_ip(ip_str: str) -> bool:
    ip = ipaddress.ip_address(ip_str)
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _validated_target(url: str) -> tuple[ParseResult, str]:
    """Parse `url` and resolve its host once: every address must be public,
    and the first one is returned so the caller connects to exactly the
    address that was checked."""
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise UnsafeUrlError(f"Esquema de URL no permitido: {parsed.scheme!r}", "scheme")

    hostname = parsed.hostname
    if not hostname:
        raise UnsafeUrlError("La URL no tiene un host válido.", "no_host")

    try:
        addrinfos = socket.getaddrinfo(hostname, parsed.port)
    except socket.gaierror as exc:
        raise UnsafeUrlError(f"No se pudo resolver el host: {hostname}", "dns") from exc

    for info in addrinfos:
        if not _is_public_ip(info[4][0]):
            raise UnsafeUrlError(
                f"El host '{hostname}' resuelve a una dirección de red no pública.",
                "private_address",
            )
    return parsed, addrinfos[0][4][0]


def assert_public_http_url(url: str) -> None:
    """Reject URLs usable for SSRF: non-http(s) schemes, and hostnames that
    resolve to a loopback/private/link-local/reserved address (localhost,
    RFC1918 ranges, cloud metadata endpoints like 169.254.169.254, etc.).

    Call this synchronously from the worker thread that's about to make the
    request, right before making it (it does a blocking DNS lookup). It only
    checks the URL itself: to download a page use fetch_public_page, which
    also checks every redirect and pins the validated address. yt-dlp still
    relies on this check plus the video host allowlist.
    """
    _validated_target(url)


def fetch_public_page(url: str, *, max_bytes: int = _MAX_BYTES) -> str:
    """Download `url` without ever reaching a non-public address.

    Each hop is validated, then fetched from the very IP that was validated
    (the Host header and TLS SNI carry the real name, so the certificate is
    still checked), so DNS rebinding between the check and the request is
    useless. Redirects are followed by hand, re-validating each target, up
    to five. The body is cut at `max_bytes` (a compressed body is inflated
    only that far), and the whole download, redirects included, must finish
    within 15 s. HTTP errors, timeouts and unsupported encodings raise
    httpx.HTTPError.
    """
    deadline = time.monotonic() + _TIMEOUT_SECONDS
    with httpx.Client(timeout=_TIMEOUT_SECONDS, follow_redirects=False) as client:
        for _ in range(_MAX_REDIRECTS + 1):
            _check_deadline(deadline)
            parsed, ip = _validated_target(url)
            host = parsed.hostname or ""
            address = f"[{ip}]" if ":" in ip else ip
            port = f":{parsed.port}" if parsed.port else ""
            pinned = parsed._replace(netloc=f"{address}{port}").geturl()
            extensions = {"sni_hostname": host} if parsed.scheme == "https" else {}
            headers = {
                "Host": f"{host}{port}",
                "User-Agent": _USER_AGENT,
                "Accept-Encoding": "identity",
            }

            with client.stream("GET", pinned, headers=headers, extensions=extensions) as response:
                if response.status_code in _REDIRECT_STATUSES:
                    location = response.headers.get("location")
                    if not location:
                        raise httpx.HTTPStatusError(
                            "Redirect without Location", request=response.request, response=response
                        )
                    url = urljoin(url, location)
                    continue
                response.raise_for_status()
                body = _read_bounded(response, max_bytes, deadline)
                return body.decode(response.encoding or "utf-8", errors="replace")
    raise UnsafeUrlError("Demasiadas redirecciones.", "redirects")


def _check_deadline(deadline: float) -> None:
    if time.monotonic() > deadline:
        raise httpx.ReadTimeout("La descarga tardó demasiado.")


def _read_bounded(response: httpx.Response, max_bytes: int, deadline: float) -> bytes:
    """At most `max_bytes` of body, read from the raw stream so neither the
    wire bytes nor a decompressed body can outgrow it, within the deadline.
    We ask for identity; gzip and deflate are still handled if sent."""
    encoding = response.headers.get("content-encoding", "identity").strip().lower()
    if encoding in ("", "identity"):
        inflater = None
    elif encoding in ("gzip", "x-gzip"):
        inflater = zlib.decompressobj(16 + zlib.MAX_WBITS)
    elif encoding == "deflate":
        inflater = zlib.decompressobj()
    else:
        raise httpx.DecodingError(f"Codificación no soportada: {encoding}")

    body = bytearray()
    for chunk in response.iter_raw():
        _check_deadline(deadline)
        room = max_bytes - len(body)
        if inflater is None:
            body.extend(chunk[:room])
        else:
            try:
                body.extend(inflater.decompress(chunk, room))
            except zlib.error as exc:
                raise httpx.DecodingError("Contenido comprimido inválido.") from exc
        if len(body) >= max_bytes:
            break
    return bytes(body)


def assert_allowed_video_host(url: str, allowed_hosts: set[str]) -> None:
    """Restrict video URLs to a known-platform allowlist so yt-dlp's generic
    extractor (which will scrape *any* URL looking for embedded media) can't
    be pointed at an arbitrary internal address.
    """
    hostname = (urlparse(url).hostname or "").lower()
    if hostname not in allowed_hosts:
        raise UnsafeUrlError(
            f"Host de video no permitido: {hostname or '(sin host)'}", "video_host"
        )
