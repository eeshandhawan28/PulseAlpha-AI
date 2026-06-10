"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { fetchHistoryStats } from "@/lib/api";

const NAV = [
  {
    href: "/analyze",
    label: "Analyze",
    icon: (active: boolean) => (
      <svg width="13" height="13" viewBox="0 0 14 14" fill="none">
        <path
          d="M1 10l3-4 3 2 3-5 3 3"
          stroke={active ? "#c9a96a" : "#5f5747"}
          strokeWidth="1.3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
  },
  {
    href: "/history",
    label: "Ledger",
    icon: (active: boolean) => (
      <svg width="13" height="13" viewBox="0 0 14 14" fill="none">
        <circle cx="7" cy="7" r="5.5" stroke={active ? "#c9a96a" : "#5f5747"} strokeWidth="1.2" />
        <path d="M7 4.5V7l2 1.5" stroke={active ? "#c9a96a" : "#5f5747"} strokeWidth="1.2" strokeLinecap="round" />
      </svg>
    ),
  },
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
    <aside className="w-[148px] min-w-[148px] flex flex-col border-r border-border bg-bg1 relative z-10">
      {/* Wordmark */}
      <div className="px-4 pt-6 pb-5 border-b border-border">
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center gap-2">
            <span className="diamond" />
            <span className="font-display font-semibold text-[15px] tracking-[0.06em] text-t1">
              PulseAlpha
            </span>
          </div>
          <p className="text-[8px] text-t3 font-body uppercase tracking-[0.3em]">
            Private Desk
          </p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex flex-col gap-0.5 px-2 py-4 flex-1">
        {NAV.map(({ href, label, icon }) => {
          const active = pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={`relative flex items-center gap-2.5 px-3 py-2.5 text-[11px] font-body uppercase tracking-[0.2em] transition-all duration-300 ${
                active
                  ? "text-gold bg-gold-dim"
                  : "text-t3 hover:text-t2 hover:bg-bg2"
              }`}
            >
              {active && (
                <span className="absolute left-0 top-[20%] bottom-[20%] w-px bg-gold" />
              )}
              {icon(active)}
              <span className={active ? "font-medium" : "font-light"}>{label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Track record */}
      <div className="border-t border-border px-4 py-4">
        <p className="text-[8px] uppercase tracking-[0.3em] text-t3 font-body mb-2">
          Track Record
        </p>
        <p
          className="font-display text-2xl font-semibold leading-none"
          style={{ color: hitRate !== null ? "#8fc8a8" : "#5f5747" }}
        >
          {hitRate !== null ? `${Math.round(hitRate * 100)}%` : "—"}
        </p>
        <p className="text-[8px] text-t3 font-body mt-1 tracking-[0.12em]">
          30-day hit rate
        </p>
      </div>
    </aside>
  );
}
