"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import type { HistoryRun } from "@/lib/api";

function stancePillClass(stance: string) {
  if (stance === "bullish") return "text-emerald bg-emerald-dim border border-emerald/30";
  if (stance === "bearish") return "text-rose bg-rose-dim border border-rose/30";
  return "text-amber bg-amber-dim border border-amber/30";
}

function confColor(conf: number) {
  if (conf >= 0.75) return "text-ice";
  if (conf >= 0.5) return "text-amber";
  return "text-rose";
}

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleDateString("en-IN", { month: "short", day: "numeric" });
  } catch {
    return "—";
  }
}

export default function HistoryTable({ runs }: { runs: HistoryRun[] }) {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [stanceFilter, setStanceFilter] = useState("all");

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return runs.filter((r) => {
      const matchSearch =
        !q || r.ticker.toLowerCase().includes(q) || r.query.toLowerCase().includes(q);
      const matchStance = stanceFilter === "all" || r.stance === stanceFilter;
      return matchSearch && matchStance;
    });
  }, [runs, search, stanceFilter]);

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* Toolbar */}
      <div className="flex gap-2 px-4 py-3 border-b border-border bg-bg1 shrink-0">
        <input
          className="flex-1 h-8 bg-bg2 border border-border rounded-md px-3 font-body text-xs text-t1 placeholder:text-t3 focus:outline-none focus:border-border-active transition-colors"
          placeholder="Search ticker or query…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          className="h-8 bg-bg2 border border-border text-t2 font-body text-xs rounded-md px-3 focus:outline-none focus:border-border-active transition-colors"
          value={stanceFilter}
          onChange={(e) => setStanceFilter(e.target.value)}
        >
          <option value="all">All stances</option>
          <option value="bullish">Bullish</option>
          <option value="bearish">Bearish</option>
          <option value="neutral">Neutral</option>
        </select>
      </div>

      {/* Column header */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-border shrink-0">
        <span className="w-28 text-[9px] uppercase tracking-[0.18em] text-t3 font-body">Ticker</span>
        <span className="flex-1 text-[9px] uppercase tracking-[0.18em] text-t3 font-body">Query</span>
        <span className="w-20 text-[9px] uppercase tracking-[0.18em] text-t3 font-body">Stance</span>
        <span className="w-12 text-right text-[9px] uppercase tracking-[0.18em] text-t3 font-body">Conf</span>
        <span className="w-16 text-right text-[9px] uppercase tracking-[0.18em] text-t3 font-body">Date</span>
      </div>

      {/* Rows */}
      <div className="flex-1 overflow-auto">
        {filtered.length === 0 && (
          <div className="flex flex-col items-center justify-center h-32 gap-2">
            <p className="text-xs text-t3 font-body">
              {runs.length === 0
                ? "No analyses yet — go to Analyze to run your first."
                : "No results match your filter."}
            </p>
          </div>
        )}
        {filtered.map((run) => (
          <div
            key={run.run_id}
            className="flex items-center gap-3 px-4 py-3 border-b border-[#0d1222] cursor-pointer hover:bg-bg2 transition-colors group"
            onClick={() => router.push(`/analyze?run_id=${run.run_id}`)}
            tabIndex={0}
            role="button"
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") router.push(`/analyze?run_id=${run.run_id}`);
            }}
          >
            <span className="w-28 font-mono text-sm font-semibold text-t1 truncate group-hover:text-amber transition-colors">
              {run.ticker}
            </span>
            <span className="flex-1 text-xs text-t2 truncate font-body">{run.query}</span>
            <span className="w-20">
              <span className={`text-[9px] font-display font-bold px-2 py-0.5 rounded ${stancePillClass(run.stance)}`}>
                {run.stance.toUpperCase()}
              </span>
            </span>
            <span className={`w-12 text-right font-mono text-xs font-semibold ${confColor(run.confidence)}`}>
              {Math.round(run.confidence * 100)}%
            </span>
            <span className="w-16 text-right text-[11px] text-t3 font-body">{formatDate(run.created_at)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
