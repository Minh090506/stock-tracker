# Phase 4: Frontend — Basis Trend Area Chart

## Priority: P2 | Status: pending | Effort: 40min

## Overview

Build a Recharts `AreaChart` showing basis_pct over time. Area colored by premium (red) vs discount (green). Zero line reference. Tooltip with details.

## Context Links

- [foreign-top-movers-bar-chart.tsx](../../frontend/src/components/foreign/foreign-top-movers-bar-chart.tsx) — Recharts pattern, tooltip styling
- [Recharts AreaChart docs](https://recharts.org/en-US/api/AreaChart)
- [BasisPoint type](../../frontend/src/types/index.ts)

## Key Insights

- `BasisPoint[]` from `useBasisTrend()` has `timestamp`, `basis_pct`, `basis`, `futures_price`, `spot_value`
- Recharts `AreaChart` with `ReferenceLine` at y=0 gives clear premium/discount visualization
- For dual-color fill: use two `<Area>` elements — one for positive values (premium/red), one for negative (discount/green), or use a gradient with `linearGradient`
- Simpler approach: single Area with `linearGradient` that transitions at y=0, or just use a single color based on the latest value. **Decision**: Use single Area with conditional fill color based on whether most recent point is premium/discount. Keep it simple (KISS).

## Requirements

- X-axis: time (HH:mm format)
- Y-axis: basis_pct (%)
- Area fill: red-tinted when latest is premium, green-tinted when discount
- ReferenceLine at y=0 (dashed, gray)
- Tooltip showing: time, basis (points), basis_pct (%), futures price, spot value
- Responsive container matching card styling
- Title: "Basis Trend (30min)"

## Architecture

```
BasisPoint[] -> transform to chart data -> Recharts AreaChart
  {time: "HH:mm", basis_pct: number, basis: number, ...}
```

## Related Code Files

| Action | File |
|--------|------|
| CREATE | `frontend/src/components/derivatives/basis-trend-area-chart.tsx` |
| MODIFY | `frontend/src/pages/derivatives-page.tsx` — wire in chart |

## Implementation Steps

1. Create `basis-trend-area-chart.tsx`:
   - Props: `{ data: BasisPoint[] }`
   - Transform data: parse `timestamp` to `HH:mm` string for X-axis
   - Use `ResponsiveContainer` (width 100%, height 300)
   - `AreaChart` with `CartesianGrid`, `XAxis`, `YAxis`, `Tooltip`, `Area`, `ReferenceLine`
   - Area config:
     - `dataKey="basis_pct"`
     - `stroke` and `fill`: red (`#ef4444` / `rgba(239,68,68,0.15)`) if latest is premium, green (`#22c55e` / `rgba(34,197,94,0.15)`) if discount
   - `ReferenceLine y={0}` with `stroke="#6b7280"` dashed
   - Tooltip: custom formatter showing basis points, pct, futures price, spot
   - Dark theme tooltip: `backgroundColor: "#1f2937"`, `border: "1px solid #374151"`

2. Update `derivatives-page.tsx` to render `BasisTrendAreaChart` with `basisTrend` data

## Todo

- [ ] Create `basis-trend-area-chart.tsx`
- [ ] Wire into derivatives page
- [ ] Verify chart renders with mock/real data
- [ ] Verify tooltip displays correct information

## Success Criteria

- Chart renders with time on X-axis, basis_pct on Y-axis
- Zero reference line visible
- Area colored by premium/discount
- Tooltip shows all relevant data points
- Responsive, fills container width
- Empty state (no data) handled gracefully

## Risk Assessment

- **Low**: Recharts AreaChart is well-tested pattern in this codebase (BarChart already used)
- If basis_pct values are very small, Y-axis domain may need explicit min/max. Add `domain={['auto', 'auto']}` to let Recharts handle it.
