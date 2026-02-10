# Phase 03: Frontend Pressure Bars

## Priority: P2
## Status: Pending
## Effort: 1h

## Context Links
- `frontend/src/components/volume/volume-detail-table.tsx` - Table to enhance
- `frontend/src/types/index.ts` - Add SessionBreakdown type
- Phase 02 output: /api/market/volume-stats with session data

## Overview

Add visual buy/sell pressure bars to each row of volume detail table. Horizontal bars show buy (red) vs sell (green) ratio, proportional widths based on volume percentages.

## Key Insights

- Current table has 8 columns, already shows buy/sell volumes as text
- Pressure bars provide instant visual comparison (faster than reading numbers)
- VN market colors: red=buy/up, green=sell/down, yellow=neutral
- Use TailwindCSS v4 for styling (no external components needed)

## Requirements

**Functional:**
- Horizontal bar showing buy (left, red) vs sell (right, green) proportions
- Bar width proportional to volume ratio
- Tooltip/label showing exact percentages
- Responsive (collapse gracefully on mobile)

**Non-functional:**
- Smooth visual integration with existing table
- No performance impact (pure CSS/inline styles)
- Accessible (screen reader friendly with aria labels)

## Architecture

```
VolumeDetailTable component
    ↓ (map over stats)
Per-row layout:
    [Symbol] [Volumes...] [NEW: Pressure Bar] [Ratios]
         ↓
Pressure bar div:
    <div className="flex h-4 rounded overflow-hidden">
      <div style="width: {buyPct}%" className="bg-red-500" />
      <div style="width: {sellPct}%" className="bg-green-500" />
      <div style="width: {neutralPct}%" className="bg-yellow-500" />
    </div>
```

## Related Code Files

**To Modify:**
- `frontend/src/components/volume/volume-detail-table.tsx` - Add pressure bar cell

**To Create:**
- `frontend/src/components/volume/volume-pressure-bar.tsx` - Reusable bar component (optional, prefer inline)

**No New Files** (KISS - inline the bar logic in table)

## Implementation Steps

1. **Add pressure bar column** to table header:
   ```tsx
   <th className="px-4 py-3 text-center">Pressure</th>
   ```

2. **Calculate percentages** in table row map:
   ```tsx
   const buyPct = stat.total_volume > 0
     ? (stat.mua_chu_dong_volume / stat.total_volume) * 100
     : 0;
   const sellPct = stat.total_volume > 0
     ? (stat.ban_chu_dong_volume / stat.total_volume) * 100
     : 0;
   const neutralPct = 100 - buyPct - sellPct;
   ```

3. **Render pressure bar** in new table cell:
   ```tsx
   <td className="px-4 py-2">
     <div className="flex h-4 rounded overflow-hidden"
          title={`Buy: ${buyPct.toFixed(1)}% | Sell: ${sellPct.toFixed(1)}%`}>
       {buyPct > 0 && (
         <div style={{width: `${buyPct}%`}} className="bg-red-500" />
       )}
       {sellPct > 0 && (
         <div style={{width: `${sellPct}%`}} className="bg-green-500" />
       )}
       {neutralPct > 0 && (
         <div style={{width: `${neutralPct}%`}} className="bg-yellow-500" />
       )}
     </div>
   </td>
   ```

4. **Position column** between "Total" and "Buy Ratio" columns

5. **Add responsive behavior** (optional):
   - Hide on mobile: `className="hidden md:table-cell"`
   - Or shrink bar width on small screens

## Todo List

- [ ] Update SessionStats type with SessionBreakdown fields (types/index.ts)
- [ ] Add "Pressure" column header to table
- [ ] Calculate buy/sell/neutral percentages per row
- [ ] Render horizontal tri-color bar (red/green/yellow)
- [ ] Add title attribute for hover tooltip
- [ ] Test with various buy/sell ratios (50/50, 80/20, 20/80)
- [ ] Verify colors match VN market convention

## Success Criteria

- Pressure bar column visible in volume detail table
- Bar widths accurately reflect buy/sell/neutral ratios
- Red (buy) always on left, green (sell) in middle, yellow (neutral) on right
- Hover shows exact percentages
- No layout shift or column overflow
- Bar height ~16px (h-4 Tailwind class)

## Risk Assessment

**Risks:**
- Column too wide, breaks table layout → Use fixed width (e.g., 150px)
- Colors unclear on different monitors → Use high contrast shades
- Neutral volume often 0, bar looks incomplete → OK, yellow section only if neutral > 0

**Mitigation:**
- Test on multiple screen sizes (laptop, tablet, mobile)
- Use Tailwind color scale (red-500, green-500, yellow-500)
- Add subtle border to empty bars for visibility

## Security Considerations

- None (client-side rendering, no user input)

## Next Steps

After completion:
- Phase 04: Create session comparison chart
- Phase 04: Wire up /api/market/volume-stats endpoint
