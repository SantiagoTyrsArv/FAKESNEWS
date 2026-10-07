"""Resolve the real client IP behind our reverse proxies.

Login rate limiting and lockout are keyed on this IP, so it must not be
spoofable. X-Forwarded-For is a list each proxy *appends* to; everything
left of what our own proxies added is whatever the client chose to send.
Trusting the leftmost entry (what `uvicorn --forwarded-allow-ips "*"` does)
lets anyone pick a fresh IP per request and walk past the IP rate limit.

Two sources, in order:

1. The web proxy (Vercel rewriting /api to this app). It sends the client IP
   it saw in X-Client-IP, together with API_PROXY_SECRET in X-Proxy-Secret.
   The API host is public, so the IP is only believed with the secret;
   counting a Vercel hop instead would let anyone calling the API directly
   pass for that hop and choose their own IP.

2. Otherwise, count TRUSTED_PROXY_HOPS platform proxies from the right: the
   chain [*X-Forwarded-For, socket peer] ends in those hops, and the entry
   just before them is the address the outermost one saw.

       Railway only (hops=1): client -> Railway edge -> app
"""

import hmac
import ipaddress

from fastapi import Request

from app.core.config import get_settings

PROXY_SECRET_HEADER = "x-proxy-secret"
CLIENT_IP_HEADER = "x-client-ip"


def client_ip(request: Request) -> str:
    settings = get_settings()
    from_web_proxy = _ip_from_web_proxy(request, settings.api_proxy_secret)
    if from_web_proxy is not None:
        return from_web_proxy

    peer = request.client.host if request.client else "unknown"
    hops = settings.trusted_proxy_hops
    if hops <= 0:
        return peer

    forwarded = request.headers.get("x-forwarded-for", "")
    chain = [part.strip() for part in forwarded.split(",") if part.strip()]
    chain.append(peer)

    index = len(chain) - 1 - hops
    return chain[index] if index >= 0 else chain[0]


def _ip_from_web_proxy(request: Request, secret: str | None) -> str | None:
    if secret is None:
        return None

    presented = request.headers.get(PROXY_SECRET_HEADER)
    if presented is None or not hmac.compare_digest(presented.encode(), secret.encode()):
        return None

    try:
        return str(ipaddress.ip_address(request.headers.get(CLIENT_IP_HEADER, "").strip()))
    except ValueError:
        return None
