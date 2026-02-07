# Phase 2: Loading Skeletons

## Context
- [page-loading-skeleton.tsx](/Users/minh/Projects/stock-tracker/frontend/src/components/ui/page-loading-skeleton.tsx) -- generic pulsing divs (3 cards + 2 blocks)
- [foreign-flow-page.tsx](/Users/minh/Projects/stock-tracker/frontend/src/pages/foreign-flow-page.tsx) -- 3 summary cards + 2-col chart grid + table
- [volume-analysis-page.tsx](/Users/minh/Projects/stock-tracker/frontend/src/pages/volume-analysis-page.tsx) -- title + 2-col (pie + 3 ratio cards) + stacked bar + table
- [signals-page.tsx](/Users/minh/Projects/stock-tracker/frontend/src/pages/signals-page.tsx) -- title + filter chips + signal cards list

## Overview
- **Priority:** P2
- **Status:** pending
- **Effort:** 1.5h

Replace the generic `PageLoadingSkeleton` with page-specific skeletons that match each page's actual layout. This reduces perceived loading time by showing structure before content loads.

## Key Insights
- Each page has a distinct layout; one generic skeleton doesn't match any of them well
- Use `animate-pulse` with `bg-gray-800` blocks matching actual component sizes
- Keep skeletons simple: gray rectangles in the right positions, no complex shapes
- Skeletons used in two places: Suspense fallback (App.tsx) AND in-page loading state

## Requirements

**Functional:**
- 3 page-specific skeletons matching actual page layouts
- Reuse in both Suspense fallback and in-page loading conditionals

**Non-functional:**
- Smooth pulse animation (existing `animate-pulse` from Tailwind)
- Skeleton layout matches actual content at lg breakpoint

## Related Code Files

**Create:**
- `frontend/src/components/ui/foreign-flow-skeleton.tsx`
- `frontend/src/components/ui/volume-analysis-skeleton.tsx`
- `frontend/src/components/ui/signals-skeleton.tsx`

**Modify:**
- `frontend/src/App.tsx` -- use page-specific skeletons in Suspense
- `frontend/src/pages/foreign-flow-page.tsx` -- use specific skeleton for loading state
- `frontend/src/pages/volume-analysis-page.tsx` -- use specific skeleton for loading state

## Implementation Steps

### Step 1: Create ForeignFlowSkeleton

File: `frontend/src/components/ui/foreign-flow-skeleton.tsx`

Matches ForeignFlowPage layout: 3 summary cards row + 2-column chart grid + table.

```tsx
export function ForeignFlowSkeleton() {
  return (
    <div className="p-6 space-y-6 animate-pulse">
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
        <div className="h-64 bg-gray-900 border border-gray-800 rounded-lg" />
        <div className="h-64 bg-gray-900 border border-gray-800 rounded-lg" />
      </div>

      {/* Table skeleton */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-3">
        <div className="h-4 w-32 bg-gray-800 rounded" />
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="h-8 bg-gray-800/50 rounded" />
        ))}
      </div>
    </div>
  );
}
```

### Step 2: Create VolumeAnalysisSkeleton

File: `frontend/src/components/ui/volume-analysis-skeleton.tsx`

Matches VolumeAnalysisPage: title + 2-col (pie chart + 3 ratio cards) + stacked bar + table.

```tsx
export function VolumeAnalysisSkeleton() {
  return (
    <div className="p-6 space-y-6 animate-pulse">
      {/* Title */}
      <div className="h-8 w-48 bg-gray-800 rounded" />

      {/* Top row: Pie chart + Ratio cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="h-64 bg-gray-900 border border-gray-800 rounded-lg" />
        <div className="grid grid-cols-3 gap-4">
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
```

### Step 3: Create SignalsSkeleton

File: `frontend/src/components/ui/signals-skeleton.tsx`

Matches SignalsPage: title + filter chips row + signal card list.

```tsx
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
```

### Step 4: Update App.tsx Suspense fallbacks

Replace `<PageLoadingSkeleton />` with page-specific skeletons:

```tsx
import { ForeignFlowSkeleton } from "./components/ui/foreign-flow-skeleton";
import { VolumeAnalysisSkeleton } from "./components/ui/volume-analysis-skeleton";
import { SignalsSkeleton } from "./components/ui/signals-skeleton";

// In routes:
<Suspense fallback={<ForeignFlowSkeleton />}>
<Suspense fallback={<VolumeAnalysisSkeleton />}>
<Suspense fallback={<SignalsSkeleton />}>
```

### Step 5: Update page loading states

In `foreign-flow-page.tsx` and `volume-analysis-page.tsx`, replace `<PageLoadingSkeleton />` with the page-specific skeleton.

**Note:** `signals-page.tsx` doesn't have an explicit loading state (useSignals is sync mock), so no change needed there until signals hook becomes async.

## Todo List

- [ ] Create `foreign-flow-skeleton.tsx`
- [ ] Create `volume-analysis-skeleton.tsx`
- [ ] Create `signals-skeleton.tsx`
- [ ] Update `App.tsx` Suspense fallbacks to use page-specific skeletons
- [ ] Update `foreign-flow-page.tsx` loading state to use `ForeignFlowSkeleton`
- [ ] Update `volume-analysis-page.tsx` loading state to use `VolumeAnalysisSkeleton`

## Success Criteria
- Each page's loading skeleton visually mirrors its actual layout
- No layout shift when content replaces skeleton
- Smooth animate-pulse animation on all skeletons

## Risk Assessment
- **Low risk**: Pure presentational components, no logic
- **Consideration**: Keep `PageLoadingSkeleton` as generic fallback for any future pages
