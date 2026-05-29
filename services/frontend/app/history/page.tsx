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
        <div className="px-5 py-4 border-b border-border bg-bg1 shrink-0">
          <h1 className="font-display font-bold text-sm text-t1">Analysis History</h1>
          <p className="text-xs text-t3 font-body mt-0.5">{runs.length} past {runs.length === 1 ? "run" : "runs"}</p>
        </div>
        <HistoryTable runs={runs} />
      </div>
    </div>
  );
}
