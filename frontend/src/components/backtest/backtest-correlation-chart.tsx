/** Bar chart: cross-correlation by lag (0..10 minutes). */

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { CrossCorrelationReport } from "../../types";

interface BacktestCorrelationChartProps {
  data: CrossCorrelationReport | null;
}

export function BacktestCorrelationChart({ data }: BacktestCorrelationChartProps) {
  if (!data || data.results.length === 0) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <h3 className="text-sm font-medium text-gray-400 mb-2">
          Cross-Correlation (Lead-Lag)
        </h3>
        <div className="h-72 flex items-center justify-center text-gray-500 text-sm">
          Chua co du lieu cross-correlation
        </div>
      </div>
    );
  }

  const chartData = data.results.map((r) => ({
    lag: `${r.lag_minutes}m`,
    correlation: r.correlation,
    samples: r.sample_size,
    isOptimal: r.lag_minutes === data.optimal_lag,
  }));

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <h3 className="text-sm font-medium text-gray-400 mb-4">
        Cross-Correlation (Lag 0-{data.results.length - 1} phut)
      </h3>
      <ResponsiveContainer width="100%" height={288}>
        <BarChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
          <XAxis
            dataKey="lag"
            tick={{ fontSize: 11, fill: "#9ca3af" }}
            tickLine={false}
            axisLine={{ stroke: "#374151" }}
          />
          <YAxis
            domain={[-1, 1]}
            tick={{ fontSize: 11, fill: "#9ca3af" }}
            tickLine={false}
            axisLine={{ stroke: "#374151" }}
            tickFormatter={(v: number) => v.toFixed(1)}
          />
          <ReferenceLine y={0} stroke="#4b5563" strokeDasharray="3 3" />
          <Tooltip
            contentStyle={{
              backgroundColor: "#1f2937",
              border: "1px solid #374151",
              borderRadius: "6px",
              fontSize: "12px",
            }}
            labelStyle={{ color: "#9ca3af" }}
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            formatter={((value: number, _name: string, props: { payload: { samples: number } }) => [
              `${value.toFixed(4)} (n=${props.payload.samples})`,
              "Correlation",
            ]) as any}
          />
          <Bar dataKey="correlation" radius={[3, 3, 0, 0]}>
            {chartData.map((entry, idx) => (
              <Cell
                key={idx}
                fill={
                  entry.isOptimal
                    ? "#facc15" // yellow highlight for optimal
                    : entry.correlation >= 0
                      ? "#f87171" // red for positive
                      : "#4ade80" // green for negative
                }
                opacity={entry.isOptimal ? 1 : 0.7}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
