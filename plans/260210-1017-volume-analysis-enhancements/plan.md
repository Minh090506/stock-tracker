---
title: "Volume Analysis Enhancements"
description: "Add session-phase tracking, pressure bars, and session comparison chart"
status: complete
priority: P2
effort: 4h
branch: master
tags: [volume-analysis, frontend, backend, charts]
created: 2026-02-10
---

# Volume Analysis Enhancements

## Overview

Enhance volume analysis page with session-phase volume tracking (ATO/Continuous/ATC), visual buy/sell pressure bars in detail table, and session comparison chart.

## Context

**Existing:**
- `SessionAggregator` tracks buy/sell/neutral volumes per symbol (session totals only)
- `TradeClassifier` has access to `trading_session` field ("ATO", "ATC", or continuous)
- Frontend has 4 working components: pie chart, summary cards, stacked bar chart, detail table
- `/api/market/snapshot` used for polling, `/api/market/volume-stats` exists but unused

**Requirements:**
1. Backend: Track volumes per session phase (ATO/Continuous/ATC)
2. Backend: Extend API to expose session breakdown
3. Frontend: Add buy/sell pressure bars to detail table
4. Frontend: New session comparison chart
5. Frontend: Wire up session data fetching

## Phases

| Phase | Description | Status | Effort |
|-------|-------------|--------|--------|
| [01](phase-01-backend-session-tracking.md) | Extend SessionStats model + SessionAggregator for session-phase tracking | Complete | 1h |
| [02](phase-02-backend-api-extension.md) | Update /api/market/volume-stats to return session breakdown | Complete | 30m |
| [03](phase-03-frontend-pressure-bars.md) | Add horizontal pressure bars to volume detail table | Complete | 1h |
| [04](phase-04-frontend-session-chart.md) | Create session comparison chart component | Complete | 1h |
| [05](phase-05-integration-testing.md) | Integration testing + visual QA | Complete | 30m |

## Key Decisions

1. **Session detection:** Use `trading_session` from `SSITradeMessage` ("ATO", "ATC", or empty/continuous)
2. **Storage approach:** Extend existing `SessionStats` model with nested session breakdown (KISS - no new aggregator)
3. **API strategy:** Use existing `/api/market/volume-stats` endpoint (already exists but unused)
4. **Visual design:** Red/green horizontal bars (VN market colors), proportional widths
5. **Chart type:** Recharts bar chart with 3 groups (ATO/Continuous/ATC)

## Dependencies

- SSI trade stream provides `trading_session` field
- VN market sessions: ATO 9:00-9:15, Continuous 9:15-14:30, ATC 14:30-14:45
- Existing `SessionAggregator` reset at 15:00 daily (Phase 2 lifespan)

## Success Criteria

- [x] `SessionStats` model includes session-phase breakdown
- [x] `/api/market/volume-stats` returns session data
- [x] Detail table shows buy/sell pressure bars per row
- [x] New session comparison chart displays ATO/Continuous/ATC breakdown
- [x] All components update in real-time with 5s polling
- [x] No performance regression (files under 200 LOC)

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Session field missing/inconsistent | Medium | Fallback to "continuous" if empty/unknown |
| Performance overhead from session tracking | Low | Minimal - just 3 counters per symbol |
| Chart layout on small screens | Low | Use responsive grid, horizontal scroll if needed |

## Next Steps

1. Read phase-01 to start backend session tracking implementation
2. Update tests for new SessionStats fields
3. Proceed sequentially through phases 02-05
