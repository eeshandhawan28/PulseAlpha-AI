from __future__ import annotations

import logging
from typing import Any

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_NSE_HOME = "https://www.nseindia.com/"
_NSE_ANNUAL_REPORTS_API = (
    "https://www.nseindia.com/api/annual-reports?index=equities&symbol={symbol}"
)
_SCREENER_DOCUMENTS_URL = "https://www.screener.in/company/{symbol}/documents/"
_BSE_ANNUAL_REPORTS_API = (
    "https://api.bseindia.com/BseIndiaAPI/api/AnnualReport/w?scripcode={bse_code}&type=AR"
)
_NSE_META_API = "https://www.nseindia.com/api/quote-equity?symbol={symbol}"

_NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}
_SCREENER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Accept-Language": "en-IN,en;q=0.9",
    "Referer": "https://www.screener.in/",
}
_BSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.bseindia.com",
    "Referer": "https://www.bseindia.com/",
}
_MAX_PDF_BYTES = 20 * 1024 * 1024  # 20 MB cap


class NSEDocumentFetcher:
    """Async helper that fetches annual report PDFs from NSE's filing API.

    Falls back to screener.in document page and BSE API when NSE fails.
    Not a BaseConnector subclass — intended as a focused utility.
    """

    async def fetch_latest_annual_report_pdf(
        self, symbol: str, timeout: float = 30.0
    ) -> tuple[bytes, str] | None:
        """Return (pdf_bytes, year_label) for the most recent annual report, or None.

        Tries three sources in order:
          1. NSE annual-reports API
          2. screener.in documents page
          3. BSE annual reports API (requires BSE scrip code lookup via NSE meta API)
        """
        # Source 1: NSE
        result = await self._fetch_from_nse(symbol)
        if result is not None:
            return result

        logger.info("NSE annual report failed for %s — trying screener.in fallback", symbol)

        # Source 2: screener.in
        result = await self._fetch_from_screener(symbol)
        if result is not None:
            return result

        logger.info("screener.in fallback failed for %s — trying BSE fallback", symbol)

        # Source 3: BSE
        result = await self._fetch_from_bse(symbol)
        if result is not None:
            return result

        logger.warning("All PDF sources exhausted for %s", symbol)
        return None

    # ── Source 1: NSE ──────────────────────────────────────────────────────

    async def _fetch_from_nse(self, symbol: str) -> tuple[bytes, str] | None:
        try:
            async with httpx.AsyncClient(
                headers=_NSE_HEADERS, follow_redirects=True
            ) as client:
                try:
                    await client.get(_NSE_HOME, timeout=10.0)
                except Exception as exc:
                    logger.debug("NSE homepage GET failed: %s", exc)

                pdf_list = await self._get_nse_pdf_urls(client, symbol)
                if not pdf_list:
                    return None

                best = pdf_list[0]
                pdf_bytes = await self._download_pdf(client, best["pdf_url"])
                logger.info("NSE annual report downloaded for %s (%s)", symbol, best["year"])
                return pdf_bytes, best["year"]
        except Exception as exc:
            logger.debug("NSE source failed for %s: %s", symbol, exc)
            return None

    def _parse_nse_pdf_urls(self, api_data: Any) -> list[dict[str, str]]:
        """Parse NSE API JSON into [{pdf_url, year}, ...] sorted by year descending.

        Handles both bare-list and dict-wrapped responses, and multiple
        field name variants observed across NSE API versions.
        """
        # Unwrap dict responses: {"data": [...]} or {"annualReports": [...]} etc.
        if isinstance(api_data, dict):
            for key in ("data", "annualReports", "reports", "items"):
                if key in api_data and isinstance(api_data[key], list):
                    api_data = api_data[key]
                    break
            else:
                # Log the keys so we can adapt if the shape changes again
                logger.debug(
                    "NSE annual-reports API returned dict with unexpected keys: %s",
                    list(api_data.keys())[:10],
                )
                return []

        if not isinstance(api_data, list):
            logger.debug(
                "NSE annual-reports API returned unexpected type: %s", type(api_data).__name__
            )
            return []

        results: list[dict[str, str]] = []
        for item in api_data:
            if not isinstance(item, dict):
                continue
            try:
                # Field name variants seen in different NSE API versions
                file_name = (
                    item.get("fileName")
                    or item.get("fileUrl")
                    or item.get("url")
                    or item.get("reportUrl")
                    or item.get("pdfUrl")
                    or ""
                )
                # Current NSE API uses fromYr + toYr (e.g. "2025", "2026")
                # Legacy versions used a single "year" field (e.g. "2024-25")
                from_yr = item.get("fromYr") or item.get("fromYear") or ""
                to_yr = item.get("toYr") or item.get("toYear") or ""
                if from_yr and to_yr:
                    # Normalise to "YYYY-YY" format, e.g. "2025-26"
                    year = f"{from_yr}-{str(to_yr)[-2:]}"
                else:
                    year = (
                        item.get("year")
                        or item.get("yearFrom")
                        or item.get("yearLabel")
                        or item.get("name")
                        or from_yr
                        or ""
                    )
                if not file_name or not year:
                    continue
                # Handle absolute URLs (external hosts) vs NSE-relative paths
                if str(file_name).startswith("http"):
                    pdf_url = str(file_name)
                else:
                    pdf_url = "https://www.nseindia.com" + str(file_name)
                results.append({"pdf_url": pdf_url, "year": str(year)})
            except Exception:
                continue

        if not results and api_data:
            # Log a sample item so we can diagnose new shapes
            logger.debug(
                "NSE _parse_pdf_urls: parsed 0 items from %d; sample keys=%s",
                len(api_data),
                list(api_data[0].keys())[:10] if isinstance(api_data[0], dict) else "?",
            )

        results.sort(key=lambda x: x["year"], reverse=True)
        return results

    async def _get_nse_pdf_urls(
        self, client: httpx.AsyncClient, symbol: str
    ) -> list[dict[str, str]]:
        url = _NSE_ANNUAL_REPORTS_API.format(symbol=symbol.upper())
        r = await client.get(url, timeout=30.0)
        r.raise_for_status()
        content_type = r.headers.get("content-type", "")
        if "application/json" not in content_type:
            raise ValueError(
                f"NSE returned non-JSON response (content-type={content_type!r}); "
                "likely rate-limited or geo-blocked"
            )
        raw = r.json()
        parsed = self._parse_nse_pdf_urls(raw)
        if not parsed:
            raise ValueError(f"No annual report PDFs parsed for symbol: {symbol}")
        return parsed

    # ── Source 2: screener.in documents page ──────────────────────────────

    async def _fetch_from_screener(self, symbol: str) -> tuple[bytes, str] | None:
        """Scrape screener.in/company/{symbol}/documents/ for annual report PDF links."""
        try:
            async with httpx.AsyncClient(
                headers=_SCREENER_HEADERS, follow_redirects=True
            ) as client:
                url = _SCREENER_DOCUMENTS_URL.format(symbol=symbol.upper())
                r = await client.get(url, timeout=20.0)
                if r.status_code in (404, 403):
                    logger.debug("screener.in documents page %s for %s", r.status_code, symbol)
                    return None
                r.raise_for_status()

                pdf_links = self._parse_screener_pdf_links(r.text)
                if not pdf_links:
                    logger.debug("No PDF links found on screener.in documents page for %s", symbol)
                    return None

                best = pdf_links[0]
                pdf_bytes = await self._download_pdf(client, best["pdf_url"])
                logger.info(
                    "screener.in annual report downloaded for %s (%s)", symbol, best["year"]
                )
                return pdf_bytes, best["year"]
        except Exception as exc:
            logger.debug("screener.in source failed for %s: %s", symbol, exc)
            return None

    def _parse_screener_pdf_links(self, html: str) -> list[dict[str, str]]:
        """Extract annual report PDF links from screener.in documents page."""
        soup = BeautifulSoup(html, "html.parser")
        results: list[dict[str, str]] = []

        # screener.in renders annual reports in a list with links containing "Annual Report"
        for link in soup.find_all("a", href=True):
            href = str(link.get("href", ""))
            text = link.get_text(strip=True)
            if not href.lower().endswith(".pdf") and "pdf" not in href.lower():
                continue
            if "annual" not in text.lower() and "annual" not in href.lower():
                continue

            # Extract year from link text or URL (e.g. "2023-24", "FY24", "2024")
            year = self._extract_year_from_text(text) or self._extract_year_from_text(href)
            if not year:
                continue

            pdf_url = href if href.startswith("http") else f"https://www.screener.in{href}"
            results.append({"pdf_url": pdf_url, "year": year})

        results.sort(key=lambda x: x["year"], reverse=True)
        return results

    def _extract_year_from_text(self, text: str) -> str:
        """Extract a fiscal year label from a string, e.g. '2023-24' or 'FY2024'."""
        import re

        # Match "2023-24" style
        m = re.search(r"(20\d{2}[-–]\d{2,4})", text)
        if m:
            return m.group(1)
        # Match standalone 4-digit year
        m = re.search(r"(20\d{2})", text)
        if m:
            return m.group(1)
        return ""

    # ── Source 3: BSE ─────────────────────────────────────────────────────

    async def _fetch_from_bse(self, symbol: str) -> tuple[bytes, str] | None:
        """Try BSE annual reports API after looking up the BSE scrip code via NSE meta API."""
        bse_code = await self._lookup_bse_code(symbol)
        if not bse_code:
            logger.debug("Could not resolve BSE scrip code for %s", symbol)
            return None
        try:
            async with httpx.AsyncClient(
                headers=_BSE_HEADERS, follow_redirects=True
            ) as client:
                url = _BSE_ANNUAL_REPORTS_API.format(bse_code=bse_code)
                r = await client.get(url, timeout=20.0)
                r.raise_for_status()
                pdf_list = self._parse_bse_pdf_urls(r.json())
                if not pdf_list:
                    logger.debug("BSE returned no annual report PDFs for %s (%s)", symbol, bse_code)
                    return None

                best = pdf_list[0]
                pdf_bytes = await self._download_pdf(client, best["pdf_url"])
                logger.info("BSE annual report downloaded for %s (%s)", symbol, best["year"])
                return pdf_bytes, best["year"]
        except Exception as exc:
            logger.debug("BSE source failed for %s: %s", symbol, exc)
            return None

    async def _lookup_bse_code(self, symbol: str) -> str | None:
        """Resolve BSE scrip code for a given NSE symbol using NSE's quote-equity API."""
        try:
            async with httpx.AsyncClient(
                headers=_NSE_HEADERS, follow_redirects=True
            ) as client:
                try:
                    await client.get(_NSE_HOME, timeout=10.0)
                except Exception:
                    pass
                url = _NSE_META_API.format(symbol=symbol.upper())
                r = await client.get(url, timeout=15.0)
                if r.status_code != 200:
                    return None
                data = r.json()
                # NSE quote-equity returns {"info": {"isin": ..., ...}, "metadata": {...}}
                # The otherExchange code lives in different locations across API versions
                info = data.get("info", {}) if isinstance(data, dict) else {}
                for key in ("otherExchangeCode", "bseScripCode", "bseid", "scripcode"):
                    val = info.get(key)
                    if val:
                        return str(val)
                # Some responses nest it under metadata
                meta = data.get("metadata", {}) if isinstance(data, dict) else {}
                for key in ("otherExchangeCode", "bseScripCode"):
                    val = meta.get(key)
                    if val:
                        return str(val)
                return None
        except Exception as exc:
            logger.debug("BSE code lookup failed for %s: %s", symbol, exc)
            return None

    def _parse_bse_pdf_urls(self, api_data: Any) -> list[dict[str, str]]:
        """Parse BSE annual reports API response into [{pdf_url, year}, ...]."""
        if isinstance(api_data, dict):
            for key in ("Table", "data", "reports"):
                if key in api_data and isinstance(api_data[key], list):
                    api_data = api_data[key]
                    break

        if not isinstance(api_data, list):
            return []

        results: list[dict[str, str]] = []
        for item in api_data:
            if not isinstance(item, dict):
                continue
            try:
                # BSE API fields: ATTACHMENT, REPORT_DT, REPORT_NO
                pdf_url = (
                    item.get("ATTACHMENT")
                    or item.get("attachment")
                    or item.get("url")
                    or ""
                )
                year = (
                    item.get("REPORT_DT")
                    or item.get("year")
                    or item.get("YEAR")
                    or ""
                )
                if not pdf_url or not year:
                    continue
                if not str(pdf_url).startswith("http"):
                    pdf_url = "https://www.bseindia.com" + str(pdf_url)
                # Normalise year to a sortable string
                year_str = self._extract_year_from_text(str(year)) or str(year)
                results.append({"pdf_url": str(pdf_url), "year": year_str})
            except Exception:
                continue

        results.sort(key=lambda x: x["year"], reverse=True)
        return results

    # ── Shared download ───────────────────────────────────────────────────

    async def _download_pdf(self, client: httpx.AsyncClient, url: str) -> bytes:
        """Stream-download a PDF.

        Relaxed content-type check: accepts application/octet-stream and
        empty content-type in addition to application/pdf, since some hosts
        serve PDFs with a generic MIME type.
        """
        chunks: list[bytes] = []
        total = 0
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            # Reject obvious HTML error pages; accept pdf, octet-stream, or no type
            if "text/html" in content_type or "text/plain" in content_type:
                raise ValueError(
                    f"Expected PDF, got HTML/text response (content-type={content_type!r})"
                )
            async for chunk in response.aiter_bytes(chunk_size=65536):
                total += len(chunk)
                if total > _MAX_PDF_BYTES:
                    raise ValueError(
                        f"PDF exceeds maximum allowed size of {_MAX_PDF_BYTES} bytes"
                    )
                chunks.append(chunk)
        if not chunks:
            raise ValueError("Empty response when downloading PDF")
        return b"".join(chunks)
