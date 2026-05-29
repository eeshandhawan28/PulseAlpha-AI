"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import type { HistoryRun } from "@/lib/api";

function stanceBadgeClass(stance: string) {
  if (stance === "bullish") return "bg-green-900 text-green-400 border-0";
  if (stance === "bearish") return "bg-red-900 text-red-400 border-0";
  return "bg-yellow-900 text-yellow-400 border-0";
}

function confColor(conf: number) {
  if (conf >= 0.75) return "text-blue-400";
  if (conf >= 0.5) return "text-yellow-400";
  return "text-red-400";
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-IN", { month: "short", day: "numeric" });
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
      <div className="flex gap-2 px-4 py-3 border-b border-border">
        <Input
          className="flex-1 bg-surface border-border text-foreground placeholder:text-muted"
          placeholder="🔍  Search ticker or query…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          className="bg-surface border border-border text-muted-foreground text-xs rounded-md px-3 py-1.5"
          value={stanceFilter}
          onChange={(e) => setStanceFilter(e.target.value)}
        >
          <option value="all">All stances</option>
          <option value="bullish">Bullish</option>
          <option value="bearish">Bearish</option>
          <option value="neutral">Neutral</option>
        </select>
      </div>

      <div className="flex items-center gap-3 px-4 py-2 border-b border-border text-[10px] uppercase tracking-widest text-muted">
        <span className="w-28">Ticker</span>
        <span className="flex-1">Query</span>
        <span className="w-16">Stance</span>
        <span className="w-10 text-right">Conf</span>
        <span className="w-14 text-right">Date</span>
      </div>

      <div className="flex-1 overflow-auto">
        {filtered.length === 0 && (
          <p className="text-center text-muted text-sm py-12">
            No runs yet — go to Analyze to run your first analysis.
          </p>
        )}
        {filtered.map((run) => (
          <div
            key={run.run_id}
            className="flex items-center gap-3 px-4 py-2.5 border-b border-[#0f1629] cursor-pointer hover:bg-surface transition-colors"
            onClick={() => router.push(`/analyze?run_id=${run.run_id}`)}
            tabIndex={0}
            role="button"
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') router.push(`/analyze?run_id=${run.run_id}`); }}
          >
            <span className="w-28 text-sm font-bold text-foreground truncate">{run.ticker}</span>
            <span className="flex-1 text-xs text-muted truncate">{run.query}</span>
            <span className="w-16">
              <Badge className={`text-[10px] font-bold ${stanceBadgeClass(run.stance)}`}>
                {run.stance.toUpperCase()}
              </Badge>
            </span>
            <span className={`w-10 text-right text-xs font-semibold ${confColor(run.confidence)}`}>
              {Math.round(run.confidence * 100)}%
            </span>
            <span className="w-14 text-right text-[11px] text-muted">
              {formatDate(run.created_at)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
