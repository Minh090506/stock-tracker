# Phase 2: Frontend — Price Board Page, Components, Hook, Routing

## Context Links
- [types/index.ts](/frontend/src/types/index.ts) — current TS types (MarketSnapshot, SessionStats)
- [App.tsx](/frontend/src/App.tsx) — router with 3 pages, index redirects to /foreign-flow
- [app-sidebar-navigation.tsx](/frontend/src/components/layout/app-sidebar-navigation.tsx) — NAV_ITEMS array
- [use-websocket.ts](/frontend/src/hooks/use-websocket.ts) — generic WS hook (not yet used by any page)
- [use-market-snapshot.ts](/frontend/src/hooks/use-market-snapshot.ts) — polling-based snapshot hook (fallback reference)
- [volume-detail-table.tsx](/frontend/src/components/volume/volume-detail-table.tsx) — sortable table pattern to follow
- [format-number.ts](/frontend/src/utils/format-number.ts) — formatVnd, formatVolume, formatPercent
- [foreign-flow-skeleton.tsx](/frontend/src/components/ui/foreign-flow-skeleton.tsx) — skeleton pattern
- [api-client.ts](/frontend/src/utils/api-client.ts) — apiFetch for REST fallback

## Overview
- **Priority**: P1
- **Status**: ✅ complete
- **Description**: Build complete price board page with sortable 30-stock table, inline SVG sparklines, flash animation on price change, loading skeleton, and integrate via WebSocket with REST polling fallback.

## Key Insights
- `useWebSocket` hook exists but no page uses it yet — this is the first consumer
- VN30 component list fetched via `/api/vn30-components` — used to filter snapshot symbols
- Sparkline data accumulated client-side from WS updates (last 50 price ticks per symbol)
- Existing sortable table pattern in `volume-detail-table.tsx` can be adapted
- All new component files must use kebab-case naming

## Requirements
### Functional
- 30-stock table: Symbol, Price, Change, Change%, Volume, Buy/Sell Pressure, Sparkline
- Real-time via `useWebSocket<MarketSnapshot>("market")` with REST fallback
- Color coding: green=price up, red=price down, yellow=ceiling or floor
- Flash animation on price change (brief background highlight)
- Sortable columns: symbol, change%, volume (click header toggles asc/desc)
- Mini sparkline per stock (last 50 ticks, inline SVG)
- Responsive: horizontal scroll on mobile (`overflow-x-auto`)
- Loading skeleton while WebSocket connecting

### Non-Functional
- All files under 200 lines
- No new npm dependencies (inline SVG for sparklines)
- Follow existing component/hook patterns

## Architecture

```
/api/vn30-components ──→ useEffect (once) ──→ vn30Symbols: string[]
                                                │
useWebSocket<MarketSnapshot>("market") ──→ snapshot
  fallback: apiFetch("/market/snapshot")    │
                                            ├─ snapshot.prices[symbol] → PriceData
                                            ├─ snapshot.quotes[symbol] → SessionStats
                                            └─ sparklineRef.current[symbol].push(price)
                                                │
PriceBoardPage ──→ PriceBoardTable (rows filtered to VN30)
                     └─ PriceBoardSparkline (inline SVG per row)
```

## Related Code Files

### New Files
1. `frontend/src/hooks/use-price-board-data.ts` — WS hook + sparkline accumulation + VN30 filtering
2. `frontend/src/pages/price-board-page.tsx` — page component
3. `frontend/src/components/price-board/price-board-table.tsx` — sortable 30-stock table with flash
4. `frontend/src/components/price-board/price-board-sparkline.tsx` — inline SVG sparkline
5. `frontend/src/components/ui/price-board-skeleton.tsx` — loading skeleton

### Modified Files
6. `frontend/src/types/index.ts` — add `PriceData` interface, update `MarketSnapshot`
7. `frontend/src/App.tsx` — add `/price-board` route, change index redirect
8. `frontend/src/components/layout/app-sidebar-navigation.tsx` — add "Price Board" at top of NAV_ITEMS

## Implementation Steps

