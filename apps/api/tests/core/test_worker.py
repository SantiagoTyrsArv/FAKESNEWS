import pytest

from app.workers.tasks import ping


@pytest.mark.asyncio
async def test_ping_task_returns_pong() -> None:
    result = await ping({})

    assert result == "pong"
