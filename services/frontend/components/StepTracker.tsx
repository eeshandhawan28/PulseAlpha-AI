import { Step, StepStatus } from "@/lib/stream";

function StepIcon({ status }: { status: StepStatus }) {
  if (status === "done")
    return (
      <span className="inline-flex w-4 h-4 rounded-full items-center justify-center bg-green-900 text-green-400 text-[9px]">
        ✓
      </span>
    );
  if (status === "active")
    return (
      <span className="inline-flex w-4 h-4 rounded-full items-center justify-center bg-blue-900 text-blue-400 text-[9px] animate-pulse">
        ●
      </span>
    );
  return (
    <span className="inline-flex w-4 h-4 rounded-full items-center justify-center bg-border text-muted text-[9px]">
      ○
    </span>
  );
}

export default function StepTracker({ steps }: { steps: Step[] }) {
  return (
    <div className="w-40 min-w-40 border-r border-border px-3 py-3 flex flex-col gap-1">
      <p className="text-[10px] uppercase tracking-widest text-muted mb-2">Pipeline</p>
      {steps.map((step) => (
        <div key={step.node} className="flex items-center gap-2">
          <StepIcon status={step.status} />
          <span
            className={`text-[11px] ${
              step.status === "active"
                ? "text-blue-300 font-semibold"
                : step.status === "done"
                ? "text-muted-foreground"
                : "text-muted"
            }`}
          >
            {step.label}
          </span>
        </div>
      ))}
    </div>
  );
}
