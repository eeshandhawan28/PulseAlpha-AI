"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Sidebar from "@/components/Sidebar";
import {
  analyzeAllWatchlist,
  fetchQuotes,
  fetchWatchlist,
  removeFromWatchlist,
  type MarketQuote,
  type WatchlistItem,
} from "@/lib/api";

const STANCE_COLORS: Record<string, string> = {
  bullish: "#8fc8a8",
  bearish: "#c97878",
  neutral: "#a39a86",
};

function StancePill({ stance }: { stance: string | null }) {
  if (!stance) {
    return (
      <span className="font-mono text-[10px] text-t3 border border-border px-2 py-0.5">—</span>
    );
  }
  const color = STANCE_COLORS[stance.toLowerCase()] ?? "#a39a86";
  return (
    <span
      className="font-body font-medium text-[10px] uppercase tracking-[0.2em] border px-2 py-0.5"
      style={{ color, borderColor: `${color}40`, background: `${color}12` }}
    >
      {stance}
    </span>
  );
}

function PortfolioSummary({ items }: { items: WatchlistItem[] }) {
  const analyzed = items.filter((i) => i.last_stance);
  if (!analyzed.length) return null;

  const counts = { bullish: 0, bearish: 0, neutral: 0 };
  for (const item of analyzed) {
    const s = (item.last_stance ?? "neutral").toLowerCase();
    if (s in counts) counts[s as keyof typeof counts]++;
  }

  return (
    <div className="flex items-center gap-4 px-5 py-2.5 border-b border-border/60 bg-bg0/60">
      <span className="font-body text-[8px] uppercase tracking-[0.35em] text-t3">Portfolio</span>
      <span className="diamond opacity-30" />
      {counts.bullish > 0 && (
        <span className="font-body text-[10px]" style={{ color: STANCE_COLORS.bullish }}>
          {counts.bullish} Bullish
        </span>
      )}
      {counts.bearish > 0 && (
        <span className="font-body text-[10px]" style={{ color: STANCE_COLORS.bearish }}>
          {counts.bearish} Bearish
        </span>
      )}
      {counts.neutral > 0 && (
        <span className="font-body text-[10px]" style={{ color: STANCE_COLORS.neutral }}>
          {counts.neutral} Neutral
        </span>
      )}
      <span className="ml-auto font-body text-[9px] text-t3">
        {analyzed.length} of {items.length} analysed
      </span>
    </div>
  );
}

function PctChange({ value }: { value: number | null }) {
  if (value === null) return <span className="text-t3 font-mono text-[10px]">—</span>;
  const pos = value >= 0;
  return (
    <span
      className="font-mono text-[10px]"
      style={{ color: pos ? "#8fc8a8" : "#c97878" }}
    >
      {pos ? "+" : ""}
      {value.toFixed(2)}%
    </span>
  );
}

