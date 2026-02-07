---
title: "Analysis Dashboard Pages (Foreign Flow, Volume, Signals)"
description: "Add 3 analysis pages with routing, charts, and REST polling to the React frontend"
status: in-progress
priority: P1
effort: 6h
branch: master
tags: [frontend, dashboard, recharts, react-router, rest-api]
created: 2026-02-07
reviewed: 2026-02-07
---

# Analysis Dashboard Pages

## Phases

| # | Phase | Effort | Status |
|---|-------|--------|--------|
| 1 | Backend: Market Snapshot REST API | 1h | complete |
| 2 | Frontend: Dependencies + Routing + Types | 1h | complete |
| 3 | Frontend: Data Hooks + API Client | 45m | complete |
| 4 | Frontend: Foreign Flow Page | 1h | complete |
| 5 | Frontend: Volume Analysis Page | 1h | complete |
| 6 | Frontend: Signals Page | 45m | complete |
| 7 | Testing + Review | 30m | in-progress |

## Key Decisions

- **Recharts** over D3/Nivo -- React-native, supports bar/pie/line/treemap, <200KB gzip
- **React Router v7** -- standard, BrowserRouter
- **REST polling** (5s interval) until Phase 4 WebSocket lands -- KISS
- **Mock fallback** -- hooks return mock data when backend is offline (dev convenience)
- VN colors: red=up/buy, green=down/sell, fuchsia=ceiling, cyan=floor

## Architecture

```
Frontend Data Flow:
  usePolling(url, 5000)     -- generic fetch+interval hook
    -> useMarketSnapshot()  -- /api/market/snapshot
    -> useForeignFlow()     -- derives from snapshot.foreign + snapshot.quotes
    -> useVolumeAnalysis()  -- derives from snapshot.quotes (SessionStats)

Routing:
  /               -> Dashboard (overview, deferred)
  /foreign-flow   -> ForeignFlowPage
  /volume         -> VolumeAnalysisPage
  /signals        -> SignalsPage
```

## Phase Details

- [Phase 1: Backend REST API](./phase-01-backend-rest-api.md) - ✅ Complete
- [Phase 2: Frontend Setup](./phase-02-frontend-setup.md) - ✅ Complete
- [Phase 3: Data Hooks](./phase-03-data-hooks.md) - ✅ Complete
- [Phase 4: Foreign Flow Page](./phase-04-foreign-flow-page.md) - ✅ Complete
- [Phase 5: Volume Analysis Page](./phase-05-volume-analysis-page.md) - ✅ Complete
- [Phase 6: Signals Page](./phase-06-signals-page.md) - ✅ Complete
- [Phase 7: Testing + Review](./phase-07-testing-review.md) - ⚠️ In Progress

## Review Summary

**Review Date**: 2026-02-07 17:09
**Status**: APPROVED WITH MINOR FIXES
**Report**: [code-reviewer-260207-1709-analysis-dashboard-pages.md](/Users/minh/Projects/stock-tracker/plans/reports/code-reviewer-260207-1709-analysis-dashboard-pages.md)

**Verdict**: Excellent implementation quality. Code is production-ready.

**Key Achievements**:
- ✅ TypeScript: 0 errors
- ✅ Production build: 828ms, proper code splitting
- ✅ All 26 files under 200 lines (largest: 119)
- ✅ No security vulnerabilities
- ✅ VN market colors applied correctly
- ✅ Clean React patterns with proper error handling

**Pending Tasks**:
- ❌ Backend endpoint tests (`test_market_router.py` not created)
- ⏳ Address review findings (see report for details)

**Next Actions**:
1. Create backend tests for 3 market router endpoints
2. Run pytest and verify all pass
3. Optionally: Add exponential backoff to polling hook
4. Commit implementation
