from __future__ import annotations

import asyncio
import logging
from typing import Any

from mftool import Mftool

from connectors.base import BaseConnector

logger = logging.getLogger(__name__)


class NAVConnector(BaseConnector):
    """Fetches mutual fund NAV data via mftool (AMFI source).

    Ticker is the AMFI scheme code (e.g. "118533" for Mirae Large Cap).
    Cache TTL recommendation: 24 hours (NAV updates once per day).
    """

    def __init__(self) -> None:
        super().__init__(
            source_name="mftool_nav",
            max_retries=3,
            timeout_seconds=20.0,
        )
        self._mf = Mftool()

    async def _fetch(self, scheme_code: str) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        quote = await loop.run_in_executor(None, self._mf.get_scheme_quote, scheme_code)
        if not quote:
            raise ValueError(f"No NAV data for scheme {scheme_code}")
        return {
            "scheme_name": quote.get("scheme_name"),
            "nav": float(quote.get("nav", 0)),
            "date": quote.get("date"),
        }
