/** Foreign Flow analysis page: real-time WS summary + polled per-symbol detail.
 *  Layout: summary cards → sector chart + cumulative flow → top buy/sell tables → detail table. */

import { useForeignFlow } from "../hooks/use-foreign-flow";
import { ForeignFlowSkeleton } from "../components/ui/foreign-flow-skeleton";
import { ErrorBanner } from "../components/ui/error-banner";
import { ForeignFlowSummaryCards } from "../components/foreign/foreign-flow-summary-cards";
import { ForeignSectorBarChart } from "../components/foreign/foreign-sector-bar-chart";
import { ForeignCumulativeFlowChart } from "../components/foreign/foreign-cumulative-flow-chart";
import { ForeignTopStocksTables } from "../components/foreign/foreign-top-stocks-tables";
import { ForeignFlowDetailTable } from "../components/foreign/foreign-flow-detail-table";

export default function ForeignFlowPage() {
  const { summary, stocks, flowHistory, loading, error, isLive, status, reconnect } =
    useForeignFlow();

  if (loading) return <ForeignFlowSkeleton />;

  if (error && !summary && stocks.length === 0) {
    return (
      <ErrorBanner
        message={`Failed to load foreign flow data: ${error.message}`}
        onRetry={reconnect}
      />
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header with connection status */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">Foreign Flow</h2>
        <div className="flex items-center gap-2 text-xs">
          <span
            className={`inline-block w-2 h-2 rounded-full ${
              isLive ? "bg-green-500" : "bg-yellow-500"
            }`}
          />
          <span className="text-gray-400">
            {isLive ? "Live" : "Polling"}
            {status === "disconnected" && " (reconnecting...)"}
          </span>
        </div>
      </div>

      {/* Non-blocking error: show stale data + warning */}
      {error && (summary || stocks.length > 0) && (
        <div className="text-xs text-yellow-400 bg-yellow-900/20 px-3 py-2 rounded">
          Connection issue — showing last known data
        </div>
      )}

      {/* Summary Cards */}
      {summary && <ForeignFlowSummaryCards summary={summary} />}

      {/* Charts Grid: sector bar chart + cumulative flow */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ForeignSectorBarChart stocks={stocks} />
        <ForeignCumulativeFlowChart flowHistory={flowHistory} />
      </div>

      {/* Top 10 Buy + Top 10 Sell */}
      <ForeignTopStocksTables stocks={stocks} />

      {/* Full Detail Table */}
      <ForeignFlowDetailTable stocks={stocks} />
    </div>
  );
}
