# Phase 4: Frontend Dashboard — Velocity Charts & Correlation Display

## Context Links

- [useDerivativesData hook](../../frontend/src/hooks/use-derivatives-data.ts) — hook pattern template
- [DerivativesPage](../../frontend/src/pages/derivatives-page.tsx) — page pattern template
- [derivatives-summary-cards](../../frontend/src/components/derivatives/derivatives-summary-cards.tsx) — card component pattern
- [basis-trend-area-chart](../../frontend/src/components/derivatives/basis-trend-area-chart.tsx) — Recharts pattern
- [App.tsx](../../frontend/src/App.tsx) — route registration
- [app-sidebar-navigation](../../frontend/src/components/layout/app-sidebar-navigation.tsx) — nav menu
- [types/index.ts](../../frontend/src/types/index.ts) — TypeScript type definitions

## Overview

- **Priority**: P1
- **Status**: complete
- **Effort**: 5h
- **Description**: Create velocity dashboard page with dual-axis overlay chart (velocity bars + VN30F price line), summary cards, imbalance gauge, and correlation display.

## Key Insights

- Follow `DerivativesPage` pattern exactly: hook extracts data, page composes components
- Real-time data arrives via existing `/ws/market` channel (velocity field in MarketSnapshot)
- Historical overlay polled via `GET /api/market/velocity/history`
- Recharts `ComposedChart` supports dual Y-axis for overlay (BarChart + LineChart)
- VN market color convention: red = buy pressure (up), green = sell pressure (down)
- Imbalance ratio 0.5 = neutral, >0.5 = buy dominant, <0.5 = sell dominant

## Requirements

### Functional
- Dual-axis chart: velocity bars (left Y) + VN30F price line (right Y)
- Summary cards: buy velocity, sell velocity, net velocity, imbalance ratio, correlation coefficient
- Imbalance gauge: horizontal bar showing buy/sell balance with color coding
- Toggle between VN30F self-velocity and VN30 basket velocity
- Historical 60-minute overlay (polled every 10s)

### Non-Functional
- Lazy-loaded page with skeleton fallback
- Responsive layout (mobile-friendly)
- < 50ms render time for chart updates
- Consistent with existing dark theme (gray-900 bg, gray-800 borders)

## Architecture

```
/ws/market (MarketSnapshot)
    |
    +---> useVelocityData() hook
              |
              +---> velocity (real-time from WS .velocity field)
              +---> history (polled from /api/market/velocity/history)
              |
              +---> VelocityPage
                      +---> VelocitySummaryCards
                      +---> VelocityPriceOverlayChart (ComposedChart)
                      +---> VelocityImbalanceGauge
```

## Related Code Files

### Files to Create
- `frontend/src/hooks/use-velocity-data.ts` — data hook
- `frontend/src/pages/velocity-page.tsx` — page component
- `frontend/src/components/velocity/velocity-summary-cards.tsx` — metric cards
- `frontend/src/components/velocity/velocity-price-overlay-chart.tsx` — dual-axis chart
- `frontend/src/components/velocity/velocity-imbalance-gauge.tsx` — buy/sell gauge
- `frontend/src/components/ui/velocity-skeleton.tsx` — loading skeleton

### Files to Modify
- `frontend/src/App.tsx` — add `/velocity` route
- `frontend/src/components/layout/app-sidebar-navigation.tsx` — add nav item
- `frontend/src/types/index.ts` — add velocity types + update MarketSnapshot

## Implementation Steps

### Step 1: Add TypeScript types to `frontend/src/types/index.ts`

