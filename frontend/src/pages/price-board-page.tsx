/** VN30 Price Board — real-time stock prices with sparklines and sorting. */

import { usePriceBoardData } from "../hooks/use-price-board-data";
import { PriceBoardSkeleton } from "../components/ui/price-board-skeleton";
import { ErrorBanner } from "../components/ui/error-banner";
import { PriceBoardTable } from "../components/price-board/price-board-table";

export default function PriceBoardPage() {
  const { rows, loading, error, isLive, status, reconnect } = usePriceBoardData();

  if (loading) return <PriceBoardSkeleton />;

  if (error && rows.length === 0) {
    return <ErrorBanner message={`Failed to load price data: ${error.message}`} onRetry={reconnect} />;
  }

  return (
    <div className="p-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">VN30 Price Board</h2>
        <div className="flex items-center gap-2 text-xs">
          <span className={`inline-block w-2 h-2 rounded-full ${
            isLive ? "bg-green-500" : "bg-yellow-500"
          }`} />
          <span className="text-gray-400">
            {isLive ? "Live" : "Polling"}
            {status === "disconnected" && " (reconnecting...)"}
          </span>
        </div>
      </div>

      {/* Non-blocking error — show stale data + warning */}
      {error && rows.length > 0 && (
        <div className="text-xs text-yellow-400 bg-yellow-900/20 px-3 py-2 rounded">
          Connection issue — showing last known data
        </div>
      )}

      {/* Price table */}
      <PriceBoardTable rows={rows} />
    </div>
  );
}
