FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# uv.lock is written by a recent uv (lock revision 3); older uv releases
# can't honor it with --frozen.
COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /uvx /usr/local/bin/

WORKDIR /app

# UV_NO_DEV keeps the dev group (pytest, ruff, ...) out of the image, and it
# also applies to every later "uv run" (CMD, Railway's pre-deploy and worker
# commands, docker-compose), so none of them installs it at start-up.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1 \
    PYTHONUNBUFFERED=1

# Dependencies only, and only from prebuilt wheels: nothing runs a package's
# setup scripts while installing. The app itself isn't installed as a package;
# it runs from /app (PYTHONPATH), and UV_NO_SYNC stops every later "uv run"
# from re-syncing (or building) the environment at start-up.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-build

# Only what the service runs: no tests, local .env or caches in the image.
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
ENV PYTHONPATH=/app     UV_NO_SYNC=1

# Unprivileged runtime user. It needs a home: the worker caches the Whisper
# model under ~/.cache when it processes a video.
RUN useradd --create-home --uid 10001 app && chown -R app:app /app
USER app

EXPOSE 8000

# sh -c so $PORT (injected by Railway and similar platforms) expands; exec so
# uvicorn replaces the shell and receives SIGTERM for a graceful shutdown.
# Proxy headers are resolved by the app (TRUSTED_PROXY_HOPS, see
# app/core/client_ip.py), not by uvicorn, whose "trust *" mode takes the
# client-controlled leftmost X-Forwarded-For entry.
CMD ["sh", "-c", "exec uv run --frozen uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-proxy-headers"]
