"""Persistent ring buffer for daily FII/DII flow data.

Stores up to 30 days of readings in data/fii_dii_history.json.
append_today() is called once on API startup; load_history() is called
by features.py to build the flow-strength DataFrame.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_MAX_DAYS = 30
_DATA_DIR = Path(__file__).parents[3] / "data"
_HISTORY_FILE = _DATA_DIR / "fii_dii_history.json"


def _load() -> list[dict[str, Any]]:
    if not _HISTORY_FILE.exists():
        return []
    try:
        return json.loads(_HISTORY_FILE.read_text())  # type: ignore[no-any-return]
    except (json.JSONDecodeError, OSError):
        logger.warning("fii_dii_history.json corrupt, starting fresh")
        return []


def _save(records: list[dict[str, Any]]) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _HISTORY_FILE.write_text(json.dumps(records, indent=2, default=str))


def load_history() -> list[dict[str, Any]]:
    """Return stored FII/DII records, most-recent last."""
    return _load()


async def append_today() -> None:
    """Fetch today's FII/DII data and append to the ring buffer (no-op if already stored)."""
    today = date.today().isoformat()
    records = _load()

    # Skip if we already have today's entry
    if records and records[-1].get("date") == today:
        logger.debug("FII/DII already stored for %s", today)
        return

    try:
        from connectors.fii_dii import FIIDIIConnector  # noqa: PLC0415

        connector = FIIDIIConnector()
        result = await connector.fetch("market")
        if result.confidence == 0.0:
            logger.warning("FII/DII fetch returned no data for %s, skipping store", today)
            return

        record = {"date": today, **result.data}
        records.append(record)
        # Keep only the last _MAX_DAYS entries
        records = records[-_MAX_DAYS:]
        _save(records)
        logger.info(
            "FII/DII stored for %s — fii_net=%s dii_net=%s",
            today,
            result.data.get("fii_net"),
            result.data.get("dii_net"),
        )
    except Exception:
        logger.warning("Failed to fetch/store FII/DII for %s", today, exc_info=True)


def history_as_of(as_of: datetime | None = None) -> list[dict[str, Any]]:
    """Return records up to (and including) as_of date. Used in backtests."""
    records = _load()
    if as_of is None:
        return records
    cutoff = as_of.date().isoformat()
    return [r for r in records if r.get("date", "") <= cutoff]
