# Phase 3: Frontend — Derivatives Summary Cards

## Priority: P2 | Status: pending | Effort: 30min

## Overview

Build the summary cards row showing contract symbol, last price, change, basis value, basis%, and premium/discount indicator. Follows `ForeignFlowSummaryCards` pattern.

## Context Links

- [foreign-flow-summary-cards.tsx](../../frontend/src/components/foreign/foreign-flow-summary-cards.tsx) — pattern to follow
- [format-number.ts](../../frontend/src/utils/format-number.ts) — `formatPercent`, `formatVolume`
- [types/index.ts](../../frontend/src/types/index.ts) — `DerivativesData` interface

## Key Insights

- `DerivativesData` already has all needed fields: `symbol`, `last_price`, `change`, `change_pct`, `volume`, `basis`, `basis_pct`, `is_premium`
- VN market colors: red = up/premium (basis > 0), green = down/discount (basis < 0)
- `basis_pct` is already computed as `basis / spot_value * 100`

## Requirements

4 summary cards in a responsive grid:

| Card | Primary Value | Secondary |
|------|--------------|-----------|
| Contract | symbol (e.g. VN30F2603) | -- |
| Price | last_price + change/change_pct | colored by change direction |
| Basis | basis value (points) | basis_pct% |
| Status | "PREMIUM" or "DISCOUNT" | basis_pct colored |

## Related Code Files

| Action | File |
|--------|------|
| CREATE | `frontend/src/components/derivatives/derivatives-summary-cards.tsx` |

## Implementation Steps

1. Create `frontend/src/components/derivatives/` directory
2. Create `derivatives-summary-cards.tsx`:
   - Props: `{ derivatives: DerivativesData }`
   - 4-col grid (`grid-cols-2 md:grid-cols-4`)
   - Card 1: Contract symbol + volume
   - Card 2: Last price + change (red if positive, green if negative)
   - Card 3: Basis points + basis_pct
   - Card 4: Premium/Discount badge with color
   - Use `bg-gray-900 border border-gray-800 rounded-lg p-4` card styling
3. Update `derivatives-page.tsx` to render `DerivativesSummaryCards` instead of placeholder

## Todo

- [ ] Create `derivatives-summary-cards.tsx`
- [ ] Wire into derivatives page
- [ ] Verify cards render with correct colors

## Success Criteria

- 4 cards displayed in responsive grid
- Price change colored correctly (red up, green down)
- Basis colored correctly (red premium, green discount)
- Volume formatted with K/M suffix

## Risk Assessment

- **None** — straightforward UI component, all data already available
