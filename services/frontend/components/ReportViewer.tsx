"use client";

import { useRef, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Props {
  ticker: string;
  stance: string | null;
  reportText: string;
  isStreaming: boolean;
}

const stancePill: Record<string, string> = {
  bullish: "text-emerald bg-emerald-dim border-emerald/30",
  bearish: "text-rose bg-rose-dim border-rose/30",
  neutral: "text-amber bg-amber-dim border-amber/30",
};

export default function ReportViewer({ ticker, stance, reportText, isStreaming }: Props) {
  const pillClass = stance ? (stancePill[stance] ?? stancePill.neutral) : "";
  const reportRef = useRef<HTMLDivElement>(null);

  const downloadPdf = useCallback(async () => {
    if (!reportRef.current || !reportText) return;
    const { default: html2canvas } = await import("html2canvas");
    const { default: jsPDF } = await import("jspdf");

    const canvas = await html2canvas(reportRef.current, {
      backgroundColor: "#0d1222",
      scale: 2,
      useCORS: true,
      logging: false,
    });

    const imgData = canvas.toDataURL("image/png");
    const pdf = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
    const pdfWidth = pdf.internal.pageSize.getWidth();
    const pdfHeight = (canvas.height * pdfWidth) / canvas.width;

    pdf.addImage(imgData, "PNG", 0, 0, pdfWidth, pdfHeight);
    const filename = `${ticker || "analysis"}-report-${new Date().toISOString().slice(0, 10)}.pdf`;
    pdf.save(filename);
  }, [reportText, ticker]);

  return (
    <div className="flex-1 bg-bg2 border border-border rounded-lg flex flex-col min-h-0 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-border shrink-0">
        <div className="flex items-center gap-3">
          <span className="font-display font-semibold text-sm text-t1">
            {ticker ? ticker : "Analysis Report"}
          </span>
          {ticker && (
            <span className="font-mono text-xs text-t3">
              — Analysis Report
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {isStreaming && (
            <span className="flex items-center gap-1.5 text-[10px] text-amber font-body">
              <span className="w-1.5 h-1.5 rounded-full bg-amber pulse-ring inline-block" />
              Streaming
            </span>
          )}
          {stance && (
            <span className={`text-[10px] font-display font-bold px-2.5 py-1 rounded border ${pillClass}`}>
              {stance.toUpperCase()}
            </span>
          )}
          {reportText && !isStreaming && (
            <button
              onClick={downloadPdf}
              className="flex items-center gap-1.5 text-[10px] font-body text-t3 hover:text-t1 transition-colors border border-border rounded px-2 py-1 hover:border-border-active"
              title="Download as PDF"
            >
              <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
                <path d="M5.5 1v6M3 5l2.5 2.5L8 5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M1 9h9" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
              </svg>
              PDF
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      <div ref={reportRef} className="flex-1 overflow-auto px-5 py-4">
        {!reportText && !isStreaming && (
          <div className="flex flex-col items-center justify-center h-full gap-3 opacity-40">
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
              <rect x="4" y="8" width="24" height="3" rx="1.5" fill="#4a5876" />
              <rect x="4" y="14" width="18" height="3" rx="1.5" fill="#4a5876" />
              <rect x="4" y="20" width="21" height="3" rx="1.5" fill="#4a5876" />
            </svg>
            <p className="text-xs text-t3 font-body">Enter a ticker and question, then click Run</p>
          </div>
        )}

        {!reportText && isStreaming && (
          <div className="flex flex-col gap-3 pt-2">
            {[92, 78, 85, 63, 70, 88, 55, 74].map((w, i) => (
              <div key={i} className="shimmer h-3 rounded" style={{ width: `${w}%` }} />
            ))}
          </div>
        )}

        {reportText && (
          <div className="report-body">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{reportText}</ReactMarkdown>
            {isStreaming && (
              <span className="cursor-blink inline-block w-[2px] h-4 bg-amber align-middle ml-0.5" />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
