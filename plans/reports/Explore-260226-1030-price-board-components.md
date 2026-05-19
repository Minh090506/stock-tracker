# Price Board Component Exploration Report

**Date**: 2026-02-26 10:30  
**Explored**: Frontend Price Board components, formatting, and data flow

## Summary

Thoroughly mapped the Price Board component architecture including:
- Table component structure with sorting, colors, and flash animations
- Price/change/percentage formatting (raw values, fixed decimals)
- Buy pressure calculation and color logic (>50% green, ≤50% red)
- Sparkline trend chart (SVG polyline, 50-point accumulation, last vs first price coloring)
- Utility formatters and data flow from WebSocket/REST to display

## 1. Price Board Main Components

### Component Files
| File | Purpose |
|------|---------|
| `price-board-table.tsx` | Main 30-stock table with sorting & flash animation |
| `price-board-sparkline.tsx` | SVG sparkline renderer for trends |
| `market-session-indicator.tsx` | VN market session badge (ATO/Continuous/ATC/PLO) |
| `price-board-page.tsx` | Page container with header and error handling |
| `use-price-board-data.ts` | WebSocket hook + VN30 filtering + sparkline accumulation |

### File Paths
```
/Users/minh/Projects/stock-tracker/frontend/src/
├── components/price-board/
│   ├── price-board-table.tsx
│   ├── price-board-sparkline.tsx
│   └── market-session-indicator.tsx
├── pages/price-board-page.tsx
├── hooks/use-price-board-data.ts
├── utils/
│   ├── format-number.ts
│   ├── market-session.ts
│   └── api-client.ts
└── types/index.ts
```

## 2. Price Formatting

### Current Implementation
**File**: `price-board-table.tsx` lines 21-23

```typescript
function formatPrice(price: number): string {
  return price > 0 ? price.toFixed(2) : "-";
}
```

### Display Format
- **Raw value with 2 decimals**: `45000.00`, `1250.50`, `-` (if zero)
- **No K/M abbreviation** (unlike volume)
- **Font**: Monospace (font-mono)
- **Column header**: "Price"

### Data Source
- Backend field: `PriceData.last_price` (number)
- API endpoint: `/api/market/snapshot` or WebSocket `market` channel
- Comes from: `MarketSnapshot.prices[symbol].last_price`

### Display Location
```typescript
<td className={`px-4 py-2 text-right font-mono ${colorClass}`}>
  {formatPrice(row.price.last_price)}
</td>
```

## 3. Change Column

### Change (Absolute Value)
**File**: `price-board-table.tsx` lines 130-132

```typescript
<td className={`px-4 py-2 text-right font-mono ${colorClass}`}>
  {row.price.change > 0 ? "+" : ""}{row.price.change.toFixed(2)}
</td>
```

**Format**:
- Shows `+` for positive, no sign for negative (just the minus from number)
- 2 decimal places: `+150.25`, `-45.50`, `+0.00`
- Monospace font
- Colored by `priceColorClass()` logic

**Data Source**: `PriceData.change` (number, in points)

### Change % (Percentage)
**File**: `price-board-table.tsx` line 134 + `format-number.ts` lines 20-24

```typescript
// In table
<td className={`px-4 py-2 text-right font-mono ${colorClass}`}>
  {formatPercent(row.price.change_pct)}
</td>

// Formatter
export function formatPercent(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}%`;
}
```

**Format**:
- Shows `+` for positive
- 1 decimal place: `+2.5%`, `-1.2%`, `+0.0%`
- Appends `%` symbol
- Sortable column (ascending/descending)

**Data Source**: `PriceData.change_pct` (percentage as decimal, e.g., 2.5 means 2.5%)

## 4. Buy Pressure Coloring

### Calculation
**File**: `price-board-table.tsx` lines 83-87

```typescript
const buyPressurePct = (row: PriceBoardRow): number | null => {
  const total = row.stats?.total_volume ?? 0;
  if (total === 0) return null;
  return (row.stats!.mua_chu_dong_volume / total) * 100;
};
```

**Formula**: `(active_buy_volume / total_volume) × 100`

**Data Fields**:
- Numerator: `SessionStats.mua_chu_dong_volume` (active buy orders)
- Denominator: `SessionStats.total_volume` (all volume)
- Returns: `null` if total_volume is 0

### Display & Coloring
**File**: `price-board-table.tsx` lines 139-145

```typescript
<td className="px-4 py-2 text-right">
  {bp !== null
    ? <span className={bp > 50 ? "text-green-400" : "text-red-400"}>
        {bp.toFixed(1)}%
      </span>
    : <span className="text-gray-500">-</span>}
