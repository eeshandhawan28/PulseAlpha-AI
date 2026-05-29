import type { Metrics } from "@/lib/stream";

interface CardProps {
  label: string;
  value: string;
  sub?: string;
  accent: string;
  bg: string;
  delay?: string;
}

function MetricCard({ label, value, sub, accent, bg, delay = "0ms" }: CardProps) {
  return (
    <div
      className={`fade-up rounded-lg border p-3 flex flex-col gap-1 ${bg}`}
      style={{ animationDelay: delay, borderColor: accent + "33" }}
    >
      <p className="text-[9px] uppercase tracking-[0.18em] font-body" style={{ color: accent }}>
        {label}
      </p>
      <p className="font-mono text-xl font-semibold text-t1 leading-none">{value}</p>
      {sub && <p className="text-[10px] text-t3 font-body">{sub}</p>}
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="rounded-lg border border-border p-3 flex flex-col gap-2">
      <div className="shimmer h-2 w-14 rounded" />
      <div className="shimmer h-6 w-20 rounded" />
    </div>
  );
}

export default function MetricCards({ metrics }: { metrics: Metrics | null }) {
  if (!metrics) {
    return (
      <div className="grid grid-cols-4 gap-2">
        {[0, 1, 2, 3].map((i) => <SkeletonCard key={i} />)}
      </div>
    );
  }

  const { stance, confidence, divergence_score, rrg_quadrant } = metrics;

  const stanceAccent =
    stance === "bullish" ? "#34d399" : stance === "bearish" ? "#f87171" : "#f59e0b";
  const stanceBg =
    stance === "bullish" ? "bg-emerald-dim" : stance === "bearish" ? "bg-rose-dim" : "bg-amber-dim";

  const confAccent = confidence >= 0.7 ? "#60a5fa" : confidence >= 0.5 ? "#f59e0b" : "#f87171";

  const quadrantAccent = "#a78bfa";

  return (
    <div className="grid grid-cols-4 gap-2">
      <MetricCard
        label="Stance"
        value={stance.toUpperCase()}
        accent={stanceAccent}
        bg={stanceBg}
        delay="0ms"
      />
      <MetricCard
        label="Confidence"
        value={`${Math.round(confidence * 100)}%`}
        sub={confidence >= 0.7 ? "High" : confidence >= 0.5 ? "Medium" : "Low"}
        accent={confAccent}
        bg="bg-ice-dim"
        delay="60ms"
      />
      <MetricCard
        label="Divergence"
        value={divergence_score.toFixed(3)}
        sub={divergence_score > 0.5 ? "High disagreement" : "Consensus"}
        accent="#a78bfa"
        bg="bg-[rgba(167,139,250,0.08)]"
        delay="120ms"
      />
      <MetricCard
        label="RRG Quadrant"
        value={rrg_quadrant}
        accent={quadrantAccent}
        bg="bg-[rgba(167,139,250,0.08)]"
        delay="180ms"
      />
    </div>
  );
}
