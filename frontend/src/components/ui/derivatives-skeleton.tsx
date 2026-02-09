/** Loading skeleton for the derivatives analysis page. */

export function DerivativesSkeleton() {
  return (
    <div className="p-6 space-y-6 animate-pulse">
      {/* Summary cards skeleton */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <div className="h-3 bg-gray-700 rounded w-20 mb-3" />
            <div className="h-6 bg-gray-700 rounded w-28" />
          </div>
        ))}
      </div>

      {/* Chart skeleton */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div className="h-4 bg-gray-700 rounded w-32 mb-4" />
        <div className="h-64 bg-gray-800 rounded" />
      </div>

      {/* Bottom row skeleton */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="h-4 bg-gray-700 rounded w-40 mb-3" />
          <div className="h-16 bg-gray-800 rounded" />
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="h-4 bg-gray-700 rounded w-32 mb-3" />
          <div className="h-16 bg-gray-800 rounded" />
        </div>
      </div>
    </div>
  );
}