export default function WatchlistPage() {
  const router = useRouter();
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [quotes, setQuotes] = useState<Record<string, MarketQuote>>({});
  const [refreshing, setRefreshing] = useState(false);
  const [refreshProgress, setRefreshProgress] = useState<string | null>(null);

  const reload = () =>
    fetchWatchlist()
      .then((data) => {
        setItems(data);
        return data;
      })
      .catch(() => [] as WatchlistItem[]);

  useEffect(() => {
    reload().then((data) => {
      if (!data.length) return;
      fetchQuotes(data.map((i) => i.ticker)).then((qs) => {
        const map: Record<string, MarketQuote> = {};
        qs.forEach((q) => (map[q.ticker] = q));
        setQuotes(map);
      });
    });
    // Refresh quotes every 60 seconds while page is open
    const interval = setInterval(() => {
      fetchWatchlist().then((data) => {
        if (!data.length) return;
        fetchQuotes(data.map((i) => i.ticker)).then((qs) => {
          const map: Record<string, MarketQuote> = {};
          qs.forEach((q) => (map[q.ticker] = q));
          setQuotes(map);
        });
      });
    }, 60_000);
    return () => clearInterval(interval);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleRemove = async (ticker: string) => {
    await removeFromWatchlist(ticker);
    reload();
  };

  const handleRefreshAll = async () => {
    if (refreshing) return;
    setRefreshing(true);
    setRefreshProgress("Starting…");
    try {
      const result = await analyzeAllWatchlist();
      setRefreshProgress(`Done — ${result.analyzed} updated`);
      reload();
    } catch {
      setRefreshProgress("Refresh failed");
    } finally {
      setRefreshing(false);
      setTimeout(() => setRefreshProgress(null), 3000);
    }
  };

  return (
    <div className="flex h-screen overflow-hidden bg-bg0">
      <Sidebar />

      <div className="flex flex-col flex-1 min-h-0">
        {/* Header */}
        <div className="px-6 py-5 border-b border-border bg-bg1 shrink-0">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-3 mb-1">
                <h1 className="font-display font-semibold text-xl text-t1 tracking-wide">
                  Watchlist
                </h1>
                <span className="diamond" />
              </div>
              <p className="text-[10px] text-t3 font-body font-light uppercase tracking-[0.25em]">
                {items.length} {items.length === 1 ? "instrument" : "instruments"} tracked
              </p>
            </div>

            <button
              onClick={handleRefreshAll}
              disabled={refreshing || items.length === 0}
              className={`h-8 px-5 font-body font-medium text-[10px] uppercase tracking-[0.25em] transition-all flex items-center gap-2 ${
                refreshing
                  ? "bg-bg2 border border-border text-t3 cursor-not-allowed"
                  : items.length === 0
                    ? "bg-bg2 border border-border text-t3 cursor-not-allowed"
                    : "gold-cta"
              }`}
            >
              {refreshing ? (
                <>
                  <span className="w-1.5 h-1.5 rounded-full bg-gold animate-pulse" />
                  {refreshProgress ?? "Refreshing…"}
                </>
              ) : (
                <>
                  <svg width="10" height="10" viewBox="0 0 12 12" fill="none">
                    <path
                      d="M10 6A4 4 0 115 2"
                      stroke="currentColor"
                      strokeWidth="1.3"
                      strokeLinecap="round"
                    />
                    <path d="M9 2l1 1-1 1" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  Refresh All
                </>
              )}
            </button>
          </div>
        </div>

        {/* Portfolio summary bar */}
        <PortfolioSummary items={items} />

        {/* Empty state */}
        {items.length === 0 && (
          <div className="flex-1 flex flex-col items-center justify-center gap-6">
            <div className="flex items-center gap-3">
              <span className="w-12 h-px bg-border" />
              <span className="diamond opacity-30" />
              <span className="w-12 h-px bg-border" />
            </div>
            <div className="text-center">
              <p className="font-body text-[11px] uppercase tracking-[0.3em] text-t3 mb-2">
                No instruments tracked
              </p>
              <p className="font-body font-light text-xs text-t3/70">
                Run an analysis and press the star icon to add a stock to your watchlist.
              </p>
            </div>
            <Link
              href="/analyze"
              className="gold-cta h-8 px-6 font-body font-medium text-[10px] uppercase tracking-[0.25em] flex items-center gap-2"
            >
              Commission Analysis
              <svg width="10" height="6" viewBox="0 0 14 8" fill="none">
                <path d="M0 4h12M9 1l3 3-3 3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </Link>
          </div>
        )}

        {/* Table */}
        {items.length > 0 && (
          <div className="flex-1 overflow-y-auto">
            {/* Column headers */}
            <div className="flex items-center gap-4 px-5 py-2 border-b border-border/40 sticky top-0 bg-bg1 z-10">
              <span className="w-28 font-body text-[8px] uppercase tracking-[0.3em] text-t3 shrink-0">
                Instrument
              </span>
              <span className="w-28 font-body text-[8px] uppercase tracking-[0.3em] text-t3 shrink-0">
                Price · 1D
              </span>
              <span className="w-16 font-body text-[8px] uppercase tracking-[0.3em] text-t3 shrink-0">
                1W
              </span>
              <span className="w-16 font-body text-[8px] uppercase tracking-[0.3em] text-t3 shrink-0">
                1M
              </span>
              <span className="w-24 font-body text-[8px] uppercase tracking-[0.3em] text-t3 shrink-0">
                Verdict
              </span>
              <span className="w-20 font-body text-[8px] uppercase tracking-[0.3em] text-t3 shrink-0">
                Conviction
              </span>
              <span className="flex-1 font-body text-[8px] uppercase tracking-[0.3em] text-t3">
                Last Run
              </span>
              <span className="w-16 font-body text-[8px] uppercase tracking-[0.3em] text-t3 shrink-0 text-right">
                Actions
              </span>
            </div>

            {items.map((item) => {
              const sym = item.ticker.replace(".NS", "").replace(".BO", "");
              const lastRun = item.last_run_at
                ? new Date(item.last_run_at).toLocaleString("en-IN", {
                    day: "2-digit",
                    month: "short",
                    hour: "2-digit",
                    minute: "2-digit",
                  })
                : "—";
              const confidence = item.last_confidence
                ? `${Math.round(item.last_confidence * 100)}%`
                : "—";
              const q = quotes[item.ticker];

              return (
                <div
                  key={item.ticker}
                  className="flex items-center gap-4 px-5 py-3.5 border-b border-border/30 last:border-0 hover:bg-bg2/40 transition-colors group"
                >
                  <div className="w-28 shrink-0">
                    <span className="font-mono text-sm text-t1 font-medium">{sym}</span>
                    <span className="block font-body text-[9px] text-t3 mt-0.5">
                      {item.ticker}
                    </span>
                  </div>

                  {/* Price + 1D */}
                  <div className="w-28 shrink-0">
                    {q ? (
                      <div className="flex flex-col gap-0.5">
                        <span className="font-mono text-[12px] text-t1">
                          ₹{q.price.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
                        </span>
                        <PctChange value={q.change_1d_pct} />
                      </div>
                    ) : (
                      <span className="font-mono text-[10px] text-t3">—</span>
                    )}
                  </div>

                  {/* 1W */}
                  <div className="w-16 shrink-0">
                    {q ? <PctChange value={q.change_1w_pct} /> : <span className="text-t3 font-mono text-[10px]">—</span>}
                  </div>

                  {/* 1M */}
                  <div className="w-16 shrink-0">
                    {q ? <PctChange value={q.change_1m_pct} /> : <span className="text-t3 font-mono text-[10px]">—</span>}
                  </div>

                  <div className="w-24 shrink-0">
                    <StancePill stance={item.last_stance} />
                  </div>

                  <div className="w-20 shrink-0 font-mono text-xs text-t2">{confidence}</div>

                  <div className="flex-1 font-body text-[10px] text-t3">{lastRun}</div>

                  <div className="w-16 shrink-0 flex items-center justify-end gap-2">
                    <Link
                      href={`/analyze?ticker=${encodeURIComponent(item.ticker)}`}
                      onClick={() => router.push(`/analyze?ticker=${encodeURIComponent(item.ticker)}`)}
                      className="font-body text-[9px] uppercase tracking-[0.2em] text-t3 hover:text-gold transition-colors border border-transparent hover:border-gold/30 px-1.5 py-1"
                      title="Analyze"
                    >
                      Run
                    </Link>
                    <button
                      onClick={() => handleRemove(item.ticker)}
                      title="Remove from watchlist"
                      className="text-t3 hover:text-blood transition-colors opacity-0 group-hover:opacity-100"
                    >
                      <svg width="10" height="10" viewBox="0 0 12 12" fill="none">
                        <path
                          d="M2 2l8 8M10 2l-8 8"
                          stroke="currentColor"
                          strokeWidth="1.3"
                          strokeLinecap="round"
                        />
                      </svg>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
