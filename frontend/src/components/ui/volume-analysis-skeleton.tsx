/** Loading skeleton matching VolumeAnalysisPage layout: title + pie/cards row + bar chart + table. */

export function VolumeAnalysisSkeleton() {
  return (
    <div className="p-6 space-y-6 animate-pulse">
      {/* Title */}
      <div className="h-8 w-48 bg-gray-800 rounded" />

      {/* Top row: Pie chart + Ratio cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="h-64 bg-gray-900 border border-gray-800 rounded-lg" />
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col items-center justify-center">
              <div className="h-7 w-16 bg-gray-800 rounded mb-1" />
              <div className="h-3 w-12 bg-gray-800 rounded" />
            </div>
          ))}
        </div>
      </div>

      {/* Stacked bar chart */}
      <div className="h-64 bg-gray-900 border border-gray-800 rounded-lg" />

      {/* Table */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-3">
        <div className="h-4 w-32 bg-gray-800 rounded" />
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="h-8 bg-gray-800/50 rounded" />
        ))}
      </div>
    </div>
  );
}
