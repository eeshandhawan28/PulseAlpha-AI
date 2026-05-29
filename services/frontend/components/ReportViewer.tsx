"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Props {
  ticker: string;
  stance: string | null;
  reportText: string;
  isStreaming: boolean;
}

function stanceBadgeClass(stance: string | null): string {
  if (stance === "bullish") return "bg-green-900 text-green-400";
  if (stance === "bearish") return "bg-red-900 text-red-400";
  return "bg-yellow-900 text-yellow-400";
}

export default function ReportViewer({ ticker, stance, reportText, isStreaming }: Props) {
  return (
    <div className="flex-1 bg-surface border border-border rounded-lg p-4 overflow-auto min-h-0">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-bold text-foreground">
          {ticker ? `${ticker} — Analysis Report` : "Analysis Report"}
        </span>
        {stance && (
          <span
            className={`text-[10px] font-bold px-2 py-0.5 rounded ${stanceBadgeClass(stance)}`}
          >
            {stance.toUpperCase()}
          </span>
        )}
      </div>

      {!reportText && !isStreaming && (
        <p className="text-xs text-muted">Enter a ticker and question above, then click Run.</p>
      )}

      {!reportText && isStreaming && (
        <div className="space-y-2">
          {[95, 80, 88, 65, 75].map((w, i) => (
            <div
              key={i}
              className="h-3 bg-border rounded animate-pulse"
              style={{ width: `${w}%` }}
            />
          ))}
        </div>
      )}

      {reportText && (
        <div className="text-sm text-muted-foreground space-y-2">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{reportText}</ReactMarkdown>
          {isStreaming && (
            <span className="inline-block w-1.5 h-4 bg-blue-400 align-middle animate-pulse ml-0.5" />
          )}
        </div>
      )}
    </div>
  );
}
