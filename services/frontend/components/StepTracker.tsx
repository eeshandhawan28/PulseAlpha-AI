import type { Step, StepStatus } from "@/lib/stream";

function StepIcon({ status, index }: { status: StepStatus; index: number }) {
  if (status === "done") {
    return (
      <div className="relative flex items-center justify-center w-7 h-7 rounded-full bg-emerald-dim border border-emerald/40 shrink-0">
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
          <path d="M2 6l3 3 5-5" stroke="#34d399" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
    );
  }
  if (status === "active") {
    return (
      <div className="pulse-ring relative flex items-center justify-center w-7 h-7 rounded-full bg-amber-dim border border-amber shrink-0">
        <span className="text-amber font-mono text-[10px] font-bold">{index + 1}</span>
      </div>
    );
  }
  return (
    <div className="relative flex items-center justify-center w-7 h-7 rounded-full border border-border shrink-0">
      <span className="text-t3 font-mono text-[10px]">{index + 1}</span>
    </div>
  );
}

export default function StepTracker({ steps }: { steps: Step[] }) {
  return (
    <div className="w-44 min-w-44 border-r border-border px-4 py-5 flex flex-col">
      <p className="font-display text-[9px] uppercase tracking-[0.2em] text-t3 mb-5">
        Pipeline
      </p>
      <div className="relative flex flex-col gap-0">
        {/* Connecting line */}
        <div className="absolute left-[13px] top-7 bottom-7 w-px bg-border" />
        {steps.map((step, i) => {
          const isDone = step.status === "done";
          const isActive = step.status === "active";
          return (
            <div key={step.node} className="flex items-center gap-3 py-2 relative">
              <StepIcon status={step.status} index={i} />
              <div className="flex flex-col min-w-0">
                <span
                  className={`text-[11px] font-body leading-tight truncate transition-colors duration-300 ${
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
                  <span className="text-[9px] text-amber/60 mt-0.5">Running…</span>
                )}
                {isDone && (
                  <span className="text-[9px] text-emerald/60 mt-0.5">Done</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
