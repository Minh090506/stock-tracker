/** Stacked bar chart showing active buy/sell/neutral volume by stock. */

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { SessionStats } from "../../types";
import { formatVolume } from "../../utils/format-number";

interface VolumeStackedBarChartProps {
  stats: SessionStats[];
}

export function VolumeStackedBarChart({ stats }: VolumeStackedBarChartProps) {
  // Sort by total volume descending
  const sortedStats = [...stats].sort((a, b) => b.total_volume - a.total_volume);

  const chartData = sortedStats.map((s) => ({
    symbol: s.symbol,
    "Active Buy": s.mua_chu_dong_volume,
    "Active Sell": s.ban_chu_dong_volume,
    Neutral: s.neutral_volume,
  }));

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <h3 className="text-lg font-semibold mb-4">Active Buy vs Sell by Stock</h3>
      {chartData.length === 0 ? (
        <div className="h-[400px] flex items-center justify-center text-gray-500">
          No volume data available
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={400}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis dataKey="symbol" stroke="#9ca3af" />
            <YAxis stroke="#9ca3af" tickFormatter={formatVolume} />
            <Tooltip
              formatter={(value) => formatVolume(value as number)}
              contentStyle={{
                backgroundColor: "#1f2937",
                border: "1px solid #374151",
                borderRadius: "0.375rem",
              }}
            />
            <Legend />
            <Bar dataKey="Active Buy" stackId="volume" fill="#ef4444" />
            <Bar dataKey="Active Sell" stackId="volume" fill="#22c55e" />
            <Bar dataKey="Neutral" stackId="volume" fill="#eab308" />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
