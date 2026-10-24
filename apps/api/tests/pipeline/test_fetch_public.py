import socket

import httpx
import pytest
import respx

from app.modules.pipeline.url_safety import UnsafeUrlError, fetch_public_page

PUBLIC = "93.184.216.34"
OTHER_PUBLIC = "93.184.216.35"


def _resolver(table: dict[str, list[str]], calls: list[str] | None = None):
    """getaddrinfo stand-in: each lookup of a host returns the next answer in
    its list (the last one repeats), so a test can change DNS between calls."""
    seen: dict[str, int] = {}

    def fake(host, port, *args, **kwargs):
        if calls is not None:
            calls.append(host)
        answers = table[host]
        i = seen.get(host, 0)
        seen[host] = i + 1
        ip = answers[min(i, len(answers) - 1)]
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port or 443))]

    return fake


@respx.mock
def test_fetches_through_the_validated_ip_with_the_real_host(monkeypatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _resolver({"news.example": [PUBLIC]}))
    route = respx.get(f"https://{PUBLIC}/article").mock(
        return_value=httpx.Response(200, text="<html>hola</html>")
    )

    assert fetch_public_page("https://news.example/article") == "<html>hola</html>"
    request = route.calls.last.request
    assert request.headers["host"] == "news.example"
    assert request.extensions["sni_hostname"] == "news.example"


@respx.mock
def test_a_dns_change_after_validation_cannot_redirect_the_connection(monkeypatch) -> None:
    # Rebinding: public when validated, private on any later lookup. The
    # connection must use the validated answer, never ask DNS again.
    calls: list[str] = []
    monkeypatch.setattr(
        socket, "getaddrinfo", _resolver({"news.example": [PUBLIC, "10.0.0.5"]}, calls)
    )
    respx.get(f"https://{PUBLIC}/").mock(return_value=httpx.Response(200, text="ok"))

    assert fetch_public_page("https://news.example/") == "ok"
    assert calls == ["news.example"]


@respx.mock
def test_rejects_a_redirect_to_an_internal_address(monkeypatch) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        _resolver({"news.example": [PUBLIC], "internal.example": ["10.0.0.5"]}),
    )
    respx.get(f"https://{PUBLIC}/").mock(
        return_value=httpx.Response(302, headers={"Location": "http://internal.example/admin"})
    )

    with pytest.raises(UnsafeUrlError):
        fetch_public_page("https://news.example/")


@respx.mock
def test_follows_a_redirect_to_another_public_host(monkeypatch) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        _resolver({"news.example": [PUBLIC], "www.news.example": [OTHER_PUBLIC]}),
    )
    respx.get(f"https://{PUBLIC}/a").mock(
        return_value=httpx.Response(301, headers={"Location": "https://www.news.example/b"})
    )
    respx.get(f"https://{OTHER_PUBLIC}/b").mock(return_value=httpx.Response(200, text="final"))

    assert fetch_public_page("https://news.example/a") == "final"


@respx.mock
def test_gives_up_after_five_redirects(monkeypatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _resolver({"news.example": [PUBLIC]}))
    respx.get(f"https://{PUBLIC}/loop").mock(
        return_value=httpx.Response(302, headers={"Location": "/loop"})
    )

    with pytest.raises(UnsafeUrlError, match="redirecciones"):
        fetch_public_page("https://news.example/loop")


@respx.mock
def test_caps_the_body_size(monkeypatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _resolver({"news.example": [PUBLIC]}))
    respx.get(f"https://{PUBLIC}/big").mock(return_value=httpx.Response(200, text="x" * 50))

    assert fetch_public_page("https://news.example/big", max_bytes=10) == "x" * 10


def test_rejects_a_private_first_hop(monkeypatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _resolver({"intranet.example": ["192.168.1.2"]}))
    with pytest.raises(UnsafeUrlError):
        fetch_public_page("http://intranet.example/")


@respx.mock
def test_asks_for_an_uncompressed_body(monkeypatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _resolver({"news.example": [PUBLIC]}))
    route = respx.get(f"https://{PUBLIC}/").mock(return_value=httpx.Response(200, text="ok"))

    fetch_public_page("https://news.example/")
    assert route.calls.last.request.headers["accept-encoding"] == "identity"


@respx.mock
def test_a_compressed_body_is_only_inflated_up_to_the_cap(monkeypatch) -> None:
    import gzip

    monkeypatch.setattr(socket, "getaddrinfo", _resolver({"news.example": [PUBLIC]}))
    bomb = gzip.compress(b"a" * 10_000_000)  # ~10 KB on the wire, 10 MB inflated
    respx.get(f"https://{PUBLIC}/").mock(
        return_value=httpx.Response(200, content=bomb, headers={"Content-Encoding": "gzip"})
    )

    assert fetch_public_page("https://news.example/", max_bytes=1000) == "a" * 1000


@respx.mock
def test_an_unknown_encoding_is_refused(monkeypatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _resolver({"news.example": [PUBLIC]}))
    respx.get(f"https://{PUBLIC}/").mock(
        return_value=httpx.Response(200, content=b"\x00", headers={"Content-Encoding": "br"})
    )

    with pytest.raises(httpx.DecodingError):
        fetch_public_page("https://news.example/")


@respx.mock
def test_a_download_slower_than_the_deadline_is_abandoned(monkeypatch) -> None:
    import app.modules.pipeline.url_safety as url_safety

    monkeypatch.setattr(socket, "getaddrinfo", _resolver({"news.example": [PUBLIC]}))
    respx.get(f"https://{PUBLIC}/").mock(
        return_value=httpx.Response(200, content=iter([b"a"] * 100))
    )
    clock = iter(range(0, 10_000, 5))  # every look at the clock is 5 s later
    monkeypatch.setattr(url_safety.time, "monotonic", lambda: next(clock))

    with pytest.raises(httpx.TimeoutException):
        fetch_public_page("https://news.example/")
