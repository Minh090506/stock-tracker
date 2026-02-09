# Phase 5: Frontend — Convergence Indicator + Open Interest Display

## Priority: P3 | Status: pending | Effort: 30min

## Overview

Two bottom-row components: (1) convergence/divergence indicator computed from basis trend slope, (2) open interest display from DB history endpoint.

## Context Links

- [BasisPoint type](../../frontend/src/types/index.ts)
- [history_router.py](../../backend/app/routers/history_router.py) — `GET /api/history/derivatives/{contract}`
- [api-client.ts](../../frontend/src/utils/api-client.ts)

## Key Insights

- **Convergence**: basis trending toward 0 = convergence (futures price approaching spot). Compute as slope of `basis_pct` over last N points. Negative slope when premium = converging. Positive slope when discount = converging.
- **Open interest**: DB column exists but always 0 currently. Display gracefully with "N/A" or "0" with note.
- Both components are informational — no interactivity needed.

## Requirements

### Convergence Indicator
- Compute slope of basis_pct from last 10+ BasisPoints
- Display: "Converging" (basis moving toward 0) or "Diverging" (basis moving away from 0)
- Visual: arrow icon (down-toward-zero or up-away), colored indicator
- Show rate: e.g. "-0.02%/min"
- If insufficient data (< 5 points): show "Insufficient data"

### Open Interest Display
- Fetch from `GET /api/history/derivatives/{contract}?start=today&end=today`
- Show latest `open_interest` value
- If 0 or unavailable: show "N/A" with explanation text
- Card styling consistent with summary cards

## Architecture

```
Convergence:
  BasisPoint[] -> last 10 points -> linear regression slope -> converging/diverging

Open Interest:
  apiFetch("/history/derivatives/{contract}") -> latest open_interest value
```

## Related Code Files

| Action | File |
|--------|------|
| CREATE | `frontend/src/components/derivatives/convergence-indicator.tsx` |
| CREATE | `frontend/src/components/derivatives/open-interest-display.tsx` |
| MODIFY | `frontend/src/pages/derivatives-page.tsx` — wire in both |

## Implementation Steps

### 1. Create `convergence-indicator.tsx`

- Props: `{ basisTrend: BasisPoint[] }`
- Compute slope:
  ```typescript
  function computeSlope(points: BasisPoint[]): number | null {
    if (points.length < 5) return null;
    const recent = points.slice(-10);
    const first = recent[0].basis_pct;
    const last = recent[recent.length - 1].basis_pct;
    const minutes = (Date.parse(recent[recent.length-1].timestamp) - Date.parse(recent[0].timestamp)) / 60000;
    return minutes > 0 ? (last - first) / minutes : null;
  }
  ```
- Determine convergence:
  - If latest `is_premium` and slope < 0 -> converging
  - If latest `is_premium` and slope > 0 -> diverging
  - If latest discount and slope > 0 -> converging
  - If latest discount and slope < 0 -> diverging
  - Simplified: converging when `Math.abs(last) < Math.abs(first)` for recent points
- Render card with direction arrow and colored text

### 2. Create `open-interest-display.tsx`

- Props: `{ contract: string }` (e.g. "VN30F2603")
- Use `usePolling` to fetch `apiFetch("/history/derivatives/{contract}?start=today&end=today")` every 60s
- Extract latest `open_interest` from response array
- Render card: title "Open Interest", value or "N/A"
- Note: since OI is always 0 currently, show "Data not available from SSI" subtext when 0

### 3. Wire into derivatives page

- 2-col grid at bottom: `<ConvergenceIndicator>` + `<OpenInterestDisplay>`
- Pass `basisTrend` and `derivatives?.symbol` respectively

## Todo

- [ ] Create `convergence-indicator.tsx`
- [ ] Create `open-interest-display.tsx`
- [ ] Wire into derivatives page
- [ ] Handle edge cases (no data, 0 OI)

## Success Criteria

- Convergence shows "Converging"/"Diverging" with correct direction
- Rate of change displayed as %/min
- Insufficient data state handled
- Open interest shows value or graceful "N/A"
- Both cards match dark theme styling

## Risk Assessment

- **Medium**: Open interest always 0. Mitigated by graceful display.
- **Low**: Slope computation is simple linear approximation, sufficient for this use case.
