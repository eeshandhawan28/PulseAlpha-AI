import pytest
from api.main import app
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_health_returns_200():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/health")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_health_body_structure():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/health")
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "environment" in body
