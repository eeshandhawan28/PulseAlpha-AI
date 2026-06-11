"use client";

import { useState } from "react";
import type { RagEvidence } from "@/lib/stream";

function parseChunk(raw: string): { section: string; text: string } {
  const m = raw.match(/^\[Section:\s*([^\]]+)\]\s*\n?([\s\S]*)/);
  if (m) return { section: m[1].trim(), text: m[2].trim() };
  return { section: "General", text: raw.trim() };
}

const SECTION_COLORS: Record<string, string> = {
  "MD&A": "#c9a96a",
  "Financial Highlights": "#8fc8a8",
  "Risk Factors": "#c97878",
  "Chairman's Statement": "#a9bdd4",
  "Directors' Report": "#a9bdd4",
  "Segment Performance": "#c9a96a",
  "Consolidated Financials": "#8fc8a8",
  "Standalone Financials": "#8fc8a8",
  "Notes to Financials": "#a39a86",
  "Corporate Governance": "#a9bdd4",
  Outlook: "#c9a96a",
  "Auditors' Report": "#a39a86",
  General: "#5f5747",
};

function sectionColor(section: string): string {
  return SECTION_COLORS[section] ?? "#a39a86";
}

function ChunkCard({ section, text, index }: { section: string; text: string; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const color = sectionColor(section);
  const isLong = text.length > 360;
  const preview = isLong && !expanded ? text.slice(0, 360).trimEnd() + "…" : text;

  return (
    <div
      className="relative bg-bg0 border border-border/40 hover:border-border/80 transition-colors"
      style={{ borderLeftColor: color, borderLeftWidth: "2px" }}
    >
      <div className="flex items-center justify-between px-4 pt-3 pb-2">
        <span
          className="font-body text-[8px] uppercase tracking-[0.28em] font-medium px-2 py-0.5 border"
          style={{ color, borderColor: `${color}40`, background: `${color}10` }}
        >
          {section}
        </span>
        <span className="font-mono text-[8px] text-t3/30">#{index + 1}</span>
      </div>
      <div className="px-4 pb-3.5">
        <p className="font-body font-light text-[12.5px] text-t2 leading-[1.8] tracking-[0.005em]">
          {preview}
        </p>
        {isLong && (
          <button
            onClick={() => setExpanded((v) => !v)}
            className="mt-2.5 font-body text-[9px] uppercase tracking-[0.2em] text-t3 hover:text-gold transition-colors"
          >
            {expanded ? "Collapse ↑" : "Read more ↓"}
          </button>
        )}
      </div>
    </div>
  );
}

interface Props {
  evidence: RagEvidence;
}

export default function RAGEvidencePanel({ evidence }: Props) {
  const [open, setOpen] = useState(false);

  const { chunks, year, pdf_url } = evidence;
  if (!chunks.length) return null;

  const parsed = chunks.map(parseChunk);
  const sectionCount = new Set(parsed.map((c) => c.section)).size;

  return (
    <div className="bg-bg1 border border-border shrink-0">
      {/* Header */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-5 py-3.5 hover:bg-bg2/40 transition-colors group"
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
          <span className="font-body text-[9px] text-t3">
            {chunks.length} excerpt{chunks.length !== 1 ? "s" : ""}{" "}
            <span className="text-t3/50">·</span> {sectionCount} section
            {sectionCount !== 1 ? "s" : ""}
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
              Source PDF
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

      {/* Cards */}
      {open && (
        <div className="border-t border-border/60 px-4 py-4 flex flex-col gap-3">
          {parsed.map((c, i) => (
            <ChunkCard key={i} section={c.section} text={c.text} index={i} />
          ))}
        </div>
      )}
    </div>
  );
}
