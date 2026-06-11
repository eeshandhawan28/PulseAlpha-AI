"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import ChartsPanel from "@/components/ChartsPanel";
import MetricCards from "@/components/MetricCards";
import RAGEvidencePanel from "@/components/RAGEvidencePanel";
import ReportViewer from "@/components/ReportViewer";
import Sidebar from "@/components/Sidebar";
import StepTracker from "@/components/StepTracker";
import { fetchHistoryRun } from "@/lib/api";
import { useAnalysisStream } from "@/lib/stream";

// ── Suggested NIFTY 50 stocks ────────────────────────────────────────────
const SUGGESTED = [
  { ticker: "RELIANCE.NS",   sym: "RELIANCE",  name: "Reliance" },
  { ticker: "HDFCBANK.NS",   sym: "HDFCBANK",  name: "HDFC Bank" },
  { ticker: "TCS.NS",        sym: "TCS",       name: "TCS" },
  { ticker: "INFY.NS",       sym: "INFY",      name: "Infosys" },
  { ticker: "ICICIBANK.NS",  sym: "ICICIBANK", name: "ICICI Bank" },
  { ticker: "BAJFINANCE.NS", sym: "BAJFIN",    name: "Bajaj Fin" },
  { ticker: "TITAN.NS",      sym: "TITAN",     name: "Titan" },
  { ticker: "ITC.NS",        sym: "ITC",       name: "ITC" },
  { ticker: "SBIN.NS",       sym: "SBIN",      name: "SBI" },
  { ticker: "HINDUNILVR.NS", sym: "HUL",       name: "HUL" },
  { ticker: "WIPRO.NS",      sym: "WIPRO",     name: "Wipro" },
  { ticker: "MARUTI.NS",     sym: "MARUTI",    name: "Maruti" },
  { ticker: "KOTAKBANK.NS",  sym: "KOTAK",     name: "Kotak Bank" },
  { ticker: "ASIANPAINT.NS", sym: "ASIANPNT",  name: "Asian Paint" },
  { ticker: "BHARTIARTL.NS", sym: "AIRTEL",    name: "Airtel" },
  { ticker: "DRREDDY.NS",    sym: "DRREDDY",   name: "Dr Reddy" },
];

const ROTATING_QUERIES = [
  "What is the Q4 outlook for this stock?",
  "Analyze momentum and institutional flows",
  "Is this a good entry point right now?",
  "What are the key risks for this position?",
  "Evaluate long-term growth prospects",
];

