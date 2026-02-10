/** Horizontal bar chart showing foreign net buy/sell aggregated by sector (top 10). */

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
import { formatVnd } from "../../utils/format-number";
import { getSector } from "../../utils/vn30-sector-map";
import type { ForeignInvestorData } from "../../types";

interface ForeignSectorBarChartProps {
  stocks: ForeignInvestorData[];
}

interface SectorRow {
  sector: string;
  buy_value: number;
  sell_value: number;
  net_value: number;
}

export function ForeignSectorBarChart({ stocks }: ForeignSectorBarChartProps) {
  // Aggregate buy/sell value by sector
  const sectorMap = new Map<string, { buy: number; sell: number }>();
  for (const s of stocks) {
    const sector = getSector(s.symbol);
    const prev = sectorMap.get(sector) ?? { buy: 0, sell: 0 };
    prev.buy += s.buy_value;
    prev.sell += s.sell_value;
    sectorMap.set(sector, prev);
  }

  // Sort by absolute net value descending, take top 10
  const rows: SectorRow[] = [...sectorMap.entries()]
    .map(([sector, v]) => ({
      sector,
      buy_value: v.buy,
      sell_value: -v.sell, // negate for left-side bars
      net_value: v.buy - v.sell,
    }))
    .sort((a, b) => Math.abs(b.net_value) - Math.abs(a.net_value))
    .slice(0, 10);

  if (rows.length === 0) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <h3 className="text-lg font-semibold text-white mb-4">
          Foreign Flow by Sector
        </h3>
        <div className="h-[350px] flex items-center justify-center text-gray-500 text-sm">
          No sector data available
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <h3 className="text-lg font-semibold text-white mb-4">
        Foreign Flow by Sector
      </h3>
      <ResponsiveContainer width="100%" height={350}>
        <BarChart
          data={rows}
          layout="vertical"
          margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            type="number"
            stroke="#9ca3af"
            tickFormatter={(v) => formatVnd(Math.abs(v))}
          />
          <YAxis
            type="category"
            dataKey="sector"
            stroke="#9ca3af"
            width={90}
            tick={{ fontSize: 12 }}
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
          <Legend />
          <Bar dataKey="buy_value" fill="#ef4444" name="Buy" />
          <Bar dataKey="sell_value" fill="#22c55e" name="Sell" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
