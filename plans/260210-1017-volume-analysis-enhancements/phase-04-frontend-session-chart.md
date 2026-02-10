# Phase 04: Frontend Session Chart

## Priority: P2
## Status: Pending
## Effort: 1h

## Context Links
- `frontend/src/pages/volume-analysis-page.tsx` - Page layout
- `frontend/src/components/volume/` - Existing chart components
- `frontend/src/hooks/use-market-snapshot.ts` - Polling pattern
- Phase 02: /api/market/volume-stats endpoint with session data

## Overview

Create new chart component showing ATO vs Continuous vs ATC session volume comparison. Use Recharts bar chart with grouped bars per stock, showing buy/sell breakdown per session.

## Key Insights

- VN sessions: ATO (9:00-9:15), Continuous (9:15-14:30), ATC (14:30-14:45)
- ATO/ATC are auction sessions (low volume), Continuous is main trading
- Chart shows which sessions have most buy vs sell pressure
- Reuse existing chart styling patterns from volume-stacked-bar-chart.tsx

## Requirements

**Functional:**
- Bar chart: X-axis = symbols, Y-axis = volume
- 3 groups per symbol: ATO, Continuous, ATC bars
- Each bar stacked: buy (red), sell (green), neutral (yellow)
- Legend: Session names + buy/sell/neutral colors
- Responsive: horizontal scroll if too many symbols

**Non-functional:**
- Recharts library (consistent with existing charts)
- TailwindCSS v4 styling
- Real-time updates (5s polling)
- File under 150 LOC

## Architecture

```
VolumeAnalysisPage
    ↓ (new hook)
useVolumeStats() → polls /api/market/volume-stats
    ↓
VolumeSessionComparisonChart component
    ↓
Recharts BarChart:
    - Data: [{symbol, ato_buy, ato_sell, cont_buy, ...}, ...]
    - 3 Bar groups (ATO, Continuous, ATC)
    - Each Bar stacked (buy/sell/neutral)
```

## Related Code Files

**To Create:**
- `frontend/src/components/volume/volume-session-comparison-chart.tsx` - New chart
- `frontend/src/hooks/use-volume-stats.ts` - New hook for /api/market/volume-stats

**To Modify:**
- `frontend/src/pages/volume-analysis-page.tsx` - Add chart to layout
- `frontend/src/types/index.ts` - Add SessionBreakdown interface

**Reference:**
- `frontend/src/components/volume/volume-stacked-bar-chart.tsx` - Styling pattern

## Implementation Steps

1. **Add SessionBreakdown type** to types/index.ts:
   ```typescript
   export interface SessionBreakdown {
     mua_chu_dong_volume: number;
     ban_chu_dong_volume: number;
     neutral_volume: number;
     total_volume: number;
   }

   export interface SessionStats {
     // ... existing fields ...
     ato: SessionBreakdown;
     continuous: SessionBreakdown;
     atc: SessionBreakdown;
   }
   ```

2. **Create use-volume-stats.ts hook**:
   ```typescript
   export function useVolumeStats(intervalMs = 5000) {
     return usePolling(
       () => apiFetch<VolumeStatsResponse>("/market/volume-stats"),
       intervalMs,
     );
   }
   ```

3. **Create volume-session-comparison-chart.tsx**:
   - Props: `stats: SessionStats[]`
   - Transform data for Recharts:
     ```typescript
     const chartData = stats.map(s => ({
       symbol: s.symbol,
       ato_buy: s.ato.mua_chu_dong_volume,
       ato_sell: s.ato.ban_chu_dong_volume,
       cont_buy: s.continuous.mua_chu_dong_volume,
       cont_sell: s.continuous.ban_chu_dong_volume,
       atc_buy: s.atc.mua_chu_dong_volume,
       atc_sell: s.atc.ban_chu_dong_volume,
     }));
     ```
   - Use BarChart with 6 Bar elements (3 sessions × 2 types)
   - Stack bars: `stackId="session"`

4. **Wire chart to page**:
   ```tsx
   // In volume-analysis-page.tsx
   const { data: volumeStats } = useVolumeStats();

   // Add after VolumeStackedBarChart
   <VolumeSessionComparisonChart stats={volumeStats?.stats || []} />
   ```

5. **Style with dark theme** matching existing charts:
   - Background: bg-gray-900
   - Border: border-gray-800
   - Text: text-gray-200
   - Grid: stroke-gray-700

## Todo List

- [ ] Add SessionBreakdown interface to types/index.ts
- [ ] Update SessionStats interface with session fields
- [ ] Create use-volume-stats.ts hook
- [ ] Create volume-session-comparison-chart.tsx component
- [ ] Transform SessionStats to Recharts data format
- [ ] Configure BarChart with 3 grouped stacks
- [ ] Add legend (ATO/Continuous/ATC + buy/sell colors)
- [ ] Add chart to volume-analysis-page.tsx
- [ ] Test with live data (verify session breakdown)

## Success Criteria

- Chart displays 3 bar groups per symbol (ATO/Continuous/ATC)
- Each bar stacked by buy (red) / sell (green) / neutral (yellow)
- Continuous session bars tallest (main trading session)
- Legend clearly identifies sessions and trade types
- Chart updates every 5 seconds with new data
- Responsive layout (horizontal scroll if needed)
- Matches dark theme of existing charts

## Risk Assessment

**Risks:**
- Too many bars, chart cluttered → Limit to top 10 stocks by volume
- ATO/ATC volumes too small to see → Use logarithmic scale or separate chart
- Data loading delay causes chart flicker → Show skeleton loader

**Mitigation:**
- Start with all 30 VN30 stocks, add filtering if cluttered
- Test with real data to see if ATO/ATC visible
- Reuse VolumeAnalysisSkeleton for loading state

## Security Considerations

- None (client-side chart rendering)

## Next Steps

After completion:
- Phase 05: Integration testing across all components
- Verify real-time updates work correctly
- Check mobile responsiveness
