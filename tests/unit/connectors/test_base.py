import pytest
from connectors.base import BaseConnector
from schemas.connectors import ConnectorResult


class OKConnector(BaseConnector):
    async def _fetch(self, ticker: str) -> dict:
        return {"price": 100.0}


class FlakyConnector(BaseConnector):
    def __init__(self, fail_times: int):
        super().__init__(source_name="flaky", max_retries=3, backoff_base=0.01)
        self._fail = fail_times
        self._n = 0

    async def _fetch(self, ticker: str) -> dict:
        self._n += 1
        if self._n <= self._fail:
            raise ConnectionError("transient")
        return {"price": 200.0}


@pytest.mark.asyncio
async def test_connector_returns_result():
    result = await OKConnector(source_name="ok").fetch("RELIANCE.NS")
    assert isinstance(result, ConnectorResult)
    assert result.ok
    assert result.ticker == "RELIANCE.NS"


@pytest.mark.asyncio
async def test_connector_retries_on_transient_failure():
    result = await FlakyConnector(fail_times=2).fetch("TCS.NS")
    assert result.ok
    assert result.data["price"] == 200.0


@pytest.mark.asyncio
async def test_connector_error_after_max_retries():
    result = await FlakyConnector(fail_times=10).fetch("INFY.NS")
    assert not result.ok
    assert result.error.code == "MAX_RETRIES_EXCEEDED"
