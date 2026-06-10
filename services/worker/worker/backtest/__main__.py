"""CLI entry point: python -m worker.backtest"""

from __future__ import annotations

import argparse
import asyncio
from datetime import date


def _parse_date(s: str) -> date:
    return date.fromisoformat(s)


def main() -> None:
    parser = argparse.ArgumentParser(description="PulseAlpha backtesting CLI")
    parser.add_argument(
        "--tickers",
        required=True,
        help="Comma-separated tickers e.g. RELIANCE.NS,TCS.NS",
    )
    parser.add_argument("--start", required=True, type=_parse_date, metavar="YYYY-MM-DD")
    parser.add_argument("--end", required=True, type=_parse_date, metavar="YYYY-MM-DD")
    parser.add_argument("--frequency", default="monthly", choices=["monthly", "weekly"])
    parser.add_argument("--fast", action="store_true", help="Use heuristic stance (no LLM)")
    parser.add_argument("--output-dir", default="backtest_results")
    parser.add_argument("--horizons", default="30,90,180", help="Comma-separated horizon days")
    args = parser.parse_args()

    from schemas.backtest import BacktestConfig

    from worker.backtest.runner import BacktestRunner

    config = BacktestConfig(
        tickers=[t.strip() for t in args.tickers.split(",")],
        start_date=args.start,
        end_date=args.end,
        frequency=args.frequency,
        fast_mode=args.fast,
        output_dir=args.output_dir,
        horizons_days=[int(h.strip()) for h in args.horizons.split(",")],
    )

    result = asyncio.run(BacktestRunner(config).run())

    n_dates = len({p.as_of_date for p in result.predictions})
    n_tickers = len({p.ticker for p in result.predictions})
    n_total = len(result.predictions)
    print(f"\nBacktest complete — {n_dates} dates × {n_tickers} tickers = {n_total} predictions")
    print(f"Output: {result.output_file}")

    h = config.horizons_days[0]
    hr = result.metrics.get(f"hit_rate_{h}d", {})
    cal = result.metrics.get(f"confidence_calibration_{h}d", [])
    dc = result.metrics.get(f"divergence_correlation_{h}d", {})

    print(
        f"\nHit rate ({h}d):  overall={hr.get('overall', 0):.2f}  "
        f"bullish={hr.get('bullish', 0):.2f}  bearish={hr.get('bearish', 0):.2f}"
    )
    cal_str = "  ".join(f"{b['bucket']}: {b['accuracy']:.2f}" for b in cal)
    print(f"Calibration:     {cal_str or 'no data'}")
    print(f"Divergence corr: {dc.get('correlation', 0):.2f} (lower divergence -> better accuracy)")


if __name__ == "__main__":
    main()
