from __future__ import annotations

import asyncio
import logging
import re
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from schemas.connectors import ConnectorError, ConnectorResult

from connectors.base import BaseConnector
from connectors.nse_document_fetcher import NSEDocumentFetcher

logger = logging.getLogger(__name__)

# Optional OpenTelemetry tracing — degrades gracefully if not installed.
try:
    from opentelemetry import trace as _otel_trace

    _tracer: Any = _otel_trace.get_tracer(__name__)
except ImportError:
    _tracer = None


def _span(name: str, **attrs: Any) -> Any:
    """Return an active OTEL span context manager, or nullcontext if OTEL unavailable."""
    if _tracer is None:
        return nullcontext()
    span = _tracer.start_as_current_span(name)
    # We can't set attributes until the span is entered, so wrap it
    return span


_VECTORSTORE_ROOT = Path(__file__).resolve().parents[4] / "data" / "vectorstore"
_EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# all-MiniLM-L6-v2 has a 256-token max input.  At ~4 chars/token that is
# ~1 000 chars of content.  We use 800 chars to stay comfortably within the
# limit so the FULL chunk influences the embedding (no silent truncation).
_CHUNK_CHARS = 800
_OVERLAP_CHARS = 150  # ~38 tokens — carries sentences across chunk boundaries
_TOP_K = 6  # retrieve extra; distance-filter brings it down
_MIN_CHUNKS_RETURNED = 1  # return at least this many even if score is weak
_DISTANCE_THRESHOLD = 1.2  # L2 distance; filters cosine_sim < 0.28 (noise)
_TTL_DAYS = 7
_MAX_EMBED_CHARS = 900  # hard cap before model truncation (safety margin)

# ── Section header patterns found in NSE annual reports ───────────────────
_SECTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)(management\s+discussion|md&a|management\s+&\s+analysis)"), "MD&A"),
    (
        re.compile(r"(?i)(financial\s+highlights|key\s+financial|financial\s+performance)"),
        "Financial Highlights",
    ),
    (re.compile(r"(?i)(risk\s+factors|risks\s+and\s+concerns|risk\s+management)"), "Risk Factors"),
    (
        re.compile(r"(?i)(chairman.{0,20}(letter|statement|message)|letter\s+to\s+shareholders)"),
        "Chairman's Statement",
    ),
    (re.compile(r"(?i)(directors.{0,10}report|board.{0,10}report)"), "Directors' Report"),
    (
        re.compile(r"(?i)(segment\s+(performance|results|review)|business\s+segment)"),
        "Segment Performance",
    ),
    (re.compile(r"(?i)(consolidated\s+(financial|balance|profit))"), "Consolidated Financials"),
    (re.compile(r"(?i)(standalone\s+(financial|balance|profit))"), "Standalone Financials"),
    (re.compile(r"(?i)(notes?\s+to\s+(the\s+)?(financial|accounts))"), "Notes to Financials"),
    (re.compile(r"(?i)(corporate\s+governance|board\s+of\s+directors)"), "Corporate Governance"),
    (re.compile(r"(?i)(outlook|guidance|future\s+prospects|year\s+ahead)"), "Outlook"),
    (re.compile(r"(?i)(auditor.{0,10}report|independent\s+auditor)"), "Auditors' Report"),
]

# Financial keyword expansions for query augmentation.
# Covers common financial concepts that users phrase differently from
# how annual reports write them (e.g. "capex" vs "capital expenditure").
_FINANCIAL_KEYWORDS = (
    "revenue EBITDA operating profit margin PAT net income EPS earnings "
    "segment performance management commentary guidance outlook "
    "risks annual report growth CAGR FCF free cash flow "
    "capital expenditure capex investment "
    "ROE ROCE return equity capital employed debt leverage "
    "subscribers ARPU users customers retail stores "
    "ESG environment sustainability CSR governance "
    "dividend buyback shareholder"
)


def _build_section_map(text: str) -> list[tuple[int, str]]:
    """Scan full document text and return a list of (char_offset, section_label)
    sorted by position.  Only standalone header lines are considered — a line
    must be entirely a section-like phrase (≤80 chars, no sentence punctuation)
    to avoid matching mid-paragraph phrases like 'The Board of Directors…'.
    """
    section_map: list[tuple[int, str]] = [(0, "General")]
    for line_match in re.finditer(r"^[ \t]*(.{3,80})[ \t]*$", text, re.MULTILINE):
        line = line_match.group(1).strip()
        # Skip lines that are clearly body text (contain sentence punctuation or
        # are very short/long)
        if any(c in line for c in (".", ",", ";", ":", "₹", "%", "(", ")")):
            continue
        for pattern, label in _SECTION_PATTERNS:
            if pattern.search(line):
                section_map.append((line_match.start(), label))
                break
    section_map.sort(key=lambda x: x[0])
    return section_map


