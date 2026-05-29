import HistoryTable from "@/components/HistoryTable";
import Sidebar from "@/components/Sidebar";
import { fetchHistory } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function HistoryPage() {
  const runs = await fetchHistory();

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex flex-col flex-1 min-h-0">
        <div className="px-4 py-3 border-b border-border">
          <h1 className="text-sm font-bold text-foreground">Analysis History</h1>
          <p className="text-xs text-muted mt-0.5">{runs.length} past runs</p>
        </div>
        <HistoryTable runs={runs} />
      </div>
    </div>
  );
}
