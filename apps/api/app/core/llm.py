from functools import lru_cache
from typing import Any

import anthropic

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

# The model thinks adaptively by default and those thinking tokens count
# against max_tokens, so a tight cap truncates the answer before its JSON.
# Kept under the SDK's limit for non-streaming requests (~21k tokens).
MAX_OUTPUT_TOKENS = 16000

# Answers that ended early: there is no complete answer to read, and retrying
# the same request would most likely end the same way.
UNFINISHED_STOP_REASONS = ("max_tokens", "refusal")


@lru_cache
def get_anthropic_client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


def log_usage(step: str, response: Any) -> None:
    """Record what one call cost, so spend can be traced per case."""
    usage = response.usage
    server_tools = usage.server_tool_use
    logger.info(
        "llm_usage",
        step=step,
        stop_reason=response.stop_reason,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        web_search_requests=server_tools.web_search_requests if server_tools else 0,
    )
