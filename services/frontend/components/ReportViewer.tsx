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
  bullish: "text-jade border-jade/40 bg-jade-dim",
  bearish: "text-blood border-blood/40 bg-blood-dim",
  neutral: "text-gold border-gold/40 bg-gold-dim",
};

export default function ReportViewer({ ticker, stance, reportText, isStreaming }: Props) {
  const pillClass = stance ? (stancePill[stance] ?? stancePill.neutral) : "";
  const reportRef = useRef<HTMLDivElement>(null);

  const downloadPdf = useCallback(async () => {
    if (!reportRef.current || !reportText) return;
    const { default: html2canvas } = await import("html2canvas");
    const { default: jsPDF } = await import("jspdf");

    const canvas = await html2canvas(reportRef.current, {
      backgroundColor: "#11100d",
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

  // Hide entirely when there's nothing to show (not streaming, no report)
  if (!reportText && !isStreaming) return null;

  return (
    <div className="bg-bg1 border border-border">
      {/* Letterhead */}
      <div className="flex items-center justify-between px-7 py-4 border-b border-border">
        <div className="flex items-baseline gap-3">
          <span className="font-display font-semibold text-lg text-t1 tracking-wide">
            {ticker ? ticker : "The Report"}
          </span>
          {ticker && (
            <span className="font-body font-light text-[10px] text-t3 uppercase tracking-[0.25em]">
              Research Note
            </span>
          )}
        </div>
        <div className="flex items-center gap-4">
          {isStreaming && (
            <span className="flex items-center gap-2 text-[10px] text-gold font-body tracking-[0.15em] uppercase">
              <span className="diamond animate-pulse" />
              Composing
            </span>
          )}
          {stance && (
            <span
              className={`text-[9px] font-body font-medium uppercase tracking-[0.3em] px-3 py-1.5 border ${pillClass}`}
            >
              {stance}
            </span>
          )}
          {reportText && !isStreaming && (
            <button
              onClick={downloadPdf}
              className="flex items-center gap-2 text-[9px] font-body uppercase tracking-[0.25em] text-t3 hover:text-gold transition-colors border border-border px-3 py-1.5 hover:border-gold/50"
              title="Download as PDF"
            >
              <svg width="10" height="10" viewBox="0 0 11 11" fill="none">
                <path d="M5.5 1v6M3 5l2.5 2.5L8 5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M1 9h9" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
              </svg>
              PDF
            </button>
          )}
        </div>
      </div>

      {/* Content — naturally tall, parent scroll container handles overflow */}
      <div ref={reportRef} className="px-7 py-6">
        {!reportText && isStreaming && (
          <div className="flex flex-col gap-3 pt-2 max-w-[82ch]">
            {[92, 78, 85, 63, 70, 88, 55, 74].map((w, i) => (
              <div key={i} className="shimmer h-3" style={{ width: `${w}%` }} />
            ))}
          </div>
        )}

        {reportText && (
          <div className="report-body">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{reportText}</ReactMarkdown>
            {isStreaming && (
              <span className="cursor-blink inline-block w-[2px] h-4 bg-gold align-middle ml-0.5" />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
