"use client";

import dynamic from "next/dynamic";
import type { ComponentType } from "react";
import { useEffect, useState } from "react";
import type { PlotParams } from "react-plotly.js";
import { fetchQuote, type MarketQuote } from "@/lib/api";
import type { ChartSpec } from "@/lib/stream";

// Plotly must be dynamically imported — no SSR support
const Plot = dynamic(() => import("react-plotly.js"), {
  ssr: false,
  loading: () => (
    <div className="h-[280px] flex items-center justify-center">
      <div className="flex items-center gap-3 opacity-40">
        <span className="w-8 h-px bg-border-active" />
        <span className="diamond animate-pulse" />
        <span className="w-8 h-px bg-border-active" />
      </div>
    </div>
  ),
}) as ComponentType<PlotParams>;

// Design tokens
const _BG0 = "#0b0a08";
const _BG1 = "#11100d";
const _GRID = "#2a2519";
const _GOLD = "#c9a96a";
const _PLAT = "#a9bdd4";
const _T1 = "#ede8dc";
const _T2 = "#a39a86";
const _T3 = "#5f5747";

type Period = "1W" | "1M" | "3M" | "1Y";

const PERIOD_DAYS: Record<Period, number> = { "1W": 5, "1M": 21, "3M": 63, "1Y": 252 };

function buildPlotData(
  ohlcv: MarketQuote["ohlcv_1y"],
  period: Period,
): { data: object[]; layout: object } {
  const days = PERIOD_DAYS[period];
  const slice = ohlcv.slice(-days);
  const dates = slice.map((r) => r.date);
  const closes = slice.map((r) => r.close);
  const volumes = slice.map((r) => r.volume);

  // MA20 (only meaningful for 3M/1Y; still computed, just might be partial)
  const ma20: (number | null)[] = closes.map((_, i) =>
    i < 19 ? null : closes.slice(i - 19, i + 1).reduce((a, b) => a + b, 0) / 20,
  );

  return {
    data: [
      {
        type: "scatter",
        x: dates,
        y: closes,
        name: "Price",
        line: { color: _GOLD, width: 1.5 },
        hovertemplate: "%{x}<br>₹%{y:,.2f}<extra></extra>",
        yaxis: "y",
      },
      {
        type: "scatter",
        x: dates,
        y: ma20,
        name: "20D MA",
        line: { color: _PLAT, width: 1, dash: "dot" },
        hovertemplate: "MA ₹%{y:,.2f}<extra></extra>",
        connectgaps: false,
        yaxis: "y",
      },
      {
        type: "bar",
        x: dates,
        y: volumes,
        name: "Volume",
        yaxis: "y2",
        marker: { color: _T3, opacity: 0.55 },
        hovertemplate: "Vol %{y:,}<extra></extra>",
      },
    ],
    layout: {
      paper_bgcolor: _BG0,
      plot_bgcolor: _BG1,
      font: { color: _T2, family: "Jost, sans-serif", size: 11 },
      margin: { t: 16, r: 16, b: 36, l: 64 },
      xaxis: { gridcolor: _GRID, zerolinecolor: _GRID, tickfont: { size: 10 }, showgrid: true },
      yaxis: {
        gridcolor: _GRID,
        zerolinecolor: _GRID,
        tickfont: { size: 10 },
        tickprefix: "₹",
        domain: [0.28, 1.0],
        showgrid: true,
      },
      yaxis2: {
        domain: [0, 0.22],
        gridcolor: _GRID,
        zerolinecolor: _GRID,
        tickfont: { size: 9 },
        showgrid: false,
        title: { text: "Vol", font: { size: 9, color: _T3 } },
      },
      legend: {
        font: { size: 10 },
        orientation: "h",
        y: 1.04,
        x: 0,
        bgcolor: "rgba(0,0,0,0)",
      },
      hovermode: "x unified",
      hoverlabel: { bgcolor: "#1e1b16", bordercolor: _GRID, font: { color: _T1 } },
    },
  };
}

interface SingleChartProps {
  c: ChartSpec;
}

function SingleChart({ c }: SingleChartProps) {
  const [period, setPeriod] = useState<Period>("3M");
  const [quote, setQuote] = useState<MarketQuote | null>(null);

  useEffect(() => {
    fetchQuote(c.ticker)
      .then(setQuote)
      .catch(() => {});
  }, [c.ticker]);

  // If we have extended 1Y data from the quote endpoint, use it; otherwise fall back to 90D
  const { data, layout } = quote
    ? buildPlotData(quote.ohlcv_1y, period)
    : { data: c.data as object[], layout: c.layout as object };

  const sym = c.ticker.replace(".NS", "").replace(".BO", "");
  const periods: Period[] = ["1W", "1M", "3M", "1Y"];

  const dayChange = quote?.change_1d_pct ?? null;
  const priceColor =
    dayChange === null ? _T2 : dayChange >= 0 ? "#8fc8a8" : "#c97878";

  return (
    <div className="bg-bg1 border border-border overflow-hidden">
      {/* Header row */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-border/60">
        <span className="font-mono text-[11px] text-t1 font-medium">{sym}</span>

        {quote && (
          <>
            <span className="diamond opacity-30" />
            <span className="font-display text-[15px] font-semibold" style={{ color: priceColor }}>
              ₹{quote.price.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
            </span>
            {dayChange !== null && (
              <span className="font-mono text-[11px]" style={{ color: priceColor }}>
                {dayChange >= 0 ? "+" : ""}
                {dayChange.toFixed(2)}%
              </span>
            )}
          </>
        )}

        {/* Period selector — pushed to the right */}
        <div className="ml-auto flex items-center gap-0.5">
          {periods.map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`font-body text-[9px] uppercase tracking-[0.2em] px-2 py-1 transition-colors ${
                period === p
                  ? "text-gold border border-gold/40 bg-gold/10"
                  : "text-t3 border border-transparent hover:text-t2"
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      <Plot
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        data={data as any[]}
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        layout={{ ...(layout as any), autosize: true }}
        useResizeHandler
        style={{ width: "100%", height: "260px" }}
        config={{ displayModeBar: false, responsive: true, scrollZoom: false }}
      />
    </div>
  );
}

interface Props {
  charts: ChartSpec[];
}

export default function ChartsPanel({ charts }: Props) {
  if (!charts.length) return null;

  return (
    <div className="flex flex-col gap-3 shrink-0">
      {charts.map((c) => (
        <SingleChart key={c.ticker} c={c} />
      ))}
    </div>
  );
}
