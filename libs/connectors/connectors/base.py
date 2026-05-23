from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any

from schemas.connectors import ConnectorError, ConnectorResult
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

_RETRYABLE = (ConnectionError, TimeoutError, OSError)


class BaseConnector(ABC):
    def __init__(
        self,
        source_name: str,
        max_retries: int = 3,
        backoff_base: float = 1.0,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.source_name = source_name
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.timeout_seconds = timeout_seconds

    @abstractmethod
    async def _fetch(self, ticker: str) -> dict[str, Any]: ...

    def _confidence(self, data: dict[str, Any]) -> float:
        return 1.0 if data else 0.0

    async def fetch(self, ticker: str) -> ConnectorResult:
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self.max_retries),
                wait=wait_exponential(
                    multiplier=self.backoff_base,
                    min=self.backoff_base,
                    max=30,
                ),
                retry=retry_if_exception_type(_RETRYABLE),
                reraise=False,
            ):
                with attempt:
                    data = await asyncio.wait_for(
                        self._fetch(ticker), timeout=self.timeout_seconds
                    )
                    return ConnectorResult(
                        source=self.source_name,
                        ticker=ticker,
                        data=data,
                        confidence=self._confidence(data),
                    )
        except RetryError as exc:
            logger.warning(
                "Connector %s max retries exceeded for %s: %s",
                self.source_name,
                ticker,
                exc,
            )
            return ConnectorResult(
                source=self.source_name,
                ticker=ticker,
                data={},
                confidence=0.0,
                error=ConnectorError(
                    code="MAX_RETRIES_EXCEEDED",
                    message=str(exc),
                    retryable=False,
                ),
            )
        except Exception as exc:
            logger.error(
                "Connector %s unexpected error for %s: %s",
                self.source_name,
                ticker,
                exc,
            )
            return ConnectorResult(
                source=self.source_name,
                ticker=ticker,
                data={},
                confidence=0.0,
                error=ConnectorError(
                    code="UNEXPECTED_ERROR",
                    message=str(exc),
                    retryable=False,
                ),
            )
        # Unreachable — required to satisfy mypy for the async-for pattern
        return ConnectorResult(  # type: ignore[return-value]
            source=self.source_name,
            ticker=ticker,
            data={},
            confidence=0.0,
        )
