/** Loading skeleton matching SignalsPage layout: title + filter chips + signal card list. */

export function SignalsSkeleton() {
  return (
    <div className="p-6 space-y-6 animate-pulse">
      {/* Title */}
      <div className="h-8 w-32 bg-gray-800 rounded" />

      {/* Filter chips */}
      <div className="flex gap-2">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-9 w-20 bg-gray-800 rounded-lg" />
        ))}
      </div>

      {/* Signal cards */}
      <div className="space-y-2">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div key={i} className="bg-gray-900 border border-gray-800 rounded-lg p-3 flex items-center gap-3">
            <div className="h-4 w-16 bg-gray-800 rounded" />
            <div className="h-6 w-14 bg-gray-800 rounded" />
            <div className="h-4 w-12 bg-gray-800 rounded" />
            <div className="h-4 flex-1 bg-gray-800 rounded" />
          </div>
        ))}
      </div>
    </div>
  );
}
