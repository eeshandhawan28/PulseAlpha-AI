"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { fetchHistoryStats } from "@/lib/api";

const NAV = [
  { href: "/analyze", label: "Analyze", icon: "📊" },
  { href: "/history", label: "History", icon: "📋" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [hitRate, setHitRate] = useState<number | null>(null);

  useEffect(() => {
    fetchHistoryStats().then((s) => setHitRate(s.hit_rate_30d));
  }, []);

  return (
    <aside className="w-36 min-w-36 flex flex-col gap-1 border-r border-border bg-[#080d1c] px-2 py-3">
      <div className="px-1 pb-3 border-b border-border mb-1">
        <span className="text-xs font-extrabold tracking-wider text-indigo-400">
          ⚡ PULSEALPHA
        </span>
      </div>

      {NAV.map((item) => {
        const active = pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`flex items-center gap-2 rounded-md px-2 py-1.5 text-xs transition-colors ${
              active
                ? "bg-blue-900 text-blue-300 font-semibold"
                : "text-muted hover:text-muted-foreground hover:bg-surface"
            }`}
          >
            <span>{item.icon}</span>
            <span>{item.label}</span>
          </Link>
        );
      })}

      <div className="mt-auto pt-3 border-t border-border">
        <div className="flex justify-between text-[10px] text-muted">
          <span>Model accuracy</span>
          <span className="text-green-400 font-bold">
            {hitRate !== null ? `${Math.round(hitRate * 100)}%` : "—"}
          </span>
        </div>
        <div className="flex justify-between text-[10px] text-muted mt-0.5">
          <span>30-day hit rate</span>
          <span className="text-[10px] text-muted">last backtest</span>
        </div>
      </div>
    </aside>
  );
}
