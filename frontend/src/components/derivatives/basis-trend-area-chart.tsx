/** Recharts AreaChart showing basis (futures - spot) over time. */

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import type { BasisPoint } from "../../types";

interface BasisTrendAreaChartProps {
  points: BasisPoint[];
}

/** Format ISO timestamp to HH:MM:SS for chart axis */
function formatTime(ts: string): string {
  const d = new Date(ts);
  return d.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function BasisTrendAreaChart({ points }: BasisTrendAreaChartProps) {
  if (points.length === 0) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <h3 className="text-sm font-medium text-gray-400 mb-2">Basis Trend</h3>
        <div className="h-64 flex items-center justify-center text-gray-500 text-sm">
          No basis data available yet
        </div>
      </div>
    );
  }

  const chartData = points.map((p) => ({
    time: formatTime(p.timestamp),
    basis: p.basis,
    basisPct: p.basis_pct,
    futuresPrice: p.futures_price,
    spotValue: p.spot_value,
  }));

  // Determine color: last point premium/discount
  const lastPoint = points[points.length - 1]!;
  const areaColor = lastPoint.is_premium ? "#f87171" : "#4ade80"; // red-400 / green-400
  const fillColor = lastPoint.is_premium ? "#f8717133" : "#4ade8033";

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <h3 className="text-sm font-medium text-gray-400 mb-4">
        Basis Trend (Futures - Spot)
      </h3>
      <ResponsiveContainer width="100%" height={280}>
        <AreaChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
          <XAxis
            dataKey="time"
            tick={{ fontSize: 11, fill: "#9ca3af" }}
            tickLine={false}
            axisLine={{ stroke: "#374151" }}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fontSize: 11, fill: "#9ca3af" }}
            tickLine={false}
            axisLine={{ stroke: "#374151" }}
            tickFormatter={(v: number) => v.toFixed(1)}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#1f2937",
              border: "1px solid #374151",
              borderRadius: "6px",
              fontSize: "12px",
            }}
            labelStyle={{ color: "#9ca3af" }}
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            formatter={((value: number) => [`${value.toFixed(2)}`, "Basis"]) as any}
          />
          <ReferenceLine
            y={0}
            stroke="#6b7280"
            strokeDasharray="4 4"
            label={{ value: "0", position: "left", fill: "#6b7280", fontSize: 11 }}
          />
          <Area
            type="monotone"
            dataKey="basis"
            stroke={areaColor}
            fill={fillColor}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 3, fill: areaColor }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
