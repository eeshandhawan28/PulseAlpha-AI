"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { fetchHistoryStats } from "@/lib/api";

const NAV = [
  { href: "/analyze", label: "Analyze", icon: (active: boolean) => (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M1 10l3-4 3 2 3-5 3 3" stroke={active ? "#f59e0b" : "#4a5876"} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )},
  { href: "/history", label: "History", icon: (active: boolean) => (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <circle cx="7" cy="7" r="5.5" stroke={active ? "#f59e0b" : "#4a5876"} strokeWidth="1.3" />
      <path d="M7 4.5V7l2 1.5" stroke={active ? "#f59e0b" : "#4a5876"} strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  )},
];

export default function Sidebar() {
  const pathname = usePathname();
  const [hitRate, setHitRate] = useState<number | null>(null);

  useEffect(() => {
    fetchHistoryStats()
      .then((s) => setHitRate(s.hit_rate_30d))
      .catch(() => {});
  }, []);

  return (
    <aside className="w-[130px] min-w-[130px] flex flex-col border-r border-border bg-bg1">
      {/* Logo */}
      <div className="px-4 pt-5 pb-4 border-b border-border">
        <div className="flex items-center gap-1.5">
          <span className="text-amber text-base leading-none">⚡</span>
          <span className="font-display font-extrabold text-[11px] tracking-[0.15em] text-t1 uppercase">
            PulseAlpha
          </span>
        </div>
        <p className="text-[8px] text-t3 font-body mt-1 tracking-wide">Market Intelligence</p>
      </div>

      {/* Nav */}
      <nav className="flex flex-col gap-1 px-2 py-3 flex-1">
        {NAV.map(({ href, label, icon }) => {
          const active = pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-2 rounded-md px-2.5 py-2 text-[11px] font-body transition-all duration-200 ${
                active
                  ? "bg-amber-dim text-amber border border-amber/20"
                  : "text-t3 hover:text-t2 hover:bg-bg2"
              }`}
            >
              {icon(active)}
              <span className={active ? "font-semibold" : ""}>{label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-border px-3 py-3">
        <p className="text-[8px] uppercase tracking-[0.15em] text-t3 font-body mb-1.5">
          Model Accuracy
        </p>
        <p className="font-mono text-lg font-semibold leading-none" style={{
          color: hitRate !== null ? "#34d399" : "#4a5876"
        }}>
          {hitRate !== null ? `${Math.round(hitRate * 100)}%` : "—"}
        </p>
        <p className="text-[8px] text-t3 font-body mt-0.5">30-day hit rate</p>
      </div>
    </aside>
  );
}
