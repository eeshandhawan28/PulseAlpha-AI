import type { Metrics } from "@/lib/stream";

interface CardProps {
  label: string;
  value: string;
  sub?: string;
  accent: string;
  delay?: string;
}

function MetricCard({ label, value, sub, accent, delay = "0ms" }: CardProps) {
  return (
    <div
      className="fade-up relative bg-bg1 border border-border p-4 pt-5 flex flex-col gap-2 overflow-hidden"
      style={{ animationDelay: delay }}
    >
      {/* Top hairline accent */}
      <div
        className="absolute top-0 left-0 right-0 h-px"
        style={{
          background: `linear-gradient(90deg, ${accent}, transparent 70%)`,
        }}
      />

      <p className="text-[8px] uppercase tracking-[0.3em] font-body text-t3">
        {label}
      </p>

      <p
        className="font-display text-[26px] font-semibold leading-none tracking-tight"
        style={{ color: accent }}
      >
        {value}
      </p>

      {sub && (
        <p className="text-[10px] font-body font-light tracking-[0.08em] text-t3">
          {sub}
        </p>
      )}
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="bg-bg1 border border-border p-4 pt-5 flex flex-col gap-3">
      <div className="shimmer h-2 w-16" />
      <div className="shimmer h-7 w-24" />
      <div className="shimmer h-2 w-12" />
    </div>
  );
}

export default function MetricCards({ metrics }: { metrics: Metrics | null }) {
  if (!metrics) {
    return (
      <div className="grid grid-cols-4 gap-3 shrink-0">
        {[0, 1, 2, 3].map((i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    );
  }

  const { stance, confidence, divergence_score, rrg_quadrant } = metrics;

  const stanceAccent =
    stance === "bullish" ? "#8fc8a8" : stance === "bearish" ? "#d28a7c" : "#c9a96a";

  const confAccent =
    confidence >= 0.7 ? "#a9bdd4" : confidence >= 0.5 ? "#c9a96a" : "#d28a7c";
  const confSub =
    confidence >= 0.7
      ? "High conviction"
      : confidence >= 0.5
      ? "Medium conviction"
      : "Low conviction";

  const divAccent = divergence_score > 0.5 ? "#d28a7c" : "#a9bdd4";
  const divSub = divergence_score > 0.5 ? "High disagreement" : "Strong consensus";

  return (
    <div className="grid grid-cols-4 gap-3 shrink-0">
      <MetricCard
        label="Verdict"
        value={stance.charAt(0).toUpperCase() + stance.slice(1)}
        accent={stanceAccent}
        delay="0ms"
      />
      <MetricCard
        label="Conviction"
        value={`${Math.round(confidence * 100)}%`}
        sub={confSub}
        accent={confAccent}
        delay="80ms"
      />
      <MetricCard
        label="Divergence"
        value={divergence_score.toFixed(2)}
        sub={divSub}
        accent={divAccent}
        delay="160ms"
      />
      <MetricCard
        label="RRG Quadrant"
        value={rrg_quadrant}
        accent="#c9a96a"
        delay="240ms"
      />
    </div>
  );
}
