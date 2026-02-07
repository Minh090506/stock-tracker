/** Horizontal bar chart showing top 10 stocks by absolute net value. */

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { formatVnd } from "../../utils/format-number";
import type { ForeignInvestorData } from "../../types";

interface ForeignTopMoversBarChartProps {
  stocks: ForeignInvestorData[];
}

export function ForeignTopMoversBarChart({
  stocks,
}: ForeignTopMoversBarChartProps) {
  // Sort by absolute net value descending and take top 10
  const topStocks = [...stocks]
    .sort((a, b) => Math.abs(b.net_value) - Math.abs(a.net_value))
    .slice(0, 10);

  // Transform for chart: negate sell_value for visual balance
  const chartData = topStocks.map((stock) => ({
    symbol: stock.symbol,
    buy_value: stock.buy_value,
    sell_value: -stock.sell_value, // Negate for left-side bars
  }));

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <h3 className="text-lg font-semibold text-white mb-4">Top Movers</h3>
      <ResponsiveContainer width="100%" height={350}>
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis type="number" stroke="#9ca3af" />
          <YAxis
            type="category"
            dataKey="symbol"
            stroke="#9ca3af"
            width={60}
          />
          <Tooltip
            formatter={(value) => formatVnd(Math.abs(Number(value)))}
            contentStyle={{
              backgroundColor: "#1f2937",
              border: "1px solid #374151",
              borderRadius: "0.375rem",
            }}
            labelStyle={{ color: "#f3f4f6" }}
          />
          <Bar dataKey="buy_value" fill="#ef4444" name="Buy" />
          <Bar dataKey="sell_value" fill="#22c55e" name="Sell" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