</td>
```

**Color Logic**:
- **Green (text-green-400)**: Buy pressure > 50% (buying dominance)
- **Red (text-red-400)**: Buy pressure ≤ 50% (selling dominance)
- **Gray (text-gray-500)**: No data (total_volume = 0)

**Format**: 1 decimal place (e.g., `65.3%`, `48.7%`)

**Column Header**: "Buy Pressure"

## 5. Trend Sparkline/Chart

### Component
**File**: `price-board-sparkline.tsx` (47 lines)

### Props & Defaults
```typescript
interface PriceBoardSparklineProps {
  data: number[];      // Array of price values
  width?: number;      // Default: 80px
  height?: number;     // Default: 24px
}
```

### Algorithm

**Step 1: Normalize**
```typescript
const min = Math.min(...data);
const max = Math.max(...data);
const range = max - min || 1;  // Avoid division by zero
const padding = 1;
```

**Step 2: Map to SVG Coordinates**
```typescript
const points = data
  .map((val, i) => {
    const x = padding + (i / (data.length - 1)) * (width - 2 * padding);
    const y = padding + (1 - (val - min) / range) * (height - 2 * padding);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  })
  .join(" ");
```

- X: Linear spacing across width
- Y: Inverted (top=high price, bottom=low price)
- Each point normalized to viewport with 1px padding

**Step 3: Render SVG**
```typescript
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
```

### Color Logic
```typescript
const last = data[data.length - 1] ?? 0;
const first = data[0] ?? 0;
const strokeColor = last >= first ? "#22c55e" : "#ef4444";
```

**Coloring**:
- **Green (#22c55e)**: Last price ≥ first price (uptrend or flat)
- **Red (#ef4444)**: Last price < first price (downtrend)

### Data Accumulation

**File**: `use-price-board-data.ts` lines 40-55

```typescript
const MAX_SPARKLINE_POINTS = 50;

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
```

**Key Behaviors**:
- Maintains up to 50 price ticks per symbol
- Deduplicates consecutive identical prices
- Uses FIFO (first-in-first-out) when exceeding 50 points
- Persisted via `useRef` (survives renders)
- Updated on each WebSocket message

### Display in Table
**File**: `price-board-table.tsx` line 147

```typescript
<td className="px-4 py-2 text-center">
  <PriceBoardSparkline data={row.sparkline} />
