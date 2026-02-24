/** Four KPI cards: optimal lag, best threshold, strongest pattern, data coverage. */

import type { BacktestSummary } from "../../types";

interface BacktestSummaryCardsProps {
  data: BacktestSummary | null;
}

export function BacktestSummaryCards({ data }: BacktestSummaryCardsProps) {
  if (!data) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 text-gray-500 text-sm">
        Dang thu thap du lieu backtest...
      </div>
    );
  }

  const { cross_correlation: cc, threshold: th, patterns: pt } = data;

  // Find best threshold bin (highest predictive value — furthest from 50%)
  const bestBin = th.bins.length > 0
    ? th.bins.reduce((best, bin) =>
        Math.abs(bin.price_up_probability - 0.5) >
        Math.abs(best.price_up_probability - 0.5)
          ? bin
          : best,
      )
    : null;

  // Find strongest pattern entry (highest |avg_correlation|)
  const strongestPattern = pt.patterns.length > 0
    ? pt.patterns.reduce((best, p) =>
        Math.abs(p.avg_correlation) > Math.abs(best.avg_correlation) ? p : best,
      )
    : null;

  const totalSamples = cc.results[0]?.sample_size ?? 0;

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {/* Optimal Lag */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div className="text-sm text-gray-400 mb-1">Optimal Lag</div>
        <div className="text-2xl font-semibold text-blue-400">
          {cc.optimal_lag} phut
        </div>
        <div className="text-xs text-gray-500 mt-1">
          r = {cc.optimal_correlation.toFixed(3)}
        </div>
      </div>

      {/* Best Threshold */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div className="text-sm text-gray-400 mb-1">Best Threshold</div>
        <div
          className={`text-2xl font-semibold ${
            bestBin && bestBin.price_up_probability > 0.6
              ? "text-red-400"
              : bestBin && bestBin.price_up_probability < 0.4
                ? "text-green-400"
                : "text-gray-400"
          }`}
        >
          {bestBin ? `P(up) = ${(bestBin.price_up_probability * 100).toFixed(0)}%` : "N/A"}
        </div>
        <div className="text-xs text-gray-500 mt-1">
          {bestBin
            ? `Imbalance ${(bestBin.imbalance_min * 100).toFixed(0)}-${(bestBin.imbalance_max * 100).toFixed(0)}%`
            : ""}
        </div>
      </div>

      {/* Strongest Pattern */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div className="text-sm text-gray-400 mb-1">Strongest Pattern</div>
        <div className="text-2xl font-semibold text-yellow-400">
          {strongestPattern
            ? `${strongestPattern.hour}:00`
            : "N/A"}
        </div>
        <div className="text-xs text-gray-500 mt-1">
          {strongestPattern
            ? `r = ${strongestPattern.avg_correlation.toFixed(3)} (${strongestPattern.session_phase})`
            : ""}
        </div>
      </div>

      {/* Data Coverage */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div className="text-sm text-gray-400 mb-1">Data Coverage</div>
        <div className="text-2xl font-semibold text-gray-300">
          {data.data_days} ngay
        </div>
        <div className="text-xs text-gray-500 mt-1">
          {totalSamples.toLocaleString()} samples
        </div>
      </div>
    </div>
  );
}
