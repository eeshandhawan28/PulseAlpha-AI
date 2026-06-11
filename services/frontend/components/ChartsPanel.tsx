"use client";

import dynamic from "next/dynamic";
import type { ComponentType } from "react";
import type { PlotParams } from "react-plotly.js";
import type { ChartSpec } from "@/lib/stream";

// Plotly must be dynamically imported — no SSR support
const Plot = dynamic(() => import("react-plotly.js"), {
  ssr: false,
  loading: () => (
    <div className="h-[280px] flex items-center justify-center">
      <div className="flex items-center gap-3 opacity-40">
        <span className="w-8 h-px bg-border-active" />
        <span className="diamond animate-pulse" />
        <span className="w-8 h-px bg-border-active" />
      </div>
    </div>
  ),
}) as ComponentType<PlotParams>;

interface Props {
  charts: ChartSpec[];
}

export default function ChartsPanel({ charts }: Props) {
  if (!charts.length) return null;

  return (
    <div className="flex flex-col gap-3 shrink-0">
      {charts.map((c) => (
        <div
          key={c.ticker}
          className="bg-bg1 border border-border overflow-hidden"
        >
          {/* Hairline label */}
          <div className="flex items-center gap-2 px-4 py-2 border-b border-border/60">
            <span className="font-body text-[8px] uppercase tracking-[0.35em] text-t3">
              Price · 90D
            </span>
            <span className="diamond opacity-40" />
            <span className="font-mono text-[10px] text-t2">
              {c.ticker.replace(".NS", "").replace(".BO", "")}
            </span>
          </div>

          <Plot
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            data={c.data as any[]}
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            layout={{ ...(c.layout as any), autosize: true }}
            useResizeHandler
            style={{ width: "100%", height: "280px" }}
            config={{
              displayModeBar: false,
              responsive: true,
              scrollZoom: false,
            }}
          />
        </div>
      ))}
    </div>
  );
}
