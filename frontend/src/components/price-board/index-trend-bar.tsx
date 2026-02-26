/** VN30 Index trend bar — shows real-time index value, breadth, and intraday sparkline.
 *  Data comes directly from SSI MI:ALL channel (not aggregated from 30 stocks). */

import type { IndexData } from "../../types";

interface IndexTrendBarProps {
  data: IndexData;
}

/** Determine trend label + color from advance_ratio */
function getTrend(advanceRatio: number): { label: string; colorClass: string } {
  if (advanceRatio >= 0.65) return { label: "Strong Up", colorClass: "text-green-400" };
  if (advanceRatio >= 0.5) return { label: "Lean Up", colorClass: "text-green-300" };
  if (advanceRatio >= 0.35) return { label: "Mixed", colorClass: "text-yellow-400" };
  if (advanceRatio >= 0.2) return { label: "Lean Down", colorClass: "text-red-300" };
  return { label: "Strong Down", colorClass: "text-red-400" };
}

/** Mini inline sparkline for index intraday */
function IndexSparkline({ data }: { data: { value: number }[] }) {
  const W = 120;
  const H = 28;
  if (data.length < 2) return <div style={{ width: W, height: H }} />;

  const values = data.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const pad = 1;

  const points = values
    .map((v, i) => {
      const x = pad + (i / (values.length - 1)) * (W - 2 * pad);
      const y = pad + (1 - (v - min) / range) * (H - 2 * pad);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  const last = values[values.length - 1] ?? 0;
  const first = values[0] ?? 0;
  const stroke = last >= first ? "#22c55e" : "#ef4444";

  return (
    <svg width={W} height={H} className="inline-block">
      <polyline
        points={points}
        fill="none"
        stroke={stroke}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function IndexTrendBar({ data }: IndexTrendBarProps) {
  const changeSign = data.change >= 0 ? "+" : "";
  const changeColor = data.change > 0
    ? "text-green-400"
    : data.change < 0
      ? "text-red-400"
      : "text-gray-300";
  const trend = getTrend(data.advance_ratio);
  const totalBreadth = data.advances + data.declines + data.no_changes;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg px-4 py-3 flex items-center gap-6 flex-wrap">
      {/* Index value + change */}
      <div className="flex items-baseline gap-3">
        <span className="text-sm text-gray-400 font-medium">VN30</span>
        <span className={`text-xl font-bold tabular-nums ${changeColor}`}>
          {data.value.toFixed(2)}
        </span>
        <span className={`text-sm font-mono ${changeColor}`}>
          {changeSign}{data.change.toFixed(2)} ({changeSign}{data.ratio_change.toFixed(2)}%)
        </span>
      </div>

      {/* Breadth bar: advances / declines / no_changes */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-gray-500">Breadth</span>
        {totalBreadth > 0 ? (
          <div className="flex items-center gap-1.5">
            <div className="flex h-2.5 w-24 rounded-full overflow-hidden bg-gray-700">
              <div
                className="bg-green-500 transition-all duration-300"
                style={{ width: `${(data.advances / totalBreadth) * 100}%` }}
              />
              <div
                className="bg-yellow-500 transition-all duration-300"
                style={{ width: `${(data.no_changes / totalBreadth) * 100}%` }}
              />
              <div
                className="bg-red-500 transition-all duration-300"
                style={{ width: `${(data.declines / totalBreadth) * 100}%` }}
              />
            </div>
            <span className="text-xs tabular-nums">
              <span className="text-green-400">{data.advances}</span>
              <span className="text-gray-500">/</span>
              <span className="text-yellow-400">{data.no_changes}</span>
              <span className="text-gray-500">/</span>
              <span className="text-red-400">{data.declines}</span>
            </span>
          </div>
        ) : (
          <span className="text-xs text-gray-500">-</span>
        )}
      </div>

      {/* Trend label */}
      <div className="flex items-center gap-1.5">
        <span className="text-xs text-gray-500">Trend</span>
        <span className={`text-xs font-semibold ${trend.colorClass}`}>{trend.label}</span>
      </div>

      {/* Intraday sparkline */}
      <div className="flex items-center gap-1.5 ml-auto">
        <span className="text-xs text-gray-500">Intraday</span>
        <IndexSparkline data={data.intraday} />
      </div>
    </div>
  );
}
