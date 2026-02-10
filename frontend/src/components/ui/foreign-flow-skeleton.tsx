/** Loading skeleton matching ForeignFlowPage layout:
 *  header + 3 summary cards + 2-col charts + 2-col top tables + detail table. */

export function ForeignFlowSkeleton() {
  return (
    <div className="p-6 space-y-6 animate-pulse">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="h-6 w-32 bg-gray-800 rounded" />
        <div className="h-4 w-16 bg-gray-800 rounded" />
      </div>

      {/* 3 summary cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <div className="h-4 w-24 bg-gray-800 rounded mb-2" />
            <div className="h-7 w-32 bg-gray-800 rounded mb-1" />
            <div className="h-3 w-20 bg-gray-800 rounded" />
          </div>
        ))}
      </div>

      {/* 2-column chart grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="h-5 w-40 bg-gray-800 rounded mb-4" />
          <div className="h-[350px] bg-gray-800/30 rounded" />
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="h-5 w-44 bg-gray-800 rounded mb-4" />
          <div className="h-[300px] bg-gray-800/30 rounded" />
        </div>
      </div>

      {/* 2-column top tables */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {[1, 2].map((i) => (
          <div key={i} className="bg-gray-900 border border-gray-800 rounded-lg">
            <div className="px-4 py-3 border-b border-gray-800">
              <div className="h-4 w-40 bg-gray-800 rounded" />
            </div>
            <div className="p-3 space-y-2">
              {[1, 2, 3, 4, 5].map((j) => (
                <div key={j} className="h-8 bg-gray-800/50 rounded" />
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Detail table skeleton */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-3">
        <div className="h-4 w-32 bg-gray-800 rounded" />
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="h-8 bg-gray-800/50 rounded" />
        ))}
      </div>
    </div>
  );
}
