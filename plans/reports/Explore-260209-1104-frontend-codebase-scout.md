# Frontend Codebase Scout Report
**Date:** 2026-02-09 | **Time:** 11:04 | **Status:** COMPLETE

## Executive Summary

Frontend is a **fully functional React 19 + TypeScript + Vite + TailwindCSS v4** dashboard with three main pages (Foreign Flow, Volume Analysis, Signals). Clean architecture: components organized by feature (foreign/, volume/, signals/), generic reusable hooks (useWebSocket, usePolling, useMarketSnapshot), and utilities for API/formatting. All state management is local (React hooks + props), no Redux. Ready for further expansion.

---

## 1. Project Structure

### Directory Layout
```
frontend/
├── src/
│   ├── App.tsx                      # Router + lazy loading + error boundaries
│   ├── main.tsx                     # React 19 StrictMode entry
│   ├── index.css                    # Tailwind v4 import
│   ├── vite-env.d.ts               # Vite client types (VITE_API_BASE_URL)
│   │
│   ├── pages/                       # 3 lazy-loaded pages
│   │   ├── foreign-flow-page.tsx   # Foreign investor analysis (useForeignFlow hook)
│   │   ├── volume-analysis-page.tsx # Volume breakdown (useMarketSnapshot hook)
│   │   └── signals-page.tsx         # Signal feed with type filter (useSignals-mock)
│   │
│   ├── components/
│   │   ├── layout/
│   │   │   ├── app-layout-shell.tsx         # Root flex layout + Outlet
│   │   │   └── app-sidebar-navigation.tsx   # Responsive nav (fixed desktop, drawer mobile)
│   │   │
│   │   ├── ui/                      # Reusable UI patterns
│   │   │   ├── error-boundary.tsx       # React error boundary (render errors)
│   │   │   ├── error-banner.tsx         # Top-level error display + retry
│   │   │   ├── page-loading-skeleton.tsx
│   │   │   ├── foreign-flow-skeleton.tsx # Cards + 2-col charts + table
│   │   │   ├── volume-analysis-skeleton.tsx
│   │   │   └── signals-skeleton.tsx
│   │   │
│   │   ├── foreign/                 # Foreign investor components
│   │   │   ├── foreign-flow-summary-cards.tsx    # 3 KPI cards
│   │   │   ├── foreign-top-movers-bar-chart.tsx  # Recharts BarChart
│   │   │   ├── foreign-net-flow-heatmap.tsx      # Recharts Treemap
│   │   │   └── foreign-flow-detail-table.tsx     # Sortable table
│   │   │
│   │   ├── volume/                  # Volume analysis components
│   │   │   ├── volume-market-pie-chart.tsx       # Recharts PieChart
│   │   │   ├── volume-ratio-summary-cards.tsx    # 3 ratio KPI cards
│   │   │   ├── volume-stacked-bar-chart.tsx      # Recharts BarChart (stacked)
│   │   │   └── volume-detail-table.tsx           # Sortable table
│   │   │
│   │   └── signals/                 # Signal feed components
│   │       ├── signal-filter-chips.tsx           # Filter button row
│   │       └── signal-feed-list.tsx              # Signal card list + severity styling
│   │
│   ├── hooks/                       # Data fetching & WebSocket
│   │   ├── use-websocket.ts        # Generic WS hook (auto-reconnect + polling fallback)
│   │   ├── use-polling.ts          # Generic polling hook (simple interval fetcher)
│   │   ├── use-market-snapshot.ts  # Polling /api/market/snapshot
│   │   ├── use-foreign-flow.ts     # Polling /api/market/foreign-detail
│   │   └── use-signals-mock.ts     # Static mock signal data (no API yet)
│   │
│   ├── types/                       # Shared TypeScript types
│   │   └── index.ts                # All domain types (TradeType, SessionStats, ForeignInvestorData, etc.)
│   │
│   └── utils/                       # Utilities
│       ├── api-client.ts           # Thin fetch wrapper (apiFetch<T>)
│       └── format-number.ts        # formatVnd, formatVolume, formatPercent
│
├── package.json                     # React 19, Vite, Recharts, TailwindCSS v4
├── tsconfig.json                    # Strict mode, ES2020, DOM.Iterable
├── tsconfig.tsbuildinfo            # Incremental build cache
├── vite.config.ts                  # React + TailwindCSS v4 plugins, dev proxy
├── index.html                       # vi language, root div, main.tsx
├── .env.production                  # (Empty) API defaults to /api proxy
├── Dockerfile                       # Multi-stage: build + nginx
├── nginx.conf                       # Static SPA + /api proxy + /ws WebSocket proxy
└── dist/                            # Build output (generated)

Config files:
├── .env.production       # VITE_API_BASE_URL (defaults to /api)
├── vite.config.ts        # Port 5173, /api and /ws dev proxy
└── tsconfig.json         # Strict + no unused locals/params
```

