"use client";

import { useState } from "react";
import type { RagEvidence } from "@/lib/stream";

function parseChunk(raw: string): { section: string; text: string } {
  // Chunks are prefixed with "[Section: MD&A]\n..." by the RAG pipeline
  const m = raw.match(/^\[Section:\s*([^\]]+)\]\s*\n?([\s\S]*)/);
  if (m) return { section: m[1].trim(), text: m[2].trim() };
  return { section: "General", text: raw.trim() };
}

interface Props {
  evidence: RagEvidence;
}

export default function RAGEvidencePanel({ evidence }: Props) {
  const [open, setOpen] = useState(false);

  const { chunks, year, pdf_url } = evidence;
  if (!chunks.length) return null;

  return (
    <div className="bg-bg1 border border-border shrink-0">
      {/* Header — always visible, click to expand */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-5 py-3 hover:bg-bg2 transition-colors group"
      >
        <div className="flex items-center gap-3">
          <span className="diamond text-gold opacity-60" />
          <span className="font-body text-[9px] uppercase tracking-[0.35em] text-t3 group-hover:text-t2 transition-colors">
            Annual Report Evidence
          </span>
          {year && (
            <span className="font-mono text-[9px] text-gold/60 border border-gold/20 px-1.5 py-0.5">
              FY {year}
            </span>
          )}
          <span className="font-mono text-[9px] text-t3">
            {chunks.length} excerpt{chunks.length !== 1 ? "s" : ""}
          </span>
        </div>

        <div className="flex items-center gap-3">
          {pdf_url && (
            <a
              href={pdf_url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="flex items-center gap-1.5 text-[9px] font-body uppercase tracking-[0.2em] text-t3 hover:text-gold transition-colors border border-border px-2 py-1 hover:border-gold/40"
            >
              <svg width="9" height="9" viewBox="0 0 11 11" fill="none">
                <path
                  d="M5.5 1v6M3 5l2.5 2.5L8 5"
                  stroke="currentColor"
                  strokeWidth="1.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <path d="M1 9h9" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
              </svg>
              PDF
            </a>
          )}
          <svg
            width="10"
            height="10"
            viewBox="0 0 10 10"
            fill="none"
            className={`text-t3 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
          >
            <path
              d="M2 4l3 3 3-3"
              stroke="currentColor"
              strokeWidth="1.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
      </button>

      {/* Expandable chunk table */}
      {open && (
        <div className="border-t border-border/60">
          {/* Column headers */}
          <div className="flex items-center gap-4 px-5 py-2 border-b border-border/40">
            <span className="w-32 text-[8px] uppercase tracking-[0.3em] text-t3 font-body shrink-0">
              Section
            </span>
            <span className="flex-1 text-[8px] uppercase tracking-[0.3em] text-t3 font-body">
              Excerpt
            </span>
          </div>

          {chunks.map((raw, i) => {
            const { section, text } = parseChunk(raw);
            const preview = text.length > 240 ? text.slice(0, 240) + "…" : text;
            return (
              <div
                key={i}
                className="flex items-start gap-4 px-5 py-3 border-b border-border/30 last:border-0 hover:bg-bg2/50 transition-colors"
              >
                <span className="w-32 shrink-0 font-body text-[9px] uppercase tracking-[0.15em] text-gold/70 pt-0.5">
                  {section}
                </span>
                <p className="flex-1 text-[11px] font-body font-light text-t2 leading-relaxed">
                  {preview}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
