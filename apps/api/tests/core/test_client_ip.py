import pytest
from starlette.requests import Request

from app.core import client_ip as client_ip_module
from app.core.config import Settings


def _request(peer: str, forwarded: str | None = None) -> Request:
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded is not None else []
    return Request({"type": "http", "headers": headers, "client": (peer, 1234)})


@pytest.fixture
def hops(monkeypatch):
    def set_hops(value: int) -> None:
        settings = Settings(_env_file=None, TRUSTED_PROXY_HOPS=value)
        monkeypatch.setattr(client_ip_module, "get_settings", lambda: settings)

    return set_hops


def test_no_trusted_proxies_uses_socket_peer(hops) -> None:
    hops(0)
    assert client_ip_module.client_ip(_request("10.0.0.1", "6.6.6.6")) == "10.0.0.1"


def test_one_proxy_takes_the_address_it_appended(hops) -> None:
    hops(1)
    # Railway edge (peer 10.0.0.1) appended the real client 203.0.113.7.
    assert client_ip_module.client_ip(_request("10.0.0.1", "203.0.113.7")) == "203.0.113.7"


def test_spoofed_leftmost_entries_are_ignored(hops) -> None:
    hops(1)
    request = _request("10.0.0.1", "1.2.3.4, 5.6.7.8, 203.0.113.7")
    assert client_ip_module.client_ip(request) == "203.0.113.7"


def test_two_proxies_skip_both_hops(hops) -> None:
    hops(2)
    # Vercel set the client IP; Railway appended Vercel's egress IP.
    request = _request("10.0.0.1", "203.0.113.7, 76.76.21.21")
    assert client_ip_module.client_ip(request) == "203.0.113.7"


def test_shorter_chain_than_expected_falls_back_to_first_entry(hops) -> None:
    hops(2)
    assert client_ip_module.client_ip(_request("10.0.0.1")) == "10.0.0.1"
