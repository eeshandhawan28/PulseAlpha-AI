import type { Step, StepStatus } from "@/lib/stream";

function StepIcon({ status, index }: { status: StepStatus; index: number }) {
  if (status === "done") {
    return (
      <div className="relative flex items-center justify-center w-6 h-6 border border-jade/40 bg-jade-dim shrink-0">
        <svg width="9" height="9" viewBox="0 0 10 10" fill="none">
          <path
            d="M1.5 5l2.5 2.5 4.5-4.5"
            stroke="#8fc8a8"
            strokeWidth="1.4"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
    );
  }
  if (status === "active") {
    return (
      <div className="pulse-ring relative flex items-center justify-center w-6 h-6 border border-gold bg-gold-dim shrink-0">
        <span
          className="w-[5px] h-[5px] bg-gold animate-pulse"
          style={{ transform: "rotate(45deg)" }}
        />
      </div>
    );
  }
  return (
    <div className="relative flex items-center justify-center w-6 h-6 border border-border shrink-0">
      <span className="text-t3 font-mono text-[9px]">
        {String(index + 1).padStart(2, "0")}
      </span>
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
    <div className="w-48 min-w-48 border-r border-border flex flex-col overflow-hidden bg-bg1/50">
      {/* Header */}
      <div className="px-4 pt-5 pb-3 border-b border-border shrink-0">
        <div className="flex items-center justify-between mb-2">
          <p className="font-body text-[9px] uppercase tracking-[0.3em] text-t3">
            The Process
          </p>
          {isStreaming && (
            <span className="flex items-center gap-1.5">
              <span className="diamond animate-pulse" />
              <span className="text-[8px] text-gold/80 font-mono uppercase tracking-wider">
                Live
              </span>
            </span>
          )}
          {!isStreaming && total > 0 && (
            <span className="text-[8px] text-t3 font-mono">
              {doneCount}/{total}
            </span>
          )}
        </div>

        {/* Progress hairline */}
        {total > 0 && (
          <div className="h-px bg-border overflow-hidden">
            <div
              className="h-full bg-gold transition-all duration-700"
              style={{ width: `${(doneCount / total) * 100}%` }}
            />
          </div>
        )}
      </div>

      {/* Steps */}
      <div className="flex-1 overflow-y-auto px-2 py-3">
        <div className="relative flex flex-col">
          {steps.length > 1 && (
            <div className="absolute left-[19px] top-6 bottom-6 w-px bg-border" />
          )}

          {steps.map((step, i) => {
            const isDone = step.status === "done";
            const isActive = step.status === "active";
            return (
              <div
                key={step.node}
                className={`relative flex items-start gap-3 px-2 py-2.5 transition-all duration-300 ${
                  isActive ? "step-row-active" : ""
                }`}
              >
                <div className="mt-0.5 shrink-0 relative z-10">
                  <StepIcon status={step.status} index={i} />
                </div>
                <div className="flex flex-col min-w-0 pt-0.5">
                  <span
                    className={`text-[11px] font-body leading-snug transition-colors duration-300 ${
                      isActive
                        ? "text-gold font-medium"
                        : isDone
                        ? "text-t2 font-light"
                        : "text-t3 font-light"
                    }`}
                  >
                    {step.label}
                  </span>
                  {isActive && (
                    <span className="text-[9px] text-gold/50 font-mono mt-0.5 italic">
                      in session…
                    </span>
                  )}
                  {isDone && (
                    <span className="text-[9px] text-jade/50 font-mono mt-0.5">
                      settled
                    </span>
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
