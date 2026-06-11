"use client";

import dynamic from "next/dynamic";
import type { ComponentType } from "react";
import { useEffect, useState } from "react";
import type { PlotParams } from "react-plotly.js";
import { fetchQuote, type MarketQuote } from "@/lib/api";
import type { ChartSpec } from "@/lib/stream";

const Plot = dynamic(() => import("react-plotly.js"), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center" style={{ height: "100%" }}>
      <div className="flex items-center gap-3 opacity-40">
        <span className="w-8 h-px bg-border" />
        <span className="diamond animate-pulse" />
        <span className="w-8 h-px bg-border" />
      </div>
    </div>
  ),
}) as ComponentType<PlotParams>;

// ── Design tokens ─────────────────────────────────────────────────────────
const _BG0 = "#0b0a08";
const _BG1 = "#11100d";
const _GRID = "#2a2519";
const _GOLD = "#c9a96a";
const _PLAT = "#a9bdd4";
const _T1 = "#ede8dc";
const _T2 = "#a39a86";
const _T3 = "#5f5747";

type Period = "1W" | "1M" | "3M" | "1Y";
const PERIOD_DAYS: Record<Period, number> = { "1W": 7, "1M": 30, "3M": 90, "1Y": 365 };
const PERIODS: Period[] = ["1W", "1M", "3M", "1Y"];

function buildPlotData(
  ohlcv: MarketQuote["ohlcv_1y"],
  period: Period,
): { data: object[]; layout: object } {
  // Slice by calendar days, not trading days, for accuracy
  const days = PERIOD_DAYS[period];
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - days);
  const cutoffStr = cutoff.toISOString().slice(0, 10);
  const slice = ohlcv.filter((r) => r.date >= cutoffStr);
  // Fallback: take last N rows if filter returns nothing
  const rows = slice.length >= 3 ? slice : ohlcv.slice(-Math.min(days, ohlcv.length));

  const dates = rows.map((r) => r.date);
  const closes = rows.map((r) => r.close);
  const volumes = rows.map((r) => r.volume);

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
        line: { color: _GOLD, width: 1.8 },
        hovertemplate: "%{x}<br>₹%{y:,.2f}<extra></extra>",
        yaxis: "y",
      },
      {
        type: "scatter",
        x: dates,
        y: ma20,
        name: "20D MA",
        line: { color: _PLAT, width: 1.2, dash: "dot" },
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
        marker: { color: _T3, opacity: 0.5 },
        hovertemplate: "Vol %{y:,}<extra></extra>",
      },
    ],
    layout: {
      paper_bgcolor: _BG0,
      plot_bgcolor: _BG1,
      font: { color: _T2, family: "Jost, sans-serif", size: 11 },
      margin: { t: 16, r: 20, b: 40, l: 70 },
      xaxis: {
        gridcolor: _GRID,
        zerolinecolor: _GRID,
        tickfont: { size: 10 },
        showgrid: true,
      },
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
        y: 1.05,
        x: 0,
        bgcolor: "rgba(0,0,0,0)",
      },
      hovermode: "x unified",
      hoverlabel: { bgcolor: "#1e1b16", bordercolor: _GRID, font: { color: _T1 } },
    },
  };
}

