import pytest
from starlette.requests import Request

from app.core import client_ip as client_ip_module
from app.core.config import Settings

SECRET = "s" * 48


def _request(peer: str, forwarded: str | None = None, **extra: str) -> Request:
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded is not None else []
    headers += [(name.replace("_", "-").encode(), value.encode()) for name, value in extra.items()]
    return Request({"type": "http", "headers": headers, "client": (peer, 1234)})


@pytest.fixture
def configure(monkeypatch):
    def apply(hops: int = 0, secret: str | None = None) -> None:
        settings = Settings(_env_file=None, TRUSTED_PROXY_HOPS=hops, API_PROXY_SECRET=secret)
        monkeypatch.setattr(client_ip_module, "get_settings", lambda: settings)

    return apply


def test_no_trusted_proxies_uses_socket_peer(configure) -> None:
    configure(hops=0)
    assert client_ip_module.client_ip(_request("10.0.0.1", "6.6.6.6")) == "10.0.0.1"


def test_one_proxy_takes_the_address_it_appended(configure) -> None:
    configure(hops=1)
    # Railway edge (peer 10.0.0.1) appended the real client 203.0.113.7.
    assert client_ip_module.client_ip(_request("10.0.0.1", "203.0.113.7")) == "203.0.113.7"


def test_spoofed_leftmost_entries_are_ignored(configure) -> None:
    configure(hops=1)
    request = _request("10.0.0.1", "1.2.3.4, 5.6.7.8, 203.0.113.7")
    assert client_ip_module.client_ip(request) == "203.0.113.7"


def test_two_proxies_skip_both_hops(configure) -> None:
    configure(hops=2)
    request = _request("10.0.0.1", "203.0.113.7, 76.76.21.21")
    assert client_ip_module.client_ip(request) == "203.0.113.7"


def test_shorter_chain_than_expected_falls_back_to_first_entry(configure) -> None:
    configure(hops=2)
    assert client_ip_module.client_ip(_request("10.0.0.1")) == "10.0.0.1"


# --- Web proxy (Vercel) with a shared secret ---------------------------------


def test_web_proxy_with_valid_secret_supplies_client_ip(configure) -> None:
    configure(hops=1, secret=SECRET)
    request = _request("10.0.0.1", "76.76.21.21", x_proxy_secret=SECRET, x_client_ip="203.0.113.7")
    assert client_ip_module.client_ip(request) == "203.0.113.7"


def test_web_proxy_ipv6_is_normalized(configure) -> None:
    configure(hops=1, secret=SECRET)
    request = _request(
        "10.0.0.1", "76.76.21.21", x_proxy_secret=SECRET, x_client_ip="2001:DB8:0:0::1"
    )
    assert client_ip_module.client_ip(request) == "2001:db8::1"


def test_direct_caller_cannot_claim_a_client_ip(configure) -> None:
    """Someone skipping the web and hitting the API host directly gets the
    address Railway saw, whatever headers they send."""
    configure(hops=1, secret=SECRET)
    request = _request(
        "10.0.0.1",
        "1.2.3.4, 198.51.100.9",
        x_proxy_secret="wrong" * 10,
        x_client_ip="1.2.3.4",
    )
    assert client_ip_module.client_ip(request) == "198.51.100.9"


def test_client_ip_header_is_ignored_without_a_configured_secret(configure) -> None:
    configure(hops=1)
    request = _request("10.0.0.1", "198.51.100.9", x_proxy_secret="", x_client_ip="1.2.3.4")
    assert client_ip_module.client_ip(request) == "198.51.100.9"


def test_missing_secret_header_falls_back_to_hops(configure) -> None:
    configure(hops=1, secret=SECRET)
    request = _request("10.0.0.1", "198.51.100.9", x_client_ip="1.2.3.4")
    assert client_ip_module.client_ip(request) == "198.51.100.9"


def test_malformed_client_ip_from_web_proxy_falls_back_to_hops(configure) -> None:
    configure(hops=1, secret=SECRET)
    request = _request(
        "10.0.0.1", "76.76.21.21", x_proxy_secret=SECRET, x_client_ip="not-an-ip, 1.2.3.4"
    )
    assert client_ip_module.client_ip(request) == "76.76.21.21"
