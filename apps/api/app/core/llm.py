from functools import lru_cache

import anthropic

from app.core.config import get_settings

settings = get_settings()


@lru_cache
def get_anthropic_client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
