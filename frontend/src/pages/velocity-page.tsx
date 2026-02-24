/** Order velocity analysis — VN30F + VN30 basket velocity with correlation. */

import { useVelocityData } from "../hooks/use-velocity-data";
import { VelocitySkeleton } from "../components/ui/velocity-skeleton";
import { ErrorBanner } from "../components/ui/error-banner";
import { VelocitySummaryCards } from "../components/velocity/velocity-summary-cards";
import { VelocityPriceOverlayChart } from "../components/velocity/velocity-price-overlay-chart";
import { VelocityImbalanceGauge } from "../components/velocity/velocity-imbalance-gauge";

export default function VelocityPage() {
  const { velocity, history, loading, error } = useVelocityData();

  if (loading) return <VelocitySkeleton />;

  if (error) {
    return (
      <ErrorBanner
        message={`Failed to load velocity data: ${error.message}`}
      />
    );
  }

  return (
    <div className="p-6 space-y-6">
      <VelocitySummaryCards data={velocity} />
      <VelocityPriceOverlayChart history={history} />
      <VelocityImbalanceGauge data={velocity} />
    </div>
  );
}
