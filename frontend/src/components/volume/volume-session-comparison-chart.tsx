/** Bar chart comparing ATO vs Continuous vs ATC session volumes. */

import { useMemo } from "react";
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

interface VolumeSessionComparisonChartProps {
  stats: SessionStats[];
}

/** Aggregate all symbols' session breakdowns into market-wide totals. */
function buildChartData(stats: SessionStats[]) {
  const sessions = { ato: "ATO", continuous: "Continuous", atc: "ATC" } as const;

  return Object.entries(sessions).map(([key, label]) => {
    let buy = 0, sell = 0, neutral = 0;
    for (const s of stats) {
      const b = s[key as keyof typeof sessions];
      if (!b) continue;
      buy += b.mua_chu_dong_volume;
      sell += b.ban_chu_dong_volume;
      neutral += b.neutral_volume;
    }
    return {
      session: label,
      "Active Buy": buy,
      "Active Sell": sell,
      Neutral: neutral,
      total: buy + sell + neutral,
    };
  });
}

export function VolumeSessionComparisonChart({ stats }: VolumeSessionComparisonChartProps) {
  const chartData = useMemo(() => buildChartData(stats), [stats]);
  const hasData = chartData.some((d) => d.total > 0);

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <h3 className="text-lg font-semibold mb-1">Session Volume Comparison</h3>
      <p className="text-sm text-gray-500 mb-4">
        ATO (9:00–9:15) · Continuous (9:15–14:30) · ATC (14:30–14:45)
      </p>
      {!hasData ? (
        <div className="h-75 flex items-center justify-center text-gray-500">
          No session data available
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={chartData} barCategoryGap="30%">
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis dataKey="session" stroke="#9ca3af" />
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
            <Bar dataKey="Active Buy" stackId="vol" fill="#ef4444" />
            <Bar dataKey="Active Sell" stackId="vol" fill="#22c55e" />
            <Bar dataKey="Neutral" stackId="vol" fill="#eab308" />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
