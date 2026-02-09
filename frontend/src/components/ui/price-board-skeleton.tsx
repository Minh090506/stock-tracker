/** Loading skeleton matching PriceBoardPage layout: header + 30-row table. */

export function PriceBoardSkeleton() {
  return (
    <div className="p-6 space-y-4 animate-pulse">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="h-6 w-40 bg-gray-800 rounded" />
        <div className="h-4 w-24 bg-gray-800 rounded" />
      </div>

      {/* Table skeleton */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-2">
        {/* Header row */}
        <div className="flex gap-4 pb-2 border-b border-gray-800">
          {[1, 2, 3, 4, 5, 6, 7].map((i) => (
            <div key={i} className="h-4 w-16 bg-gray-800 rounded flex-1" />
          ))}
        </div>
        {/* 10 visible skeleton rows */}
        {Array.from({ length: 10 }, (_, i) => (
          <div key={i} className="h-8 bg-gray-800/40 rounded" />
        ))}
      </div>
    </div>
  );
}
