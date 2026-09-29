import ipaddress
import socket
from urllib.parse import urlparse

_ALLOWED_SCHEMES = {"http", "https"}


class UnsafeUrlError(Exception):
    pass


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


def assert_public_http_url(url: str) -> None:
    """Reject URLs usable for SSRF: non-http(s) schemes, and hostnames that
    resolve to a loopback/private/link-local/reserved address (localhost,
    RFC1918 ranges, cloud metadata endpoints like 169.254.169.254, etc.).

    Call this synchronously from the worker thread that's about to make the
    request, right before making it (it does a blocking DNS lookup).

    Caveat: this validates the URL given to us, not every hop of a redirect
    chain the HTTP client might follow afterwards — a malicious server could
    still 302 a validated public URL to an internal address. Full protection
    would require disabling redirects and re-validating each hop, which
    trafilatura/yt-dlp don't expose cleanly; out of scope for this MVP.
    """
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise UnsafeUrlError(f"Esquema de URL no permitido: {parsed.scheme!r}")

    hostname = parsed.hostname
    if not hostname:
        raise UnsafeUrlError("La URL no tiene un host válido.")

    try:
        addrinfos = socket.getaddrinfo(hostname, parsed.port)
    except socket.gaierror as exc:
        raise UnsafeUrlError(f"No se pudo resolver el host: {hostname}") from exc

    for info in addrinfos:
        sockaddr = info[4]
        if not _is_public_ip(sockaddr[0]):
            raise UnsafeUrlError(
                f"El host '{hostname}' resuelve a una dirección de red no pública."
            )


def assert_allowed_video_host(url: str, allowed_hosts: set[str]) -> None:
    """Restrict video URLs to a known-platform allowlist so yt-dlp's generic
    extractor (which will scrape *any* URL looking for embedded media) can't
    be pointed at an arbitrary internal address.
    """
    hostname = (urlparse(url).hostname or "").lower()
    if hostname not in allowed_hosts:
        raise UnsafeUrlError(f"Host de video no permitido: {hostname or url!r}")
