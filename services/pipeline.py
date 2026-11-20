from __future__ import annotations

from config.logging import get_logger
from config.settings import settings
from llm.client import LLMClient, LLMNetworkError
from llm.prompts import build_messages
from services.cache import TTLCache
from services.postprocessor import PostProcessingError, postprocess_output

logger = get_logger(__name__)

FALLBACK_PREFIX = "Сервис автоматической суммаризации временно недоступен."


class TextProcessingPipeline:
    def __init__(self, llm_client: LLMClient, cache: TTLCache) -> None:
        self.llm = llm_client
        self.cache = cache

    async def execute(self, text: str) -> tuple[str, bool, bool]:
        """Возвращает (result_text, is_fallback, from_cache)."""
        cache_key = self.cache.make_key(
            text=text,
            model=settings.llm_model,
            temperature=settings.llm_temperature,
        )
        logger.info(
            "Pipeline start: text_length=%s model=%s temperature=%s",
            len(text),
            settings.llm_model,
            settings.llm_temperature,
        )

        cached_result = self.cache.get(cache_key)
        if cached_result is not None:
            logger.info("Pipeline finished from cache")
            return cached_result, False, True

        messages = build_messages(text)
        logger.info("Prompt constructed (system + user)")

        try:
            raw_response = await self.llm.chat_completion(messages)
            logger.info("Post-processing LLM output")
            final_text = postprocess_output(raw_response)
            self.cache.set(cache_key, final_text)
            logger.info("Pipeline finished successfully (cached for reuse)")
            return final_text, False, False
        except (LLMNetworkError, PostProcessingError) as exc:
            logger.error("External/processing error, using fallback: %s", exc)
            fallback = f"{FALLBACK_PREFIX} Начало исходного текста: {text[:120]}..."
            logger.warning("Pipeline finished with fallback response")
            return fallback, True, False
