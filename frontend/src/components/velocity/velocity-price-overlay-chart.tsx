/** Dual-axis ComposedChart: velocity bars (left Y) + VN30F price line (right Y). */

import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { VelocityHistoryPoint } from "../../types";

interface VelocityPriceOverlayChartProps {
  history: VelocityHistoryPoint[];
}

/** Format ISO timestamp to HH:mm */
function formatTime(ts: string): string {
  const d = new Date(ts);
  return d.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
}

interface ChartRow {
  time: string;
  netVelocity: number;
  buyVol: number;
  sellVol: number;
}

export function VelocityPriceOverlayChart({ history }: VelocityPriceOverlayChartProps) {
  if (history.length === 0) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <h3 className="text-sm font-medium text-gray-400 mb-2">Velocity Over Time</h3>
        <div className="h-64 flex items-center justify-center text-gray-500 text-sm">
          No velocity history available yet
        </div>
      </div>
    );
  }

  const chartData: ChartRow[] = history.map((p) => ({
    time: formatTime(p.timestamp),
    netVelocity: p.buy_vol - p.sell_vol,
    buyVol: p.buy_vol,
    sellVol: p.sell_vol,
  }));

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <h3 className="text-sm font-medium text-gray-400 mb-4">
        Net Velocity (Buy - Sell Volume / min)
      </h3>
      <ResponsiveContainer width="100%" height={320}>
        <ComposedChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
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
            tickFormatter={(v: number) => {
              const abs = Math.abs(v);
              if (abs >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
              if (abs >= 1e3) return `${(v / 1e3).toFixed(0)}K`;
              return v.toFixed(0);
            }}
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
            formatter={((value: number, name: string) => {
              const abs = Math.abs(value);
              const formatted = abs >= 1e6
                ? `${(value / 1e6).toFixed(2)}M`
                : abs >= 1e3
                  ? `${(value / 1e3).toFixed(1)}K`
                  : value.toFixed(0);
              const label = name === "netVelocity" ? "Net" : name === "buyVol" ? "Buy" : "Sell";
              return [formatted, label];
            }) as any}
          />
          {/* Stacked buy/sell bars for context */}
          <Bar dataKey="buyVol" stackId="vol" fill="#f8717188" name="buyVol" />
          <Bar dataKey="sellVol" stackId="vol" fill="#4ade8088" name="sellVol" />
          {/* Net velocity line overlay */}
          <Line
            type="monotone"
            dataKey="netVelocity"
            stroke="#facc15"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 3, fill: "#facc15" }}
            name="netVelocity"
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