// ── Hero / Idle state ────────────────────────────────────────────────────
function HeroState({
  ticker,
  setTicker,
  query,
  setQuery,
  onRun,
  error,
}: {
  ticker: string;
  setTicker: (t: string) => void;
  query: string;
  setQuery: (q: string) => void;
  onRun: () => void;
  error: string | null;
}) {
  const [qIdx, setQIdx] = useState(0);
  const queryRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const t = setInterval(() => setQIdx((i) => (i + 1) % ROTATING_QUERIES.length), 3500);
    return () => clearInterval(t);
  }, []);

  const pickStock = (s: (typeof SUGGESTED)[0]) => {
    setTicker(s.ticker);
    if (!query) setQuery("Analyze the investment case and near-term outlook");
    queryRef.current?.focus();
  };

  return (
    <div className="flex-1 flex flex-col items-center justify-center relative overflow-hidden">
      <div className="hero-glow" />

      <div className="hero-stagger relative z-10 flex flex-col items-center gap-10 w-full max-w-[760px] px-8">
        {/* Maison plate */}
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="flex items-center gap-4">
            <span className="diamond" />
            <span className="font-body text-[10px] font-medium uppercase tracking-[0.45em] text-gold">
              PulseAlpha
            </span>
            <span className="diamond" />
          </div>
          <h1 className="font-display text-[52px] leading-[1.08] font-medium text-t1 tracking-tight">
            Research worthy of{" "}
            <em className="gold-text font-semibold">conviction</em>.
          </h1>
          <p className="font-body font-light text-sm text-t2 tracking-[0.08em] max-w-md">
            A private intelligence desk for Indian equities — five analyst
            minds, one verdict, delivered in real time.
          </p>
        </div>

        {/* Commission panel */}
        <div className="framed w-full bg-bg1/80 backdrop-blur-sm px-8 pt-7 pb-8 flex flex-col gap-6">
          <div className="flex gap-8 items-end">
            <div className="flex flex-col gap-1 w-[170px] shrink-0">
              <label className="font-body text-[9px] uppercase tracking-[0.3em] text-t3">
                Instrument
              </label>
              <input
                className="lux-input font-mono text-sm w-full"
                placeholder="TICKER.NS"
                value={ticker}
                onChange={(e) => setTicker(e.target.value.toUpperCase())}
                onKeyDown={(e) => e.key === "Enter" && ticker.trim() && onRun()}
                spellCheck={false}
                autoComplete="off"
              />
            </div>
            <div className="flex flex-col gap-1 flex-1 min-w-0">
              <label className="font-body text-[9px] uppercase tracking-[0.3em] text-t3">
                Mandate
              </label>
              <input
                ref={queryRef}
                className="lux-input font-body font-light text-sm w-full"
                placeholder={ROTATING_QUERIES[qIdx]}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && ticker.trim() && onRun()}
              />
            </div>
          </div>

          <button
            onClick={onRun}
            disabled={!ticker.trim()}
            className="gold-cta h-12 w-full font-body font-medium text-[12px] uppercase tracking-[0.35em] flex items-center justify-center gap-3"
          >
            Commission Analysis
            <svg width="14" height="8" viewBox="0 0 14 8" fill="none">
              <path d="M0 4h12M9 1l3 3-3 3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>

          {error && (
            <div className="w-full px-4 py-2.5 bg-blood-dim border border-blood/25 text-blood text-xs font-body flex items-center gap-2">
              <span className="diamond" style={{ background: "var(--blood)" }} />
              {error}
            </div>
          )}
        </div>

        {/* Quick access */}
        <div className="w-full flex flex-col items-center gap-5">
          <div className="ornament-rule">
            <span className="diamond" />
            <span className="font-body text-[9px] uppercase tracking-[0.35em] text-t3 shrink-0">
              The Watchlist · NIFTY 50
            </span>
            <span className="diamond" />
          </div>

          <div className="flex flex-wrap justify-center gap-2">
            {SUGGESTED.map((s) => (
              <button
                key={s.ticker}
                onClick={() => pickStock(s)}
                className={`stock-chip ${ticker === s.ticker ? "selected" : ""}`}
              >
                <span className="font-mono text-[11px] font-medium text-t1">{s.sym}</span>
                <span className="font-body font-light text-[10px] text-t3">{s.name}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Hint */}
        <p className="text-[10px] text-t3 font-body font-light tracking-[0.15em]">
          Press{" "}
          <kbd className="px-1.5 py-0.5 bg-bg2 border border-border text-[10px] font-mono text-t2">
            Enter
          </kbd>{" "}
          to commission · the desk reports in real time
        </p>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────
function AnalyzeContent() {
  const searchParams = useSearchParams();
  const runId = searchParams.get("run_id");

  const [ticker, setTicker] = useState("");
  const [query, setQuery] = useState("");
  const { steps, metrics, reportText, charts, ragEvidence, isStreaming, error, start, reset } =
    useAnalysisStream();
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
    return () => {
      ignore = true;
    };
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

  const isIdle =
    steps.length === 0 && !displayReport && !isStreaming && !runId;

  return (
    <div className="flex h-screen overflow-hidden bg-bg0">
      <Sidebar />

      {isIdle ? (
        <HeroState
          ticker={ticker}
          setTicker={setTicker}
          query={query}
          setQuery={setQuery}
          onRun={handleRun}
          error={error}
        />
      ) : (
        <div className="flex flex-col flex-1 min-w-0">
          {/* Compact commission bar */}
          <div className="flex gap-3 items-center px-5 py-3 border-b border-border bg-bg1 shrink-0">
            {!isStreaming && (
              <button
                onClick={() => {
                  reset();
                  setLoadedReport(null);
                  setLoadedTicker(null);
                  setLoadedStance(null);
                }}
                title="New analysis"
                className="w-7 h-7 flex items-center justify-center border border-border text-t3 hover:text-gold hover:border-gold/50 transition-colors shrink-0"
              >
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M5 2H2v3M2 2l4 4M10 6A5 5 0 115 1" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            )}

            <input
              className="lux-input w-40 font-mono text-xs"
              placeholder="RELIANCE.NS"
              value={ticker}
              onChange={(e) => setTicker(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isStreaming}
            />
            <input
              className="lux-input flex-1 font-body font-light text-xs"
              placeholder="What is the Q3 outlook for this stock?"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isStreaming}
            />
            <button
              onClick={isStreaming ? reset : handleRun}
              disabled={!isStreaming && !ticker.trim()}
              className={`h-8 px-5 font-body font-medium text-[10px] uppercase tracking-[0.25em] transition-all flex items-center gap-2 shrink-0 ${
                isStreaming
                  ? "bg-bg2 border border-blood/40 text-blood hover:border-blood/70"
                  : !ticker.trim()
                  ? "bg-bg2 border border-border text-t3 cursor-not-allowed"
                  : "gold-cta"
              }`}
            >
              {isStreaming ? (
                <>
                  <span className="w-1.5 h-1.5 rounded-full bg-blood animate-pulse" />
                  Halt
                </>
              ) : (
                "Run"
              )}
            </button>
          </div>

          {error && (
            <div className="mx-5 mt-3 px-4 py-2.5 bg-blood-dim border border-blood/25 text-blood text-xs font-body flex items-center gap-2 shrink-0">
              <span className="diamond" style={{ background: "var(--blood)" }} />
              {error}
            </div>
          )}

          {/* Main body */}
          <div className="flex flex-1 min-h-0">
            <StepTracker steps={steps} isStreaming={isStreaming} />
            <div className="flex flex-col flex-1 min-h-0 min-w-0">
              {/* Metrics — fixed at top */}
              <div className="px-5 pt-5 pb-3 shrink-0">
                <MetricCards metrics={metrics} />
              </div>
              {/* Scrollable content area: charts → report → RAG evidence */}
              <div className="flex-1 overflow-y-auto px-5 pb-5 flex flex-col gap-4 min-h-0">
                <ChartsPanel charts={charts} />
                <ReportViewer
                  ticker={displayTicker}
                  stance={displayStance}
                  reportText={displayReport}
                  isStreaming={isStreaming}
                />
                {ragEvidence && <RAGEvidencePanel evidence={ragEvidence} />}
              </div>
            </div>
          </div>
        </div>
      )}
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
