"""Persistent watchlist store — flat JSON file, same pattern as history_store.py."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_PATH = Path(__file__).parents[3] / "watchlist.json"


class WatchlistStore:
    def __init__(self, path: Path = _DEFAULT_PATH) -> None:
        self._path = path

    def _load(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        try:
            return json.loads(self._path.read_text())  # type: ignore[no-any-return]
        except (json.JSONDecodeError, OSError):
            logger.warning("watchlist.json corrupt or unreadable, starting fresh")
            return []

    def _save(self, items: list[dict[str, Any]]) -> None:
        self._path.write_text(json.dumps(items, indent=2, default=str))

    def list_items(self) -> list[dict[str, Any]]:
        return self._load()

    def add(self, ticker: str) -> dict[str, Any]:
        items = self._load()
        if any(i["ticker"] == ticker for i in items):
            return next(i for i in items if i["ticker"] == ticker)
        item: dict[str, Any] = {
            "ticker": ticker,
            "added_at": datetime.now(UTC).isoformat(),
            "last_stance": None,
            "last_confidence": None,
            "last_run_at": None,
            "rrg_quadrant": None,
        }
        items.append(item)
        self._save(items)
        return item

    def remove(self, ticker: str) -> bool:
        items = self._load()
        filtered = [i for i in items if i["ticker"] != ticker]
        if len(filtered) == len(items):
            return False
        self._save(filtered)
        return True

    def update_from_run(
        self,
        ticker: str,
        stance: str,
        confidence: float,
        rrg_quadrant: str,
    ) -> None:
        """Called after a successful analysis run to keep watchlist fresh."""
        items = self._load()
        for item in items:
            if item["ticker"] == ticker:
                item["last_stance"] = stance
                item["last_confidence"] = confidence
                item["last_run_at"] = datetime.now(UTC).isoformat()
                item["rrg_quadrant"] = rrg_quadrant
                break
        self._save(items)

    def has(self, ticker: str) -> bool:
        return any(i["ticker"] == ticker for i in self._load())


_store = WatchlistStore()


def list_items() -> list[dict[str, Any]]:
    return _store.list_items()


def add(ticker: str) -> dict[str, Any]:
    return _store.add(ticker)


def remove(ticker: str) -> bool:
    return _store.remove(ticker)


def update_from_run(ticker: str, stance: str, confidence: float, rrg_quadrant: str) -> None:
    _store.update_from_run(ticker, stance, confidence, rrg_quadrant)


def has(ticker: str) -> bool:
    return _store.has(ticker)