```typescript
// -- Velocity --

export interface VelocityData {
  symbol: string;
  buy_vol_per_min: number;
  sell_vol_per_min: number;
  net_vol_per_min: number;
  buy_count_per_min: number;
  sell_count_per_min: number;
  imbalance_ratio: number;
  acceleration: number;
  last_updated: string | null;
}

export interface CorrelationData {
  coefficient: number;
  sample_size: number;
  window_minutes: number;
  last_updated: string | null;
}

export interface VelocitySnapshot {
  vn30f: VelocityData | null;
  basket: VelocityData | null;
  correlation: CorrelationData | null;
}

export interface VelocityHistoryPoint {
  timestamp: string;
  buy_vol: number;
  sell_vol: number;
  buy_count: number;
  sell_count: number;
  buy_value: number;
  sell_value: number;
}
```

Update `MarketSnapshot`:
```typescript
export interface MarketSnapshot {
  quotes: Record<string, SessionStats>;
  prices: Record<string, PriceData>;
  indices: Record<string, IndexData>;
  foreign: ForeignSummary | null;
  derivatives: DerivativesData | null;
  velocity: VelocitySnapshot | null;  // NEW
}
```

### Step 2: Create `frontend/src/hooks/use-velocity-data.ts`

Follow `useDerivativesData` pattern:

```typescript
/** Combines real-time velocity snapshot (WS) with polled history. */

import { useWebSocket } from "./use-websocket";
import { usePolling } from "./use-polling";
import { apiFetch } from "../utils/api-client";
import type { MarketSnapshot, VelocitySnapshot, VelocityHistoryPoint } from "../types";

interface VelocityPageData {
  velocity: VelocitySnapshot | null;
  history: VelocityHistoryPoint[];
  loading: boolean;
  error: Error | null;
}

export function useVelocityData(
  historyMinutes = 60,
  historyPollMs = 10_000,
): VelocityPageData {
  const ws = useWebSocket<MarketSnapshot>("market", {
    fallbackFetcher: () => apiFetch<MarketSnapshot>("/market/snapshot"),
    fallbackIntervalMs: 5000,
  });

  const history = usePolling(
    () => apiFetch<VelocityHistoryPoint[]>(
      `/market/velocity/history?symbol=VN30F&minutes=${historyMinutes}`
    ),
    historyPollMs,
  );

  return {
    velocity: ws.data?.velocity ?? null,
    history: history.data ?? [],
    loading: !ws.data && !history.data && history.loading,
    error: ws.error ?? history.error,
  };
}
```

### Step 3: Create `frontend/src/components/velocity/velocity-summary-cards.tsx`

Display 5 metric cards in a grid:
1. **Buy Velocity** — `buy_vol_per_min` (red text, VN convention)
2. **Sell Velocity** — `sell_vol_per_min` (green text)
3. **Net Velocity** — `net_vol_per_min` (red if positive, green if negative)
4. **Imbalance** — `imbalance_ratio` as percentage with color gradient
5. **Correlation** — `coefficient` with color coding (-1 red, 0 gray, +1 blue)

Follow `derivatives-summary-cards.tsx` structure (grid layout, bg-gray-900 cards).

### Step 4: Create `frontend/src/components/velocity/velocity-price-overlay-chart.tsx`

Recharts `ComposedChart` with dual Y-axis:
- Left Y-axis: velocity (volume per minute)
- Right Y-axis: VN30F price
- Data: merge historical velocity + price data by timestamp
- Bar: net velocity (red if positive/buy, green if negative/sell)
- Line: VN30F price overlay (white/yellow)

```typescript
import { ComposedChart, Bar, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
```

Chart config:
- Height: 320px
- X-axis: time (formatted HH:mm)
- Left Y-axis: auto-scaled volume
- Right Y-axis: auto-scaled price with orientation="right"
- Bar fill: dynamic red/green based on net_velocity sign
- Line stroke: #facc15 (amber-400 for VN30F price)

### Step 5: Create `frontend/src/components/velocity/velocity-imbalance-gauge.tsx`

Horizontal bar showing buy/sell proportion:
- Full width bar, split into red (buy) and green (sell) segments
- Width proportional to `imbalance_ratio`
- Labels: "Mua" on left, "Bán" on right
- Center label: percentage (e.g., "65% Mua")
- Threshold markers at 33% and 67% (extreme zones)

