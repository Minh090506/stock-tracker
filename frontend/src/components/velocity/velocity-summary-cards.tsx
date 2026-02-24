/** Five KPI cards: buy velocity, sell velocity, net velocity, imbalance ratio, correlation. */

import { formatVolume } from "../../utils/format-number";
import type { VelocitySnapshot } from "../../types";

interface VelocitySummaryCardsProps {
  data: VelocitySnapshot | null;
}

/** Format correlation coefficient with color class. */
function correlationColor(coeff: number): string {
  if (coeff >= 0.5) return "text-blue-400";
  if (coeff <= -0.5) return "text-red-400";
  return "text-gray-400";
}

export function VelocitySummaryCards({ data }: VelocitySummaryCardsProps) {
  if (!data?.vn30f) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 text-gray-500 text-sm">
        Waiting for velocity data...
      </div>
    );
  }

  const v = data.vn30f;
  const corr = data.correlation;
  const netColor = v.net_vol_per_min > 0 ? "text-red-400" : v.net_vol_per_min < 0 ? "text-green-400" : "text-gray-400";
  const imbalancePct = (v.imbalance_ratio * 100).toFixed(1);
  const imbalanceColor = v.imbalance_ratio > 0.55 ? "text-red-400" : v.imbalance_ratio < 0.45 ? "text-green-400" : "text-gray-400";

  return (
    <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
      {/* Buy Velocity */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div className="text-sm text-gray-400 mb-1">Buy Velocity</div>
        <div className="text-2xl font-semibold text-red-400">
          {formatVolume(v.buy_vol_per_min)}
        </div>
        <div className="text-xs text-gray-500 mt-1">
          {v.buy_count_per_min.toFixed(0)} orders/min
        </div>
      </div>

      {/* Sell Velocity */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div className="text-sm text-gray-400 mb-1">Sell Velocity</div>
        <div className="text-2xl font-semibold text-green-400">
          {formatVolume(v.sell_vol_per_min)}
        </div>
        <div className="text-xs text-gray-500 mt-1">
          {v.sell_count_per_min.toFixed(0)} orders/min
        </div>
      </div>

      {/* Net Velocity */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div className="text-sm text-gray-400 mb-1">Net Velocity</div>
        <div className={`text-2xl font-semibold ${netColor}`}>
          {v.net_vol_per_min > 0 ? "+" : ""}{formatVolume(v.net_vol_per_min)}
        </div>
        <div className="text-xs text-gray-500 mt-1">
          Accel: {v.acceleration > 0 ? "+" : ""}{v.acceleration.toFixed(1)}
        </div>
      </div>

      {/* Imbalance Ratio */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div className="text-sm text-gray-400 mb-1">Imbalance</div>
        <div className={`text-2xl font-semibold ${imbalanceColor}`}>
          {imbalancePct}%
        </div>
        <div className="text-xs text-gray-500 mt-1">
          {v.imbalance_ratio > 0.5 ? "Buy dominant" : v.imbalance_ratio < 0.5 ? "Sell dominant" : "Neutral"}
        </div>
      </div>

      {/* Correlation */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div className="text-sm text-gray-400 mb-1">Correlation</div>
        <div className={`text-2xl font-semibold ${corr ? correlationColor(corr.coefficient) : "text-gray-500"}`}>
          {corr ? corr.coefficient.toFixed(3) : "N/A"}
        </div>
        <div className="text-xs text-gray-500 mt-1">
          {corr ? `${corr.sample_size} samples / ${corr.window_minutes}m` : "Collecting..."}
        </div>
      </div>
    </div>
  );
}