// ── Fullscreen modal ──────────────────────────────────────────────────────
function FullscreenModal({
  ticker,
  quote,
  period,
  onClose,
}: {
  ticker: string;
  quote: MarketQuote;
  period: Period;
  onClose: () => void;
}) {
  const [activePeriod, setActivePeriod] = useState<Period>(period);
  const { data, layout } = buildPlotData(quote.ohlcv_1y, activePeriod);
  const sym = ticker.replace(".NS", "").replace(".BO", "");
  const dayChange = quote.change_1d_pct;
  const priceColor = dayChange === null ? _T2 : dayChange >= 0 ? "#8fc8a8" : "#c97878";

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col"
      style={{ background: "rgba(11,10,8,0.97)" }}
    >
      {/* Modal header */}
      <div className="flex items-center justify-between px-8 py-4 border-b border-border shrink-0">
        <div className="flex items-center gap-5">
          <span className="font-mono text-lg font-semibold text-t1">{sym}</span>
          <span className="diamond opacity-30" />
          <span className="font-display text-2xl font-semibold" style={{ color: priceColor }}>
            ₹{quote.price.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
          </span>
          {dayChange !== null && (
            <span className="font-mono text-sm" style={{ color: priceColor }}>
              {dayChange >= 0 ? "+" : ""}
              {dayChange.toFixed(2)}%
            </span>
          )}
        </div>

        <div className="flex items-center gap-4">
          {/* Period selector */}
          <div className="flex items-center gap-0.5">
            {PERIODS.map((p) => (
              <button
                key={p}
                onClick={() => setActivePeriod(p)}
                className={`font-body text-[10px] uppercase tracking-[0.2em] px-3 py-1.5 transition-colors ${
                  activePeriod === p
                    ? "text-gold border border-gold/40 bg-gold/10"
                    : "text-t3 border border-transparent hover:text-t2 hover:border-border"
                }`}
              >
                {p}
              </button>
            ))}
          </div>

          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center border border-border text-t3 hover:text-gold hover:border-gold/40 transition-colors"
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path
                d="M2 2l8 8M10 2l-8 8"
                stroke="currentColor"
                strokeWidth="1.4"
                strokeLinecap="round"
              />
            </svg>
          </button>
        </div>
      </div>

      {/* Trend summary strip */}
      <div className="flex items-center gap-8 px-8 py-2.5 border-b border-border/40 shrink-0">
        {(
          [
            ["1W", quote.change_1w_pct],
            ["1M", quote.change_1m_pct],
            ["3M", quote.change_3m_pct],
            ["1Y", quote.change_1y_pct],
            ["52W H", quote.high_52w],
            ["52W L", quote.low_52w],
          ] as [string, number | null][]
        ).map(([label, val]) => (
          <div key={label} className="flex flex-col gap-0.5">
            <span className="font-body text-[8px] uppercase tracking-[0.25em] text-t3">
              {label}
            </span>
            {val !== null ? (
              label.includes("W H") || label.includes("W L") ? (
                <span className="font-mono text-[11px] text-t2">
                  ₹{val.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
                </span>
              ) : (
                <span
                  className="font-mono text-[11px]"
                  style={{ color: val >= 0 ? "#8fc8a8" : "#c97878" }}
                >
                  {val >= 0 ? "+" : ""}
                  {val.toFixed(2)}%
                </span>
              )
            ) : (
              <span className="font-mono text-[11px] text-t3">—</span>
            )}
          </div>
        ))}
      </div>

      {/* Full-height chart */}
      <div className="flex-1 min-h-0 px-4 py-4">
        <Plot
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          data={data as any[]}
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          layout={{ ...(layout as any), autosize: true }}
          useResizeHandler
          style={{ width: "100%", height: "100%" }}
          config={{ displayModeBar: false, responsive: true, scrollZoom: true }}
        />
      </div>
    </div>
  );
}

// ── Single chart tile ─────────────────────────────────────────────────────
function ChartTile({ c }: { c: ChartSpec }) {
  const [period, setPeriod] = useState<Period>("3M");
  const [quote, setQuote] = useState<MarketQuote | null>(null);
  const [loading, setLoading] = useState(true);
  const [fullscreen, setFullscreen] = useState(false);

  useEffect(() => {
    setLoading(true);
    fetchQuote(c.ticker)
      .then(setQuote)
      .finally(() => setLoading(false));
  }, [c.ticker]);

  const sym = c.ticker.replace(".NS", "").replace(".BO", "");

  // Use 1Y data from quote if available, otherwise 90D fallback from pipeline
  const plotReady = !loading && quote !== null;
  const { data, layout } = plotReady
    ? buildPlotData(quote.ohlcv_1y, period)
    : { data: c.data as object[], layout: c.layout as object };

  const dayChange = quote?.change_1d_pct ?? null;
  const priceColor = dayChange === null ? _T2 : dayChange >= 0 ? "#8fc8a8" : "#c97878";

  return (
    <>
      {fullscreen && quote && (
        <FullscreenModal
          ticker={c.ticker}
          quote={quote}
          period={period}
          onClose={() => setFullscreen(false)}
        />
      )}

      <div className="bg-bg1 border border-border overflow-hidden">
        {/* Header */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-border/60">
          {/* Ticker + price */}
          <div className="flex items-center gap-3 flex-1 min-w-0">
            <span className="font-mono text-[13px] text-t1 font-semibold">{sym}</span>
            {quote && (
              <>
                <span className="diamond opacity-30" />
                <span className="font-display text-[17px] font-semibold" style={{ color: priceColor }}>
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
            {loading && (
              <span className="font-body text-[9px] uppercase tracking-[0.2em] text-t3 animate-pulse">
                Loading…
              </span>
            )}
          </div>

          {/* Period toggle — disabled until 1Y data loads */}
          <div className="flex items-center gap-0.5">
            {PERIODS.map((p) => (
              <button
                key={p}
                onClick={() => plotReady && setPeriod(p)}
                disabled={!plotReady}
                className={`font-body text-[9px] uppercase tracking-[0.15em] px-2 py-1 transition-colors ${
                  !plotReady
                    ? "text-t3/30 cursor-not-allowed border border-transparent"
                    : period === p
                      ? "text-gold border border-gold/40 bg-gold/10"
                      : "text-t3 border border-transparent hover:text-t2"
                }`}
              >
                {p}
              </button>
            ))}
          </div>

          {/* Fullscreen button */}
          <button
            onClick={() => quote && setFullscreen(true)}
            disabled={!quote}
            title="Fullscreen"
            className="w-7 h-7 flex items-center justify-center border border-border/60 text-t3 hover:text-gold hover:border-gold/40 transition-colors disabled:opacity-30 disabled:cursor-not-allowed shrink-0"
          >
            <svg width="11" height="11" viewBox="0 0 12 12" fill="none">
              <path
                d="M1 4.5V1h3.5M7.5 1H11v3.5M11 7.5V11H7.5M4.5 11H1V7.5"
                stroke="currentColor"
                strokeWidth="1.2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        </div>

        {/* Trend mini-strip — shown once data loads */}
        {quote && (
          <div className="flex divide-x divide-border/30 border-b border-border/40">
            {(
              [
                ["1W", quote.change_1w_pct],
                ["1M", quote.change_1m_pct],
                ["3M", quote.change_3m_pct],
                ["1Y", quote.change_1y_pct],
              ] as [string, number | null][]
            ).map(([label, val]) => (
              <div key={label} className="flex-1 flex flex-col items-center py-2 gap-0.5">
                <span className="font-body text-[8px] uppercase tracking-[0.2em] text-t3">
                  {label}
                </span>
                {val !== null ? (
                  <span
                    className="font-mono text-[10px]"
                    style={{ color: val >= 0 ? "#8fc8a8" : "#c97878" }}
                  >
                    {val >= 0 ? "+" : ""}
                    {val.toFixed(2)}%
                  </span>
                ) : (
                  <span className="font-mono text-[10px] text-t3">—</span>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Chart */}
        <Plot
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          data={data as any[]}
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          layout={{ ...(layout as any), autosize: true }}
          useResizeHandler
          style={{ width: "100%", height: "340px" }}
          config={{ displayModeBar: false, responsive: true, scrollZoom: false }}
        />
      </div>
    </>
  );
}

// ── Panel ─────────────────────────────────────────────────────────────────
interface Props {
  charts: ChartSpec[];
}

export default function ChartsPanel({ charts }: Props) {
  if (!charts.length) return null;

  return (
    <div className="flex flex-col gap-4 shrink-0">
      {charts.map((c) => (
        <ChartTile key={c.ticker} c={c} />
      ))}
    </div>
  );
}