### Step 6: Create `frontend/src/components/ui/velocity-skeleton.tsx`

Follow `derivatives-skeleton.tsx` pattern:
- Skeleton cards (5 items)
- Skeleton chart area
- Skeleton gauge bar

### Step 7: Create `frontend/src/pages/velocity-page.tsx`

```typescript
/** Order velocity analysis — VN30F + VN30 basket velocity with correlation. */

import { useVelocityData } from "../hooks/use-velocity-data";
import { VelocitySkeleton } from "../components/ui/velocity-skeleton";
import { ErrorBanner } from "../components/ui/error-banner";
import { VelocitySummaryCards } from "../components/velocity/velocity-summary-cards";
import { VelocityPriceOverlayChart } from "../components/velocity/velocity-price-overlay-chart";
import { VelocityImbalanceGauge } from "../components/velocity/velocity-imbalance-gauge";

export default function VelocityPage() {
  const { velocity, history, loading, error } = useVelocityData();
  if (loading) return <VelocitySkeleton />;
  if (error) return <ErrorBanner message={`Failed to load velocity data: ${error.message}`} />;

  return (
    <div className="p-6 space-y-6">
      <VelocitySummaryCards data={velocity} />
      <VelocityPriceOverlayChart velocity={velocity} history={history} />
      <VelocityImbalanceGauge data={velocity} />
    </div>
  );
}
```

### Step 8: Register route in `App.tsx`

Add after `/derivatives` route:
```tsx
import { VelocitySkeleton } from "./components/ui/velocity-skeleton";
const VelocityPage = lazy(() => import("./pages/velocity-page"));

<Route
  path="/velocity-analysis"
  element={
    <ErrorBoundary>
      <Suspense fallback={<VelocitySkeleton />}>
        <VelocityPage />
      </Suspense>
    </ErrorBoundary>
  }
/>
```

### Step 9: Add nav item in `app-sidebar-navigation.tsx`

Add to `NAV_ITEMS` array after "Derivatives":
```typescript
{ to: "/velocity-analysis", label: "Velocity" },
```

## Todo List

- [x] Add VelocityData, CorrelationData, VelocitySnapshot types to `types/index.ts`
- [x] Update MarketSnapshot type with `velocity` field
- [x] Add VelocityHistoryPoint type
- [x] Create `use-velocity-data.ts` hook
- [x] Create `velocity-summary-cards.tsx`
- [x] Create `velocity-price-overlay-chart.tsx` (ComposedChart)
- [x] Create `velocity-imbalance-gauge.tsx`
- [x] Create `velocity-skeleton.tsx`
- [x] Create `velocity-page.tsx`
- [x] Add route in App.tsx
- [x] Add nav item in sidebar
- [x] Test responsive layout on mobile
- [x] Run `npx --package typescript tsc --noEmit` to check types

## Success Criteria

- `/velocity-analysis` page loads with skeleton, then shows data
- Dual-axis chart renders velocity bars + price line correctly
- Summary cards update in real-time via WS
- Imbalance gauge reflects current buy/sell balance
- Page is responsive (mobile & desktop)
- No TypeScript errors
- Navigation sidebar shows "Velocity" link

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Recharts ComposedChart performance with 60 data points | Very Low | Low | 60 points is well within Recharts capacity |
| MarketSnapshot payload increase breaks existing pages | Very Low | Low | Optional field, backward compatible |
| Chart axis scaling issues with vastly different Y ranges | Medium | Medium | Use dual Y-axis with independent auto-scale |

## Security Considerations

- No user input beyond URL params (handled by hooks)
- Data is read-only display

## Next Steps

- Phase 5 adds alert types that appear on the Signals page (existing)
- Future: VN30F vs basket toggle selector on chart
- Future: Correlation coefficient trend line
