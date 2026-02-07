# Planner Report: Analysis Dashboard Pages

**Date**: 2026-02-07
**Plan**: `plans/260207-1609-analysis-dashboard-pages/`

## Summary

Created 7-phase implementation plan for adding 3 analysis dashboard pages (Foreign Flow, Volume Analysis, Signals) to the VN Stock Tracker frontend.

## Key Findings from Codebase Research

1. **Backend ready**: `MarketDataProcessor.get_market_snapshot()` exists but not exposed via REST. `ForeignInvestorTracker.get_all()` and `SessionAggregator.get_all_stats()` provide all needed data.
2. **Frontend bare**: Only `App.tsx` placeholder, empty dirs. No routing, no chart lib (except lightweight-charts for candlestick).
3. **Vite proxy configured**: `/api` -> `localhost:8000` already in `vite.config.ts`.
4. **232 backend tests passing** -- new endpoints must not break existing.

## Plan Structure

| Phase | What | Effort |
|-------|------|--------|
| 1 | Backend: 3 REST endpoints (`/api/market/snapshot`, `/foreign-detail`, `/volume-stats`) | 1h |
| 2 | Frontend: Install react-router-dom + recharts, setup routing + layout + types | 1h |
| 3 | Frontend: `usePolling`, `useMarketSnapshot`, `useForeignFlow` hooks | 45m |
| 4 | Foreign Flow page: heatmap, bar chart, summary cards, detail table | 1h |
| 5 | Volume Analysis page: pie chart, stacked bar, ratio cards, table | 1h |
| 6 | Signals page: mock feed with filter chips (real data deferred to analytics engine) | 45m |
| 7 | Backend tests + frontend build verification + code review | 30m |

**Total estimated effort**: ~6h

## File Count

- **Backend**: 2 files (1 new router + 1 modify main.py) + 1 test file
- **Frontend**: ~22 new/modified files across pages, components, hooks, utils, types

## Architectural Decisions

- **REST polling** (5s) instead of WebSocket -- WebSocket API is Phase 4 (not built yet). Hooks designed so internal swap to WS is seamless.
- **Recharts** over D3/Nivo -- declarative React components, supports all needed chart types, <200KB.
- **Volume page reuses `useMarketSnapshot()`** instead of separate API call -- avoids redundant fetch (DRY).
- **Signals page uses mock data** -- no analytics engine yet. Structured for easy swap to real API.
- **Lazy import** in `market_router.py` to avoid circular import with `main.py` (same pattern as existing `history_router.py`).

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Circular import in market_router | Blocks backend | Lazy import inside function body |
| Recharts bundle size | +200KB | Tree-shakeable; only import used charts |
| Empty data on dev (no SSI stream) | Bad DX | Hooks handle null gracefully; consider mock data flag |
