"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import MetricCards from "@/components/MetricCards";
import ReportViewer from "@/components/ReportViewer";
import Sidebar from "@/components/Sidebar";
import StepTracker from "@/components/StepTracker";
import { fetchHistoryRun } from "@/lib/api";
import { useAnalysisStream } from "@/lib/stream";

function AnalyzeContent() {
  const searchParams = useSearchParams();
  const runId = searchParams.get("run_id");

  const [ticker, setTicker] = useState("");
  const [query, setQuery] = useState("");
  const { steps, metrics, reportText, isStreaming, error, start, reset } = useAnalysisStream();
  const [loadedReport, setLoadedReport] = useState<string | null>(null);
  const [loadedTicker, setLoadedTicker] = useState<string | null>(null);
  const [loadedStance, setLoadedStance] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) return;
    let ignore = false;
    fetchHistoryRun(runId).then((run) => {
      if (ignore || !run) return;
      setLoadedTicker(run.ticker);
      setLoadedStance(run.stance);
      setLoadedReport(run.report);
      setTicker(run.ticker);
      setQuery(run.query);
    });
    return () => { ignore = true; };
  }, [runId]);

  const handleRun = () => {
    if (!ticker.trim() || isStreaming) return;
    setLoadedReport(null);
    setLoadedTicker(null);
    setLoadedStance(null);
    start(ticker, query || "Analyze this ticker");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && ticker.trim()) handleRun();
  };

  const displayTicker = loadedTicker ?? ticker;
  const displayStance = loadedStance ?? metrics?.stance ?? null;
  const displayReport = loadedReport ?? reportText;

  return (
    <div className="flex h-screen overflow-hidden bg-bg0">
      <Sidebar />
      <div className="flex flex-col flex-1 min-w-0">

        {/* Query bar */}
        <div className="flex gap-2 items-center px-4 py-3 border-b border-border bg-bg1 shrink-0">
          <div className="relative">
            <input
              className="w-36 h-9 bg-bg2 border border-border rounded-md px-3 font-mono text-sm text-t1 placeholder:text-t3 focus:outline-none focus:border-border-active transition-colors"
              placeholder="RELIANCE.NS"
              value={ticker}
              onChange={(e) => setTicker(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isStreaming}
            />
          </div>
          <input
            className="flex-1 h-9 bg-bg2 border border-border rounded-md px-3 font-body text-sm text-t1 placeholder:text-t3 focus:outline-none focus:border-border-active transition-colors"
            placeholder="What is the Q3 outlook for this stock?"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isStreaming}
          />
          <button
            onClick={isStreaming ? reset : handleRun}
            disabled={!isStreaming && !ticker.trim()}
            className={`h-9 px-5 rounded-md font-display font-bold text-sm transition-all duration-200 flex items-center gap-2 shrink-0 ${
              isStreaming
                ? "bg-bg2 border border-border text-t2 hover:border-rose/40 hover:text-rose"
                : !ticker.trim()
                ? "bg-bg2 border border-border text-t3 cursor-not-allowed"
                : "bg-amber text-bg0 hover:bg-amber/90 shadow-[0_0_20px_rgba(245,158,11,0.25)]"
            }`}
          >
            {isStreaming ? (
              <>
                <span className="w-1.5 h-1.5 rounded-full bg-rose animate-pulse" />
                Stop
              </>
            ) : (
              <>
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M3 2l7 4-7 4V2z" fill="currentColor" />
                </svg>
                Run
              </>
            )}
          </button>
        </div>

        {error && (
          <div className="mx-4 mt-3 px-4 py-2.5 rounded-lg bg-rose-dim border border-rose/20 text-rose text-xs font-body flex items-center gap-2">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <circle cx="6" cy="6" r="5" stroke="currentColor" strokeWidth="1.3"/>
              <path d="M6 4v2.5M6 8h.01" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
            </svg>
            {error}
          </div>
        )}

        {/* Main content */}
        <div className="flex flex-1 min-h-0">
          <StepTracker steps={steps} />
          <div className="flex flex-col flex-1 gap-3 p-4 min-h-0 min-w-0">
            <MetricCards metrics={metrics} />
            <ReportViewer
              ticker={displayTicker}
              stance={displayStance}
              reportText={displayReport}
              isStreaming={isStreaming}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export default function AnalyzePage() {
  return (
    <Suspense>
      <AnalyzeContent />
    </Suspense>
  );
}
