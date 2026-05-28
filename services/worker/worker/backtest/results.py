from __future__ import annotations

import json
import logging
from pathlib import Path

from schemas.backtest import BacktestResult

logger = logging.getLogger(__name__)


def save_results(result: BacktestResult, output_dir: str) -> str:
    """Serialize BacktestResult to JSON and write to output_dir.

    Returns absolute file path.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    filename = (
        f"{result.run_id}_{result.config.start_date}_{result.config.end_date}.json"
    )
    file_path = out_path / filename

    payload = result.model_dump(mode="json")
    file_path.write_text(json.dumps(payload, indent=2))

    logger.info("Backtest results written to %s", file_path.resolve())
    return str(file_path.resolve())
