"use client";

import { useCallback, useEffect, useRef, useState } from "react";
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

export interface ChartSpec {
  ticker: string;
  data: object[];
  layout: object;
}

export interface RagEvidence {
  chunks: string[];
  year: string;
  pdf_url: string;
}

const INITIAL_STEPS: Step[] = [
  { node: "ingest", label: "Market data", status: "pending" },
  { node: "features", label: "RRG features", status: "pending" },
  { node: "divergence", label: "Divergence score", status: "pending" },
  { node: "council", label: "Council", status: "pending" },
  { node: "report", label: "Report", status: "pending" },
];

export function useAnalysisStream() {
  const [steps, setSteps] = useState<Step[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [reportText, setReportText] = useState("");
  const [charts, setCharts] = useState<ChartSpec[]>([]);
  const [ragEvidence, setRagEvidence] = useState<RagEvidence | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const stepActiveAt = useRef<Record<string, number>>({});
  const receivedDone = useRef(false);

  const start = useCallback((ticker: string, query: string) => {
    esRef.current?.close();
    setSteps(INITIAL_STEPS);
    stepActiveAt.current = {};
    receivedDone.current = false;
    setMetrics(null);
    setReportText("");
    setCharts([]);
    setRagEvidence(null);
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
          if (event.status === "active") {
            stepActiveAt.current[event.node as string] = Date.now();
            setSteps((prev) =>
              prev.map((s) =>
                s.node === event.node ? { ...s, status: "active" as StepStatus } : s
              )
            );
          } else if (event.status === "done") {
            const activeAt = stepActiveAt.current[event.node as string] ?? 0;
            const elapsed = Date.now() - activeAt;
            const MIN_DURATION = 700;
            const delay = Math.max(0, MIN_DURATION - elapsed);
            setTimeout(() => {
              setSteps((prev) =>
                prev.map((s) =>
                  s.node === event.node ? { ...s, status: "done" as StepStatus } : s
                )
              );
            }, delay);
          }
        } else if (event.type === "metrics") {
          setMetrics({
            stance: event.stance,
            confidence: event.confidence,
            divergence_score: event.divergence_score,
            rrg_quadrant: event.rrg_quadrant,
          });
        } else if (event.type === "charts") {
          setCharts(event.charts as ChartSpec[]);
        } else if (event.type === "rag_evidence") {
          setRagEvidence({
            chunks: event.chunks as string[],
            year: event.year as string,
            pdf_url: event.pdf_url as string,
          });
        } else if (event.type === "chunk") {
          setReportText((prev) => prev + (event.text as string));
        } else if (event.type === "error") {
          setError(event.message as string);
          setIsStreaming(false);
          es.close();
        } else if (event.type === "done") {
          receivedDone.current = true;
          setRunId(event.run_id as string);
          setIsStreaming(false);
          es.close();
        }
      } catch {
        // malformed event — skip
      }
    };

    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED && !receivedDone.current) {
        setError("Connection to analysis server lost. Is the API running on port 8000?");
        setIsStreaming(false);
        es.close();
      }
    };
  }, []);

  useEffect(() => {
    return () => {
      esRef.current?.close();
    };
  }, []);

  const reset = useCallback(() => {
    esRef.current?.close();
    receivedDone.current = false;
    setSteps([]);
    setMetrics(null);
    setReportText("");
    setCharts([]);
    setRagEvidence(null);
    setRunId(null);
    setError(null);
    setIsStreaming(false);
  }, []);

  return { steps, metrics, reportText, charts, ragEvidence, isStreaming, runId, error, start, reset };
}
