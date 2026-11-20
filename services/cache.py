from __future__ import annotations

import hashlib
import time
from typing import Optional

from config.logging import get_logger
from config.settings import settings

logger = get_logger(__name__)


class TTLCache:
    def __init__(self, ttl_seconds: int | None = None) -> None:
        self.ttl = settings.cache_ttl_seconds if ttl_seconds is None else ttl_seconds
        self._storage: dict[str, tuple[str, float]] = {}

    @staticmethod
    def make_key(text: str, model: str, temperature: float) -> str:
        """Ключ = SHA-256(model + temperature + text)."""
        raw_key = f"{model}:{temperature}:{text}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[str]:
        short = key[:12]
        entry = self._storage.get(key)
        if entry is None:
            logger.info("Cache MISS key=%s", short)
            return None

        value, expires_at = entry
        if time.time() > expires_at:
            del self._storage[key]
            logger.info("Cache EXPIRED (MISS) key=%s ttl=%ss", short, self.ttl)
            return None

        logger.info("Cache HIT key=%s", short)
        return value

    def set(self, key: str, value: str) -> None:
        self._storage[key] = (value, time.time() + self.ttl)
        logger.info("Cache SET key=%s ttl=%ss", key[:12], self.ttl)

    def clear(self) -> None:
        self._storage.clear()
