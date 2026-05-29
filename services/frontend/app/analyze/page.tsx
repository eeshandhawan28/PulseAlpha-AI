"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import MetricCards from "@/components/MetricCards";
import ReportViewer from "@/components/ReportViewer";
import Sidebar from "@/components/Sidebar";
import StepTracker from "@/components/StepTracker";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
    if (e.key === "Enter") handleRun();
  };

  const displayTicker = loadedTicker ?? ticker;
  const displayStance = loadedStance ?? metrics?.stance ?? null;
  const displayReport = loadedReport ?? reportText;

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex flex-col flex-1 min-w-0">
        <div className="flex gap-2 px-4 py-3 border-b border-border">
          <Input
            className="w-40 bg-surface border-border text-foreground placeholder:text-muted"
            placeholder="RELIANCE.NS"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isStreaming}
          />
          <Input
            className="flex-1 bg-surface border-border text-foreground placeholder:text-muted"
            placeholder="What's the Q3 outlook?"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isStreaming}
          />
          <Button
            onClick={isStreaming ? reset : handleRun}
            disabled={!ticker.trim() && !isStreaming}
            className={
              isStreaming
                ? "bg-blue-900 text-blue-300 hover:bg-blue-800"
                : "bg-blue-800 text-blue-100 hover:bg-blue-700"
            }
          >
            {isStreaming ? "⏹ Stop" : "▶ Run"}
          </Button>
        </div>

        {error && (
          <div className="mx-4 mt-2 p-2 rounded bg-red-950 border border-red-800 text-red-400 text-xs">
            {error}
          </div>
        )}

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
