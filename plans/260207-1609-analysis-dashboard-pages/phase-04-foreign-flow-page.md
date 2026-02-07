# Phase 4: Foreign Flow Page

## Context

- Route: `/foreign-flow`
- Data source: `useForeignFlow()` -> `{ summary: ForeignSummary, stocks: ForeignInvestorData[] }`
- VN colors: red=buy(positive), green=sell(negative)

## Overview

- **Priority**: P1
- **Status**: pending
- **Effort**: 1h

## Page Layout

```
┌──────────────────────────────────────────────────────┐
│  Foreign Flow   [Last updated: HH:MM:SS]             │
├──────────────────────┬───────────────────────────────┤
│  Net Flow Summary    │  Top Buy vs Sell Bar Chart    │
│  (3 KPI cards)       │  (horizontal bar, top 10)     │
├──────────────────────┴───────────────────────────────┤
│  VN30 Heatmap (Treemap by net value intensity)       │
├──────────────────────────────────────────────────────┤
│  Detailed Table (all stocks, sortable)               │
└──────────────────────────────────────────────────────┘
```

## Components

### Page: `frontend/src/pages/foreign-flow-page.tsx` (~50 lines)

Composes all sub-components. Uses `useForeignFlow()`. Wraps content in Suspense boundary with loading skeleton.

```tsx
export function ForeignFlowPage() {
  const { data, loading, error } = useForeignFlow();
  if (loading) return <PageSkeleton />;
  if (error) return <ErrorBanner message={error.message} />;
  if (!data) return null;
  return (
    <div className="space-y-6 p-6">
      <ForeignFlowSummaryCards summary={data.summary} />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ForeignTopMoversBarChart stocks={data.stocks} />
        <ForeignNetFlowHeatmap stocks={data.stocks} />
      </div>
      <ForeignFlowDetailTable stocks={data.stocks} />
    </div>
  );
}
```

### `frontend/src/components/foreign/foreign-flow-summary-cards.tsx` (~50 lines)

Three KPI cards:
- **Total Net Flow**: `summary.total_net_value` formatted as VND (positive=red, negative=green)
- **Buy Volume**: `summary.total_buy_volume`
- **Sell Volume**: `summary.total_sell_volume`

### `frontend/src/components/foreign/foreign-top-movers-bar-chart.tsx` (~60 lines)

Recharts `<BarChart>` horizontal:
- Take top 5 buy + top 5 sell (sorted by `|net_value|`)
- Two bars per stock: buy_value (red), sell_value (green)
- Y-axis: symbol name, X-axis: value in billions VND

```tsx
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
// Transform stocks -> sorted top movers data
// Render horizontal BarChart
```

### `frontend/src/components/foreign/foreign-net-flow-heatmap.tsx` (~70 lines)

Recharts `<Treemap>`:
- Each cell = 1 stock from VN30
- Size = `total_room` (or equal sizing if room not available)
- Color intensity = `net_value` (red gradient for net buy, green gradient for net sell)
- Label = symbol + net_value abbreviated

```tsx
import { Treemap, ResponsiveContainer } from "recharts";
// Custom content renderer for coloring by net_value
```

### `frontend/src/components/foreign/foreign-flow-detail-table.tsx` (~80 lines)

HTML table with TailwindCSS:
- Columns: Symbol | Buy Vol | Sell Vol | Net Vol | Net Value | Buy Speed | Sell Speed | Room
- Sortable by clicking column headers (local state)
- Alternating row colors on dark background
- Net values colored: positive=red, negative=green

### Shared: `frontend/src/components/ui/page-loading-skeleton.tsx` (~20 lines)

Reusable loading skeleton with pulsing animation.

### Shared: `frontend/src/components/ui/error-banner.tsx` (~15 lines)

Red banner with error message and retry button.

## Files Summary

| Action | File | Lines |
|--------|------|-------|
| Rewrite | `frontend/src/pages/foreign-flow-page.tsx` | ~50 |
| Create | `frontend/src/components/foreign/foreign-flow-summary-cards.tsx` | ~50 |
| Create | `frontend/src/components/foreign/foreign-top-movers-bar-chart.tsx` | ~60 |
| Create | `frontend/src/components/foreign/foreign-net-flow-heatmap.tsx` | ~70 |
| Create | `frontend/src/components/foreign/foreign-flow-detail-table.tsx` | ~80 |
| Create | `frontend/src/components/ui/page-loading-skeleton.tsx` | ~20 |
| Create | `frontend/src/components/ui/error-banner.tsx` | ~15 |

## Todo

- [ ] Create shared UI components (skeleton, error banner)
- [ ] Build summary cards component
- [ ] Build horizontal bar chart (top movers)
- [ ] Build treemap heatmap (net flow intensity)
- [ ] Build sortable detail table
- [ ] Compose in `foreign-flow-page.tsx`
- [ ] Verify `npm run build` compiles

## Success Criteria

- Page renders 4 visual sections (cards, chart, heatmap, table)
- Bar chart shows top 10 movers (5 buy + 5 sell)
- Heatmap colors stocks by net flow direction/intensity
- Table is sortable by any column
- VN color convention: red=buy, green=sell
- All components <200 lines each

## Utility: Number Formatting

Create `frontend/src/utils/format-number.ts` (~30 lines):
- `formatVnd(value)` -- format as VND with B/M suffix (e.g., "1.2B")
- `formatVolume(value)` -- format with K/M suffix
- `formatPercent(value)` -- format as percentage with +/- sign
