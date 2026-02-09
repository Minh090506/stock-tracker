/** Derivatives basis analysis page — VN30F futures vs VN30 index spread. */

import { useDerivativesData } from "../hooks/use-derivatives-data";
import { DerivativesSkeleton } from "../components/ui/derivatives-skeleton";
import { ErrorBanner } from "../components/ui/error-banner";
import { DerivativesSummaryCards } from "../components/derivatives/derivatives-summary-cards";
import { BasisTrendAreaChart } from "../components/derivatives/basis-trend-area-chart";
import { ConvergenceIndicator } from "../components/derivatives/convergence-indicator";
import { OpenInterestDisplay } from "../components/derivatives/open-interest-display";

export default function DerivativesPage() {
  const { derivatives, basisTrend, loading, error } = useDerivativesData();

  if (loading) return <DerivativesSkeleton />;

  if (error) {
    return (
      <ErrorBanner
        message={`Failed to load derivatives data: ${error.message}`}
      />
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Summary Cards */}
      <DerivativesSummaryCards data={derivatives} />

      {/* Basis Trend Chart */}
      <BasisTrendAreaChart points={basisTrend} />

      {/* Bottom Row: Convergence + Open Interest */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ConvergenceIndicator points={basisTrend} />
        <OpenInterestDisplay contract={derivatives?.symbol ?? null} />
      </div>
    </div>
  );
}
