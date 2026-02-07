/** Market-wide volume ratio pie chart showing buy/sell/neutral breakdown. */

import { PieChart, Pie, Cell, Legend, ResponsiveContainer, Tooltip } from "recharts";
import type { SessionStats } from "../../types";

interface VolumeMarketPieChartProps {
  stats: SessionStats[];
}

export function VolumeMarketPieChart({ stats }: VolumeMarketPieChartProps) {
  // Aggregate all stats
  const totalBuy = stats.reduce((sum, s) => sum + s.mua_chu_dong_volume, 0);
  const totalSell = stats.reduce((sum, s) => sum + s.ban_chu_dong_volume, 0);
  const totalNeutral = stats.reduce((sum, s) => sum + s.neutral_volume, 0);

  const chartData = [
    { name: "Active Buy", value: totalBuy, color: "#ef4444" },
    { name: "Active Sell", value: totalSell, color: "#22c55e" },
    { name: "Neutral", value: totalNeutral, color: "#eab308" },
  ];

  const total = totalBuy + totalSell + totalNeutral;

  const renderLabel = (entry: { percent?: number; name?: string }) => {
    const percent = ((entry.percent || 0) * 100).toFixed(1);
    return `${entry.name || ""} ${percent}%`;
  };

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <h3 className="text-lg font-semibold mb-4">Market-Wide Volume Ratio</h3>
      {total === 0 ? (
        <div className="h-[280px] flex items-center justify-center text-gray-500">
          No volume data available
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <PieChart>
            <Pie
              data={chartData}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              outerRadius={80}
              label={renderLabel}
              labelLine={false}
            >
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip formatter={(value) => (value as number).toLocaleString()} />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