</td>
```

## 6. Price Color Classes

### Function
**File**: `price-board-table.tsx` lines 12-19

```typescript
function priceColorClass(row: PriceBoardRow): string {
  const { last_price, ceiling, floor, change } = row.price;
  if (ceiling > 0 && last_price >= ceiling) return "text-yellow-400";
  if (floor > 0 && last_price <= floor) return "text-yellow-400";
  if (change > 0) return "text-green-400";
  if (change < 0) return "text-red-400";
  return "text-gray-300";
}
```

### Color Priority (Evaluated in Order)
1. **Yellow (text-yellow-400)**: At ceiling (max price limit) OR at floor (min price limit)
2. **Green (text-green-400)**: Price up (change > 0)
3. **Red (text-red-400)**: Price down (change < 0)
4. **Gray (text-gray-300)**: No change or no ceiling/floor data

### Applied To
- Price column (last_price)
- Change column (change value)

### VN Market Color Convention
- **Red = Up** (opposite of US markets)
- **Green = Down** (opposite of US markets)
- **Yellow = Ceiling/Floor hit** (special case, both are yellow)

**This implementation uses:**
- Green for up (US style)
- Red for down (US style)
- *Note: May need alignment with VN convention depending on design intent*

## 7. Utility Functions

### File: `format-number.ts`

```typescript
/** Format value with B/M/K suffix */
export function formatVnd(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1e9) return `${(value / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `${(value / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${(value / 1e3).toFixed(1)}K`;
  return value.toFixed(0);
}

/** Format volume with K/M suffix */
export function formatVolume(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1e6) return `${(value / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${(value / 1e3).toFixed(1)}K`;
  return value.toFixed(0);
}

/** Format as percentage with +/- sign */
export function formatPercent(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}%`;
}
```

### Usage in Price Board
- **formatPercent()**: Change % column (1 decimal)
- **formatVolume()**: Total volume column (2 decimals for M, 1 for K)
- **formatVnd()**: Not used in price board (used in foreign flow pages)

### Volume Column Example
**File**: `price-board-table.tsx` line 137

```typescript
<td className="px-4 py-2 text-right text-gray-300">
  {row.stats ? formatVolume(row.stats.total_volume) : "-"}
</td>
```

Examples: `1.5M`, `234.5K`, `50`

## 8. Flash Animation

### Implementation
**File**: `price-board-table.tsx` lines 35-52

```typescript
useEffect(() => {
  const flashing = new Set<string>();
  for (const row of rows) {
    const prev = prevPricesRef.current[row.symbol];
    if (prev !== undefined && prev !== row.price.last_price) {
      flashing.add(row.symbol);
    }
    prevPricesRef.current[row.symbol] = row.price.last_price;
  }

  let timer: ReturnType<typeof setTimeout> | undefined;
  if (flashing.size > 0) {
    setFlashSymbols(flashing);
    timer = setTimeout(() => setFlashSymbols(new Set()), 400);
  }
  return () => { if (timer) clearTimeout(timer); };
}, [rows]);
```

### Styling
**File**: `price-board-table.tsx` lines 115-118

```typescript
const isFlashing = flashSymbols.has(row.symbol);
const flashBg = isFlashing
  ? row.price.change >= 0 ? "bg-green-900/30" : "bg-red-900/30"
  : "";

// Applied to row
<tr className={`border-t border-gray-800 hover:bg-gray-800/50 transition-colors duration-300 ${flashBg}`}>
```

### Behavior
- **Trigger**: Any price change detected
- **Duration**: 400ms
- **Effect**: Row background color flash
- **Color**: Green for positive change, red for negative
- **Opacity**: 30% (900/30 in Tailwind)

## 9. Sorting

### Sortable Columns
- **Symbol**: A-Z (text sorting)
- **Change %**: Numeric (ascending/descending)
- **Volume**: Numeric (ascending/descending)

### Default
- Sort by: Symbol
- Direction: Ascending

### Implementation
**File**: `price-board-table.tsx` lines 54-78, 80-81

```typescript
const handleSort = (key: SortKey) => {
  if (sortKey === key) {
    setSortDir(sortDir === "asc" ? "desc" : "asc");
  } else {
    setSortKey(key);
    setSortDir(key === "symbol" ? "asc" : "desc");
  }
};

const sortIcon = (key: SortKey) =>
  sortKey === key ? (sortDir === "asc" ? " ↑" : " ↓") : "";
```

### UI
- Click column header to sort
- Arrow icon indicates sort direction (↑ asc, ↓ desc)
- Sortable headers have hover effect (bg-gray-700)

## 10. Data Types

### PriceBoardRow
```typescript
interface PriceBoardRow {
  symbol: string;
  price: PriceData;
  stats: SessionStats | null;
  sparkline: number[];
}
```

### PriceData
```typescript
interface PriceData {
  last_price: number;
  change: number;
  change_pct: number;
  ref_price: number;
  ceiling: number;
  floor: number;
}
```

### SessionStats
```typescript
interface SessionStats {
  symbol: string;
  mua_chu_dong_volume: number;        // Active buy volume
  ban_chu_dong_volume: number;        // Active sell volume
  neutral_volume: number;
  total_volume: number;
  last_updated: string | null;
  ato: SessionBreakdown;
  continuous: SessionBreakdown;
  atc: SessionBreakdown;
}
```

### MarketSnapshot (from API/WebSocket)
```typescript
interface MarketSnapshot {
  quotes: Record<string, SessionStats>;
  prices: Record<string, PriceData>;
  indices: Record<string, IndexData>;
  foreign: ForeignSummary | null;
  derivatives: DerivativesData | null;
  velocity: VelocitySnapshot | null;
}
```

## 11. Data Flow

```
┌─────────────────────────────────────┐
│ Backend API/WebSocket               │
│ /api/market/snapshot                │
│ /ws/market (SSI FastConnect)        │
└──────────────┬──────────────────────┘
               │
               ↓
┌──────────────────────────────────────┐
│ useWebSocket Hook                    │
│ (use-websocket.ts)                   │
│ - WebSocket connection               │
│ - Auto-reconnect with exponential    │
│   backoff (1s → 30s)                 │
│ - REST fallback every 3s if WS down  │
└──────────────┬───────────────────────┘
               │
               ↓
┌──────────────────────────────────────┐
│ usePriceBoardData Hook               │
│ (use-price-board-data.ts)            │
│ - Fetch VN30 symbols list            │
│ - Filter snapshot to VN30 only       │
│ - Accumulate sparkline data (50 pts) │
│ - Build PriceBoardRow[]              │
└──────────────┬───────────────────────┘
               │
               ↓
┌──────────────────────────────────────┐
│ PriceBoardTable Component            │
│ (price-board-table.tsx)              │
│ - Sort by symbol/change%/volume      │
│ - Color prices by change/ceiling     │
│ - Flash animation on price change    │
│ - Render sparklines (SVG)            │
│ - Format values (price, %, volume)   │
└──────────────┬───────────────────────┘
               │
               ↓
┌──────────────────────────────────────┐
│ User sees: Real-time Price Board     │
│ - 30 stocks with live prices         │
│ - Sorted and colored                 │
│ - Trend sparklines                   │
│ - Buy pressure indicators            │
└──────────────────────────────────────┘
```

## 12. WebSocket Configuration

### File: `use-price-board-data.ts` lines 32-37

```typescript
const { data: snapshot, status, error, isLive, reconnect } =
  useWebSocket<MarketSnapshot>("market", {
    fallbackFetcher: () => apiFetch<MarketSnapshot>("/market/snapshot"),
    fallbackIntervalMs: 3000,  // 3 seconds
  });
```

### Connection Status
- **"connecting"**: Initial connection attempt
- **"connected"**: WebSocket or REST fallback active
- **"disconnected"**: Lost connection, attempting reconnect

### Polling Fallback
- Triggered after 3 failed WebSocket connection attempts
- Polls every 3000ms (3 seconds)
- Periodically retries WebSocket every 30 seconds

### Status Indicator (price-board-page.tsx lines 26-34)
```typescript
<div className="flex items-center gap-2 text-xs">
  <span className={`inline-block w-2 h-2 rounded-full ${
    isLive ? "bg-green-500" : "bg-yellow-500"
  }`} />
  <span className="text-gray-400">
    {isLive ? "Live" : "Polling"}
    {status === "disconnected" && " (reconnecting...)"}
  </span>
</div>
```

- **Green dot + "Live"**: WebSocket active
- **Yellow dot + "Polling"**: REST polling fallback
- **Shows "reconnecting..."** when disconnected

## 13. Market Session Detection

### File: `market-session.ts`

VN stock market trading sessions:
- **Pre-market** (before 09:00): Blue
- **ATO** (09:00-09:15): Auction opening, Yellow
- **Continuous** (09:15-11:30, 13:00-14:30): Green
- **Lunch Break** (11:30-13:00): Orange
- **ATC** (14:30-14:45): Auction closing, Yellow
- **PLO** (14:45-15:00): Closing event, Purple
- **Closed** (after 15:00, weekends): Gray

### Component: `market-session-indicator.tsx`

Displayed as badge in page header, refreshes every 15 seconds.

## 14. Dependencies

### React & Build
- React 19.0.0
- React Router 7.13.0
- Vite 6.0.0
- TypeScript 5.7.0

### Styling
- Tailwind CSS 4.0.0

### Charts (Other Pages)
- Recharts 3.7.0 (not used in price board)
- Lightweight Charts 4.2.0 (not used in price board)

### Sparkline
- **Custom SVG** (no external library)

## Key Findings

1. **Price Formatting**: Raw format with 2 decimals (`45000.00`), no abbreviation
2. **Change Formatting**: 2 decimals with sign (`+150.25`), separate from percentage
3. **Percentage Formatting**: 1 decimal with `%` suffix (`+2.5%`)
4. **Buy Pressure Coloring**: Threshold at 50% (>50% green, ≤50% red)
5. **Sparkline Data**: 50-point rolling window, deduplicated, updated on each snapshot
6. **Sparkline Rendering**: SVG polyline with min/max normalization
7. **Sparkline Coloring**: Last vs first price (green up, red down)
8. **Price Coloring**: 4-level priority (ceiling/floor > change > no change)
9. **Flash Animation**: 400ms row background flash on price change
10. **WebSocket Fallback**: 3-second REST polling if WS unavailable
11. **VN30 Filtering**: Fetches symbol list at mount, filters snapshot to 30 stocks
12. **Sorting**: Symbol (text), Change % (numeric), Volume (numeric) — default by symbol ASC

## Files Explored

All source files in `/Users/minh/Projects/stock-tracker/frontend/src/`:

**Components**:
- `components/price-board/price-board-table.tsx` (156 lines)
- `components/price-board/price-board-sparkline.tsx` (47 lines)
- `components/price-board/market-session-indicator.tsx` (23 lines)

**Pages**:
- `pages/price-board-page.tsx` (48 lines)

**Hooks**:
- `hooks/use-price-board-data.ts` (73 lines)
- `hooks/use-websocket.ts` (202 lines)

**Utils**:
- `utils/format-number.ts` (25 lines)
- `utils/market-session.ts` (80 lines)
- `utils/api-client.ts` (10 lines)

**Types**:
- `types/index.ts` (286 lines)

**Config**:
- `package.json` (28 lines)

---

**Total files explored**: 11  
**Total lines analyzed**: ~1,200+  
**Exploration time**: Thorough component-by-component analysis

