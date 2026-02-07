/** Treemap heatmap showing VN30 stocks colored by net buy/sell intensity. */

import { Treemap, ResponsiveContainer } from "recharts";
import { formatVnd } from "../../utils/format-number";
import type { ForeignInvestorData } from "../../types";

interface ForeignNetFlowHeatmapProps {
  stocks: ForeignInvestorData[];
}

export function ForeignNetFlowHeatmap({
  stocks,
}: ForeignNetFlowHeatmapProps) {
  // Transform to treemap format
  const treeData = stocks.map((stock) => ({
    name: stock.symbol,
    size: Math.abs(stock.net_value) || 1, // Size by abs value, min 1
    net_value: stock.net_value,
  }));

  // Find max absolute net value for color intensity scaling
  const maxAbsNetValue = Math.max(
    ...stocks.map((s) => Math.abs(s.net_value)),
    1,
  );

  // Custom content renderer
  const CustomizedContent = (props: {
    x?: number;
    y?: number;
    width?: number;
    height?: number;
    name?: string;
    value?: number;
    net_value?: number;
  }) => {
    const { x, y, width, height, name, net_value } = props;

    if (!x || !y || !width || !height || !name || net_value === undefined) {
      return null;
    }

    // Calculate color intensity
    const intensity = Math.min(Math.abs(net_value) / maxAbsNetValue, 1);

    // Color interpolation: red for positive, green for negative
    let bgColor: string;
    if (net_value > 0) {
      // Red gradient
      const r = Math.floor(239 * intensity + 100 * (1 - intensity));
      bgColor = `rgb(${r}, 68, 68)`;
    } else if (net_value < 0) {
      // Green gradient
      const g = Math.floor(197 * intensity + 100 * (1 - intensity));
      bgColor = `rgb(34, ${g}, 94)`;
    } else {
      bgColor = "rgb(75, 85, 99)"; // gray-600
    }

    return (
      <g>
        <rect
          x={x}
          y={y}
          width={width}
          height={height}
          style={{ fill: bgColor, stroke: "#1f2937", strokeWidth: 2 }}
        />
        {width > 40 && height > 30 && (
          <>
            <text
              x={x + width / 2}
              y={y + height / 2 - 6}
              textAnchor="middle"
              fill="#fff"
              fontSize={12}
              fontWeight="bold"
            >
              {name}
            </text>
            <text
              x={x + width / 2}
              y={y + height / 2 + 10}
              textAnchor="middle"
              fill="#fff"
              fontSize={10}
            >
              {formatVnd(net_value)}
            </text>
          </>
        )}
      </g>
    );
  };

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <h3 className="text-lg font-semibold text-white mb-4">
        Foreign Flow Heatmap
      </h3>
      <ResponsiveContainer width="100%" height={300}>
        <Treemap
          data={treeData}
          dataKey="size"
          stroke="#1f2937"
          content={<CustomizedContent />}
        />
      </ResponsiveContainer>
    </div>
  );
}