def _section_at_offset(section_map: list[tuple[int, str]], offset: int) -> str:
    """Return the section label active at the given character offset."""
    label = "General"
    for pos, sec in section_map:
        if pos <= offset:
            label = sec
        else:
            break
    return label


class DocumentRAGConnector(BaseConnector):
    """RAG connector for NSE annual report PDFs.

    Lifecycle per fetch(ticker):
      1. Check ChromaDB collection TTL — if fresh (<7 days), skip to step 4.
      2. Download latest annual report PDF from NSE.
      3. Extract text → detect sections → chunk → embed → persist to ChromaDB.
      4. Embed user_query (always augmented with financial keywords) → retrieve
         top-K chunks, distance-filter noise, return best matches.
      5. Return ConnectorResult with chunks labelled by section and year.

    Degrades silently: any failure returns empty ConnectorResult with error logged.
    """

    def __init__(
        self,
        user_query: str,
        vectorstore_root: Path = _VECTORSTORE_ROOT,
    ) -> None:
        super().__init__(
            source_name="nse_annual_report_rag",
            max_retries=1,
            timeout_seconds=120.0,
        )
        self._user_query = user_query
        self._vectorstore_root = vectorstore_root
        self._fetcher = NSEDocumentFetcher()
        self._embed_model: Any = None  # lazy-loaded SentenceTransformer

    # ── Embedding model ────────────────────────────────────────────────────

    def _get_embed_model(self) -> Any:
        """Lazy-load sentence-transformers model (CPU, ~80 MB on first use)."""
        if self._embed_model is None:
            from sentence_transformers import SentenceTransformer  # noqa: PLC0415

            self._embed_model = SentenceTransformer(_EMBED_MODEL_NAME, device="cpu")
        return self._embed_model

    def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed texts.  Truncates each to _MAX_EMBED_CHARS before encoding."""
        model = self._get_embed_model()
        truncated = [t[:_MAX_EMBED_CHARS] for t in texts]
        embeddings = model.encode(
            truncated,
            batch_size=32,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embeddings.tolist()  # type: ignore[no-any-return]

    # ── ChromaDB helpers ───────────────────────────────────────────────────

    def _collection_name(self, symbol: str, year: str) -> str:
        safe_year = year.replace("-", "_")
        return f"rag_{symbol}_{safe_year}"

    def _is_collection_fresh(self, collection: Any) -> bool:
        meta = collection.metadata or {}
        indexed_at_str = meta.get("indexed_at_utc")
        if not indexed_at_str:
            return False
        try:
            indexed_at = datetime.fromisoformat(indexed_at_str)
            if indexed_at.tzinfo is None:
                indexed_at = indexed_at.replace(tzinfo=UTC)
            return datetime.now(UTC) - indexed_at < timedelta(days=_TTL_DAYS)
        except (ValueError, TypeError):
            return False

    def _find_fresh_collection(
        self, chroma_client: Any, symbol: str
    ) -> tuple[str, str, str] | tuple[None, None, None]:
        try:
            prefix = f"rag_{symbol}_"
            for item in chroma_client.list_collections():
                name = item.name if hasattr(item, "name") else str(item)
                if not name.startswith(prefix):
                    continue
                try:
                    collection = chroma_client.get_collection(name=name)
                except Exception:
                    continue
                if self._is_collection_fresh(collection):
                    year_part = name[len(prefix) :]
                    year = year_part.replace("_", "-", 1)
                    pdf_url: str = (collection.metadata or {}).get("pdf_url", "")
                    return year, name, pdf_url
        except Exception as exc:
            logger.debug("ChromaDB list_collections failed: %s", exc)
        return None, None, None

    # ── Text extraction ────────────────────────────────────────────────────

    def _extract_text(self, pdf_bytes: bytes) -> str:
        """Extract plain text from PDF bytes using pdfplumber."""
        import io  # noqa: PLC0415

        import pdfplumber  # noqa: PLC0415

        text_parts: list[str] = []
        with _span("rag.extract_text"):
            try:
                with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(page_text)
            except Exception as exc:
                logger.warning("PDF extraction failed: %s", exc)
                return ""
        return "\n\n".join(text_parts)

    # ── Section-aware chunking ─────────────────────────────────────────────

    def _chunk_text(self, text: str) -> list[str]:
        """Sliding-window chunking with paragraph-boundary snapping.

        Chunk size is kept to _CHUNK_CHARS (800) so the full content fits
        within all-MiniLM-L6-v2's 256-token limit (~200 tokens / 800 chars).
        Each chunk is prefixed with [Section: <name>] derived from a pre-scan
        of the full document for standalone header lines — this prevents false
        matches on mid-paragraph phrases like 'The Board of Directors…'.
        """
        if not text.strip():
            return []

        section_map = _build_section_map(text)
        chunks: list[str] = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + _CHUNK_CHARS, text_len)
            # Snap to paragraph boundary in last 20% of window
            if end < text_len:
                snap_start = start + int(_CHUNK_CHARS * 0.8)
                boundary = text.rfind("\n\n", snap_start, end)
                if boundary != -1:
                    end = boundary

            chunk_raw = text[start:end].strip()
            if chunk_raw:
                section = _section_at_offset(section_map, start)
                chunks.append(f"[Section: {section}]\n{chunk_raw}")

            if end >= text_len:
                break
            start = end - _OVERLAP_CHARS

        return chunks

    # ── Index build and retrieval ──────────────────────────────────────────

    def _build_index(
        self,
        chroma_client: Any,
        chunks: list[str],
        symbol: str,
        year: str,
        pdf_url: str = "",
    ) -> None:
        """Embed chunks and persist to ChromaDB with cosine-distance space."""

        collection_name = self._collection_name(symbol, year)
        try:
            chroma_client.delete_collection(name=collection_name)
        except Exception:
            pass

        collection = chroma_client.create_collection(
            name=collection_name,
            metadata={
                "symbol": symbol,
                "year": year,
                "pdf_url": pdf_url,
                "indexed_at_utc": datetime.now(UTC).isoformat(),
                "hnsw:space": "cosine",
            },
            embedding_function=None,
        )
        with _span("rag.embed_chunks"):
            embeddings = self._embed_texts(chunks)
        ids = [f"{symbol}_{year}_{i}" for i in range(len(chunks))]
        metadatas = [
            {"symbol": symbol, "year": year, "chunk_index": i, "char_count": len(c)}
            for i, c in enumerate(chunks)
        ]
        batch_size = 100
        for batch_start in range(0, len(chunks), batch_size):
            batch_end = batch_start + batch_size
            collection.add(
                ids=ids[batch_start:batch_end],
                documents=chunks[batch_start:batch_end],
                embeddings=embeddings[batch_start:batch_end],
                metadatas=metadatas[batch_start:batch_end],
            )
        logger.info("RAG index built for %s %s: %d chunks", symbol, year, len(chunks))

    def _build_query_text(self, ticker: str) -> str:
        """Always augment with financial keywords for annual-report retrieval.

        The user query provides the intent; the financial keywords improve
        semantic matching against annual report language.
        """
        symbol = ticker.replace(".NS", "").replace(".BO", "").upper()
        user_q = self._user_query.strip()
        return f"{user_q} {symbol} {_FINANCIAL_KEYWORDS}"

    def _retrieve(
        self,
        chroma_client: Any,
        symbol: str,
        year: str,
        ticker: str,
    ) -> list[str]:
        """Retrieve top-K chunks and filter by distance threshold.

        Returns at least _MIN_CHUNKS_RETURNED even if all distances are weak,
        so the LLM always has something to work with. Low-confidence retrievals
        are logged so the evidence block reflects the quality accurately.
        """
        collection_name = self._collection_name(symbol, year)
        collection = chroma_client.get_collection(name=collection_name)
        query_text = self._build_query_text(ticker)
        query_embedding = self._embed_texts([query_text[:_MAX_EMBED_CHARS]])

        n_results = min(_TOP_K, collection.count())
        if n_results == 0:
            return []

        with _span("rag.vector_query"):
            results = collection.query(
                query_embeddings=query_embedding,
                n_results=n_results,
                include=["documents", "distances"],
            )

        raw_docs: list[str] = results.get("documents", [[]])[0]
        raw_distances: list[float] = results.get("distances", [[]])[0]

        if not raw_docs:
            return []

        # Zip and sort by distance (ascending = most similar first)
        scored: list[tuple[float, str]] = sorted(zip(raw_distances, raw_docs), key=lambda x: x[0])

        # Keep chunks below threshold; always keep at least _MIN_CHUNKS_RETURNED
        filtered = [doc for dist, doc in scored if dist <= _DISTANCE_THRESHOLD]
        if not filtered:
            # Fallback: return best chunk regardless of score
            filtered = [scored[0][1]] if scored else []

        # Remove TOC-like noise chunks: chunks where ≥35% of tokens are bare
        # integers (page-number tables) are not useful for analysis.
        def _is_toc_noise(doc: str) -> bool:
            # Strip the section prefix for analysis
            body = re.sub(r"^\[Section:[^\]]+\]\s*", "", doc)
            tokens = body.split()
            if not tokens:
                return True
            int_count = sum(1 for t in tokens if re.fullmatch(r"\d{1,4}", t.strip(".,|")))
            return (int_count / len(tokens)) >= 0.35

        filtered = [d for d in filtered if not _is_toc_noise(d)]
        if not filtered and scored:
            filtered = [scored[0][1]]

        # Deduplicate by section — keep best-distance chunk per section label
        seen_sections: dict[str, str] = {}
        m = re.compile(r"^\[Section:\s*([^\]]+)\]")
        for doc in filtered:  # already sorted best-first
            match = m.match(doc)
            sec = match.group(1).strip() if match else "General"
            if sec not in seen_sections:
                seen_sections[sec] = doc
        filtered = list(seen_sections.values())

        mean_dist = sum(d for d, _ in scored[: len(filtered)]) / len(filtered) if filtered else 1.5
        logger.info(
            "RAG retrieve %s %s: returned %d/%d chunks, mean_dist=%.3f",
            symbol,
            year,
            len(filtered),
            n_results,
            mean_dist,
        )
        return filtered

    # ── Confidence ─────────────────────────────────────────────────────────

    def _confidence(self, data: dict[str, Any]) -> float:
        chunks = data.get("chunks", [])
        n = len(chunks)
        if n == 0:
            return 0.0
        if n >= 4:
            return 0.85
        if n >= 2:
            return 0.6
        return 0.35

    # ── Main fetch ─────────────────────────────────────────────────────────

    async def _fetch(self, ticker: str) -> dict[str, Any]:
        import chromadb  # noqa: PLC0415

        symbol = ticker.replace(".NS", "").replace(".BO", "").upper()
        loop = asyncio.get_running_loop()

        self._vectorstore_root.mkdir(parents=True, exist_ok=True)
        chroma_client = chromadb.PersistentClient(path=str(self._vectorstore_root))

        # 1. Cache hit?
        year, _col_name, cached_pdf_url = self._find_fresh_collection(chroma_client, symbol)
        if year and _col_name:
            chunks = await loop.run_in_executor(
                None, self._retrieve, chroma_client, symbol, year, ticker
            )
            return {"chunks": chunks, "year": year, "pdf_url": cached_pdf_url, "cache_hit": True}

        # 2. Fetch PDF (tries NSE → screener.in → BSE in order)
        result = await self._fetcher.fetch_latest_annual_report_pdf(symbol)
        if result is None:
            raise ValueError(
                f"No annual report PDF found for {symbol} (tried NSE, screener.in, and BSE)"
            )
        pdf_bytes, year, pdf_url = result

        # 3. Extract text
        raw_text = await loop.run_in_executor(None, self._extract_text, pdf_bytes)
        if not raw_text.strip():
            raise ValueError(f"PDF text extraction yielded empty result for {symbol}")

        # 4. Section-aware chunk
        chunks = self._chunk_text(raw_text)
        if not chunks:
            raise ValueError(f"Chunking yielded no chunks for {symbol}")

        # 5. Embed and index
        await loop.run_in_executor(
            None, self._build_index, chroma_client, chunks, symbol, year, pdf_url
        )

        # 6. Retrieve top-K relevant to user query
        retrieved = await loop.run_in_executor(
            None, self._retrieve, chroma_client, symbol, year, ticker
        )
        return {"chunks": retrieved, "year": year, "pdf_url": pdf_url, "cache_hit": False}

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
            logger.info("DocumentRAGConnector: no data for %s — %s", ticker, exc)
            return ConnectorResult(
                source=self.source_name,
                ticker=ticker,
                data={},
                confidence=0.0,
                error=ConnectorError(code="NO_DOCUMENT", message=str(exc), retryable=False),
            )
        except Exception as exc:
            logger.warning("DocumentRAGConnector unexpected error for %s: %s", ticker, exc)
            return ConnectorResult(
                source=self.source_name,
                ticker=ticker,
                data={},
                confidence=0.0,
                error=ConnectorError(code="RAG_ERROR", message=str(exc), retryable=False),
            )
