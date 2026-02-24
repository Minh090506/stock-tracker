/** Horizontal bar showing buy/sell proportion with threshold markers. */

import type { VelocitySnapshot } from "../../types";

interface VelocityImbalanceGaugeProps {
  data: VelocitySnapshot | null;
}

export function VelocityImbalanceGauge({ data }: VelocityImbalanceGaugeProps) {
  const ratio = data?.vn30f?.imbalance_ratio ?? 0.5;
  const buyPct = ratio * 100;
  const sellPct = 100 - buyPct;

  const label = buyPct > 50 ? `${buyPct.toFixed(1)}% Buy` : buyPct < 50 ? `${sellPct.toFixed(1)}% Sell` : "50/50";

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <h3 className="text-sm font-medium text-gray-400 mb-3">Buy / Sell Imbalance</h3>

      {/* Labels */}
      <div className="flex justify-between text-xs text-gray-500 mb-1">
        <span className="text-red-400">Buy</span>
        <span>{label}</span>
        <span className="text-green-400">Sell</span>
      </div>

      {/* Gauge bar */}
      <div className="relative h-6 rounded-md overflow-hidden flex">
        <div
          className="bg-red-500/70 transition-all duration-300"
          style={{ width: `${buyPct}%` }}
        />
        <div
          className="bg-green-500/70 transition-all duration-300"
          style={{ width: `${sellPct}%` }}
        />

        {/* Threshold markers at 33% and 67% */}
        <div className="absolute left-1/3 top-0 bottom-0 w-px bg-gray-400/30" />
        <div className="absolute left-2/3 top-0 bottom-0 w-px bg-gray-400/30" />
        {/* Center marker */}
        <div className="absolute left-1/2 top-0 bottom-0 w-px bg-white/40" />
      </div>

      {/* Extreme zone labels */}
      <div className="flex justify-between text-[10px] text-gray-600 mt-1">
        <span>Strong Buy</span>
        <span>Neutral</span>
        <span>Strong Sell</span>
      </div>
    </div>
  );
}
