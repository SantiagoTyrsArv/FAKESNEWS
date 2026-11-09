"""Case progress over WebSocket.

Requirement: WebSockets. The report page (apps/web/app/reports/[id]) used to
poll GET /submissions/{id} every 2 s; now it opens this socket and the bar
moves as soon as the worker changes phase. Flow:

1. The page asks for a ticket (POST /submissions/{id}/ws-ticket, through the
   /api proxy, authenticated by the httpOnly session cookie). See
   ws_tickets.py for why the cookie can't authenticate the socket itself.
2. It connects to wss://<api>/ws/submissions/{id}?ticket=... directly.
3. Before accepting, this endpoint checks, in order:
   - Origin is one of CORS_ORIGINS. Browsers always send it on a WebSocket
     handshake and pages can't forge it, so this blocks cross-site WebSocket
     hijacking (CSWSH).
   - The ticket exists, and spends it (single use).
   - The ticket was issued for this case, and the case still belongs to the
     ticket's user.
   Any failure closes with 1008 (policy violation) before the handshake.
4. It subscribes to submission:{id} (events.py, published by the worker)
   *before* reading the current status, sends that status, and forwards each
   event until a terminal status, the client leaving, or WS_MAX_SECONDS.
"""

import asyncio
import contextlib
import json
import uuid
from typing import Annotated

import redis.asyncio as redis_asyncio
from fastapi import APIRouter, Depends, Query, WebSocket, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.core.rate_limit import get_redis_dependency
from app.modules.submissions import service, ws_tickets
from app.modules.submissions.events import channel_name

settings = get_settings()
logger = get_logger(__name__)

router = APIRouter(tags=["submissions"])

_POLL_SECONDS = 1.0


@router.websocket("/ws/submissions/{submission_id}")
async def submission_progress(
    websocket: WebSocket,
    submission_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[redis_asyncio.Redis, Depends(get_redis_dependency)],
    ticket: Annotated[str, Query(max_length=200)] = "",
) -> None:
    if websocket.headers.get("origin") not in settings.cors_origins:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    redeemed = await ws_tickets.redeem_ticket(redis_client, ticket)
    if redeemed is None or redeemed[1] != submission_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    user_id = redeemed[0]

    try:
        await service.get_submission(db, submission_id=submission_id, user_id=user_id)
    except service.SubmissionNotFoundError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    pubsub = redis_client.pubsub()
    receiver: asyncio.Task | None = None
    try:
        # Subscribe first, then read: a change landing in between is then
        # queued on the channel instead of lost.
        await pubsub.subscribe(channel_name(submission_id))
        submission = await service.get_submission(db, submission_id=submission_id, user_id=user_id)
        await db.refresh(submission)
        current = {"status": submission.status, "error": submission.error}
        # The socket can stay open for minutes: don't hold a database
        # connection for that long.
        await db.close()

        await websocket.send_json(current)
        if current["status"] in service.TERMINAL_STATUSES:
            await websocket.close(code=status.WS_1000_NORMAL_CLOSURE)
            return

        loop = asyncio.get_running_loop()
        deadline = loop.time() + settings.ws_max_seconds
        # Watches the client side: a receive() returns when it disconnects.
        receiver = asyncio.create_task(websocket.receive())
        while True:
            if receiver.done():
                if receiver.result()["type"] == "websocket.disconnect":
                    return
                receiver = asyncio.create_task(websocket.receive())

            remaining = deadline - loop.time()
            if remaining <= 0:
                await websocket.close(code=status.WS_1000_NORMAL_CLOSURE)
                return

            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=min(_POLL_SECONDS, remaining)
            )
            if message is None:
                continue
            data = message["data"]
            await websocket.send_text(data)
            if json.loads(data).get("status") in service.TERMINAL_STATUSES:
                await websocket.close(code=status.WS_1000_NORMAL_CLOSURE)
                return
    finally:
        if receiver is not None:
            receiver.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await receiver
        with contextlib.suppress(Exception):
            await pubsub.aclose()
