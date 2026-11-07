import asyncio

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
TIMEOUT_SECONDS = 20
RETRY_WAIT_SECONDS = 2
MAX_RETRY_WAIT_SECONDS = 30
RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})
# A project on prepay with no balance: waiting does not help.
QUOTA_STATUSES = frozenset({402})


class LLMError(Exception):
    pass


class LLMQuotaError(LLMError):
    pass


async def _post(model: str, payload: dict) -> httpx.Response:
    headers = {"x-goog-api-key": settings.gemini_api_key}
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        return await client.post(GEMINI_URL.format(model=model), json=payload, headers=headers)


def _retry_wait(response: httpx.Response) -> float:
    try:
        wait = float(response.headers["Retry-After"])
    except (KeyError, ValueError):
        return RETRY_WAIT_SECONDS
    return min(wait, MAX_RETRY_WAIT_SECONDS)


def _parse[T: BaseModel](response: httpx.Response, schema: type[T], step: str, model: str) -> T:
    data = response.json()
    candidates = data.get("candidates") or []
    if not candidates or candidates[0].get("finishReason") != "STOP":
        raise LLMError("Gemini no terminó la respuesta")
    usage = data.get("usageMetadata", {})
    logger.info(
        "llm_usage",
        step=step,
        model=model,
        input_tokens=usage.get("promptTokenCount"),
        output_tokens=usage.get("candidatesTokenCount"),
    )
    parts = candidates[0].get("content", {}).get("parts", [])
    try:
        return schema.model_validate_json("".join(part.get("text", "") for part in parts))
    except ValidationError as exc:
        raise LLMError("La respuesta de Gemini no cumple el esquema") from exc


async def generate_structured[T: BaseModel](
    *, step: str, system: str, user: str, schema: type[T], model: str | None = None
) -> T:
    """One JSON answer that fits `schema`. A temporary failure is retried
    once; an answer outside the schema isn't, since it would cost the quota
    for what most likely is the same result."""
    model_name = model or settings.gemini_model
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseJsonSchema": schema.model_json_schema(),
        },
    }
    error: LLMError = LLMError("Gemini no respondió")
    wait: float = RETRY_WAIT_SECONDS
    for attempt in range(2):
        if attempt:
            await asyncio.sleep(wait)
        try:
            response = await _post(model_name, payload)
        except httpx.HTTPError as exc:
            error = LLMError(f"Fallo de red con Gemini: {type(exc).__name__}")
            continue

        if response.status_code in QUOTA_STATUSES:
            logger.error("llm_quota_exhausted", status=response.status_code)
            raise LLMQuotaError(f"Gemini respondió {response.status_code}")
        if response.status_code in RETRYABLE_STATUSES:
            wait = _retry_wait(response)
            error = (
                LLMQuotaError("Gemini respondió 429")
                if response.status_code == 429
                else LLMError(f"Gemini respondió {response.status_code}")
            )
            continue
        if response.status_code != 200:
            raise LLMError(f"Gemini respondió {response.status_code}")
        return _parse(response, schema, step, model_name)

    if isinstance(error, LLMQuotaError):
        logger.error("llm_quota_exhausted", status=429)
    raise error