### File Count Summary
- **Pages:** 3 (ForeignFlow, VolumeAnalysis, Signals)
- **Components:** 16 (4 layout, 4 ui, 4 foreign, 4 volume, 2 signals)
- **Hooks:** 5 (websocket, polling, market-snapshot, foreign-flow, signals-mock)
- **Utils:** 2 (api-client, format-number)
- **Types:** 1 (index.ts with 8+ interfaces)
- **Total:** ~34 .tsx/.ts files

---

## 2. Component Architecture

### App.tsx — Root Router
```typescript
- BrowserRouter with 3 routes:
  - "/" → /foreign-flow (default redirect)
  - "/foreign-flow" → ForeignFlowPage (lazy)
  - "/volume" → VolumeAnalysisPage (lazy)
  - "/signals" → SignalsPage (lazy)
- Suspense + skeleton fallbacks
- ErrorBoundary wraps each page
- Layout: AppLayoutShell (outlet for nested routes)
```

### Layout Components

**AppLayoutShell.tsx** (33 lines)
- Root flex layout: min-h-screen, bg-gray-950, text-white
- Mobile hamburger button (MD breakpoint)
- Sidebar component (responsive state)
- Main content area with Outlet
- Clean responsive structure

**AppSidebarNavigation.tsx** (87 lines)
- Static desktop (md:static) + overlay drawer on mobile (fixed, -translate-x-full)
- NavLink routing with active state styling
- Auto-close on route change (mobile)
- Backdrop overlay for mobile
- Title: "VN Stock Tracker" + "Real-time VN30 Analytics"
- 3 nav items: Foreign Flow, Volume Analysis, Signals
- Footer: "SSI FastConnect"

### UI Components

**ErrorBoundary.tsx** (React Class Component)
- Catches render errors
- Fallback UI: centered error card with message + "Try Again" button
- Logs error + componentStack to console
- Re-renders on retry click

**ErrorBanner.tsx** (Functional)
- Inline error display (red-900/30 bg + red-800 border)
- Message + optional Retry button
- Compact, inline error messaging

**Skeletons** (4 files)
- PageLoadingSkeleton: title + 3 cards + 2 charts
- ForeignFlowSkeleton: 3 cards + 2-col charts + 5-row table
- VolumeAnalysisSkeleton: title + pie + 3-col cards + bar chart + table
- SignalsSkeleton: title + 4 filter chips + 6 signal cards
- All use `animate-pulse` + gray-800/900 placeholders

### Feature Components

#### Foreign Flow Components
1. **ForeignFlowSummaryCards** (56 lines)
   - 3 KPI cards: Total Net Flow, Total Buy Volume, Total Sell Volume
   - Color logic: net_value > 0 = red, < 0 = green, = 0 = gray
   - Uses formatVnd, formatVolume utilities
   
