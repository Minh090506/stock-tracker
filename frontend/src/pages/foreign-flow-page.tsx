/** Foreign Flow analysis page showing investor net flow, top movers, heatmap, and detail table. */

import { useForeignFlow } from "../hooks/use-foreign-flow";
import { PageLoadingSkeleton } from "../components/ui/page-loading-skeleton";
import { ErrorBanner } from "../components/ui/error-banner";
import { ForeignFlowSummaryCards } from "../components/foreign/foreign-flow-summary-cards";
import { ForeignTopMoversBarChart } from "../components/foreign/foreign-top-movers-bar-chart";
import { ForeignNetFlowHeatmap } from "../components/foreign/foreign-net-flow-heatmap";
import { ForeignFlowDetailTable } from "../components/foreign/foreign-flow-detail-table";

export default function ForeignFlowPage() {
  const { data, loading, error, refresh } = useForeignFlow();

  if (loading) {
    return <PageLoadingSkeleton />;
  }

  if (error) {
    return (
      <ErrorBanner
        message={`Failed to load foreign flow data: ${error.message}`}
        onRetry={refresh}
      />
    );
  }

  if (!data) {
    return (
      <ErrorBanner message="No foreign flow data available" onRetry={refresh} />
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Summary Cards */}
      <ForeignFlowSummaryCards summary={data.summary} />

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ForeignTopMoversBarChart stocks={data.stocks} />
        <ForeignNetFlowHeatmap stocks={data.stocks} />
      </div>

      {/* Detail Table */}
      <ForeignFlowDetailTable stocks={data.stocks} />
    </div>
  );
}
