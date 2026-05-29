# PulseAlpha AI — Finance News & Data Scraper Design Spec

**Date:** 2026-05-29  
**Status:** Approved

---

## Goal

Add three new data connectors that give the report LLM rich, current context: official NSE corporate announcements, scraped article summaries from Indian financial media via Google News, and analyst-grade fundamentals + pros/cons from screener.in. All three run concurrently in the ingest pipeline and feed named evidence blocks into the report prompt.

---

## Architecture

```
libs/connectors/connectors/
  nse_announcements.py     ← NSE JSON API (session-cookie handshake)
  news_aggregator.py       ← Google News RSS discovery + httpx article fetch + BS4 parse
  screener.py              ← screener.in company page scraper

services/worker/worker/nodes/ingest.py     ← add 3 new concurrent fetches
services/worker/worker/report/evidence.py  ← add 3 new evidence blocks per ticker

tests/unit/connectors/
  test_nse_announcements.py
  test_news_aggregator.py
  test_screener.py
```

All three connectors extend `BaseConnector` and return `ConnectorResult`. Results stored in `state.alt_data` (announcements, screener) and `state.sentiment` (news). `build_evidence_blocks` picks them up into three new blocks per ticker.

---

## Connector 1 — NSEAnnouncementsConnector

**File:** `libs/connectors/connectors/nse_announcements.py`

**Source:** NSE India JSON API (free, no auth, requires session cookies)

**Approach:**
1. GET `https://www.nseindia.com/` with browser headers → captures session cookies
2. GET `https://www.nseindia.com/api/corporates-announcements?index=equities&symbol={SYMBOL}` using those cookies
3. Symbol: strip `.NS` / `.BO` suffix, uppercase (e.g., `HDFCBANK.NS` → `HDFCBANK`)

**Response parsing:** Each item has `subject`, `an_dt` (date string), `desc` (category), `attchmntFile` (PDF URL). Return last 8 announcements.

**Error handling:** NSE sometimes returns HTML (rate limited or geo-blocked) — detect with `Content-Type` check, return `ConnectorResult` with `FETCH_ERROR` and empty data. Never raises.

**Cache TTL:** 60 minutes, keyed as `pulse:nse_ann:{ticker}`

**Output shape:**
```python
{
  "announcements": [
    {"date": "29-May-2026", "subject": "Board Meeting – Q4 Results", "category": "Results", "url": "https://..."},
    ...
  ]
}
```

---

## Connector 2 — NewsAggregatorConnector

**File:** `libs/connectors/connectors/news_aggregator.py`

**Sources:** Google News RSS → article pages from ET Markets, Moneycontrol, Business Standard, Mint, LiveMint, Hindu Business Line

**Two-phase approach:**

**Phase 1 — Discovery:**
GET `https://news.google.com/rss/search?q={COMPANY_NAME}+stock+India&hl=en-IN&gl=IN&ceid=IN:en`
Parse with `feedparser`. Extract top 6 entries: title, source name, URL, published date.
Filter out duplicates by title similarity. Skip entries older than 7 days.

**Phase 2 — Article fetch:**
For each discovered URL (up to 5), GET with `follow_redirects=True`, `timeout=6s`.
BS4 parse: find article body using a priority selector list:
```
article p, .article-body p, .story-body p, .content-body p, [itemprop="articleBody"] p
```
Take first 3 `<p>` tags, join text, truncate to 500 chars. Skip if no `<p>` found.

**Company name resolution:** `HDFCBANK.NS` → search for `"HDFC Bank"` (uses yfinance `info["shortName"]` cached from fundamentals fetch, falls back to ticker without suffix).

**Concurrency:** All article fetches run in `asyncio.gather` with per-task 6s timeout. Slow articles are skipped, not waited on.

**Cache TTL:** 30 minutes, keyed as `pulse:news:{ticker}`

**Output shape:**
```python
{
  "articles": [
    {
      "title": "HDFC Bank Q4 profit rises 23% to ₹16,512 crore",
      "summary": "HDFC Bank reported a 23% year-on-year rise in net profit...",
      "source": "Economic Times",
      "url": "https://economictimes.com/...",
      "published": "29 May 2026"
    },
    ...
  ]
}
```

---

## Connector 3 — ScreenerConnector

**File:** `libs/connectors/connectors/screener.py`

**Source:** screener.in company page (public, no login required for summary data)

**URL:** `https://www.screener.in/company/{SYMBOL}/`
Symbol: strip `.NS` / `.BO`, uppercase (e.g., `HDFCBANK.NS` → `HDFCBANK`)

