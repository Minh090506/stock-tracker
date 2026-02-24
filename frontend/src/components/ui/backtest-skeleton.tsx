/** Loading skeleton for the backtest analysis page. */

export function BacktestSkeleton() {
  return (
    <div className="p-6 space-y-6 animate-pulse">
      {/* Controls skeleton */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-wrap gap-4">
        <div className="h-9 bg-gray-700 rounded w-40" />
        <div className="h-9 bg-gray-700 rounded w-32" />
        <div className="h-9 bg-gray-700 rounded w-32" />
        <div className="h-9 bg-gray-700 rounded w-36" />
      </div>

      {/* Summary cards skeleton (4 cards) */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <div className="h-3 bg-gray-700 rounded w-20 mb-3" />
            <div className="h-6 bg-gray-700 rounded w-28" />
          </div>
        ))}
      </div>

      {/* Charts skeleton */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="h-4 bg-gray-700 rounded w-48 mb-4" />
          <div className="h-72 bg-gray-800 rounded" />
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="h-4 bg-gray-700 rounded w-48 mb-4" />
          <div className="h-72 bg-gray-800 rounded" />
        </div>
      </div>

      {/* Table skeleton */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div className="h-4 bg-gray-700 rounded w-56 mb-4" />
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-8 bg-gray-800 rounded" />
          ))}
        </div>
      </div>
    </div>
  );
}
