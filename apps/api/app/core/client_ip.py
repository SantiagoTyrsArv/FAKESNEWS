"""Resolve the real client IP behind a known number of reverse proxies.

Login rate limiting and lockout are keyed on this IP, so it must not be
spoofable. X-Forwarded-For is a list each proxy *appends* to; everything
left of what our own proxies added is whatever the client chose to send.
Trusting the leftmost entry (what `uvicorn --forwarded-allow-ips "*"` does)
lets anyone pick a fresh IP per request and walk past the IP rate limit.

Instead we count from the right: with N trusted proxies in front of the app,
the chain [*X-Forwarded-For, socket peer] ends in N proxy hops, and the
entry just before them is the address the outermost trusted proxy saw.

    Railway only        (N=1): client -> Railway edge -> app
    Vercel + Railway    (N=2): client -> Vercel -> Railway edge -> app
"""

from fastapi import Request

from app.core.config import get_settings


def client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    hops = get_settings().trusted_proxy_hops
    if hops <= 0:
        return peer

    forwarded = request.headers.get("x-forwarded-for", "")
    chain = [part.strip() for part in forwarded.split(",") if part.strip()]
    chain.append(peer)

    index = len(chain) - 1 - hops
    return chain[index] if index >= 0 else chain[0]
