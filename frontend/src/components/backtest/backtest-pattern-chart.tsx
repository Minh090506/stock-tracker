/** Grouped bar chart: average correlation by hour-of-day, colored by session phase. */

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
import type { PatternReport } from "../../types";

interface BacktestPatternChartProps {
  data: PatternReport | null;
}

const PHASE_COLORS: Record<string, string> = {
  ato: "#60a5fa",       // blue
  continuous: "#9ca3af", // gray
  atc: "#fb923c",       // orange
};

export function BacktestPatternChart({ data }: BacktestPatternChartProps) {
  if (!data || data.patterns.length === 0) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <h3 className="text-sm font-medium text-gray-400 mb-2">
          Time-of-Day Patterns
        </h3>
        <div className="h-72 flex items-center justify-center text-gray-500 text-sm">
          Chua co du lieu pattern
        </div>
      </div>
    );
  }

  const chartData = data.patterns.map((p) => ({
    hour: `${p.hour}:00`,
    correlation: p.avg_correlation,
    phase: p.session_phase,
    imbalance: p.avg_imbalance,
    samples: p.sample_count,
  }));

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <h3 className="text-sm font-medium text-gray-400 mb-2">
        Correlation by Hour-of-Day
      </h3>
      <div className="flex gap-4 mb-3">
        {Object.entries(PHASE_COLORS).map(([phase, color]) => (
          <div key={phase} className="flex items-center gap-1.5 text-xs text-gray-500">
            <span
              className="inline-block w-3 h-3 rounded-sm"
              style={{ backgroundColor: color }}
            />
            {phase.toUpperCase()}
          </div>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={288}>
        <BarChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
          <XAxis
            dataKey="hour"
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
            formatter={((value: number, _name: string, props: { payload: { phase: string; samples: number } }) => [
              `${value.toFixed(4)} (${props.payload.phase}, n=${props.payload.samples})`,
              "Avg Correlation",
            ]) as any}
          />
          <Bar dataKey="correlation" radius={[3, 3, 0, 0]}>
            {chartData.map((entry, idx) => (
              <Cell
                key={idx}
                fill={PHASE_COLORS[entry.phase] ?? "#9ca3af"}
                opacity={0.8}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
