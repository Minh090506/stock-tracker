/** Three KPI cards showing total net flow, buy volume, and sell volume. */

import { formatVnd, formatVolume } from "../../utils/format-number";
import type { ForeignSummary } from "../../types";

interface ForeignFlowSummaryCardsProps {
  summary: ForeignSummary;
}

export function ForeignFlowSummaryCards({
  summary,
}: ForeignFlowSummaryCardsProps) {
  const netFlowColor =
    summary.total_net_value > 0
      ? "text-red-400"
      : summary.total_net_value < 0
        ? "text-green-400"
        : "text-gray-400";

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {/* Total Net Flow */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div className="text-sm text-gray-400 mb-1">Total Net Flow</div>
        <div className={`text-2xl font-semibold ${netFlowColor}`}>
          {formatVnd(summary.total_net_value)}
        </div>
        <div className="text-xs text-gray-500 mt-1">
          Volume: {formatVolume(summary.total_net_volume)}
        </div>
      </div>

      {/* Total Buy Volume */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div className="text-sm text-gray-400 mb-1">Total Buy Volume</div>
        <div className="text-2xl font-semibold text-red-400">
          {formatVolume(summary.total_buy_volume)}
        </div>
        <div className="text-xs text-gray-500 mt-1">
          Value: {formatVnd(summary.total_buy_value)}
        </div>
      </div>

      {/* Total Sell Volume */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div className="text-sm text-gray-400 mb-1">Total Sell Volume</div>
        <div className="text-2xl font-semibold text-green-400">
          {formatVolume(summary.total_sell_volume)}
        </div>
        <div className="text-xs text-gray-500 mt-1">
          Value: {formatVnd(summary.total_sell_value)}
        </div>
      </div>
    </div>
  );
}
