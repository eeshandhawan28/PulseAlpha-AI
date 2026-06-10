import type { Metrics } from "@/lib/stream";

interface CardProps {
  label: string;
  value: string;
  sub?: string;
  accent: string;
  glowClass: string;
  icon: React.ReactNode;
  delay?: string;
}

function MetricCard({ label, value, sub, accent, glowClass, icon, delay = "0ms" }: CardProps) {
  return (
    <div
      className={`fade-up relative rounded-xl border p-4 flex flex-col gap-2 overflow-hidden ${glowClass}`}
      style={{ animationDelay: delay, borderColor: accent + "28", background: accent + "08" }}
    >
      {/* Subtle corner accent */}
      <div
        className="absolute top-0 right-0 w-16 h-16 rounded-bl-full opacity-10"
        style={{ background: `radial-gradient(circle at top right, ${accent}, transparent)` }}
      />

      <div className="flex items-center justify-between">
        <p className="text-[9px] uppercase tracking-[0.22em] font-body font-medium" style={{ color: accent + "cc" }}>
          {label}
        </p>
        <div style={{ color: accent + "80" }}>{icon}</div>
      </div>

      <p className="font-mono text-2xl font-bold text-t1 leading-none tracking-tight" style={{ color: accent }}>
        {value}
      </p>

      {sub && (
        <p className="text-[10px] font-body" style={{ color: accent + "80" }}>
          {sub}
        </p>
      )}
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="rounded-xl border border-border p-4 flex flex-col gap-3 bg-bg1">
      <div className="shimmer h-2 w-16 rounded" />
      <div className="shimmer h-7 w-24 rounded" />
      <div className="shimmer h-2 w-12 rounded" />
    </div>
  );
}

// Icons
const StanceIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
    <path d="M2 10l3-4 3 2.5 4-5.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const ConfidenceIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
    <circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth="1.3" />
    <path d="M7 4.5v3l2 1.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
  </svg>
);

const DivergenceIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
    <path d="M2 7h3M9 7h3M7 2v3M7 9v3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    <circle cx="7" cy="7" r="2" stroke="currentColor" strokeWidth="1.3" />
  </svg>
);

const RRGIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
    <rect x="2" y="2" width="4" height="4" rx="1" stroke="currentColor" strokeWidth="1.3" />
    <rect x="8" y="2" width="4" height="4" rx="1" stroke="currentColor" strokeWidth="1.3" />
    <rect x="2" y="8" width="4" height="4" rx="1" stroke="currentColor" strokeWidth="1.3" />
    <rect x="8" y="8" width="4" height="4" rx="1" stroke="currentColor" strokeWidth="1.3" />
  </svg>
);

export default function MetricCards({ metrics }: { metrics: Metrics | null }) {
  if (!metrics) {
    return (
      <div className="grid grid-cols-4 gap-2 shrink-0">
        {[0, 1, 2, 3].map((i) => <SkeletonCard key={i} />)}
      </div>
    );
  }

  const { stance, confidence, divergence_score, rrg_quadrant } = metrics;

  const stanceAccent =
    stance === "bullish" ? "#34d399" : stance === "bearish" ? "#f87171" : "#f59e0b";
  const stanceGlow =
    stance === "bullish"
      ? "metric-card-bullish"
      : stance === "bearish"
      ? "metric-card-bearish"
      : "metric-card-neutral";

  const confAccent = confidence >= 0.7 ? "#60a5fa" : confidence >= 0.5 ? "#f59e0b" : "#f87171";
  const confSub = confidence >= 0.7 ? "High conviction" : confidence >= 0.5 ? "Medium conviction" : "Low conviction";

  const divAccent = divergence_score > 0.5 ? "#f87171" : "#a78bfa";
  const divSub = divergence_score > 0.5 ? "High disagreement" : "Strong consensus";

  return (
    <div className="grid grid-cols-4 gap-2 shrink-0">
      <MetricCard
        label="Stance"
        value={stance.charAt(0).toUpperCase() + stance.slice(1)}
        accent={stanceAccent}
        glowClass={stanceGlow}
        icon={<StanceIcon />}
        delay="0ms"
      />
      <MetricCard
        label="Confidence"
        value={`${Math.round(confidence * 100)}%`}
        sub={confSub}
        accent={confAccent}
        glowClass=""
        icon={<ConfidenceIcon />}
        delay="60ms"
      />
      <MetricCard
        label="Divergence"
        value={divergence_score.toFixed(2)}
        sub={divSub}
        accent={divAccent}
        glowClass=""
        icon={<DivergenceIcon />}
        delay="120ms"
      />
      <MetricCard
        label="RRG Quadrant"
        value={rrg_quadrant}
        accent="#a78bfa"
        glowClass=""
        icon={<RRGIcon />}
        delay="180ms"
      />
    </div>
  );
}
