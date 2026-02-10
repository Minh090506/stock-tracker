/** Area chart showing cumulative foreign net flow (total_net_value) over intraday. */

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import { formatVnd } from "../../utils/format-number";
import type { FlowPoint } from "../../hooks/use-foreign-flow";

interface ForeignCumulativeFlowChartProps {
  flowHistory: FlowPoint[];
}

export function ForeignCumulativeFlowChart({
  flowHistory,
}: ForeignCumulativeFlowChartProps) {
  // Determine color: red if latest net > 0 (net buy), green if < 0 (net sell)
  const latest = flowHistory[flowHistory.length - 1]?.net_value ?? 0;
  const color = latest >= 0 ? "#ef4444" : "#22c55e";
  const gradientId = "foreignFlowGradient";

  // Format timestamp for X-axis: HH:mm
  const formatTime = (iso: string) => {
    const d = new Date(iso);
    return `${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`;
  };

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <h3 className="text-lg font-semibold text-white mb-4">
        Cumulative Foreign Flow
      </h3>
      {flowHistory.length < 2 ? (
        <div className="h-[300px] flex items-center justify-center text-gray-500 text-sm">
          Waiting for data...
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart
            data={flowHistory}
            margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
          >
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.3} />
                <stop offset="95%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis
              dataKey="timestamp"
              tickFormatter={formatTime}
              stroke="#9ca3af"
              tick={{ fontSize: 11 }}
            />
            <YAxis
              stroke="#9ca3af"
              tickFormatter={(v) => formatVnd(v)}
              tick={{ fontSize: 11 }}
            />
            <Tooltip
              labelFormatter={(label) => formatTime(String(label))}
              formatter={(value) => [formatVnd(Number(value)), "Net Flow"]}
              contentStyle={{
                backgroundColor: "#1f2937",
                border: "1px solid #374151",
                borderRadius: "0.375rem",
              }}
              labelStyle={{ color: "#f3f4f6" }}
            />
            <ReferenceLine y={0} stroke="#6b7280" strokeDasharray="3 3" />
            <Area
              type="monotone"
              dataKey="net_value"
              stroke={color}
              fill={`url(#${gradientId})`}
              strokeWidth={2}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
