---
title: "Derivatives Basis Analysis Panel"
description: "Add /derivatives page with basis trend chart, summary cards, and convergence indicator"
status: complete
priority: P2
effort: 3h
branch: master
tags: [frontend, backend, derivatives, recharts]
created: 2026-02-09
---

# Derivatives Basis Analysis Panel

## Goal

Expose the existing `DerivativesTracker.get_basis_trend()` via REST and build a `/derivatives` page with summary cards, basis chart, and convergence indicator.

## What Already Exists

- **Backend**: `DerivativesTracker` with `get_data()`, `get_basis_trend()`, `get_current_basis()` -- fully implemented
- **Backend**: `GET /api/market/snapshot` returns `MarketSnapshot.derivatives: DerivativesData`
- **Backend**: `GET /api/history/derivatives/{contract}` returns DB history (price, basis, open_interest)
- **Frontend**: `DerivativesData` type defined in `types/index.ts`
- **Frontend**: `useWebSocket("market")` returns `MarketSnapshot` including derivatives
- **Frontend**: Recharts used throughout (BarChart, PieChart), consistent dark theme

## What Needs to Be Built

| Phase | Scope | Effort |
|-------|-------|--------|
| [Phase 1](./phase-01-backend-basis-trend-endpoint.md) | Backend: `GET /api/market/basis-trend` endpoint | 20min |
| [Phase 2](./phase-02-frontend-types-hooks-page-skeleton.md) | Frontend: types, hooks, page structure, skeleton, nav item | 40min |
| [Phase 3](./phase-03-frontend-derivatives-summary-cards.md) | Frontend: derivatives summary cards component | 30min |
| [Phase 4](./phase-04-frontend-basis-trend-area-chart.md) | Frontend: basis trend AreaChart (Recharts) | 40min |
| [Phase 5](./phase-05-frontend-convergence-open-interest.md) | Frontend: convergence indicator + open interest display | 30min |

## Architecture

```
DerivativesTracker (in-memory)
  |
  +-- GET /api/market/snapshot      -> DerivativesData (real-time via WS "market" channel)
  +-- GET /api/market/basis-trend   -> BasisPoint[] (NEW - REST only, polled every 10s)
  +-- GET /api/history/derivatives  -> DB history (existing)
  |
  v
/derivatives page
  +-- DerivativesSummaryCards   <- DerivativesData from useMarketSnapshot()
  +-- BasisTrendAreaChart       <- BasisPoint[] from useBasisTrend() polling
  +-- ConvergenceIndicator      <- computed from BasisPoint[] trend
  +-- OpenInterestDisplay       <- DB history endpoint (stretch)
```

## Data Flow

1. **Real-time summary**: `useMarketSnapshot()` (existing) -> extract `snapshot.derivatives`
2. **Basis trend chart**: New `useBasisTrend()` hook -> polls `GET /api/market/basis-trend?minutes=30` every 10s
3. **Convergence**: Computed client-side from basis trend array (slope of last N points)
4. **Open interest**: `apiFetch("/history/derivatives/{contract}")` on mount (existing endpoint)

## Key Decisions

- Use Recharts `AreaChart` (not lightweight-charts) for consistency with existing pages
- Poll basis-trend at 10s interval (not WS) -- trend data is low-frequency, no need for WS channel
- Convergence is client-computed from trend slope, not a backend metric
- VN market colors: red for premium (basis > 0), green for discount (basis < 0)

## File Inventory

### Backend (2 files modified)
- `backend/app/routers/market_router.py` -- add `/basis-trend` endpoint
- (no new files needed)

### Frontend (8 new files, 3 modified)
| File | Type |
|------|------|
| `frontend/src/types/index.ts` | MODIFY: add `BasisPoint` type |
| `frontend/src/hooks/use-basis-trend.ts` | NEW: polling hook for basis-trend |
| `frontend/src/hooks/use-derivatives-data.ts` | NEW: combines snapshot + trend |
| `frontend/src/pages/derivatives-page.tsx` | NEW: page component |
| `frontend/src/components/derivatives/derivatives-summary-cards.tsx` | NEW |
| `frontend/src/components/derivatives/basis-trend-area-chart.tsx` | NEW |
| `frontend/src/components/derivatives/convergence-indicator.tsx` | NEW |
| `frontend/src/components/derivatives/open-interest-display.tsx` | NEW |
| `frontend/src/components/ui/derivatives-skeleton.tsx` | NEW: loading skeleton |
| `frontend/src/components/layout/app-sidebar-navigation.tsx` | MODIFY: add nav item |
| `frontend/src/App.tsx` | MODIFY: add route + lazy import |

## Risk Assessment

- **Low risk**: Backend change is trivial (1 endpoint, no new dependencies)
- **Low risk**: Frontend follows established patterns exactly
- **Medium risk**: Open interest data may always be 0 (noted in project memory). Display "N/A" gracefully.

## Success Criteria

- [x] `GET /api/market/basis-trend?minutes=30` returns `BasisPoint[]`
- [x] `/derivatives` page renders summary cards with real-time data
- [x] Basis trend chart shows premium/discount areas with VN market colors
- [x] Convergence indicator shows basis direction
- [x] Navigation sidebar includes "Derivatives" link
- [x] All components < 200 lines, dark theme consistent
