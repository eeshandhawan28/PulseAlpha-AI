"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import MetricCards from "@/components/MetricCards";
import ReportViewer from "@/components/ReportViewer";
import Sidebar from "@/components/Sidebar";
import StepTracker from "@/components/StepTracker";
import { fetchHistoryRun } from "@/lib/api";
import { useAnalysisStream } from "@/lib/stream";

// ── Suggested NIFTY 50 stocks ────────────────────────────────────────────
const SUGGESTED = [
  { ticker: "RELIANCE.NS", sym: "RELIANCE", name: "Reliance", color: "#f97316" },
  { ticker: "HDFCBANK.NS", sym: "HDFCBANK", name: "HDFC Bank", color: "#60a5fa" },
  { ticker: "TCS.NS",      sym: "TCS",      name: "TCS",       color: "#a78bfa" },
  { ticker: "INFY.NS",     sym: "INFY",     name: "Infosys",   color: "#a78bfa" },
  { ticker: "ICICIBANK.NS",sym: "ICICIBANK",name: "ICICI Bank",color: "#60a5fa" },
  { ticker: "BAJFINANCE.NS",sym:"BAJFIN",   name: "Bajaj Fin", color: "#34d399" },
  { ticker: "TITAN.NS",    sym: "TITAN",    name: "Titan",     color: "#fbbf24" },
  { ticker: "ITC.NS",      sym: "ITC",      name: "ITC",       color: "#fb7185" },
  { ticker: "SBIN.NS",     sym: "SBIN",     name: "SBI",       color: "#60a5fa" },
  { ticker: "HINDUNILVR.NS",sym:"HUL",      name: "HUL",       color: "#fb7185" },
  { ticker: "WIPRO.NS",    sym: "WIPRO",    name: "Wipro",     color: "#a78bfa" },
  { ticker: "MARUTI.NS",   sym: "MARUTI",   name: "Maruti",    color: "#22d3ee" },
  { ticker: "KOTAKBANK.NS",sym: "KOTAK",    name: "Kotak Bank",color: "#60a5fa" },
  { ticker: "ASIANPAINT.NS",sym:"ASIANPNT", name: "Asian Paint",color: "#fbbf24" },
  { ticker: "BHARTIARTL.NS",sym:"AIRTEL",   name: "Airtel",    color: "#f97316" },
  { ticker: "DRREDDY.NS",  sym: "DRREDDY",  name: "Dr Reddy",  color: "#34d399" },
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

  // Cycle placeholder query text
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
      {/* Background orbs */}
      <div className="hero-orb hero-orb-1" />
      <div className="hero-orb hero-orb-2" />
      <div className="hero-orb hero-orb-3" />

      {/* Center content */}
      <div className="hero-content relative z-10 flex flex-col items-center gap-10 w-full max-w-[680px] px-6">

        {/* Brand header */}
        <div className="text-center flex flex-col items-center gap-2">
          <div className="flex items-center gap-2 mb-1">
            <div className="w-8 h-8 rounded-lg bg-amber-dim border border-amber/30 flex items-center justify-center">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M2 11l3-4.5 3 2.5 3-5.5 3 3.5" stroke="#f59e0b" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <span className="font-display font-extrabold text-xl tracking-tight text-t1">PulseAlpha</span>
          </div>
          <p className="text-t3 font-body text-sm tracking-wide">
            AI equity research · Indian markets · Real-time analysis
          </p>
        </div>

        {/* Search block */}
        <div className="w-full flex flex-col gap-3">
          <div className="hero-search-group flex gap-2 items-stretch w-full">
            <input
              className="w-[155px] h-12 bg-bg1 border border-border rounded-xl px-4 font-mono text-sm text-t1 placeholder:text-t3 focus:outline-none focus:border-amber/60 focus:bg-bg2 transition-all"
              placeholder="TICKER.NS"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              onKeyDown={(e) => e.key === "Enter" && ticker.trim() && onRun()}
              spellCheck={false}
              autoComplete="off"
            />
            <input
              ref={queryRef}
              className="flex-1 h-12 bg-bg1 border border-border rounded-xl px-4 font-body text-sm text-t1 placeholder:text-t3 focus:outline-none focus:border-amber/60 focus:bg-bg2 transition-all"
              placeholder={ROTATING_QUERIES[qIdx]}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && ticker.trim() && onRun()}
            />
            <button
              onClick={onRun}
              disabled={!ticker.trim()}
              className={`h-12 px-6 rounded-xl font-display font-bold text-sm flex items-center gap-2 transition-all duration-200 shrink-0 ${
                ticker.trim()
                  ? "bg-amber text-bg0 hover:bg-amber/90 shadow-[0_0_32px_rgba(245,158,11,0.35)] hover:shadow-[0_0_48px_rgba(245,158,11,0.5)]"
                  : "bg-bg2 border border-border text-t3 cursor-not-allowed"
              }`}
            >
              <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                <path d="M3 2l8 4.5L3 11V2z" fill="currentColor" />
              </svg>
              Run Analysis
            </button>
          </div>

          {error && (
            <div className="w-full px-4 py-2.5 rounded-xl bg-rose-dim border border-rose/20 text-rose text-xs font-body flex items-center gap-2">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <circle cx="6" cy="6" r="5" stroke="currentColor" strokeWidth="1.3" />
                <path d="M6 4v2.5M6 8h.01" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
              </svg>
              {error}
            </div>
          )}
        </div>

        {/* Suggested stocks */}
        <div className="w-full flex flex-col items-center gap-4">
          <div className="flex items-center gap-3 w-full">
            <div className="flex-1 h-px bg-border" />
            <span className="text-[10px] uppercase tracking-[0.22em] text-t3 font-body shrink-0">
              Quick access — NIFTY 50
            </span>
            <div className="flex-1 h-px bg-border" />
          </div>

          <div className="flex flex-wrap justify-center gap-2">
            {SUGGESTED.map((s) => (
              <button
                key={s.ticker}
                onClick={() => pickStock(s)}
                className="stock-chip"
                style={
                  {
                    "--chip-color": s.color,
                    borderColor: ticker === s.ticker ? s.color : undefined,
                    background:
                      ticker === s.ticker
                        ? `${s.color}18`
                        : undefined,
                    boxShadow:
                      ticker === s.ticker
                        ? `0 0 14px ${s.color}30`
                        : undefined,
                  } as React.CSSProperties
                }
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLButtonElement).style.borderColor = s.color;
                  (e.currentTarget as HTMLButtonElement).style.boxShadow = `0 0 14px ${s.color}28`;
                }}
                onMouseLeave={(e) => {
                  if (ticker !== s.ticker) {
                    (e.currentTarget as HTMLButtonElement).style.borderColor = "";
                    (e.currentTarget as HTMLButtonElement).style.boxShadow = "";
                  }
                }}
              >
                {/* Sector dot */}
                <span
                  className="w-[5px] h-[5px] rounded-full shrink-0"
                  style={{ background: s.color }}
                />
                <span className="font-mono text-[11px] font-semibold text-t1">{s.sym}</span>
                <span className="text-[10px] text-t3">{s.name}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Hint */}
        <p className="text-[10px] text-t3 font-body tracking-wide">
          Press{" "}
          <kbd className="px-1.5 py-0.5 bg-bg2 border border-border rounded text-[10px] font-mono text-t2">
            Enter
          </kbd>{" "}
          to run · Results stream in real-time
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
  const { steps, metrics, reportText, isStreaming, error, start, reset } =
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
        /* ── Hero (idle) state ── */
        <HeroState
          ticker={ticker}
          setTicker={setTicker}
          query={query}
          setQuery={setQuery}
          onRun={handleRun}
          error={error}
        />
      ) : (
        /* ── Analysis state ── */
        <div className="flex flex-col flex-1 min-w-0">
          {/* Compact query bar */}
          <div className="flex gap-2 items-center px-4 py-2.5 border-b border-border bg-bg1 shrink-0">
            {/* Back to hero */}
            {!isStreaming && (
              <button
                onClick={() => {
                  reset();
                  setLoadedReport(null);
                  setLoadedTicker(null);
                  setLoadedStance(null);
                }}
                title="New analysis"
                className="w-7 h-7 flex items-center justify-center rounded-md border border-border text-t3 hover:text-t1 hover:border-border-active transition-colors shrink-0"
              >
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M5 2H2v3M2 2l4 4M10 6A5 5 0 115 1" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            )}

            <input
              className="w-36 h-8 bg-bg2 border border-border rounded-lg px-3 font-mono text-xs text-t1 placeholder:text-t3 focus:outline-none focus:border-amber/50 transition-all"
              placeholder="RELIANCE.NS"
              value={ticker}
              onChange={(e) => setTicker(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isStreaming}
            />
            <input
              className="flex-1 h-8 bg-bg2 border border-border rounded-lg px-3 font-body text-xs text-t1 placeholder:text-t3 focus:outline-none focus:border-amber/50 transition-all"
              placeholder="What is the Q3 outlook for this stock?"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isStreaming}
            />
            <button
              onClick={isStreaming ? reset : handleRun}
              disabled={!isStreaming && !ticker.trim()}
              className={`h-8 px-4 rounded-lg font-display font-bold text-xs transition-all flex items-center gap-1.5 shrink-0 ${
                isStreaming
                  ? "bg-bg2 border border-rose/30 text-rose hover:border-rose/60"
                  : !ticker.trim()
                  ? "bg-bg2 border border-border text-t3 cursor-not-allowed"
                  : "bg-amber text-bg0 hover:bg-amber/90 shadow-[0_0_16px_rgba(245,158,11,0.3)]"
              }`}
            >
              {isStreaming ? (
                <>
                  <span className="w-1.5 h-1.5 rounded-full bg-rose animate-pulse" />
                  Stop
                </>
              ) : (
                <>
                  <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                    <path d="M2.5 1.5l6 3.5-6 3.5V1.5z" fill="currentColor" />
                  </svg>
                  Run
                </>
              )}
            </button>
          </div>

          {error && (
            <div className="mx-4 mt-2 px-3 py-2 rounded-lg bg-rose-dim border border-rose/20 text-rose text-xs font-body flex items-center gap-2 shrink-0">
              <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
                <circle cx="5.5" cy="5.5" r="4.5" stroke="currentColor" strokeWidth="1.2" />
                <path d="M5.5 3.5v2.5M5.5 7.5h.01" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
              </svg>
              {error}
            </div>
          )}

          {/* Main body */}
          <div className="flex flex-1 min-h-0">
            <StepTracker steps={steps} isStreaming={isStreaming} />
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