2. **ForeignTopMoversBarChart** (67 lines)
   - Recharts BarChart (horizontal layout)
   - Top 10 stocks by absolute net value
   - Negates sell_value for visual balance (red left, green right)
   - Styled with dark theme (strokeDasharray grid)
   
3. **ForeignNetFlowHeatmap** (112 lines)
   - Recharts Treemap with custom content renderer
   - Size by absolute net value
   - Red gradient for positive, green for negative
   - Intensity scaling by max abs value
   - Shows symbol + value on large cells

4. **ForeignFlowDetailTable** (120 lines)
   - Sortable table (click headers)
   - Columns: Symbol, Buy Vol, Sell Vol, Net Vol, Net Value, Buy Speed, Sell Speed
   - Color-coded (red buy, green sell)
   - Alternating row backgrounds
   - State: sortKey, sortDir (remember last sort)

#### Volume Analysis Components
1. **VolumeMarketPieChart** (61 lines)
   - Aggregate market-wide volume ratio
   - 3 segments: Active Buy (red), Active Sell (green), Neutral (yellow)
   - Label shows percentage
   - Handles zero-volume edge case

2. **VolumeRatioSummaryCards** (41 lines)
   - 3 centered KPI cards with colored values
   - Buy%, Sell%, Neutral%
   - Calculated from stats aggregation

3. **VolumeStackedBarChart** (62 lines)
   - Recharts BarChart (vertical)
   - All stocks, sorted by total_volume desc
   - Stacked: Active Buy (red) + Active Sell (green) + Neutral (yellow)
   - YAxis uses formatVolume for labels

4. **VolumeDetailTable** (107 lines)
   - Sortable table by symbol, buy_vol, sell_vol, total_vol, buy_ratio
   - Color-coded row backgrounds: buy_ratio > 60% = red tint, < 40% = green tint
   - Columns: Symbol, Buy Vol, Buy Value, Sell Vol, Sell Value, Neutral, Total, Buy Ratio
   - Default sort: total_vol desc

#### Signal Components
1. **SignalFilterChips** (44 lines)
   - 4 filter options: All, Foreign, Volume, Divergence
   - Click to change active filter
   - Active = white bg + text-gray-900, inactive = gray-800

2. **SignalFeedList** (76 lines)
   - Reverse chronological display (latest at top)
   - SignalCard sub-component: time + severity badge + symbol + message
   - Severity styling (blue/yellow/red)
   - Scrollable container: max-h-[calc(100vh-200px)]
   - "No signals" message if empty

---

## 3. Data Flow & Hooks

### Hook Architecture

**useWebSocket** (Generic, Channel-Based)
```typescript
// 202 lines — Production-grade with reconnect + fallback
export function useWebSocket<T>(
  channel: "market" | "foreign" | "index",
  options?: {
    token?: string,
    fallbackFetcher?: () => Promise<T>,
    fallbackIntervalMs?: 5000,
    maxReconnectAttempts?: 3,
  }
): WebSocketResult<T>

// Returns:
{
  data: T | null,           // Latest WS or fallback data
  status: "connecting" | "connected" | "disconnected",
  error: Error | null,
  isLive: boolean,          // true = WS active, false = polling
  reconnect: () => void,    // Force manual reconnect
}
```

**Reconnection Logic:**
- Exponential backoff: 1s → 2s → 4s ... max 30s
- Max 3 attempts before fallback to REST polling
- Periodically re-attempts WS while in fallback (30s interval)
- Invalidates in-flight polling responses on WS connect (`generation` counter)
- Cleans up timers on unmount

**usePolling** (Generic, Simple Interval)
```typescript
// 47 lines — Simple, robust fetcher-based polling
export function usePolling<T>(
  fetcher: () => Promise<T>,
  intervalMs: number = 5000
): PollingResult<T>

// Returns:
{
  data: T | null,
  loading: boolean,
  error: Error | null,
  refresh: () => void,    // Force immediate fetch
}
```

