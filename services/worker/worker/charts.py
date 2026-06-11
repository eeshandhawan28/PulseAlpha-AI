"""Plotly chart specs generated from OHLCV data in AnalysisState.

Each chart is a plain dict with 'ticker', 'data', and 'layout' keys —
the exact shape that react-plotly.js expects on the frontend.
Charts are styled to match the dark luxury design system.
"""

from __future__ import annotations

from typing import Any

from schemas.state import AnalysisState

# ── Design tokens matching globals.css ────────────────────────────────────
_BG0 = "#0b0a08"
_BG1 = "#11100d"
_GRID = "#2a2519"
_GOLD = "#c9a96a"
_PLAT = "#a9bdd4"
_T1 = "#ede8dc"
_T2 = "#a39a86"
_T3 = "#5f5747"


def build_price_charts(state: AnalysisState) -> list[dict[str, Any]]:
    """Build one Plotly price chart per ticker that has OHLCV data."""
    charts: list[dict[str, Any]] = []
    for ticker in state.ticker_universe:
        ohlcv: list[dict[str, Any]] = state.market_data.get(ticker, {}).get("ohlcv") or []
        if len(ohlcv) < 5:
            continue
        chart = _price_chart(ticker, ohlcv)
        charts.append(chart)
    return charts


def _price_chart(ticker: str, ohlcv: list[dict[str, Any]]) -> dict[str, Any]:
    dates = [r["date"] for r in ohlcv]
    closes = [float(r["close"]) for r in ohlcv]
    volumes = [int(r.get("volume", 0)) for r in ohlcv]

    # 20-day simple moving average (None for first 19 points)
    ma20: list[float | None] = []
    for i in range(len(closes)):
        if i < 19:
            ma20.append(None)
        else:
            ma20.append(sum(closes[i - 19 : i + 1]) / 20)

    sym = ticker.replace(".NS", "").replace(".BO", "")

    return {
        "ticker": ticker,
        "data": [
            {
                "type": "scatter",
                "x": dates,
                "y": closes,
                "name": "Price",
                "line": {"color": _GOLD, "width": 1.5},
                "hovertemplate": "%{x}<br>₹%{y:,.2f}<extra></extra>",
                "yaxis": "y",
            },
            {
                "type": "scatter",
                "x": dates,
                "y": ma20,
                "name": "20D MA",
                "line": {"color": _PLAT, "width": 1, "dash": "dot"},
                "hovertemplate": "MA ₹%{y:,.2f}<extra></extra>",
                "connectgaps": False,
                "yaxis": "y",
            },
            {
                "type": "bar",
                "x": dates,
                "y": volumes,
                "name": "Volume",
                "yaxis": "y2",
                "marker": {"color": _T3, "opacity": 0.55},
                "hovertemplate": "Vol %{y:,}<extra></extra>",
            },
        ],
        "layout": {
            "paper_bgcolor": _BG0,
            "plot_bgcolor": _BG1,
            "font": {"color": _T2, "family": "Jost, sans-serif", "size": 11},
            "margin": {"t": 32, "r": 16, "b": 36, "l": 64},
            "xaxis": {
                "gridcolor": _GRID,
                "zerolinecolor": _GRID,
                "tickfont": {"size": 10},
                "showgrid": True,
            },
            "yaxis": {
                "gridcolor": _GRID,
                "zerolinecolor": _GRID,
                "tickfont": {"size": 10},
                "tickprefix": "₹",
                "domain": [0.28, 1.0],
                "showgrid": True,
            },
            "yaxis2": {
                "domain": [0, 0.22],
                "gridcolor": _GRID,
                "zerolinecolor": _GRID,
                "tickfont": {"size": 9},
                "showgrid": False,
                "title": {"text": "Vol", "font": {"size": 9, "color": _T3}},
            },
            "legend": {
                "font": {"size": 10},
                "orientation": "h",
                "y": 1.05,
                "x": 0,
                "bgcolor": "rgba(0,0,0,0)",
            },
            "hovermode": "x unified",
            "hoverlabel": {
                "bgcolor": "#1e1b16",
                "bordercolor": _GRID,
                "font": {"color": _T1},
            },
            "title": {
                "text": sym,
                "font": {"size": 13, "color": _T1},
                "x": 0.5,
                "y": 0.98,
            },
        },
    }
