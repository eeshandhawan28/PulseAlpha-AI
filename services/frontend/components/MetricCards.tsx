import { Metrics } from "@/lib/stream";

interface Card {
  label: string;
  value: string;
  color: string;
}

function stanceColor(stance: string): string {
  if (stance === "bullish") return "text-green-400";
  if (stance === "bearish") return "text-red-400";
  return "text-yellow-400";
}

function toCards(metrics: Metrics): Card[] {
  return [
    {
      label: "Stance",
      value: metrics.stance.toUpperCase(),
      color: stanceColor(metrics.stance),
    },
    {
      label: "Confidence",
      value: `${Math.round(metrics.confidence * 100)}%`,
      color: "text-blue-400",
    },
    {
      label: "Divergence",
      value: metrics.divergence_score.toFixed(2),
      color: "text-purple-400",
    },
    {
      label: "RRG Quad",
      value: metrics.rrg_quadrant,
      color: "text-yellow-400",
    },
  ];
}

function EmptyCard({ label }: { label: string }) {
  return (
    <div className="bg-surface border border-border rounded-lg px-3 py-2">
      <p className="text-[10px] uppercase tracking-wide text-muted">{label}</p>
      <div className="mt-1 h-5 w-12 bg-border rounded animate-pulse" />
    </div>
  );
}

const EMPTY_LABELS = ["Stance", "Confidence", "Divergence", "RRG Quad"];

export default function MetricCards({ metrics }: { metrics: Metrics | null }) {
  if (!metrics) {
    return (
      <div className="grid grid-cols-4 gap-2">
        {EMPTY_LABELS.map((l) => (
          <EmptyCard key={l} label={l} />
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-4 gap-2">
      {toCards(metrics).map((card) => (
        <div key={card.label} className="bg-surface border border-border rounded-lg px-3 py-2">
          <p className="text-[10px] uppercase tracking-wide text-muted">{card.label}</p>
          <p className={`text-lg font-bold mt-0.5 ${card.color}`}>{card.value}</p>
        </div>
      ))}
    </div>
  );
}
