# Phase 2: Frontend Dependencies + Routing + Layout

## Context

- Frontend: React 19, TS 5.7, Vite 6, TailwindCSS v4
- NO routing, NO chart library (except lightweight-charts for candlestick)
- Single `App.tsx` placeholder, empty `components/`, `hooks/`, `utils/`

## Overview

- **Priority**: P1
- **Status**: pending
- **Effort**: 1h

## Requirements

1. Install `react-router-dom@7` and `recharts`
2. Set up BrowserRouter with 4 routes
3. Create shared layout with sidebar navigation
4. Create TypeScript types mirroring backend domain models

## Implementation Steps

### Step 1: Install dependencies

```bash
cd frontend && npm install react-router-dom recharts
npm install -D @types/recharts  # if needed, recharts ships own types
```

### Step 2: Create types file

**File**: `frontend/src/types/index.ts` (~80 lines)

Mirror backend domain models:
```typescript
// Trade types
export type TradeType = "mua_chu_dong" | "ban_chu_dong" | "neutral";

export interface SessionStats {
  symbol: string;
  mua_chu_dong_volume: number;
  mua_chu_dong_value: number;
  ban_chu_dong_volume: number;
  ban_chu_dong_value: number;
  neutral_volume: number;
  total_volume: number;
  last_updated: string | null;
}

export interface ForeignInvestorData {
  symbol: string;
  buy_volume: number;
  sell_volume: number;
  net_volume: number;
  buy_value: number;
  sell_value: number;
  net_value: number;
  total_room: number;
  current_room: number;
  buy_speed_per_min: number;
  sell_speed_per_min: number;
  buy_acceleration: number;
  sell_acceleration: number;
  last_updated: string | null;
}

export interface ForeignSummary {
  total_buy_value: number;
  total_sell_value: number;
  total_net_value: number;
  total_buy_volume: number;
  total_sell_volume: number;
  total_net_volume: number;
  top_buy: ForeignInvestorData[];
  top_sell: ForeignInvestorData[];
}

export interface IntradayPoint {
  timestamp: string;
  value: number;
}

export interface IndexData {
  index_id: string;
  value: number;
  prior_value: number;
  change: number;
  ratio_change: number;
  total_volume: number;
  advances: number;
  declines: number;
  no_changes: number;
  intraday: IntradayPoint[];
  advance_ratio: number;
  last_updated: string | null;
}

export interface DerivativesData {
  symbol: string;
  last_price: number;
  change: number;
  change_pct: number;
  volume: number;
  basis: number;
  basis_pct: number;
  is_premium: boolean;
  last_updated: string | null;
}

export interface MarketSnapshot {
  quotes: Record<string, SessionStats>;
  indices: Record<string, IndexData>;
  foreign: ForeignSummary | null;
  derivatives: DerivativesData | null;
}

// API response wrappers
export interface ForeignDetailResponse {
  summary: ForeignSummary;
  stocks: ForeignInvestorData[];
}

export interface VolumeStatsResponse {
  stats: SessionStats[];
}

// Signals (mock until Phase 6 analytics engine)
export type SignalType = "foreign" | "volume" | "divergence";
export type SignalSeverity = "info" | "warning" | "critical";

export interface Signal {
  id: string;
  type: SignalType;
  severity: SignalSeverity;
  symbol: string;
  message: string;
  value: number;
  timestamp: string;
}
```

### Step 3: Create layout shell

**File**: `frontend/src/components/layout/app-sidebar-navigation.tsx` (~60 lines)

Sidebar nav with links to /foreign-flow, /volume, /signals. Dark theme (bg-gray-950). Active link highlighted.

**File**: `frontend/src/components/layout/app-layout-shell.tsx` (~30 lines)

Flex container: sidebar (fixed 240px) + main content area with `<Outlet />`.

### Step 4: Set up routing

**File**: `frontend/src/App.tsx` (rewrite, ~30 lines)

```tsx
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AppLayoutShell } from "./components/layout/app-layout-shell";
import { ForeignFlowPage } from "./pages/foreign-flow-page";
import { VolumeAnalysisPage } from "./pages/volume-analysis-page";
import { SignalsPage } from "./pages/signals-page";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayoutShell />}>
          <Route index element={<Navigate to="/foreign-flow" replace />} />
          <Route path="/foreign-flow" element={<ForeignFlowPage />} />
          <Route path="/volume" element={<VolumeAnalysisPage />} />
          <Route path="/signals" element={<SignalsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
```

### Step 5: Create placeholder pages (filled in Phases 4-6)

**Files** (stubs, ~10 lines each):
- `frontend/src/pages/foreign-flow-page.tsx`
- `frontend/src/pages/volume-analysis-page.tsx`
- `frontend/src/pages/signals-page.tsx`

## Files Summary

| Action | File | Lines |
|--------|------|-------|
| Modify | `frontend/package.json` | npm install |
| Rewrite | `frontend/src/types/index.ts` | ~100 |
| Create | `frontend/src/components/layout/app-sidebar-navigation.tsx` | ~60 |
| Create | `frontend/src/components/layout/app-layout-shell.tsx` | ~30 |
| Rewrite | `frontend/src/App.tsx` | ~30 |
| Create | `frontend/src/pages/foreign-flow-page.tsx` | ~10 stub |
| Create | `frontend/src/pages/volume-analysis-page.tsx` | ~10 stub |
| Create | `frontend/src/pages/signals-page.tsx` | ~10 stub |

## Todo

- [ ] `npm install react-router-dom recharts`
- [ ] Rewrite `types/index.ts` with all domain types
- [ ] Create layout components (sidebar + shell)
- [ ] Rewrite `App.tsx` with BrowserRouter + Routes
- [ ] Create 3 placeholder page components
- [ ] Verify `npm run build` compiles

## Success Criteria

- `npm run build` succeeds
- Navigating to `/` redirects to `/foreign-flow`
- Sidebar renders with 3 nav links; active link highlighted
- Each page stub renders its title text
