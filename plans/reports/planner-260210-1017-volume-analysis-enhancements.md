# Plan Report: Volume Analysis Enhancements

**Agent:** planner
**Plan ID:** 260210-1017-volume-analysis-enhancements
**Date:** 2026-02-10
**Status:** Complete

## Summary

Created comprehensive 5-phase implementation plan for enhancing VN Stock Tracker volume analysis page with session-phase tracking (ATO/Continuous/ATC), visual buy/sell pressure bars, and session comparison chart.

## Plan Structure

```
plans/260210-1017-volume-analysis-enhancements/
├── plan.md                           # Overview + phase summary
├── phase-01-backend-session-tracking.md   # 1h - SessionStats + SessionAggregator
├── phase-02-backend-api-extension.md      # 30m - /api/market/volume-stats
├── phase-03-frontend-pressure-bars.md     # 1h - Detail table enhancements
├── phase-04-frontend-session-chart.md     # 1h - New Recharts component
└── phase-05-integration-testing.md        # 30m - Testing + QA
```

## Key Decisions

1. **Session Detection:** Use `trading_session` from SSITradeMessage ("ATO", "ATC", or empty/continuous)
2. **Data Model:** Extend existing `SessionStats` with nested `SessionBreakdown` objects (KISS - no new aggregator)
3. **API Strategy:** Use existing `/api/market/volume-stats` endpoint (already exists but unused)
4. **Visual Design:** Horizontal pressure bars (red/green/yellow), proportional widths
5. **Chart Type:** Recharts grouped bar chart with 3 stacks per symbol

## Technical Approach

**Backend (Phases 01-02):**
- Add `SessionBreakdown` Pydantic model with buy/sell/neutral counters
- Extend `SessionStats` with `ato`/`continuous`/`atc` fields
- Update `SessionAggregator.add_trade()` to detect session from `trading_session` field
- Pydantic auto-serializes nested models - no API changes needed

**Frontend (Phases 03-04):**
- Add pressure bar column to `volume-detail-table.tsx` (inline flex div, no new component)
- Create `volume-session-comparison-chart.tsx` with Recharts BarChart
- Create `use-volume-stats.ts` hook polling `/api/market/volume-stats`
- Update types with `SessionBreakdown` interface

**Testing (Phase 05):**
- Backend: pytest unit tests for session detection logic
- Frontend: manual QA with live SSI stream
- Integration: verify real-time updates, responsive layout, performance

## Effort Estimate

- Phase 01: 1h (backend session tracking)
- Phase 02: 30m (API endpoint validation)
- Phase 03: 1h (pressure bars)
- Phase 04: 1h (session chart)
- Phase 05: 30m (testing)
- **Total: 4h**

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| `trading_session` field missing/inconsistent | Fallback to "continuous" if empty/unknown |
| Backward compatibility broken | Keep all existing fields, session breakdowns additive |
| Performance overhead | Minimal - just 3 counters per symbol |
| Chart cluttered with 30 stocks | Start with all, add filtering if needed |

## File Impact

**Backend (3 files):**
- `backend/app/models/domain.py` - Add SessionBreakdown, extend SessionStats
- `backend/app/services/session_aggregator.py` - Session detection logic
- `backend/app/services/trade_classifier.py` - Pass trading_session field

**Frontend (5 files):**
- `frontend/src/types/index.ts` - Add SessionBreakdown interface
- `frontend/src/hooks/use-volume-stats.ts` - New hook (20 LOC)
- `frontend/src/components/volume/volume-detail-table.tsx` - Add pressure bar column
- `frontend/src/components/volume/volume-session-comparison-chart.tsx` - New chart (~120 LOC)
- `frontend/src/pages/volume-analysis-page.tsx` - Wire new chart

**Tests (2 files):**
- `backend/tests/test_session_aggregator_sessions.py` - New
- `backend/tests/test_market_router_sessions.py` - New

## Dependencies

- SSI FastConnect provides `trading_session` field in trade messages
- VN market sessions: ATO 9:00-9:15, Continuous 9:15-14:30, ATC 14:30-14:45
- Existing `SessionAggregator` reset at 15:00 daily (Phase 2 lifespan)
- Recharts library already in use for other volume charts

## YAGNI/KISS/DRY Compliance

✅ **YAGNI:**
- No session filtering dropdown (defer to future)
- No logarithmic scale (test with real data first)
- No separate pressure bar component (inline logic sufficient)

✅ **KISS:**
- Reuse existing `/api/market/volume-stats` endpoint
- Extend existing `SessionStats` model (no new aggregator)
- Inline pressure bar rendering (no new component)

✅ **DRY:**
- Reuse polling pattern from `use-market-snapshot.ts`
- Reuse chart styling from `volume-stacked-bar-chart.tsx`
- Pydantic auto-serialization (no manual JSON mapping)

## Success Criteria

- [ ] `SessionStats` includes ATO/Continuous/ATC breakdown
- [ ] `/api/market/volume-stats` returns session data
- [ ] Detail table shows buy/sell pressure bars
- [ ] Session comparison chart displays 3 groups per symbol
- [ ] Real-time updates every 5s
- [ ] All tests pass
- [ ] API response time <50ms
- [ ] No visual regressions

## Next Steps

1. Delegate to `researcher` agents for technical deep-dive (optional - plan is detailed)
2. Update active plan context: `node ~/.claude/scripts/set-active-plan.cjs plans/260210-1017-volume-analysis-enhancements`
3. Begin Phase 01: Backend session tracking implementation
4. Follow sequential execution (01 → 02 → 03 → 04 → 05)

## Unresolved Questions

None. Plan is comprehensive and ready for implementation.