**Specific Hooks:**

1. **useMarketSnapshot** (13 lines)
   - Polls /api/market/snapshot (5s default)
   - Returns MarketSnapshot type
   - Used by VolumeAnalysisPage

2. **useForeignFlow** (13 lines)
   - Polls /api/market/foreign-detail (5s default)
   - Returns ForeignDetailResponse (summary + stocks array)
   - Used by ForeignFlowPage

3. **useSignals** (Mock, 88 lines)
   - Returns hardcoded MOCK_SIGNALS array
   - 8 sample signals (foreign, volume, divergence types)
   - Timestamps generated relative to current time
   - TBD: Will replace with real API endpoint

### Data Flow Diagram
```
API Endpoints ──┐
                ├→ usePolling / useMarketSnapshot ──→ Page Component
                │
                └→ (useWebSocket — prepared but not yet used in pages)

Page Component ──→ Feature Components (consume data via props)
                       ├─ Summary Cards (aggregate/format)
                       ├─ Charts (Recharts)
                       └─ Tables (sortable)

Utils:
  ├─ formatVnd()      → "1.2B" / "500M"
  ├─ formatVolume()   → "2.5M" / "500K"
  └─ formatPercent()  → "+5.2%"
```

---

## 4. Type System

### Core Types (`src/types/index.ts`)

```typescript
// Trade classification
type TradeType = "mua_chu_dong" | "ban_chu_dong" | "neutral"

// Per-stock session stats (volume breakdown)
interface SessionStats {
  symbol: string
  mua_chu_dong_volume: number       // Active buy volume
  mua_chu_dong_value: number
  ban_chu_dong_volume: number       // Active sell volume
  ban_chu_dong_value: number
  neutral_volume: number
  total_volume: number
  last_updated: string | null
}

// Foreign investor per-stock metrics
interface ForeignInvestorData {
  symbol: string
  buy_volume, buy_value
  sell_volume, sell_value
  net_volume, net_value
  total_room, current_room    // Foreign ownership room
  buy_speed_per_min, sell_speed_per_min
  buy_acceleration, sell_acceleration
  last_updated: string | null
}

// Aggregate foreign summary
interface ForeignSummary {
  total_buy_value, total_sell_value, total_net_value
  total_buy_volume, total_sell_volume, total_net_volume
  top_buy: ForeignInvestorData[]
  top_sell: ForeignInvestorData[]
}

// Index intraday data
interface IntradayPoint {
  timestamp: string
  value: number
}

interface IndexData {
  index_id: string
  value: number
  prior_value: number
  change: number
  ratio_change: number
  total_volume: number
  advances, declines, no_changes: number
  intraday: IntradayPoint[]
  advance_ratio: number
  last_updated: string | null
}

// Derivatives (futures)
interface DerivativesData {
  symbol: string
  last_price: number
  change: number
  change_pct: number
  volume: number
  basis: number
  basis_pct: number
  is_premium: boolean
  last_updated: string | null
}

// Unified snapshot (all market data at once)
interface MarketSnapshot {
  quotes: Record<string, SessionStats>      // Keyed by symbol
  indices: Record<string, IndexData>        // Keyed by index_id
  foreign: ForeignSummary | null
  derivatives: DerivativesData | null
}

// API response wrappers
interface ForeignDetailResponse {
  summary: ForeignSummary
  stocks: ForeignInvestorData[]
}

interface VolumeStatsResponse {
  stats: SessionStats[]
}

// Signals (mock until analytics engine)
type SignalType = "foreign" | "volume" | "divergence"
type SignalSeverity = "info" | "warning" | "critical"

interface Signal {
  id: string
  type: SignalType
  severity: SignalSeverity
  symbol: string
  message: string
  value: number
  timestamp: string
}
```

### Type Flow
```
Backend API
    ↓
apiFetch<T>() catches + deserializes
    ↓
Component receives typed data prop
    ↓
Rendering with type-safe accessors
```

