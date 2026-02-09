/** Inline SVG sparkline for last N price ticks. */

interface PriceBoardSparklineProps {
  data: number[];
  width?: number;
  height?: number;
}

export function PriceBoardSparkline({
  data,
  width = 80,
  height = 24,
}: PriceBoardSparklineProps) {
  if (data.length < 2) return <div style={{ width, height }} />;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const padding = 1;

  const points = data
    .map((val, i) => {
      const x = padding + (i / (data.length - 1)) * (width - 2 * padding);
      const y = padding + (1 - (val - min) / range) * (height - 2 * padding);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  // Color based on trend: last vs first
  const last = data[data.length - 1] ?? 0;
  const first = data[0] ?? 0;
  const strokeColor = last >= first ? "#22c55e" : "#ef4444";

  return (
    <svg width={width} height={height} className="inline-block">
      <polyline
        points={points}
        fill="none"
        stroke={strokeColor}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
