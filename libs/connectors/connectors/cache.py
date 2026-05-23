from __future__ import annotations
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class RedisCache:
    """JSON-serializing Redis cache with configurable TTL and key prefix."""

    def __init__(self, client: Any, prefix: str, ttl_seconds: int = 900) -> None:
        self._client = client
        self._prefix = prefix
        self._ttl = ttl_seconds

    def _key(self, ticker: str) -> str:
        return f"pulse:{self._prefix}:{ticker}"

    async def get(self, ticker: str) -> dict[str, Any] | None:
        raw = await self._client.get(self._key(ticker))
        if raw is None:
            return None
        try:
            return json.loads(raw)  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            logger.warning("Cache decode error for key %s", self._key(ticker))
            return None

    async def set(self, ticker: str, data: dict[str, Any]) -> None:
        await self._client.setex(self._key(ticker), self._ttl, json.dumps(data))
