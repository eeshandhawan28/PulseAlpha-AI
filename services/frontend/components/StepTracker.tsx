import type { Step, StepStatus } from "@/lib/stream";

function StepIcon({ status, index }: { status: StepStatus; index: number }) {
  if (status === "done") {
    return (
      <div className="relative flex items-center justify-center w-6 h-6 rounded-full bg-emerald-dim border border-emerald/40 shrink-0">
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
          <path d="M1.5 5l2.5 2.5 4.5-4.5" stroke="#34d399" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
    );
  }
  if (status === "active") {
    return (
      <div className="pulse-ring relative flex items-center justify-center w-6 h-6 rounded-full bg-amber-dim border border-amber shrink-0">
        <span className="w-1.5 h-1.5 rounded-full bg-amber animate-pulse" />
      </div>
    );
  }
  return (
    <div className="relative flex items-center justify-center w-6 h-6 rounded-full border border-border shrink-0">
      <span className="text-t3 font-mono text-[9px]">{index + 1}</span>
    </div>
  );
}

export default function StepTracker({
  steps,
  isStreaming,
}: {
  steps: Step[];
  isStreaming: boolean;
}) {
  const doneCount = steps.filter((s) => s.status === "done").length;
  const total = steps.length;

  return (
    <div className="w-44 min-w-44 border-r border-border flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-4 pt-4 pb-3 border-b border-border shrink-0">
        <div className="flex items-center justify-between mb-1.5">
          <p className="font-display text-[9px] uppercase tracking-[0.2em] text-t3">
            Pipeline
          </p>
          {isStreaming && (
            <span className="flex items-center gap-1">
              <span className="w-1 h-1 rounded-full bg-amber animate-pulse" />
              <span className="text-[8px] text-amber/70 font-mono uppercase tracking-wider">Live</span>
            </span>
          )}
          {!isStreaming && total > 0 && (
            <span className="text-[8px] text-t3 font-mono">{doneCount}/{total}</span>
          )}
        </div>

        {/* Progress bar */}
        {total > 0 && (
          <div className="h-0.5 bg-border rounded-full overflow-hidden">
            <div
              className="h-full bg-amber rounded-full transition-all duration-500"
              style={{ width: `${(doneCount / total) * 100}%` }}
            />
          </div>
        )}
      </div>

      {/* Steps */}
      <div className="flex-1 overflow-y-auto px-2 py-2">
        <div className="relative flex flex-col">
          {/* Connecting line */}
          {steps.length > 1 && (
            <div className="absolute left-[19px] top-6 bottom-6 w-px bg-border" />
          )}

          {steps.map((step, i) => {
            const isDone = step.status === "done";
            const isActive = step.status === "active";
            return (
              <div
                key={step.node}
                className={`relative flex items-start gap-2.5 px-2 py-2 rounded-md transition-all duration-200 ${
                  isActive ? "step-row-active" : ""
                }`}
              >
                <div className="mt-0.5 shrink-0">
                  <StepIcon status={step.status} index={i} />
                </div>
                <div className="flex flex-col min-w-0 pt-0.5">
                  <span
                    className={`text-[11px] font-body leading-snug transition-colors duration-300 ${
                      isActive
                        ? "text-amber font-semibold"
                        : isDone
                        ? "text-t2"
                        : "text-t3"
                    }`}
                  >
                    {step.label}
                  </span>
                  {isActive && (
                    <span className="text-[9px] text-amber/50 font-mono mt-0.5">analyzing…</span>
                  )}
                  {isDone && (
                    <span className="text-[9px] text-emerald/50 font-mono mt-0.5">complete</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
