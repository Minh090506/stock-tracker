# Phase 5: Volume Analysis Page

## Context

- Route: `/volume`
- Data source: `useMarketSnapshot()` -> `data.quotes` is `Record<string, SessionStats>`
- SessionStats has: `mua_chu_dong_volume/value`, `ban_chu_dong_volume/value`, `neutral_volume`, `total_volume`
- VN colors: red=active buy (mua chu dong), green=active sell (ban chu dong), yellow=neutral

## Overview

- **Priority**: P1
- **Status**: pending
- **Effort**: 1h

## Page Layout

```
┌──────────────────────────────────────────────────────┐
│  Volume Analysis   [Last updated: HH:MM:SS]          │
├──────────────────────┬───────────────────────────────┤
│  Market-Wide Pie     │  Buy/Sell Ratio KPI Cards     │
│  (buy vs sell vs     │  (total buy%, sell%, neutral%) │
│   neutral ratio)     │                               │
├──────────────────────┴───────────────────────────────┤
│  Stacked Bar: Active Buy vs Sell per Stock (VN30)    │
├──────────────────────────────────────────────────────┤
│  Volume Detail Table (all stocks, sortable)          │
└──────────────────────────────────────────────────────┘
```

## Components

### Page: `frontend/src/pages/volume-analysis-page.tsx` (~45 lines)

```tsx
export function VolumeAnalysisPage() {
  const { data, loading, error } = useMarketSnapshot();
  if (loading) return <PageSkeleton />;
  if (error) return <ErrorBanner message={error.message} />;
  if (!data) return null;

  const stats = Object.values(data.quotes);
  return (
    <div className="space-y-6 p-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <VolumeMarketPieChart stats={stats} />
        <VolumeRatioCards stats={stats} />
      </div>
      <VolumeStackedBarChart stats={stats} />
      <VolumeDetailTable stats={stats} />
    </div>
  );
}
```

### `frontend/src/components/volume/volume-market-pie-chart.tsx` (~50 lines)

Recharts `<PieChart>`:
- 3 slices: total mua_chu_dong_volume (red), ban_chu_dong_volume (green), neutral_volume (yellow)
- Aggregate across all symbols
- Show percentage labels on each slice

### `frontend/src/components/volume/volume-ratio-cards.tsx` (~40 lines)

3 KPI cards derived from aggregated stats:
- **Buy Ratio**: `sum(mua_chu_dong_volume) / sum(total_volume) * 100`%
- **Sell Ratio**: `sum(ban_chu_dong_volume) / sum(total_volume) * 100`%
- **Neutral**: remainder
- Color-coded: red/green/yellow

### `frontend/src/components/volume/volume-stacked-bar-chart.tsx` (~60 lines)

Recharts `<BarChart>` vertical stacked:
- X-axis: stock symbols (VN30, sorted by total_volume desc)
- Stacked bars: mua_chu_dong_volume (red) + ban_chu_dong_volume (green) + neutral (yellow)
- Tooltip shows exact numbers

```tsx
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from "recharts";
```

### `frontend/src/components/volume/volume-detail-table.tsx` (~70 lines)

HTML table:
- Columns: Symbol | Buy Vol | Buy Value | Sell Vol | Sell Value | Neutral | Total | Buy Ratio
- Buy Ratio = `mua_chu_dong_volume / total_volume * 100`
- Sortable by column click
- Highlight rows where buy_ratio > 60% (strong buy) or < 40% (strong sell)

## Files Summary

| Action | File | Lines |
|--------|------|-------|
| Rewrite | `frontend/src/pages/volume-analysis-page.tsx` | ~45 |
| Create | `frontend/src/components/volume/volume-market-pie-chart.tsx` | ~50 |
| Create | `frontend/src/components/volume/volume-ratio-cards.tsx` | ~40 |
| Create | `frontend/src/components/volume/volume-stacked-bar-chart.tsx` | ~60 |
| Create | `frontend/src/components/volume/volume-detail-table.tsx` | ~70 |

## Todo

- [ ] Build pie chart (market-wide ratio)
- [ ] Build ratio KPI cards
- [ ] Build stacked bar chart (per-stock breakdown)
- [ ] Build sortable detail table
- [ ] Compose in `volume-analysis-page.tsx`
- [ ] Verify `npm run build` compiles

## Success Criteria

- Pie chart shows 3 slices with correct proportions
- Stacked bar chart renders all VN30 stocks sorted by volume
- Table is sortable; rows highlighted by buy ratio strength
- All VN color conventions applied (red=buy, green=sell, yellow=neutral)
- All components <200 lines

## Design Note

No separate API call needed. Volume data comes from `MarketSnapshot.quotes` which is already fetched by `useMarketSnapshot()`. This avoids redundant network calls (DRY).
