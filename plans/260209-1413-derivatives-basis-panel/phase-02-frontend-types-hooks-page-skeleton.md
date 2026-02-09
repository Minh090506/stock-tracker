# Phase 2: Frontend — Types, Hooks, Page Structure, Skeleton, Nav

## Priority: P1 | Status: pending | Effort: 40min

## Overview

Set up the frontend scaffolding: add `BasisPoint` type, create data hooks, page component, loading skeleton, sidebar nav entry, and App.tsx route.

## Context Links

- [types/index.ts](../../frontend/src/types/index.ts) — add `BasisPoint` type
- [use-polling.ts](../../frontend/src/hooks/use-polling.ts) — reuse for basis-trend polling
- [use-market-snapshot.ts](../../frontend/src/hooks/use-market-snapshot.ts) — already returns `derivatives` field
- [foreign-flow-page.tsx](../../frontend/src/pages/foreign-flow-page.tsx) — page pattern to follow
- [foreign-flow-skeleton.tsx](../../frontend/src/components/ui/foreign-flow-skeleton.tsx) — skeleton pattern
- [app-sidebar-navigation.tsx](../../frontend/src/components/layout/app-sidebar-navigation.tsx) — add nav item
- [App.tsx](../../frontend/src/App.tsx) — add route

## Requirements

### Functional
- `BasisPoint` TS type matching backend model
- `useBasisTrend(minutes?, intervalMs?)` hook polling `/api/market/basis-trend`
- `useDerivativesData()` hook combining snapshot derivatives + basis trend
- Derivatives page with loading/error/empty states
- Skeleton matching page layout (4 summary cards + chart + 2-col bottom)
- "Derivatives" nav item in sidebar (between "Volume Analysis" and "Signals")
- Lazy-loaded route at `/derivatives`

### Non-functional
- All files < 200 lines
- Dark theme consistent with existing pages

## Architecture

```
useDerivativesData()
  +-- useMarketSnapshot()     -> snapshot.derivatives (DerivativesData)
  +-- useBasisTrend(30, 10000) -> BasisPoint[] (polled every 10s)
  |
  v
DerivativesPage
  +-- DerivativesSummaryCards (Phase 3)
  +-- BasisTrendAreaChart (Phase 4)
  +-- ConvergenceIndicator + OpenInterestDisplay (Phase 5)
```

## Related Code Files

| Action | File |
|--------|------|
| MODIFY | `frontend/src/types/index.ts` |
| CREATE | `frontend/src/hooks/use-basis-trend.ts` |
| CREATE | `frontend/src/hooks/use-derivatives-data.ts` |
| CREATE | `frontend/src/pages/derivatives-page.tsx` |
| CREATE | `frontend/src/components/ui/derivatives-skeleton.tsx` |
| MODIFY | `frontend/src/components/layout/app-sidebar-navigation.tsx` |
| MODIFY | `frontend/src/App.tsx` |

## Implementation Steps

### 1. Add `BasisPoint` type to `types/index.ts`

```typescript
export interface BasisPoint {
  timestamp: string;
  futures_symbol: string;
  futures_price: number;
  spot_value: number;
  basis: number;
  basis_pct: number;
  is_premium: boolean;
}
```

Add after the existing `DerivativesData` interface (line ~93).

### 2. Create `use-basis-trend.ts`

```typescript
/** Polls /api/market/basis-trend for basis history points. */
import { usePolling } from "./use-polling";
import { apiFetch } from "../utils/api-client";
import type { BasisPoint } from "../types";

export function useBasisTrend(minutes = 30, intervalMs = 10000) {
  return usePolling(
    () => apiFetch<BasisPoint[]>(`/market/basis-trend?minutes=${minutes}`),
    intervalMs,
  );
}
```

### 3. Create `use-derivatives-data.ts`

```typescript
/** Combines real-time derivatives snapshot with basis trend history. */
import { useMarketSnapshot } from "./use-market-snapshot";
import { useBasisTrend } from "./use-basis-trend";

export function useDerivativesData() {
  const snapshot = useMarketSnapshot(5000);
  const trend = useBasisTrend(30, 10000);

  return {
    derivatives: snapshot.data?.derivatives ?? null,
    basisTrend: trend.data ?? [],
    loading: snapshot.loading && trend.loading,
    error: snapshot.error || trend.error,
    refresh: () => { snapshot.refresh(); trend.refresh(); },
  };
}
```

### 4. Create `derivatives-skeleton.tsx`

Skeleton matching layout: 4 cards top row + chart + 2-col bottom row. Follow `foreign-flow-skeleton.tsx` pattern.

### 5. Create `derivatives-page.tsx`

Follow `foreign-flow-page.tsx` pattern:
- Import `useDerivativesData`
- Loading -> skeleton, error -> ErrorBanner, no data -> ErrorBanner
- Render: summary cards, chart, bottom row (convergence + open interest)
- Initially render placeholder `<div>` for Phase 3-5 components

### 6. Add nav item to `app-sidebar-navigation.tsx`

Insert `{ to: "/derivatives", label: "Derivatives" }` after "Volume Analysis" in `NAV_ITEMS`.

### 7. Add route to `App.tsx`

- Lazy import: `const DerivativesPage = lazy(() => import("./pages/derivatives-page"));`
- Import skeleton: `import { DerivativesSkeleton } from "./components/ui/derivatives-skeleton";`
- Add route between `/volume` and `/signals`

## Todo

- [ ] Add `BasisPoint` type
- [ ] Create `use-basis-trend.ts`
- [ ] Create `use-derivatives-data.ts`
- [ ] Create `derivatives-skeleton.tsx`
- [ ] Create `derivatives-page.tsx` (with placeholder sections)
- [ ] Add sidebar nav item
- [ ] Add App.tsx route
- [ ] Verify page loads at `/derivatives` with skeleton -> empty state

## Success Criteria

- `/derivatives` route renders without errors
- Sidebar shows "Derivatives" link, active state works
- Loading skeleton displays while data fetches
- Empty/error states handled gracefully

## Risk Assessment

- **Low**: All patterns are direct copies of existing page setup
