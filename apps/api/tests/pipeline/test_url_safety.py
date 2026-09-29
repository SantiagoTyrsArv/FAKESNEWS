import socket

import pytest

from app.modules.pipeline.url_safety import (
    UnsafeUrlError,
    assert_allowed_video_host,
    assert_public_http_url,
)


def _fake_addrinfo(ip: str):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443))]


def test_rejects_non_http_scheme() -> None:
    with pytest.raises(UnsafeUrlError):
        assert_public_http_url("file:///etc/passwd")


def test_rejects_url_without_host() -> None:
    with pytest.raises(UnsafeUrlError):
        assert_public_http_url("https://")


def test_rejects_loopback_address(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: _fake_addrinfo("127.0.0.1"))
    with pytest.raises(UnsafeUrlError):
        assert_public_http_url("http://localhost/")


def test_rejects_cloud_metadata_address(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: _fake_addrinfo("169.254.169.254"))
    with pytest.raises(UnsafeUrlError):
        assert_public_http_url("http://169.254.169.254/latest/meta-data/")


def test_rejects_private_network_address(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: _fake_addrinfo("10.0.0.5"))
    with pytest.raises(UnsafeUrlError):
        assert_public_http_url("http://internal.example/")


def test_rejects_unresolvable_host(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*_a, **_k):
        raise socket.gaierror("no such host")

    monkeypatch.setattr(socket, "getaddrinfo", _raise)
    with pytest.raises(UnsafeUrlError):
        assert_public_http_url("http://does-not-resolve.invalid/")


def test_allows_public_address(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: _fake_addrinfo("93.184.216.34"))
    assert_public_http_url("https://example.com/article")  # should not raise


def test_allowed_video_host_accepts_whitelisted() -> None:
    assert_allowed_video_host("https://www.youtube.com/watch?v=x", {"www.youtube.com"})


def test_allowed_video_host_rejects_others() -> None:
    with pytest.raises(UnsafeUrlError):
        assert_allowed_video_host("https://internal.example/video", {"www.youtube.com"})