### Step 1: Add `PriceData` type + update `MarketSnapshot` in `types/index.ts`

Add after `SessionStats` interface (~line 16):

```typescript
// -- Price data --

export interface PriceData {
  last_price: number;
  change: number;
  change_pct: number;
  ref_price: number;
  ceiling: number;
  floor: number;
}
```

Update `MarketSnapshot` (~line 86):

```typescript
export interface MarketSnapshot {
  quotes: Record<string, SessionStats>;
  prices: Record<string, PriceData>;       // <-- NEW
  indices: Record<string, IndexData>;
  foreign: ForeignSummary | null;
  derivatives: DerivativesData | null;
}
```

### Step 2: Create `use-price-board-data.ts` hook

Path: `frontend/src/hooks/use-price-board-data.ts`

Responsibilities:
- Fetch VN30 symbols once via `/api/vn30-components`
- Connect to WS "market" channel with REST fallback
- Filter snapshot to VN30 symbols only
- Accumulate sparkline data (last 50 prices per symbol) in a ref
- Merge `PriceData` + `SessionStats` into a flat row type

```typescript
/** Hook for price board: WS market data + sparkline accumulation + VN30 filtering. */

import { useState, useEffect, useRef, useMemo } from "react";
import { useWebSocket } from "./use-websocket";
import { apiFetch } from "../utils/api-client";
import type { MarketSnapshot, PriceData, SessionStats } from "../types";

export interface PriceBoardRow {
  symbol: string;
  price: PriceData;
  stats: SessionStats | null;
  sparkline: number[];  // last 50 prices
}

const MAX_SPARKLINE_POINTS = 50;

export function usePriceBoardData() {
  const [vn30Symbols, setVn30Symbols] = useState<string[]>([]);

  // Fetch VN30 component list once
  useEffect(() => {
    apiFetch<string[]>("/vn30-components")
      .then(setVn30Symbols)
      .catch(() => {}); // silent — will show empty table until loaded
  }, []);

  // WebSocket with REST fallback
  const { data: snapshot, status, error, isLive, reconnect } =
    useWebSocket<MarketSnapshot>("market", {
      fallbackFetcher: () => apiFetch<MarketSnapshot>("/market/snapshot"),
      fallbackIntervalMs: 3000,
    });

  // Sparkline accumulation (persisted across renders via ref)
  const sparklineRef = useRef<Record<string, number[]>>({});

  // Update sparklines when snapshot changes
  useEffect(() => {
    if (!snapshot?.prices) return;
    for (const [symbol, pd] of Object.entries(snapshot.prices)) {
      if (pd.last_price === 0) continue;
      const arr = sparklineRef.current[symbol] ?? [];
      // Only push if price differs from last point (dedup flat updates)
      if (arr.length === 0 || arr[arr.length - 1] !== pd.last_price) {
        arr.push(pd.last_price);
        if (arr.length > MAX_SPARKLINE_POINTS) arr.shift();
        sparklineRef.current[symbol] = arr;
      }
    }
  }, [snapshot]);

  // Build rows filtered to VN30
  const rows: PriceBoardRow[] = useMemo(() => {
    if (!snapshot || vn30Symbols.length === 0) return [];
    return vn30Symbols
      .map((symbol) => ({
        symbol,
        price: snapshot.prices?.[symbol] ?? {
          last_price: 0, change: 0, change_pct: 0,
          ref_price: 0, ceiling: 0, floor: 0,
        },
        stats: snapshot.quotes?.[symbol] ?? null,
        sparkline: sparklineRef.current[symbol] ?? [],
      }))
      .filter((r) => r.price.last_price > 0); // hide symbols with no trades yet
  }, [snapshot, vn30Symbols]);

  const loading = status === "connecting" && !snapshot;

  return { rows, loading, error, isLive, status, reconnect };
}
```

**~75 lines** — well under 200.

### Step 3: Create `price-board-sparkline.tsx`

Path: `frontend/src/components/price-board/price-board-sparkline.tsx`

Simple inline SVG. No charting library.

