# Phase 7: Frontend Backtest Dashboard

## Context Links
- [Parent Plan](./plan.md)
- Dependencies: Phase 6 (Backtest Engine API endpoints)
- [Phase 4 Frontend Patterns](./phase-04-frontend-velocity-dashboard.md)

## Overview
- **Priority**: P2 (after Phase 6 + data accumulation)
- **Status**: complete
- **Effort**: 4h
- **Description**: Interactive backtest dashboard showing cross-correlation heatmap, threshold probability table, time-of-day pattern chart. Hybrid: pre-computed daily summary + on-demand custom analysis.

## Key Insights
- Reuse existing frontend patterns: usePolling for REST, Recharts for charts
- 3 visualization sections matching 3 analysis types
- Pre-computed summary loads instantly on page visit; on-demand analysis shows loading spinner
- Date range picker needed for custom analysis (simple: "Last N days" dropdown, not calendar)
- VN market hours: 9:00-11:30, 13:00-14:45 — gap at lunch shown as break in charts

## Requirements

### Functional
- **Correlation heatmap**: bar chart showing Pearson coefficient for each lag (k=0..10 min), highlight optimal lag
- **Threshold table**: table with bins showing imbalance range, sample count, P(price up), avg change, color-coded
- **Pattern chart**: grouped bar chart by hour-of-day showing avg correlation strength
- **Controls**: symbol selector (VN30F / VN30 basket), days dropdown (5/10/20/30), analysis trigger button
- **Loading states**: skeleton while analysis runs (~5-10s), pre-computed loads instantly
- **Insufficient data**: friendly message if <5 trading days collected

### Non-Functional
- Page load <200ms (pre-computed data is small JSON)
- Chart renders <100ms
- Responsive layout (mobile-friendly)

## Architecture

```
Frontend BacktestPage
    |
    +--- useBacktestData() hook
    |       |
    |       +--- GET /api/backtest/summary (pre-computed, instant)
    |       +--- GET /api/backtest/correlation?... (on-demand)
    |       +--- GET /api/backtest/threshold?... (on-demand)
    |       +--- GET /api/backtest/patterns?... (on-demand)
    |
    +--- Components
            |
            +--- backtest-correlation-chart.tsx (bar chart, lag vs corr)
            +--- backtest-threshold-table.tsx (conditional probability table)
            +--- backtest-pattern-chart.tsx (hour-of-day grouped bars)
            +--- backtest-controls.tsx (symbol, days, run button)
            +--- backtest-summary-cards.tsx (key metrics: optimal lag, best threshold)
```

## Related Code Files

### Files to CREATE
- `frontend/src/pages/backtest-page.tsx` (~50 LOC)
- `frontend/src/hooks/use-backtest-data.ts` (~80 LOC)
- `frontend/src/components/backtest/backtest-correlation-chart.tsx` (~100 LOC)
- `frontend/src/components/backtest/backtest-threshold-table.tsx` (~90 LOC)
- `frontend/src/components/backtest/backtest-pattern-chart.tsx` (~80 LOC)
- `frontend/src/components/backtest/backtest-controls.tsx` (~70 LOC)
- `frontend/src/components/backtest/backtest-summary-cards.tsx` (~60 LOC)
- `frontend/src/components/ui/backtest-skeleton.tsx` (~30 LOC)

### Files to MODIFY
- `frontend/src/types/index.ts` — add backtest types
- `frontend/src/App.tsx` — add `/backtest` route
- `frontend/src/components/layout/app-sidebar-navigation.tsx` — add nav item
- `frontend/src/utils/api-client.ts` — add backtest API functions (if pattern requires)

## Implementation Steps

### Step 1: TypeScript Types (`types/index.ts`)
```typescript
// -- Backtest types --

export interface CrossCorrelationResult {
  lag_minutes: number;
  correlation: number;
  sample_size: number;
}

export interface CrossCorrelationReport {
  symbol: string;
  date_from: string;
  date_to: string;
  results: CrossCorrelationResult[];
  optimal_lag: number;
  optimal_correlation: number;
}

export interface ThresholdBin {
  imbalance_min: number;
  imbalance_max: number;
  sample_count: number;
  price_up_probability: number;
  avg_price_change: number;
  avg_magnitude: number;
}

export interface ThresholdReport {
  symbol: string;
  lookahead_minutes: number;
  date_from: string;
  date_to: string;
  bins: ThresholdBin[];
}

export interface TimePatternEntry {
  hour: number;
  session_phase: string;
  avg_correlation: number;
  avg_imbalance: number;
  sample_count: number;
}

export interface PatternReport {
  symbol: string;
  date_from: string;
  date_to: string;
  patterns: TimePatternEntry[];
}

export interface BacktestSummary {
  computed_at: string;
  data_days: number;
  cross_correlation: CrossCorrelationReport;
  threshold: ThresholdReport;
  patterns: PatternReport;
}
```

