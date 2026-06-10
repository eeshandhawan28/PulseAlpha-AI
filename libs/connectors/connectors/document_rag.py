from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from schemas.connectors import ConnectorError, ConnectorResult

from connectors.base import BaseConnector
from connectors.nse_document_fetcher import NSEDocumentFetcher

logger = logging.getLogger(__name__)

_VECTORSTORE_ROOT = Path("data/vectorstore")
_EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_CHUNK_CHARS = 2048       # ~512 tokens at 4 chars/token
_OVERLAP_CHARS = 256      # ~64 tokens overlap
_TOP_K = 5
_TTL_DAYS = 7
_MAX_EMBED_CHARS = 8000   # truncation before embedding


class DocumentRAGConnector(BaseConnector):
    """RAG connector for NSE annual report PDFs.

    Lifecycle per fetch(ticker):
      1. Check ChromaDB collection TTL — if fresh (<7 days), skip to step 4.
      2. Download latest annual report PDF from NSE.
      3. Extract text → chunk → embed → persist to ChromaDB.
      4. Embed user_query → retrieve top-K chunks by cosine similarity.
      5. Return ConnectorResult(data={"chunks": [...], "year": str}).

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
        """Lazy-load sentence-transformers model (CPU, ~80 MB download on first use)."""
        if self._embed_model is None:
            from sentence_transformers import SentenceTransformer  # noqa: PLC0415

            self._embed_model = SentenceTransformer(
                _EMBED_MODEL_NAME,
                device="cpu",
            )
        return self._embed_model

    def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed text list. Truncates each to _MAX_EMBED_CHARS. Returns list of float vectors."""
        model = self._get_embed_model()
        truncated = [t[:_MAX_EMBED_CHARS] for t in texts]
        embeddings = model.encode(
            truncated,
            batch_size=32,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embeddings.tolist()

    # ── ChromaDB helpers ───────────────────────────────────────────────────

    def _collection_name(self, symbol: str, year: str) -> str:
        safe_year = year.replace("-", "_")
        return f"rag_{symbol}_{safe_year}"

    def _is_collection_fresh(self, collection: Any) -> bool:
        """Return True if the collection was indexed within _TTL_DAYS."""
        meta = collection.metadata or {}
        indexed_at_str = meta.get("indexed_at_utc")
        if not indexed_at_str:
            return False
        try:
            indexed_at = datetime.fromisoformat(indexed_at_str)
            if indexed_at.tzinfo is None:
                indexed_at = indexed_at.replace(tzinfo=UTC)
            age = datetime.now(UTC) - indexed_at
            return age < timedelta(days=_TTL_DAYS)
        except (ValueError, TypeError):
            return False

    def _find_fresh_collection(
        self, chroma_client: Any, symbol: str
    ) -> tuple[str, str] | tuple[None, None]:
        """Scan collections for a fresh one matching this symbol.
        Returns (year, collection_name) or (None, None)."""
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
                    year_part = name[len(prefix):]
                    # "2024_25" → "2024-25" (replace first underscore only)
                    year = year_part.replace("_", "-", 1)
                    return year, name
        except Exception as exc:
            logger.debug("ChromaDB list_collections failed: %s", exc)
        return None, None

    # ── Text extraction ────────────────────────────────────────────────────

    def _extract_text(self, pdf_bytes: bytes) -> str:
        """Extract all text from PDF bytes using pdfplumber."""
        import io  # noqa: PLC0415

        import pdfplumber  # noqa: PLC0415

        text_parts: list[str] = []
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

    # ── Chunking ───────────────────────────────────────────────────────────

    def _chunk_text(self, text: str) -> list[str]:
        """Sliding-window character chunking with paragraph-boundary snapping."""
        if not text.strip():
            return []
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
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
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
    ) -> None:
        """Embed chunks and persist to a new ChromaDB collection."""
        import chromadb  # noqa: PLC0415

        collection_name = self._collection_name(symbol, year)
        # Delete stale collection if it exists
        try:
            chroma_client.delete_collection(name=collection_name)
        except Exception:
            pass

        collection = chroma_client.create_collection(
            name=collection_name,
            metadata={
                "symbol": symbol,
                "year": year,
                "indexed_at_utc": datetime.now(UTC).isoformat(),
            },
            embedding_function=None,
        )
        embeddings = self._embed_texts(chunks)
        ids = [f"{symbol}_{year}_{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "symbol": symbol,
                "year": year,
                "chunk_index": i,
                "char_count": len(c),
            }
            for i, c in enumerate(chunks)
        ]
        # Upsert in batches to avoid memory spikes on large documents
        batch_size = 100
        for batch_start in range(0, len(chunks), batch_size):
            batch_end = batch_start + batch_size
            collection.add(
                ids=ids[batch_start:batch_end],
                documents=chunks[batch_start:batch_end],
                embeddings=embeddings[batch_start:batch_end],
                metadatas=metadatas[batch_start:batch_end],
            )

    def _build_query_text(self, ticker: str) -> str:
        """Augment a bare ticker query with financial context keywords."""
        q = self._user_query.strip()
        if len(q.split()) <= 2:
            symbol = ticker.replace(".NS", "").replace(".BO", "").upper()
            q = (
                f"{symbol} management commentary revenue growth segment performance "
                f"risks outlook guidance annual report"
            )
        return q

    def _retrieve(self, chroma_client: Any, symbol: str, year: str, ticker: str) -> list[str]:
        """Embed user_query and retrieve top-K chunks by cosine similarity."""
        collection_name = self._collection_name(symbol, year)
        collection = chroma_client.get_collection(name=collection_name)
        query_text = self._build_query_text(ticker)
        query_embedding = self._embed_texts([query_text[:_MAX_EMBED_CHARS]])
        results = collection.query(
            query_embeddings=query_embedding,
            n_results=min(_TOP_K, collection.count()),
            include=["documents"],
        )
        documents = results.get("documents", [[]])[0]
        return [doc for doc in documents if doc]

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

        # 1. Check for fresh cached collection
        year, _collection_name = self._find_fresh_collection(chroma_client, symbol)
        if year and _collection_name:
            chunks = await loop.run_in_executor(
                None, self._retrieve, chroma_client, symbol, year, ticker
            )
            return {"chunks": chunks, "year": year, "cache_hit": True}

        # 2. Fetch PDF from NSE
        result = await self._fetcher.fetch_latest_annual_report_pdf(symbol)
        if result is None:
            raise ValueError(f"No annual report PDF found for {symbol}")
        pdf_bytes, year = result

        # 3. Extract text (CPU-bound)
        raw_text = await loop.run_in_executor(None, self._extract_text, pdf_bytes)
        if not raw_text.strip():
            raise ValueError(f"PDF text extraction yielded empty result for {symbol}")

        # 4. Chunk
        chunks = self._chunk_text(raw_text)
        if not chunks:
            raise ValueError(f"Chunking yielded no chunks for {symbol}")

        # 5. Build index (CPU-bound: embedding + ChromaDB write)
        await loop.run_in_executor(
            None, self._build_index, chroma_client, chunks, symbol, year
        )

        # 6. Retrieve top-K relevant to user query
        retrieved = await loop.run_in_executor(
            None, self._retrieve, chroma_client, symbol, year, ticker
        )
        return {"chunks": retrieved, "year": year, "cache_hit": False}

    async def fetch(self, ticker: str) -> ConnectorResult:
        """Override: catch errors and degrade silently. Never raises."""
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
                error=ConnectorError(
                    code="NO_DOCUMENT", message=str(exc), retryable=False
                ),
            )
        except Exception as exc:
            logger.warning(
                "DocumentRAGConnector unexpected error for %s: %s", ticker, exc
            )
            return ConnectorResult(
                source=self.source_name,
                ticker=ticker,
                data={},
                confidence=0.0,
                error=ConnectorError(
                    code="RAG_ERROR", message=str(exc), retryable=False
                ),
            )
