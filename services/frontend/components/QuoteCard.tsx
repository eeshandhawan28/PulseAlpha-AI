"use client";

import { useEffect, useState } from "react";
import { fetchQuote, type MarketQuote } from "@/lib/api";

function PctBadge({ value }: { value: number | null }) {
  if (value === null) return <span className="text-t3">—</span>;
  const pos = value >= 0;
  return (
    <span
      className="font-mono text-[11px]"
      style={{ color: pos ? "#8fc8a8" : "#c97878" }}
    >
      {pos ? "+" : ""}
      {value.toFixed(2)}%
    </span>
  );
}

function fmt(n: number): string {
  if (n >= 1e7) return `₹${(n / 1e7).toFixed(2)}Cr`;
  if (n >= 1e5) return `₹${(n / 1e5).toFixed(2)}L`;
  return `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

function fmtVol(n: number | null): string {
  if (!n) return "—";
  if (n >= 1e7) return `${(n / 1e7).toFixed(2)}Cr`;
  if (n >= 1e5) return `${(n / 1e5).toFixed(1)}L`;
  return n.toLocaleString("en-IN");
}

interface Props {
  ticker: string;
}

export default function QuoteCard({ ticker }: Props) {
  const [quote, setQuote] = useState<MarketQuote | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!ticker) return;
    setLoading(true);
    fetchQuote(ticker)
      .then(setQuote)
      .finally(() => setLoading(false));
  }, [ticker]);

  if (loading) {
    return (
      <div className="bg-bg1 border border-border px-5 py-4 animate-pulse">
        <div className="h-3 w-24 bg-bg2 rounded mb-3" />
        <div className="h-6 w-32 bg-bg2 rounded" />
      </div>
    );
  }

  if (!quote) return null;

  const sym = ticker.replace(".NS", "").replace(".BO", "");
  const dayChange = quote.change_1d_pct;
  const priceColor = dayChange === null ? "#ede8dc" : dayChange >= 0 ? "#8fc8a8" : "#c97878";

  // 52W position as a percentage for the range bar
  const range = quote.high_52w - quote.low_52w;
  const position = range > 0 ? ((quote.price - quote.low_52w) / range) * 100 : 50;

  return (
    <div className="bg-bg1 border border-border shrink-0">
      {/* Price header */}
      <div className="flex items-end justify-between px-5 py-4 border-b border-border/60">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-body text-[8px] uppercase tracking-[0.35em] text-t3">
              {sym}
            </span>
            <span className="diamond opacity-30" />
            <span className="font-body text-[8px] uppercase tracking-[0.2em] text-t3">
              Live · 15min delay
            </span>
          </div>
          <div className="flex items-baseline gap-3">
            <span
              className="font-display text-3xl font-semibold leading-none"
              style={{ color: priceColor }}
            >
              {fmt(quote.price)}
            </span>
            <PctBadge value={dayChange} />
          </div>
        </div>

        {/* Volume */}
        <div className="text-right">
          <p className="font-body text-[8px] uppercase tracking-[0.25em] text-t3 mb-0.5">
            Volume
          </p>
          <p className="font-mono text-[11px] text-t2">{fmtVol(quote.volume_today)}</p>
          <p className="font-body text-[8px] text-t3 mt-0.5">
            avg {fmtVol(quote.avg_volume_20d)}
          </p>
        </div>
      </div>

      {/* Trend grid */}
      <div className="grid grid-cols-4 divide-x divide-border/40 border-b border-border/60">
        {(
          [
            ["1W", quote.change_1w_pct],
            ["1M", quote.change_1m_pct],
            ["3M", quote.change_3m_pct],
            ["1Y", quote.change_1y_pct],
          ] as [string, number | null][]
        ).map(([label, val]) => (
          <div key={label} className="flex flex-col items-center py-2.5 gap-0.5">
            <span className="font-body text-[8px] uppercase tracking-[0.25em] text-t3">
              {label}
            </span>
            <PctBadge value={val} />
          </div>
        ))}
      </div>

      {/* 52W range bar */}
      <div className="px-5 py-3">
        <div className="flex items-center justify-between mb-1.5">
          <span className="font-mono text-[9px] text-t3">{fmt(quote.low_52w)}</span>
          <span className="font-body text-[8px] uppercase tracking-[0.25em] text-t3">
            52W Range
          </span>
          <span className="font-mono text-[9px] text-t3">{fmt(quote.high_52w)}</span>
        </div>
        <div className="relative h-1 bg-bg2 rounded-full">
          <div
            className="absolute top-0 h-1 rounded-full"
            style={{
              left: 0,
              width: `${Math.min(Math.max(position, 2), 98)}%`,
              background: "linear-gradient(90deg, #5f5747 0%, #c9a96a 100%)",
            }}
          />
          <div
            className="absolute top-1/2 -translate-y-1/2 w-2 h-2 rounded-full border border-bg0"
            style={{
              left: `calc(${Math.min(Math.max(position, 2), 98)}% - 4px)`,
              background: priceColor,
            }}
          />
        </div>
      </div>
    </div>
  );
}
