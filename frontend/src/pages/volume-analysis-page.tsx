/** Volume Analysis page showing buy/sell/neutral volume breakdown. */

import { useMarketSnapshot } from "../hooks/use-market-snapshot";
import { VolumeAnalysisSkeleton } from "../components/ui/volume-analysis-skeleton";
import { ErrorBanner } from "../components/ui/error-banner";
import { VolumeMarketPieChart } from "../components/volume/volume-market-pie-chart";
import { VolumeRatioSummaryCards } from "../components/volume/volume-ratio-summary-cards";
import { VolumeStackedBarChart } from "../components/volume/volume-stacked-bar-chart";
import { VolumeDetailTable } from "../components/volume/volume-detail-table";

export default function VolumeAnalysisPage() {
  const { data, loading, error } = useMarketSnapshot();

  if (loading && !data) return <VolumeAnalysisSkeleton />;
  if (error) return <ErrorBanner message={error.message} />;
  if (!data) return <ErrorBanner message="No market data available" />;

  const stats = Object.values(data.quotes);

  return (
    <div className="p-6 space-y-6">
      <h2 className="text-2xl font-bold">Volume Analysis</h2>

      {/* Top row: Pie chart + Summary cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <VolumeMarketPieChart stats={stats} />
        <VolumeRatioSummaryCards stats={stats} />
      </div>

      {/* Stacked bar chart */}
      <VolumeStackedBarChart stats={stats} />

      {/* Detail table */}
      <VolumeDetailTable stats={stats} />
    </div>
  );
}