```typescript
/** Inline SVG sparkline for last N price ticks. */

interface PriceBoardSparklineProps {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
}

export function PriceBoardSparkline({
  data,
  width = 80,
  height = 24,
  color = "#60a5fa",
}: PriceBoardSparklineProps) {
  if (data.length < 2) return <div style={{ width, height }} />;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1; // avoid division by zero
  const padding = 1;

  const points = data
    .map((val, i) => {
      const x = padding + (i / (data.length - 1)) * (width - 2 * padding);
      const y = padding + (1 - (val - min) / range) * (height - 2 * padding);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  // Determine color: compare last vs first
  const trend = data[data.length - 1] >= data[0] ? "#22c55e" : "#ef4444";
  const strokeColor = color === "#60a5fa" ? trend : color;

  return (
    <svg width={width} height={height} className="inline-block">
      <polyline
        points={points}
        fill="none"
        stroke={strokeColor}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
```

**~40 lines** — minimal.

### Step 4: Create `price-board-table.tsx`

Path: `frontend/src/components/price-board/price-board-table.tsx`

Follows `volume-detail-table.tsx` sort pattern. Adds flash animation + color coding.

```typescript
/** Sortable 30-stock price table with flash animation and sparklines. */

import { useState, useRef, useEffect } from "react";
import type { PriceBoardRow } from "../../hooks/use-price-board-data";
import { PriceBoardSparkline } from "./price-board-sparkline";
import { formatVolume, formatPercent } from "../../utils/format-number";

type SortKey = "symbol" | "change_pct" | "volume";
type SortDir = "asc" | "desc";

// Color logic: ceiling/floor=yellow, up=green, down=red, neutral=white
function priceColorClass(row: PriceBoardRow): string {
  const { last_price, ceiling, floor, change } = row.price;
  if (ceiling > 0 && last_price >= ceiling) return "text-yellow-400";
  if (floor > 0 && last_price <= floor) return "text-yellow-400";
  if (change > 0) return "text-green-400";
  if (change < 0) return "text-red-400";
  return "text-gray-300";
}

function formatPrice(price: number): string {
  // VN stock prices in VND, typically shown as x1000 (e.g., 52.30 = 52,300 VND)
  return price > 0 ? price.toFixed(2) : "-";
}

interface PriceBoardTableProps {
  rows: PriceBoardRow[];
}

export function PriceBoardTable({ rows }: PriceBoardTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("symbol");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const prevPricesRef = useRef<Record<string, number>>({});
  const [flashSymbols, setFlashSymbols] = useState<Set<string>>(new Set());

  // Detect price changes for flash animation
  useEffect(() => {
    const flashing = new Set<string>();
    for (const row of rows) {
      const prev = prevPricesRef.current[row.symbol];
      if (prev !== undefined && prev !== row.price.last_price) {
        flashing.add(row.symbol);
      }
      prevPricesRef.current[row.symbol] = row.price.last_price;
    }
    if (flashing.size > 0) {
      setFlashSymbols(flashing);
      const timer = setTimeout(() => setFlashSymbols(new Set()), 400);
      return () => clearTimeout(timer);
    }
  }, [rows]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir(key === "symbol" ? "asc" : "desc");
    }
  };

  const sorted = [...rows].sort((a, b) => {
    let aVal: number | string;
    let bVal: number | string;
    switch (sortKey) {
      case "symbol":
        aVal = a.symbol; bVal = b.symbol; break;
      case "change_pct":
        aVal = a.price.change_pct; bVal = b.price.change_pct; break;
      case "volume":
        aVal = a.stats?.total_volume ?? 0;
        bVal = b.stats?.total_volume ?? 0; break;
    }
    if (aVal < bVal) return sortDir === "asc" ? -1 : 1;
    if (aVal > bVal) return sortDir === "asc" ? 1 : -1;
    return 0;
  });

  const sortIcon = (key: SortKey) =>
    sortKey === key ? (sortDir === "asc" ? " ↑" : " ↓") : "";

  const buyPressure = (row: PriceBoardRow) => {
    const total = row.stats?.total_volume ?? 0;
    if (total === 0) return null;
    return ((row.stats!.mua_chu_dong_volume / total) * 100).toFixed(1);
  };

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-x-auto">
      <table className="w-full text-sm min-w-[640px]">
        <thead className="bg-gray-800">
          <tr>
            <th onClick={() => handleSort("symbol")}
              className="px-4 py-3 text-left cursor-pointer hover:bg-gray-700">
              Symbol{sortIcon("symbol")}
            </th>
            <th className="px-4 py-3 text-right">Price</th>
            <th className="px-4 py-3 text-right">Change</th>
            <th onClick={() => handleSort("change_pct")}
              className="px-4 py-3 text-right cursor-pointer hover:bg-gray-700">
              Change%{sortIcon("change_pct")}
            </th>
            <th onClick={() => handleSort("volume")}
              className="px-4 py-3 text-right cursor-pointer hover:bg-gray-700">
              Volume{sortIcon("volume")}
            </th>
            <th className="px-4 py-3 text-right">Buy Pressure</th>
            <th className="px-4 py-3 text-center">Trend</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => {
            const colorClass = priceColorClass(row);
            const isFlashing = flashSymbols.has(row.symbol);
            const flashBg = isFlashing
              ? row.price.change >= 0
                ? "bg-green-900/30"
                : "bg-red-900/30"
              : "";

            return (
              <tr key={row.symbol}
                className={`border-t border-gray-800 hover:bg-gray-800/50 transition-colors duration-300 ${flashBg}`}>
                <td className="px-4 py-2 font-semibold text-white">{row.symbol}</td>
                <td className={`px-4 py-2 text-right font-mono ${colorClass}`}>
                  {formatPrice(row.price.last_price)}
                </td>
                <td className={`px-4 py-2 text-right font-mono ${colorClass}`}>
                  {row.price.change > 0 ? "+" : ""}{row.price.change.toFixed(2)}
                </td>
                <td className={`px-4 py-2 text-right font-mono ${colorClass}`}>
                  {formatPercent(row.price.change_pct)}
                </td>
                <td className="px-4 py-2 text-right">
                  {row.stats ? formatVolume(row.stats.total_volume) : "-"}
                </td>
                <td className="px-4 py-2 text-right">
                  {buyPressure(row) !== null
                    ? <span className={Number(buyPressure(row)) > 50 ? "text-green-400" : "text-red-400"}>
                        {buyPressure(row)}%
                      </span>
                    : "-"
                  }
                </td>
                <td className="px-4 py-2 text-center">
                  <PriceBoardSparkline data={row.sparkline} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
```