---

## 5. Configuration & Build Setup

### Vite Config (`vite.config.ts`)
```typescript
defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
})
```

**Key Details:**
- React Fast Refresh enabled
- TailwindCSS v4 plugin (no CSS layer needed)
- Dev proxy: /api → backend:8000, /ws → backend:8000
- Production: nginx handles proxying

### TypeScript Config (`tsconfig.json`)
- **target:** ES2020 (modern syntax OK: `X | None`, `list[str]`, match/case — compatible with Python 3.12)
- **strict mode:** enabled
- **noUnusedLocals, noUnusedParameters:** enabled (catches dead code)
- **noUncheckedIndexedAccess:** enabled (safer Record access)
- **jsx:** react-jsx (React 19 auto-import transform)
- **module:** ESNext
- **moduleResolution:** bundler

### Package.json Dependencies

**Runtime:**
- `react@^19.0.0` — Latest React 19
- `react-dom@^19.0.0`
- `react-router-dom@^7.13.0` — Latest v7 (hooks-based)
- `recharts@^3.7.0` — Declarative charting library
- `lightweight-charts@^4.2.0` — Professional candlestick charts (installed but not yet used)

**DevDependencies:**
- `typescript@^5.7.0` — Latest TypeScript
- `vite@^6.0.0` — Latest Vite with optimized builds
- `tailwindcss@^4.0.0` — Latest v4 (no content config needed)
- `@tailwindcss/vite@^4.0.0` — Native Vite plugin
- `@vitejs/plugin-react@^4.3.0` — React Fast Refresh

**Build Script:**
```json
"build": "tsc -b && vite build"
```
- TypeScript check first
- Then Vite production build (minify + tree-shake)

### Environment Variables

**Frontend env:** `src/vite-env.d.ts`
```typescript
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
}
```

**Default:** `/api` (works with nginx proxy in dev + prod)

---

## 6. Styling & Theme

### TailwindCSS v4 Integration

**index.css**
```css
@import "tailwindcss";
```
- Single import (v4 magic)
- No layer definitions needed
- Automatically includes reset, default plugins

