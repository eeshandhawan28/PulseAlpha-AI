import pytest
from unittest.mock import AsyncMock, MagicMock
from connectors.cache import RedisCache


@pytest.fixture
def redis_stub():
    stored: dict = {}
    client = MagicMock()

    async def fake_setex(key, ttl, value):
        stored[key] = value

    async def fake_get(key):
        return stored.get(key)

    client.setex = AsyncMock(side_effect=fake_setex)
    client.get = AsyncMock(side_effect=fake_get)
    return client


@pytest.mark.asyncio
async def test_cache_miss_returns_none(redis_stub):
    cache = RedisCache(client=redis_stub, prefix="test")
    assert await cache.get("RELIANCE.NS") is None


@pytest.mark.asyncio
async def test_cache_roundtrip(redis_stub):
    cache = RedisCache(client=redis_stub, prefix="fund", ttl_seconds=3600)
    await cache.set("RELIANCE.NS", {"pe": 25.0})
    result = await cache.get("RELIANCE.NS")
    assert result == {"pe": 25.0}