### Step 2: Hook (`use-backtest-data.ts`)
```typescript
// Load pre-computed summary on mount via usePolling (60s refresh)
// Provide runCustomAnalysis(symbol, days, type) for on-demand
// Return { summary, customResult, loading, error, runAnalysis }
```

### Step 3: Correlation Chart (`backtest-correlation-chart.tsx`)
- Recharts BarChart: X=lag (0-10 min), Y=Pearson coefficient (-1 to +1)
- Red bars for positive correlation, green for negative
- Highlight bar at optimal lag with different color/border
- Reference line at y=0
- Tooltip: lag, correlation, sample size

### Step 4: Threshold Table (`backtest-threshold-table.tsx`)
- Table with columns: Imbalance Range, Samples, P(Up), Avg Change, Avg |Change|
- Color-code P(Up): >60% green, <40% red, 40-60% neutral
- Highlight rows with high predictive value (P(Up) >70% or <30%)

### Step 5: Pattern Chart (`backtest-pattern-chart.tsx`)
- Recharts GroupedBarChart: X=hour (9,10,11,13,14), grouped by session phase
- Y=average correlation coefficient
- Color: ATO=blue, continuous=gray, ATC=orange
- Shows when velocity-price relationship is strongest

### Step 6: Summary Cards (`backtest-summary-cards.tsx`)
- Card 1: Optimal Lag (e.g., "3 phút" with correlation value)
- Card 2: Best Threshold (e.g., "Imbalance >80% → P(up) = 72%")
- Card 3: Strongest Pattern (e.g., "14:00-14:30 correlation highest")
- Card 4: Data Coverage (e.g., "15 trading days, 4,050 data points")

### Step 7: Controls (`backtest-controls.tsx`)
- Symbol dropdown: "VN30F (Phái sinh)" / "VN30 Basket (Rổ cơ sở)"
- Days dropdown: 5 / 10 / 20 / 30 ngày
- Lookahead dropdown: 1 / 3 / 5 / 10 phút (for threshold analysis)
- "Chạy Phân Tích" button with loading state
- Disclaimer text: "Tương quan ≠ nhân quả. Kết quả chỉ mang tính tham khảo."

### Step 8: Page + Routing
- Add lazy route `/backtest` in App.tsx
- Add "Backtest" nav item in sidebar (below "Tốc độ lệnh")
- Add BacktestSkeleton for loading fallback

## Todo List
- [x] Add backtest TypeScript types to `types/index.ts`
- [x] Create `use-backtest-data.ts` hook (pre-computed + on-demand)
- [x] Create `backtest-correlation-chart.tsx` (bar chart, lag vs correlation)
- [x] Create `backtest-threshold-table.tsx` (conditional probability table)
- [x] Create `backtest-pattern-chart.tsx` (hour-of-day grouped bars)
- [x] Create `backtest-summary-cards.tsx` (key insight cards)
- [x] Create `backtest-controls.tsx` (symbol, days, run button)
- [x] Create `backtest-skeleton.tsx` (loading state)
- [x] Create `backtest-page.tsx` (page layout)
- [x] Add route + sidebar nav item
- [x] Test with mock data while accumulating real data — deferred (awaiting 5+ trading days of data)

## Success Criteria
- Pre-computed summary loads in <200ms
- On-demand analysis shows loading state, results render within 1s of API response
- All 3 chart types render correctly with sample data
- Insufficient data (<5 days) shows friendly message
- Mobile-responsive layout (stacks vertically on small screens)
- TypeScript compiles clean (`npx --package typescript tsc --noEmit`)

## Risk Assessment
- **No data yet**: Show "Đang thu thập dữ liệu..." message with progress (X/5 ngày)
- **Slow on-demand queries**: Show loading spinner, disable button while running
- **Misleading correlations**: Disclaimer prominently displayed, show confidence intervals
- **Chart rendering with sparse data**: Handle empty bins gracefully, show N/A

## Security Considerations
- Rate-limit on-demand endpoints (prevent abuse of heavy SQL queries)
- No user input goes directly to SQL (all parameterized in backend)

## Next Steps
- Accumulate 5+ trading days of data
- Run first backtest analysis
- Iterate on threshold/pattern parameters based on initial results
