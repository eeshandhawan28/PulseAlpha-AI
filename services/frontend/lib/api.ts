const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface HistoryRun {
  run_id: string;
  ticker: string;
  query: string;
  stance: string;
  confidence: number;
  divergence_score: number;
  rrg_quadrant: string;
  report: string;
  created_at: string;
}

export interface HistoryStats {
  hit_rate_30d: number | null;
}

export async function fetchHistory(): Promise<HistoryRun[]> {
  try {
    const res = await fetch(`${API_URL}/history`, { cache: "no-store" });
    if (!res.ok) return [];
    return res.json();
  } catch (err) {
    console.error("[api] fetchHistory failed:", err);
    return [];
  }
}

export async function fetchHistoryRun(runId: string): Promise<HistoryRun | null> {
  try {
    const res = await fetch(`${API_URL}/history/${runId}`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch (err) {
    console.error("[api] fetchHistoryRun failed:", err);
    return null;
  }
}

export async function fetchHistoryStats(): Promise<HistoryStats> {
  try {
    const res = await fetch(`${API_URL}/history/stats`, { cache: "no-store" });
    if (!res.ok) return { hit_rate_30d: null };
    return res.json();
  } catch (err) {
    console.error("[api] fetchHistoryStats failed:", err);
    return { hit_rate_30d: null };
  }
}

export function getStreamUrl(ticker: string, query: string): string {
  const params = new URLSearchParams({ ticker, query });
  return `${API_URL}/analyze/stream?${params.toString()}`;
}

// ── Market quotes ─────────────────────────────────────────────────────────

export interface MarketQuote {
  ticker: string;
  price: number;
  currency: string;
  change_1d_pct: number | null;
  change_1w_pct: number | null;
  change_1m_pct: number | null;
  change_3m_pct: number | null;
  change_1y_pct: number | null;
  high_52w: number;
  low_52w: number;
  avg_volume_20d: number | null;
  volume_today: number | null;
  ohlcv_1y: Array<{
    date: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  }>;
}

export async function fetchQuote(ticker: string): Promise<MarketQuote | null> {
  try {
    const res = await fetch(`${API_URL}/market/quote/${encodeURIComponent(ticker)}`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function fetchQuotes(tickers: string[]): Promise<MarketQuote[]> {
  if (!tickers.length) return [];
  try {
    const res = await fetch(
      `${API_URL}/market/quotes?tickers=${encodeURIComponent(tickers.join(","))}`,
      { cache: "no-store" },
    );
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

// ── Watchlist ──────────────────────────────────────────────────────────────

export interface WatchlistItem {
  ticker: string;
  added_at: string;
  last_stance: string | null;
  last_confidence: number | null;
  last_run_at: string | null;
  rrg_quadrant: string | null;
}

export async function fetchWatchlist(): Promise<WatchlistItem[]> {
  try {
    const res = await fetch(`${API_URL}/watchlist`, { cache: "no-store" });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export async function addToWatchlist(ticker: string): Promise<WatchlistItem | null> {
  try {
    const res = await fetch(`${API_URL}/watchlist`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker }),
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function removeFromWatchlist(ticker: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_URL}/watchlist/${encodeURIComponent(ticker)}`, {
      method: "DELETE",
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function checkWatchlistStatus(ticker: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_URL}/watchlist/${encodeURIComponent(ticker)}/status`, {
      cache: "no-store",
    });
    if (!res.ok) return false;
    const data = await res.json();
    return data.in_watchlist as boolean;
  } catch {
    return false;
  }
}

export async function analyzeAllWatchlist(): Promise<{
  analyzed: number;
  results: Array<{ ticker: string; stance?: string; confidence?: number; status: string }>;
}> {
  const res = await fetch(`${API_URL}/watchlist/analyze-all`, { method: "POST" });
  if (!res.ok) throw new Error("analyze-all failed");
  return res.json();
}
