from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_TRACE_DIR = Path("data/traces")
_TTL = timedelta(hours=6)


def save_trace(run_id: str, data: dict[str, Any]) -> None:
    """Persist the full pipeline state for a run to data/traces/{run_id}.json.

    Cleans up traces older than 6 hours before writing so the directory
    doesn't grow unbounded during development.
    """
    _TRACE_DIR.mkdir(parents=True, exist_ok=True)
    _cleanup_old_traces()
    path = _TRACE_DIR / f"{run_id}.json"
    try:
        path.write_text(json.dumps(data, default=str, indent=2))
        logger.debug("Saved run trace → %s", path)
    except Exception as exc:
        logger.warning("Failed to write trace for %s: %s", run_id, exc)


def _cleanup_old_traces() -> None:
    """Remove JSON trace files older than _TTL from the traces directory."""
    if not _TRACE_DIR.exists():
        return
    cutoff = datetime.now(UTC) - _TTL
    for f in _TRACE_DIR.glob("*.json"):
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=UTC)
            if mtime < cutoff:
                f.unlink()
                logger.debug("Removed stale trace: %s", f.name)
        except Exception:
            pass