**~130 lines** — under 200 limit. Flash animation uses CSS `transition-colors duration-300` with conditional background class that clears after 400ms.

### Step 5: Create `price-board-skeleton.tsx`

Path: `frontend/src/components/ui/price-board-skeleton.tsx`

```typescript
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
        {/* 10 visible rows */}
        {Array.from({ length: 10 }, (_, i) => (
          <div key={i} className="h-8 bg-gray-800/40 rounded" />
        ))}
      </div>
    </div>
  );
}
```

**~28 lines** — minimal.

### Step 6: Create `price-board-page.tsx`

Path: `frontend/src/pages/price-board-page.tsx`

```typescript
/** VN30 Price Board — real-time stock prices with sparklines and sorting. */

import { usePriceBoardData } from "../hooks/use-price-board-data";
import { PriceBoardSkeleton } from "../components/ui/price-board-skeleton";
import { ErrorBanner } from "../components/ui/error-banner";
import { PriceBoardTable } from "../components/price-board/price-board-table";

export default function PriceBoardPage() {
  const { rows, loading, error, isLive, status, reconnect } = usePriceBoardData();

  if (loading) {
    return <PriceBoardSkeleton />;
  }

  if (error && rows.length === 0) {
    return (
      <ErrorBanner
        message={`Failed to load price data: ${error.message}`}
        onRetry={reconnect}
      />
    );
  }

  return (
    <div className="p-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">VN30 Price Board</h2>
        <div className="flex items-center gap-2 text-xs">
          <span className={`inline-block w-2 h-2 rounded-full ${
            isLive ? "bg-green-500" : "bg-yellow-500"
          }`} />
          <span className="text-gray-400">
            {isLive ? "Live" : "Polling"}
            {status === "disconnected" && " (reconnecting...)"}
          </span>
        </div>
      </div>

      {/* Error banner (non-blocking — show stale data + warning) */}
      {error && rows.length > 0 && (
        <div className="text-xs text-yellow-400 bg-yellow-900/20 px-3 py-2 rounded">
          Connection issue — showing last known data
        </div>
      )}

      {/* Price table */}
      <PriceBoardTable rows={rows} />
    </div>
  );
}
```

