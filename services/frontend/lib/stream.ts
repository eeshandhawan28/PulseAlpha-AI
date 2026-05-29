"use client";

import { useCallback, useRef, useState } from "react";
import { getStreamUrl } from "./api";

export type StepStatus = "pending" | "active" | "done";

export interface Step {
  node: string;
  label: string;
  status: StepStatus;
}

export interface Metrics {
  stance: string;
  confidence: number;
  divergence_score: number;
  rrg_quadrant: string;
}

const INITIAL_STEPS: Step[] = [
  { node: "ingest", label: "Market data", status: "pending" },
  { node: "features", label: "RRG features", status: "pending" },
  { node: "divergence", label: "Divergence score", status: "pending" },
  { node: "council", label: "Council", status: "pending" },
  { node: "report", label: "Report", status: "pending" },
];

export function useAnalysisStream() {
  const [steps, setSteps] = useState<Step[]>(INITIAL_STEPS);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [reportText, setReportText] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  const start = useCallback((ticker: string, query: string) => {
    esRef.current?.close();
    setSteps(INITIAL_STEPS);
    setMetrics(null);
    setReportText("");
    setRunId(null);
    setError(null);
    setIsStreaming(true);

    const url = getStreamUrl(ticker.trim(), query.trim());
    const es = new EventSource(url);
    esRef.current = es;

    es.onmessage = (e: MessageEvent) => {
      try {
        const event = JSON.parse(e.data as string);
        if (event.type === "step") {
          setSteps((prev) =>
            prev.map((s) =>
              s.node === event.node ? { ...s, status: event.status as StepStatus } : s
            )
          );
        } else if (event.type === "metrics") {
          setMetrics({
            stance: event.stance,
            confidence: event.confidence,
            divergence_score: event.divergence_score,
            rrg_quadrant: event.rrg_quadrant,
          });
        } else if (event.type === "chunk") {
          setReportText((prev) => prev + (event.text as string));
        } else if (event.type === "error") {
          setError(event.message as string);
          setIsStreaming(false);
          es.close();
        } else if (event.type === "done") {
          setRunId(event.run_id as string);
          setIsStreaming(false);
          es.close();
        }
      } catch {
        // malformed event — skip
      }
    };

    es.onerror = () => {
      setError("Connection to analysis server lost. Is the API running on port 8000?");
      setIsStreaming(false);
      es.close();
    };
  }, []);

  const reset = useCallback(() => {
    esRef.current?.close();
    setSteps(INITIAL_STEPS);
    setMetrics(null);
    setReportText("");
    setRunId(null);
    setError(null);
    setIsStreaming(false);
  }, []);

  return { steps, metrics, reportText, isStreaming, runId, error, start, reset };
}
