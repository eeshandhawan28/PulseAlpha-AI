from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

_NSE_HOME = "https://www.nseindia.com/"
_NSE_ANNUAL_REPORTS_API = (
    "https://www.nseindia.com/api/annual-reports?index=equities&symbol={symbol}"
)
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}
_MAX_PDF_BYTES = 20 * 1024 * 1024  # 20 MB cap


class NSEDocumentFetcher:
    """Async helper that fetches annual report PDFs from NSE's filing API.

    Not a BaseConnector subclass — intended as a focused utility.
    Uses the same two-phase cookie handshake as NSEAnnouncementsConnector:
    first GET the homepage to acquire session cookies, then call the API.
    """

    async def fetch_latest_annual_report_pdf(
        self, symbol: str, timeout: float = 30.0
    ) -> tuple[bytes, str] | None:
        """Return (pdf_bytes, year_label) for the most recent annual report, or None."""
        try:
            async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True) as client:
                # Step 1: Establish session — NSE validates cookies before serving API
                try:
                    await client.get(_NSE_HOME, timeout=10.0)
                except Exception as exc:
                    logger.debug("NSE homepage GET failed (cookies may be missing): %s", exc)

                # Step 2: Fetch the list of PDF URLs
                pdf_list = await self._get_pdf_urls(client, symbol)
                if not pdf_list:
                    return None

                # Step 3: Download the most recent PDF (first after sort desc)
                best = pdf_list[0]
                pdf_bytes = await self._download_pdf(client, best["pdf_url"])
                return pdf_bytes, best["year"]
        except Exception as exc:
            logger.debug("NSEDocumentFetcher failed for %s: %s", symbol, exc)
            return None

    def _parse_pdf_urls(self, api_data: list[dict]) -> list[dict[str, str]]:
        """Parse NSE API JSON into [{pdf_url, year}, ...] sorted by year descending.

        Returns [] on bad / empty input — never raises.
        """
        results: list[dict[str, str]] = []
        if not isinstance(api_data, list):
            return results
        for item in api_data:
            try:
                file_name = item.get("fileName", "")
                year = item.get("year", "")
                if not file_name or not year:
                    continue
                pdf_url = "https://www.nseindia.com" + file_name
                results.append({"pdf_url": pdf_url, "year": year})
            except Exception:
                continue
        results.sort(key=lambda x: x["year"], reverse=True)
        return results

    async def _get_pdf_urls(self, client: httpx.AsyncClient, symbol: str) -> list[dict]:
        """Call NSE annual-reports API, return parsed PDF URL list.

        Raises ValueError on non-JSON response or empty parsed list.
        """
        url = _NSE_ANNUAL_REPORTS_API.format(symbol=symbol.upper())
        r = await client.get(url, timeout=30.0)
        r.raise_for_status()
        content_type = r.headers.get("content-type", "")
        if "application/json" not in content_type:
            raise ValueError("NSE returned non-JSON response (rate-limited or geo-blocked)")
        parsed = self._parse_pdf_urls(r.json())
        if not parsed:
            raise ValueError(f"No annual report PDFs found for symbol: {symbol}")
        return parsed

    async def _download_pdf(self, client: httpx.AsyncClient, url: str) -> bytes:
        """Stream-download a PDF from NSE.

        Raises ValueError if:
        - Content-Type does not contain "pdf"
        - Total size exceeds _MAX_PDF_BYTES (20 MB)
        """
        chunks: list[bytes] = []
        total = 0
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "pdf" not in content_type.lower():
                raise ValueError(f"Expected pdf content-type, got: {content_type!r}")
            async for chunk in response.aiter_bytes(chunk_size=65536):
                total += len(chunk)
                if total > _MAX_PDF_BYTES:
                    raise ValueError(f"PDF exceeds maximum allowed size of {_MAX_PDF_BYTES} bytes")
                chunks.append(chunk)
        return b"".join(chunks)