**~50 lines** — clean and focused.

### Step 7: Add route in `App.tsx`

Import + add route before existing routes:

```typescript
import { PriceBoardSkeleton } from "./components/ui/price-board-skeleton";

const PriceBoardPage = lazy(() => import("./pages/price-board-page"));
```

Add route inside `<Route element={<AppLayoutShell />}>`:

```tsx
<Route index element={<Navigate to="/price-board" replace />} />
<Route
  path="/price-board"
  element={
    <ErrorBoundary>
      <Suspense fallback={<PriceBoardSkeleton />}>
        <PriceBoardPage />
      </Suspense>
    </ErrorBoundary>
  }
/>
```

Change `index` redirect from `/foreign-flow` to `/price-board`.

### Step 8: Add nav item in `app-sidebar-navigation.tsx`

Update `NAV_ITEMS` to add "Price Board" at the top:

```typescript
const NAV_ITEMS = [
  { to: "/price-board", label: "Price Board" },
  { to: "/foreign-flow", label: "Foreign Flow" },
  { to: "/volume", label: "Volume Analysis" },
  { to: "/signals", label: "Signals" },
] as const;
```

## Todo List
- [x] Add `PriceData` interface to `types/index.ts`
- [x] Add `prices` field to `MarketSnapshot` interface
- [x] Create `hooks/use-price-board-data.ts`
- [x] Create `components/price-board/price-board-sparkline.tsx`
- [x] Create `components/price-board/price-board-table.tsx`
- [x] Create `components/ui/price-board-skeleton.tsx`
- [x] Create `pages/price-board-page.tsx`
- [x] Update `App.tsx` — add route + change default redirect
- [x] Update `app-sidebar-navigation.tsx` — add nav item
- [x] Run `npx --package typescript tsc --noEmit` to verify no type errors
- [x] Run `npm run dev` and verify page loads with skeleton

## Success Criteria
- Price Board appears as first nav item and default route (`/`)
- Table renders 30 VN30 stocks with real-time prices via WebSocket
- Prices flash briefly on change (green=up, red=down background pulse)
- Sorting works on Symbol, Change%, Volume columns
- Sparkline shows per-stock price trend (accumulates from WS updates)
- Color coding: green=up, red=down, yellow=ceiling/floor
- Loading skeleton shown while WS connecting
- Graceful fallback to REST polling if WS fails
- Live/Polling indicator in header
- Horizontal scroll on mobile
- All files under 200 lines
- No new npm dependencies

## Risk Assessment
- **Sparkline cold start**: On page load sparkline is empty — normal, accumulates over time. Show empty placeholder for <2 points.
- **VN30 symbols fetch fail**: Silent catch — table stays empty. Could add retry but YAGNI for now.
- **Flash animation performance**: Only sets state for changed symbols, clears after 400ms. 30 symbols max — no perf concern.
- **WS reconnect churn**: Handled by `useWebSocket` hook's exponential backoff + REST fallback.

## Security Considerations
- No new API endpoints — uses existing `/api/market/snapshot` and `/ws/market`
- No user-supplied data rendered — all data from SSI stream
- VN30 symbols list from backend — no client-side hardcoding

## Next Steps
- After both phases complete: run full test suite, verify WS broadcast includes prices
- Future: add VN30 index summary card above table (already available in `snapshot.indices`)
- Future: click row to expand with order book depth (data in QuoteCache bid/ask)
