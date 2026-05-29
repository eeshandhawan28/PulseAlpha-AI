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
  } catch {
    return [];
  }
}

export async function fetchHistoryRun(runId: string): Promise<HistoryRun | null> {
  try {
    const res = await fetch(`${API_URL}/history/${runId}`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function fetchHistoryStats(): Promise<HistoryStats> {
  try {
    const res = await fetch(`${API_URL}/history/stats`, { cache: "no-store" });
    if (!res.ok) return { hit_rate_30d: null };
    return res.json();
  } catch {
    return { hit_rate_30d: null };
  }
}

export function getStreamUrl(ticker: string, query: string): string {
  const params = new URLSearchParams({ ticker, query });
  return `${API_URL}/analyze/stream?${params.toString()}`;
}
