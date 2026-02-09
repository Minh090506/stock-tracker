/** Shows whether basis is converging toward zero or diverging away.
 * Computed client-side from linear regression slope of recent basis points.
 */

import type { BasisPoint } from "../../types";

interface ConvergenceIndicatorProps {
  points: BasisPoint[];
}

/** Compute linear regression slope over the last N basis values. */
function computeSlope(values: number[]): number {
  const n = values.length;
  if (n < 2) return 0;
  let sumX = 0, sumY = 0, sumXY = 0, sumXX = 0;
  for (let i = 0; i < n; i++) {
    const v = values[i]!;
    sumX += i;
    sumY += v;
    sumXY += i * v;
    sumXX += i * i;
  }
  return (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX);
}

export function ConvergenceIndicator({ points }: ConvergenceIndicatorProps) {
  // Use last 20 points for slope calculation
  const recent = points.slice(-20);
  const basisValues: number[] = recent.map((p) => p.basis);
  const slope = computeSlope(basisValues);
  const lastBasis = basisValues.length > 0 ? basisValues[basisValues.length - 1]! : 0;

  // Converging = basis moving toward zero, diverging = moving away
  // If basis > 0 and slope < 0 → converging. If basis < 0 and slope > 0 → converging.
  const isConverging = lastBasis > 0 ? slope < -0.01 : lastBasis < 0 ? slope > 0.01 : true;
  const isStable = Math.abs(slope) <= 0.01;

  let label: string;
  let color: string;
  let arrow: string;

  if (isStable) {
    label = "Stable";
    color = "text-gray-400";
    arrow = "→";
  } else if (isConverging) {
    label = "Converging";
    color = "text-yellow-400";
    arrow = lastBasis > 0 ? "↘" : "↗";
  } else {
    label = "Diverging";
    color = lastBasis > 0 ? "text-red-400" : "text-green-400";
    arrow = lastBasis > 0 ? "↗" : "↘";
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <h3 className="text-sm font-medium text-gray-400 mb-3">
        Basis Convergence
      </h3>

      {points.length < 2 ? (
        <div className="text-gray-500 text-sm">Insufficient data</div>
      ) : (
        <div className="flex items-center gap-4">
          <span className={`text-3xl ${color}`}>{arrow}</span>
          <div>
            <div className={`text-lg font-semibold ${color}`}>{label}</div>
            <div className="text-xs text-gray-500">
              Slope: {slope > 0 ? "+" : ""}{slope.toFixed(3)} / tick
            </div>
            <div className="text-xs text-gray-500 mt-0.5">
              Based on last {recent.length} data points
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
