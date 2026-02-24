/** Loading skeleton for the velocity analysis page. */

export function VelocitySkeleton() {
  return (
    <div className="p-6 space-y-6 animate-pulse">
      {/* Summary cards skeleton (5 cards) */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <div className="h-3 bg-gray-700 rounded w-20 mb-3" />
            <div className="h-6 bg-gray-700 rounded w-28" />
          </div>
        ))}
      </div>

      {/* Chart skeleton */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div className="h-4 bg-gray-700 rounded w-48 mb-4" />
        <div className="h-80 bg-gray-800 rounded" />
      </div>

      {/* Gauge skeleton */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div className="h-4 bg-gray-700 rounded w-40 mb-3" />
        <div className="h-6 bg-gray-800 rounded" />
      </div>
    </div>
  );
}