**Color Palette** (consistent across all components)
- **Background:** gray-950 (near black), gray-900 (dark gray), gray-800 (borders)
- **Text:** white (primary), gray-400 (secondary), gray-600 (tertiary)
- **Accent colors:**
  - **Red** (#ef4444): buy, positive sentiment (VN market convention)
  - **Green** (#22c55e): sell, negative sentiment (VN market convention)
  - **Yellow** (#eab308): neutral trades
  - **Blue/Red** (#fbbf24, #ef4444): severity badges (info/warning/critical)

**Key Utilities Used:**
- Flexbox (flex, flex-1, items-center, gap-*)
- Grid (grid-cols-1, lg:grid-cols-2, gap-6)
- Responsive (md:, lg:)
- Spacing (p-*, m-*)
- Borders (border, border-gray-800, rounded-lg)
- Animations (animate-pulse for skeletons)
- Shadows (none used — flat design)

**Dark Mode:** Hardcoded dark theme (no light mode toggle)

---

## 7. API Integration

### API Client (`src/utils/api-client.ts`)

```typescript
const BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api"

export async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`)
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`)
  return res.json() as Promise<T>
}
```

**Features:**
- Generic typing for type-safe responses
- Simple fetch wrapper (no Auth, no custom headers yet)
- Error handling: rejects on non-2xx status
- Used by usePolling hooks

### Expected Backend Endpoints

Based on code, frontend expects:
- **GET /api/market/snapshot** → MarketSnapshot
- **GET /api/market/foreign-detail** → ForeignDetailResponse
- (Optional) WebSocket /ws/market, /ws/foreign, /ws/index

---

## 8. UI Patterns & Best Practices

### Loading States
- **Suspense + Lazy Components:** Each page lazy-loaded with Suspense boundary
- **Skeleton Loaders:** Page-specific skeletons match final layout (prevents CLS)
- **Fallback Fetchers:** usePolling uses `loading` flag; pages check `if (loading && !data) return <Skeleton />`

### Error Handling
- **ErrorBoundary:** Catches render errors, shows fallback UI + retry
- **ErrorBanner:** Inline error display with optional retry action
- **Hook Errors:** usePolling/useWebSocket catch fetch errors, expose via `error` prop

### Responsive Design
- **Mobile-first CSS:** Base styles for mobile, md:, lg: breakpoints for desktop
- **Responsive Grids:**
  ```css
  grid grid-cols-1 md:grid-cols-3 gap-4  /* 1 col mobile, 3 col desktop */
  grid grid-cols-1 lg:grid-cols-2 gap-6  /* 1 col tablet, 2 col desktop */
  ```
- **Mobile Sidebar:** Fixed overlay with backdrop, auto-closes on route change
- **Table Overflow:** Horizontal scroll on small screens

### Data Aggregation
- **Summary Cards:** Aggregate stats from array (reduce)
- **Sorting:** Client-side sort (react state) for tables
- **Filtering:** Signal page filters by type (array.filter)

### Component Composition
- **Presentational:** Components receive data via props, no fetch logic
- **Container:** Pages handle data fetching, error states, loading
- **Reusable UI:** ErrorBanner, Skeletons, chart wrappers
- **Props Interfaces:** Explicit props interfaces for all components

---

## 9. Existing UI Patterns & Reusable Components

### Reusable Patterns

1. **KPI Cards** (Summary Cards)
   - Dark background, border, padding
   - Label (small gray text), Value (large bold colored), Subtext (smaller gray)
   - 3-column grid on desktop, 1 column mobile
   - Used by: ForeignFlowSummaryCards, VolumeRatioSummaryCards

2. **Chart Containers**
   - Dark background, border, padding, title
   - ResponsiveContainer wrapping Recharts chart
   - Styled grid, axis, tooltip (dark theme colors)
   - Used by: All foreign/volume charts

3. **Sortable Tables**
   - Dark header (bg-gray-950/800)
   - Alternating row backgrounds (gray-900/gray-950)
   - Clickable column headers with sort indicator (↑/↓)
   - Color-coded text (red=buy, green=sell, yellow=neutral)
   - Used by: ForeignFlowDetailTable, VolumeDetailTable

4. **Loading Skeletons**
   - Gray-800 placeholder boxes
   - animate-pulse class
   - Match final layout structure
   - Used by: Suspense fallbacks

5. **Filter Chips**
   - Row of buttons with active state
   - Active: white bg, dark text
   - Inactive: gray-800 bg, gray text
   - Used by: SignalFilterChips

---

## 10. Known Issues & Improvements Noted

### Missing/Incomplete Features
1. **useSignals** is mock data only — no real analytics backend yet
2. **useWebSocket** hook is implemented but not used in pages (pages use polling only)
3. **lightweight-charts** library installed but not used (prepared for future candlestick/OHLCV view)
4. **Authentication:** No auth token handling in API client (no login required for demo)
5. **Real-time Updates:** Pages use polling (5s interval) instead of WebSocket

### Code Observations
- All components are functional components (except ErrorBoundary class component)
- No Redux/Context state management — local component state only
- Tables use basic Array.sort() — O(n log n) — fine for VN30 (30 stocks)
- No virtualization on tables/lists (fine for small datasets like 30 stocks)
- No database/local storage caching (data fetched fresh on each poll)

### Styling Notes
- **VN Market Color Convention:** Red = buy/up, Green = sell/down (opposite of US markets)
- All colors hardcoded; no CSS variables for theme switching
- No animation library (Framer Motion, etc.) — just CSS animations
- Accessible focus states on buttons (focus:ring-red-500)

---

## 11. Testing

No frontend tests found in codebase. Preparation:
- Jest setup: TypeScript + React Testing Library
- Test files: `*.test.tsx` / `*.test.ts`
- Directories: `tests/`, `__tests__/`, or co-located with source

---

## 12. Documentation Files

Located in `/Users/minh/Projects/stock-tracker/plans/reports/`:
- `code-review-260209-1056-use-websocket-hook.md` — WebSocket hook review
- `docs-manager-260209-1059-websocket-hook-documentation.md` — Hook docs
- Previous code reviews of chart, table, dashboard pages

---

## 13. File Sizes & Metrics

| File | Lines | Purpose |
|------|-------|---------|
| use-websocket.ts | 202 | Generic WS with reconnect |
| foreign-flow-detail-table.tsx | 120 | Sortable table |
| foreign-net-flow-heatmap.tsx | 112 | Treemap chart |
| volume-detail-table.tsx | 107 | Sortable table |
| app-sidebar-navigation.tsx | 87 | Responsive sidebar |
| volume-stacked-bar-chart.tsx | 62 | Stacked bar chart |
| foreign-flow-summary-cards.tsx | 56 | KPI cards |
| volume-market-pie-chart.tsx | 61 | Pie chart |
| signal-feed-list.tsx | 76 | Signal cards |

**Total Frontend LOC:** ~1,500 lines (including imports, blanks)

---

## 14. Build & Deploy Info

### Build Output
```bash
npm run build
# → TypeScript type check
# → Vite build (minify, code split, tree-shake)
# → Output: dist/ directory
```

### Deployment
- **Docker:** `Dockerfile` multi-stage build (Node build + nginx serve)
- **Nginx Config:** `nginx.conf` routes /api and /ws to backend, serves SPA on /
- **Environment:** `.env.production` (empty, uses defaults)

---

## 15. Summary Table

| Aspect | Details |
|--------|---------|
| **React Version** | 19.0.0 (latest) |
| **Build Tool** | Vite 6.0.0 |
| **TypeScript** | 5.7.0, strict mode |
| **Styling** | TailwindCSS v4.0.0 |
| **State Management** | React hooks only (no Redux) |
| **Charting** | Recharts 3.7.0 (primary), lightweight-charts 4.2.0 (prepared) |
| **Routing** | React Router v7.13.0 |
| **Pages** | 3 (Foreign Flow, Volume, Signals) |
| **Components** | 16 feature + 4 layout + 4 ui |
| **Hooks** | 5 (2 generic, 3 specific) |
| **API Calls** | 2 polling endpoints + 1 mock signals |
| **Data Fetching** | Polling (5s interval) + optional WebSocket |
| **Error Handling** | ErrorBoundary + ErrorBanner |
| **Loading States** | Suspense + skeleton loaders |
| **Responsive Design** | Mobile-first, tailored breakpoints |
| **Color Scheme** | Dark gray (bg) + red/green (sentiment) |
| **Auth** | None (demo mode) |
| **Tests** | None yet |

---

## Unresolved Questions

1. **Lightweight Charts:** Why installed but not used? Plan to add candlestick charts?
2. **WebSocket Hook:** Ready but pages use polling — when should they switch to WS?
3. **Signals Analytics:** When will real analytics engine replace mock data?
4. **Authentication:** Should frontend support API tokens?
5. **Local Storage:** Cache market snapshots across page reloads?
6. **Testing:** Target coverage % and test framework (Jest + RTL)?
7. **Accessibility:** ARIA labels, keyboard nav, screen reader testing?
8. **Performance:** Monitor Core Web Vitals? Profiling needed?
9. **Error Recovery:** Should failed requests auto-retry with backoff?
10. **i18n:** Support Vietnamese + English UI text?

---

**End of Report**

Generated: 2026-02-09 11:04
Work Context: /Users/minh/Projects/stock-tracker
