from __future__ import annotations

import asyncio

import httpx

from config.logging import get_logger
from config.settings import settings

logger = get_logger(__name__)


class LLMNetworkError(Exception):
    """Ошибка сети, таймаута или внешнего API после всех попыток."""


class LLMClient:
    def __init__(self) -> None:
        self.base_url = settings.llm_base_url.rstrip("/")
        self.api_key = settings.llm_api_key
        self.model = settings.llm_model
        self.temperature = settings.llm_temperature
        self.timeout = settings.llm_timeout
        self.max_retries = settings.llm_max_retries
        self.retry_delay = settings.llm_retry_delay

    async def chat_completion(self, messages: list[dict[str, str]]) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }

        total_attempts = self.max_retries + 1
        last_error: Exception | None = None

        for attempt in range(1, total_attempts + 1):
            logger.info(
                "LLM request attempt %s/%s: model=%s url=%s",
                attempt,
                total_attempts,
                self.model,
                url,
            )
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(url, json=payload, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    if not isinstance(content, str):
                        raise TypeError("LLM content is not a string")
                    logger.info("LLM response received: length=%s", len(content))
                    return content
            except httpx.TimeoutException as exc:
                last_error = exc
                logger.error(
                    "Attempt %s: LLM timeout after %ss",
                    attempt,
                    self.timeout,
                )
            except httpx.HTTPStatusError as exc:
                last_error = exc
                status = exc.response.status_code
                logger.error("Attempt %s: HTTP %s from LLM", attempt, status)
                # Клиентские ошибки (кроме rate-limit) ретраить бессмысленно
                if 400 <= status < 500 and status != 429:
                    break
            except httpx.HTTPError as exc:
                last_error = exc
                logger.error("Attempt %s: Network error: %s", attempt, exc)
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                last_error = exc
                logger.error("Attempt %s: Malformed LLM response: %s", attempt, exc)
                break

            if attempt < total_attempts:
                delay = self.retry_delay * attempt
                logger.warning("Retrying LLM request in %.1fs", delay)
                await asyncio.sleep(delay)

        logger.error("All LLM attempts exhausted")
        raise LLMNetworkError(
            "Failed to get response from LLM after retries"
        ) from last_error
