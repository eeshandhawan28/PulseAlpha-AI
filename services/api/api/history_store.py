from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_PATH = Path(__file__).parents[3] / "history.json"


class HistoryStore:
    def __init__(self, history_file: Path = _DEFAULT_PATH) -> None:
        self._path = history_file

    def _load(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        try:
            return json.loads(self._path.read_text())  # type: ignore[no-any-return]
        except (json.JSONDecodeError, OSError):
            logger.warning("history.json corrupt or unreadable, starting fresh")
            return []

    def _save(self, runs: list[dict[str, Any]]) -> None:
        self._path.write_text(json.dumps(runs, indent=2, default=str))

    def append_run(self, run: dict[str, Any]) -> None:
        runs = self._load()
        runs.append(run)
        self._save(runs)

    def list_runs(self) -> list[dict[str, Any]]:
        runs = self._load()
        return sorted(runs, key=lambda r: r.get("created_at", ""), reverse=True)

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        for run in self._load():
            if run.get("run_id") == run_id:
                return run
        return None


# Module-level singleton used by FastAPI routes
_store = HistoryStore()


def append_run(run: dict[str, Any]) -> None:
    _store.append_run(run)


def list_runs() -> list[dict[str, Any]]:
    return _store.list_runs()


def get_run(run_id: str) -> dict[str, Any] | None:
    return _store.get_run(run_id)
