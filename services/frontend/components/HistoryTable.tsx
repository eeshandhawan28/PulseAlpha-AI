"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import type { HistoryRun } from "@/lib/api";

function stancePillClass(stance: string) {
  if (stance === "bullish") return "text-jade border-jade/40 bg-jade-dim";
  if (stance === "bearish") return "text-blood border-blood/40 bg-blood-dim";
  return "text-gold border-gold/40 bg-gold-dim";
}

function confColor(conf: number) {
  if (conf >= 0.75) return "text-plat";
  if (conf >= 0.5) return "text-gold";
  return "text-blood";
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
      <div className="flex gap-4 px-6 py-4 border-b border-border bg-bg1 shrink-0">
        <input
          className="lux-input flex-1 font-body font-light text-xs"
          placeholder="Search instrument or mandate…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          className="h-9 bg-bg2 border border-border text-t2 font-body font-light text-xs px-3 focus:outline-none focus:border-gold/50 transition-colors uppercase tracking-[0.1em]"
          value={stanceFilter}
          onChange={(e) => setStanceFilter(e.target.value)}
        >
          <option value="all">All verdicts</option>
          <option value="bullish">Bullish</option>
          <option value="bearish">Bearish</option>
          <option value="neutral">Neutral</option>
        </select>
      </div>

      {/* Column header */}
      <div className="flex items-center gap-4 px-6 py-2.5 border-b border-border shrink-0">
        <span className="w-28 text-[8px] uppercase tracking-[0.3em] text-t3 font-body">
          Instrument
        </span>
        <span className="flex-1 text-[8px] uppercase tracking-[0.3em] text-t3 font-body">
          Mandate
        </span>
        <span className="w-20 text-[8px] uppercase tracking-[0.3em] text-t3 font-body">
          Verdict
        </span>
        <span className="w-12 text-right text-[8px] uppercase tracking-[0.3em] text-t3 font-body">
          Conv.
        </span>
        <span className="w-16 text-right text-[8px] uppercase tracking-[0.3em] text-t3 font-body">
          Date
        </span>
      </div>

      {/* Ledger rows */}
      <div className="flex-1 overflow-auto">
        {filtered.length === 0 && (
          <div className="flex flex-col items-center justify-center h-40 gap-3">
            <div className="flex items-center gap-3 opacity-50">
              <span className="w-8 h-px bg-border-active" />
              <span className="diamond" />
              <span className="w-8 h-px bg-border-active" />
            </div>
            <p className="text-xs text-t3 font-body font-light tracking-[0.1em]">
              {runs.length === 0
                ? "The ledger is empty — commission your first analysis."
                : "No entries match your filter."}
            </p>
          </div>
        )}
        {filtered.map((run) => (
          <div
            key={run.run_id}
            className="ledger-row flex items-center gap-4 px-6 py-3.5 border-b border-border/60 cursor-pointer hover:bg-bg2 group"
            onClick={() => router.push(`/analyze?run_id=${run.run_id}`)}
            tabIndex={0}
            role="button"
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") router.push(`/analyze?run_id=${run.run_id}`);
            }}
          >
            <span className="w-28 font-mono text-[13px] font-medium text-t1 truncate group-hover:text-gold transition-colors">
              {run.ticker}
            </span>
            <span className="flex-1 text-xs text-t2 font-light truncate font-body">
              {run.query}
            </span>
            <span className="w-20">
              <span
                className={`text-[8px] font-body font-medium uppercase tracking-[0.25em] px-2 py-1 border ${stancePillClass(run.stance)}`}
              >
                {run.stance}
              </span>
            </span>
            <span
              className={`w-12 text-right font-mono text-xs font-medium ${confColor(run.confidence)}`}
            >
              {Math.round(run.confidence * 100)}%
            </span>
            <span className="w-16 text-right text-[11px] text-t3 font-body font-light">
              {formatDate(run.created_at)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
