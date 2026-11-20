import os
import time
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("LLM_API_KEY", "test-key")

from fastapi.testclient import TestClient  # noqa: E402

from llm.client import LLMClient, LLMNetworkError  # noqa: E402
from main import app  # noqa: E402
from services.cache import TTLCache  # noqa: E402
from services.pipeline import TextProcessingPipeline  # noqa: E402

client = TestClient(app)

SAMPLE_TEXT = (
    "Достаточно длинный текст для проверки успешной работы пайплайна и кеша."
)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_validation_error_on_short_text():
    response = client.post("/process", json={"text": "Слишком коротко"})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any(item.get("type") == "string_too_short" for item in detail)


def test_validation_error_on_missing_text():
    response = client.post("/process", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_pipeline_success_and_cache_hit():
    mock_llm = AsyncMock()
    mock_llm.chat_completion.return_value = "```text\nГотовая краткая выжимка.\n```"
    cache = TTLCache(ttl_seconds=60)
    pipeline = TextProcessingPipeline(llm_client=mock_llm, cache=cache)

    res1, fallback1, cached1 = await pipeline.execute(SAMPLE_TEXT)
    assert res1 == "Готовая краткая выжимка."
    assert fallback1 is False
    assert cached1 is False
    assert mock_llm.chat_completion.call_count == 1

    res2, fallback2, cached2 = await pipeline.execute(SAMPLE_TEXT)
    assert res2 == "Готовая краткая выжимка."
    assert fallback2 is False
    assert cached2 is True
    assert mock_llm.chat_completion.call_count == 1


def test_cache_key_depends_on_model_and_temperature():
    key_a = TTLCache.make_key("same", "gpt-4o-mini", 0.3)
    key_b = TTLCache.make_key("same", "gpt-4o-mini", 0.7)
    key_c = TTLCache.make_key("same", "other-model", 0.3)
    key_d = TTLCache.make_key("same", "gpt-4o-mini", 0.3)

    assert key_a == key_d
    assert key_a != key_b
    assert key_a != key_c
    assert len(key_a) == 64


def test_cache_expiry():
    cache = TTLCache(ttl_seconds=1)
    key = cache.make_key("text", "model", 0.3)
    cache.set(key, "value")
    assert cache.get(key) == "value"
    time.sleep(1.1)
    assert cache.get(key) is None


@pytest.mark.asyncio
async def test_pipeline_fallback_on_network_error():
    mock_llm = AsyncMock()
    mock_llm.chat_completion.side_effect = LLMNetworkError("Connection timeout")
    pipeline = TextProcessingPipeline(llm_client=mock_llm, cache=TTLCache())

    res, is_fallback, from_cache = await pipeline.execute(
        "Текст, при обработке которого внешний LLM сервис недоступен."
    )
    assert is_fallback is True
    assert from_cache is False
    assert "временно недоступен" in res


@pytest.mark.asyncio
async def test_llm_client_retries_then_raises():
    with (
        patch("llm.client.settings") as mock_settings,
        patch("llm.client.httpx.AsyncClient") as mock_async_client,
        patch("llm.client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        mock_settings.llm_base_url = "https://example.com/v1"
        mock_settings.llm_api_key = "test"
        mock_settings.llm_model = "gpt-test"
        mock_settings.llm_temperature = 0.3
        mock_settings.llm_timeout = 1.0
        mock_settings.llm_max_retries = 2
        mock_settings.llm_retry_delay = 0.01

        mock_client_instance = AsyncMock()
        mock_client_instance.post.side_effect = Exception("should use HTTPError")
        # httpx.ConnectError is an HTTPError
        import httpx

        mock_client_instance.post.side_effect = httpx.ConnectError("offline")
        mock_async_client.return_value.__aenter__ = AsyncMock(
            return_value=mock_client_instance
        )
        mock_async_client.return_value.__aexit__ = AsyncMock(return_value=None)

        llm = LLMClient()
        with pytest.raises(LLMNetworkError):
            await llm.chat_completion([{"role": "user", "content": "hi"}])

        assert mock_client_instance.post.call_count == 3
        assert mock_sleep.await_count == 2