**Extracted data:**
- **Pros:** `ul.pros li` → list of green analyst bullets (e.g., "Company is almost debt free")
- **Cons:** `ul.cons li` → list of red analyst bullets (e.g., "Promoter holding has decreased")
- **Key ratios** from `#top-ratios` spans: Stock P/E, Market Cap, Dividend Yield, ROCE, ROE
- **Financial trends** from the summary table: 5-year sales CAGR, 5-year profit CAGR (if present)

**Error handling:** If screener returns a 404 or the symbol isn't found, return empty with `NOT_FOUND`. If HTML structure doesn't match selectors, return partial data with `confidence=0.3`.

**Cache TTL:** 6 hours, keyed as `pulse:screener:{ticker}`

**Output shape:**
```python
{
  "pros": ["Company is almost debt free", "Stock is trading at 1.07 times its book value"],
  "cons": ["Promoter holding is low: 0.00%", "Company has low interest coverage ratio"],
  "ratios": {"pe": "20.3", "market_cap": "₹12,32,456 Cr", "roce": "17.8%", "roe": "16.9%"},
  "cagr": {"sales_5yr": "18%", "profit_5yr": "21%"}
}
```

---

## Ingest Integration

**File:** `services/worker/worker/nodes/ingest.py`

Add to `ingest_all_data` (all three run concurrently, after existing connector gather completes):

```python
ann_conn = NSEAnnouncementsConnector()
news_conn = NewsAggregatorConnector()
scr_conn = ScreenerConnector()

ann_tasks = [_safe_fetch(ann_conn, t, node, state) for t in tickers]
news_tasks = [_safe_fetch(news_conn, t, node, state) for t in tickers]
scr_tasks  = [_safe_fetch(scr_conn, t, node, state) for t in tickers]

scrape_results = await asyncio.gather(*ann_tasks, *news_tasks, *scr_tasks)
```

Store results into `state.alt_data`:
```python
for i, ticker in enumerate(tickers):
    state.alt_data[f"{ticker}_announcements"] = scrape_results[i].data or {}
    state.alt_data[f"{ticker}_screener"]      = scrape_results[n + i].data or {}  # wait — separate gather
# news stored in state.sentiment[ticker]["articles"]
```

Actually wire as three separate gathers to keep index math simple — see plan.

---

## Evidence Blocks

**File:** `services/worker/worker/report/evidence.py`

Add three new blocks per ticker in `build_evidence_blocks`:

### `{ticker}_ANNOUNCEMENTS`
```
Latest NSE corporate announcements:
- 29 May 2026 [Results]: Board Meeting – Q4FY26 results declared
- 15 May 2026 [Dividend]: Interim dividend of ₹19 per share
- 02 Apr 2026 [Disclosure]: Allotment of equity shares under ESOP
```
confidence = 0.9 if data present, else 0.0

### `{ticker}_NEWS`
```
Recent news (from Google News / Indian financial media):

**Economic Times** (29 May): HDFC Bank Q4 profit rises 23% to ₹16,512 crore, beats estimates.
HDFC Bank reported a 23% year-on-year rise in net profit for Q4FY26 to ₹16,512 crore, beating analyst estimates of ₹15,800 crore. Net interest income grew 10% to ₹29,077 crore...

**Moneycontrol** (28 May): FII buying surges in banking sector ahead of RBI policy.
Foreign institutional investors purchased a net ₹4,200 crore of Indian banking stocks on Wednesday...
```
confidence = 0.7 if ≥2 articles, 0.4 if 1 article, 0.0 if none

### `{ticker}_SCREENER`
```
Analyst view (screener.in):

Pros:
• Company is almost debt free
• Stock is trading at 1.07 times its book value
• Company has delivered good profit growth of 21.3% CAGR over last 5 years

Cons:
• Promoter holding is low: 0.00%
• Company has low interest coverage ratio

Key metrics: P/E: 20.3 | ROCE: 17.8% | ROE: 16.9% | Market Cap: ₹12,32,456 Cr
5yr Sales CAGR: 18% | 5yr Profit CAGR: 21%
```
confidence = 0.85 if pros/cons present, 0.4 if ratios only, 0.0 if empty

---

## Caching Strategy

| Connector | TTL | Key pattern |
|---|---|---|
| NSEAnnouncementsConnector | 60 min | `pulse:nse_ann:{ticker}` |
| NewsAggregatorConnector | 30 min | `pulse:news:{ticker}` |
| ScreenerConnector | 6 hours | `pulse:screener:{ticker}` |

Cache layer is optional — connectors work without Redis (skip cache silently).

---

## What Is NOT Included

- Full article text (truncated to 500 chars — avoids copyright issues)
- BSE announcements (NSE covers same data for NSE-listed stocks)
- Paid data sources (screener.in premium, Trendlyne API)
- Sentiment scoring / NLP on headlines (Phase 4 scope)
- NSE bulk/block deal data (separate connector, future scope)
