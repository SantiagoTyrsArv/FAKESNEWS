"""Single-use tickets for the case progress WebSocket.

Requirement: WebSockets. The session cookie (httpOnly) belongs to the web's
domain, fakesnews.vercel.app, and Vercel's /api proxy cannot carry a
WebSocket, so the browser opens the socket straight against the API, where
the cookie is never sent. Instead it first asks for a ticket through the
proxy, a request the cookie does authenticate, and presents the ticket when
connecting. A ticket lives 30 seconds and is spent on first use (GETDEL).
"""

import secrets
import uuid

import redis.asyncio as redis

TICKET_TTL_SECONDS = 30
_MAX_TICKET_LENGTH = 100


def _key(ticket: str) -> str:
    return f"ws-ticket:{ticket}"


async def issue_ticket(client: redis.Redis, *, user_id: uuid.UUID, submission_id: uuid.UUID) -> str:
    ticket = secrets.token_urlsafe(32)
    await client.set(_key(ticket), f"{user_id}:{submission_id}", ex=TICKET_TTL_SECONDS)
    return ticket


async def redeem_ticket(client: redis.Redis, ticket: str) -> tuple[uuid.UUID, uuid.UUID] | None:
    if not ticket or len(ticket) > _MAX_TICKET_LENGTH:
        return None
    value = await client.getdel(_key(ticket))
    if not value:
        return None
    try:
        user_id, submission_id = value.split(":", 1)
        return uuid.UUID(user_id), uuid.UUID(submission_id)
    except ValueError:
        return None
