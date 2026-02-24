/** Conditional probability table: imbalance bins → P(price up), avg change. */

import type { ThresholdReport } from "../../types";

interface BacktestThresholdTableProps {
  data: ThresholdReport | null;
}

function probColor(p: number): string {
  if (p >= 0.7) return "text-red-400 font-semibold";
  if (p >= 0.6) return "text-red-300";
  if (p <= 0.3) return "text-green-400 font-semibold";
  if (p <= 0.4) return "text-green-300";
  return "text-gray-300";
}

function rowHighlight(p: number): string {
  if (p >= 0.7 || p <= 0.3) return "bg-gray-800/50";
  return "";
}

export function BacktestThresholdTable({ data }: BacktestThresholdTableProps) {
  if (!data || data.bins.length === 0) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <h3 className="text-sm font-medium text-gray-400 mb-2">
          Threshold Analysis
        </h3>
        <div className="h-40 flex items-center justify-center text-gray-500 text-sm">
          Chua co du lieu threshold
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <h3 className="text-sm font-medium text-gray-400 mb-4">
        Imbalance → Price Direction (lookahead {data.lookahead_minutes} phut)
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-gray-500 border-b border-gray-800">
              <th className="text-left py-2 px-3">Imbalance Range</th>
              <th className="text-right py-2 px-3">Samples</th>
              <th className="text-right py-2 px-3">P(Up)</th>
              <th className="text-right py-2 px-3">Avg Change</th>
              <th className="text-right py-2 px-3">Avg |Change|</th>
            </tr>
          </thead>
          <tbody>
            {data.bins.map((bin, i) => (
              <tr
                key={i}
                className={`border-b border-gray-800/50 ${rowHighlight(bin.price_up_probability)}`}
              >
                <td className="py-2 px-3 text-gray-300">
                  {(bin.imbalance_min * 100).toFixed(0)}% – {(bin.imbalance_max * 100).toFixed(0)}%
                </td>
                <td className="py-2 px-3 text-right text-gray-400">
                  {bin.sample_count.toLocaleString()}
                </td>
                <td className={`py-2 px-3 text-right ${probColor(bin.price_up_probability)}`}>
                  {(bin.price_up_probability * 100).toFixed(1)}%
                </td>
                <td
                  className={`py-2 px-3 text-right ${
                    bin.avg_price_change > 0
                      ? "text-red-400"
                      : bin.avg_price_change < 0
                        ? "text-green-400"
                        : "text-gray-400"
                  }`}
                >
                  {bin.avg_price_change > 0 ? "+" : ""}
                  {bin.avg_price_change.toFixed(4)}
                </td>
                <td className="py-2 px-3 text-right text-gray-300">
                  {bin.avg_magnitude.toFixed(4)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
