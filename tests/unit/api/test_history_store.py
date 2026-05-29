import json
import pytest
from pathlib import Path
from api.history_store import HistoryStore


@pytest.fixture
def store(tmp_path):
    return HistoryStore(history_file=tmp_path / "history.json")


def test_list_runs_empty(store):
    assert store.list_runs() == []


def test_append_and_list(store):
    run = {
        "run_id": "abc123",
        "ticker": "RELIANCE.NS",
        "query": "Q3 outlook?",
        "stance": "bullish",
        "confidence": 0.82,
        "divergence_score": 0.23,
        "rrg_quadrant": "Leading",
        "report": "## Summary\nBullish.",
        "created_at": "2026-05-29T10:00:00Z",
    }
    store.append_run(run)
    runs = store.list_runs()
    assert len(runs) == 1
    assert runs[0]["run_id"] == "abc123"


def test_list_runs_newest_first(store):
    store.append_run({"run_id": "first", "created_at": "2026-05-01T00:00:00Z"})
    store.append_run({"run_id": "second", "created_at": "2026-05-29T00:00:00Z"})
    runs = store.list_runs()
    assert runs[0]["run_id"] == "second"


def test_get_run_by_id(store):
    store.append_run({"run_id": "xyz", "ticker": "TCS.NS"})
    run = store.get_run("xyz")
    assert run is not None
    assert run["ticker"] == "TCS.NS"


def test_get_run_missing_returns_none(store):
    assert store.get_run("nonexistent") is None


def test_load_handles_corrupt_json(tmp_path):
    """HistoryStore._load returns [] on corrupt JSON."""
    f = tmp_path / "history.json"
    f.write_text("{corrupt json{{")
    store = HistoryStore(history_file=f)
    assert store.list_runs() == []


def test_load_handles_missing_file(tmp_path):
    """HistoryStore._load returns [] when file doesn't exist."""
    store = HistoryStore(history_file=tmp_path / "nonexistent.json")
    assert store.list_runs() == []
