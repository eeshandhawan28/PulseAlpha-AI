import HistoryTable from "@/components/HistoryTable";
import Sidebar from "@/components/Sidebar";
import { fetchHistory } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function HistoryPage() {
  const runs = await fetchHistory();

  return (
    <div className="flex h-screen overflow-hidden bg-bg0">
      <Sidebar />
      <div className="flex flex-col flex-1 min-h-0">
        <div className="px-6 py-5 border-b border-border bg-bg1 shrink-0">
          <div className="flex items-center gap-3 mb-1">
            <h1 className="font-display font-semibold text-xl text-t1 tracking-wide">
              The Ledger
            </h1>
            <span className="diamond" />
          </div>
          <p className="text-[10px] text-t3 font-body font-light uppercase tracking-[0.25em]">
            {runs.length} commissioned {runs.length === 1 ? "analysis" : "analyses"}
          </p>
        </div>
        <HistoryTable runs={runs} />
      </div>
    </div>
  );
}
