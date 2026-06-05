from __future__ import annotations

import logging
from typing import Any

import httpx
from bs4 import BeautifulSoup
from schemas.connectors import ConnectorError, ConnectorResult

from connectors.base import BaseConnector

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.screener.in/company/{symbol}/"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Accept-Language": "en-IN,en;q=0.9",
    "Referer": "https://www.screener.in/",
}


class ScreenerConnector(BaseConnector):
    """Scrapes screener.in for analyst pros/cons and key financial ratios.

    Public company pages require no login for the summary section.
    Cache TTL recommendation: 6 hours (fundamentals change infrequently).
    """

    def __init__(self) -> None:
        super().__init__(
            source_name="screener_in",
            max_retries=2,
            timeout_seconds=20.0,
        )

    async def _fetch(self, ticker: str) -> dict[str, Any]:
        symbol = ticker.replace(".NS", "").replace(".BO", "").upper()
        url = _BASE_URL.format(symbol=symbol)

        async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True) as client:
            r = await client.get(url, timeout=self.timeout_seconds)
            if r.status_code == 404:
                raise ValueError(f"Company {symbol} not found on screener.in")
            r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")
        return self._parse(soup)

    def _parse(self, soup: BeautifulSoup) -> dict[str, Any]:
        pros = [li.get_text(strip=True) for li in soup.select("ul.pros li")]
        cons = [li.get_text(strip=True) for li in soup.select("ul.cons li")]

        # Key ratios from the #top-ratios list
        ratios: dict[str, str] = {}
        for item in soup.select("#top-ratios li"):
            name_el = item.select_one(".name")
            value_el = item.select_one(".number") or item.select_one(".value")
            if name_el and value_el:
                key = (
                    name_el.get_text(strip=True)
                    .lower()
                    .replace(" ", "_")
                    .replace("/", "_")
                    .replace("%", "pct")
                )
                ratios[key] = value_el.get_text(strip=True)

        # 5-year CAGR from compounded growth section
        cagr: dict[str, str] = {}
        for section in soup.select("section"):
            heading = section.find(["h2", "h3"])
            if heading and "compounded" in heading.get_text(strip=True).lower():
                for row in section.select("table tbody tr"):
                    cols = row.select("td")
                    if len(cols) >= 3:
                        label = cols[0].get_text(strip=True).lower()
                        val_5yr = cols[2].get_text(strip=True)
                        if "sales" in label or "revenue" in label:
                            cagr["sales_5yr"] = val_5yr
                        elif "profit" in label or "net" in label:
                            cagr["profit_5yr"] = val_5yr

        if not pros and not cons and not ratios:
            raise ValueError(
                "No pros/cons or ratios found — page structure may have changed"
            )

        return {
            "pros": pros[:5],
            "cons": cons[:5],
            "ratios": ratios,
            "cagr": cagr,
        }

    def _confidence(self, data: dict[str, Any]) -> float:
        has_prose = bool(data.get("pros") or data.get("cons"))
        has_ratios = bool(data.get("ratios"))
        if has_prose and has_ratios:
            return 0.85
        if has_prose or has_ratios:
            return 0.4
        return 0.0

    async def fetch(self, ticker: str) -> ConnectorResult:
        try:
            data = await self._fetch(ticker)
            return ConnectorResult(
                source=self.source_name,
                ticker=ticker,
                data=data,
                confidence=self._confidence(data),
            )
        except ValueError as exc:
            code = "NOT_FOUND" if "not found" in str(exc).lower() else "PARSE_ERROR"
            return ConnectorResult(
                source=self.source_name,
                ticker=ticker,
                data={},
                confidence=0.0,
                error=ConnectorError(code=code, message=str(exc)),
            )
        except Exception as exc:
            return ConnectorResult(
                source=self.source_name,
                ticker=ticker,
                data={},
                confidence=0.0,
                error=ConnectorError(code="FETCH_ERROR", message=str(exc)),
            )
