# Phase 05: Integration Testing

## Priority: P2
## Status: Pending
## Effort: 30m

## Context Links
- All previous phases (01-04)
- `backend/tests/` - Test suite
- `frontend/src/` - Components to test

## Overview

Integration testing across backend session tracking, API endpoints, frontend components. Verify real-time updates, data consistency, visual correctness, and performance.

## Key Insights

- Backend changes are non-breaking (additive only)
- Frontend adds new components without modifying existing
- Main risk: session detection logic accuracy
- Need to test with real SSI stream data

## Requirements

**Functional Tests:**
- SessionAggregator correctly distributes volumes to ATO/Continuous/ATC
- /api/market/volume-stats returns complete session breakdown
- Pressure bars accurately reflect buy/sell ratios
- Session chart displays 3 groups per symbol
- Real-time polling updates all components

**Non-functional Tests:**
- API response time under 50ms
- Frontend re-renders smooth (no flicker)
- Charts responsive on mobile/tablet/desktop
- No console errors or warnings

## Test Scenarios

### Backend Tests

1. **SessionAggregator session detection:**
   ```python
   def test_ato_session_aggregation():
       # Given: Trade with trading_session="ATO"
       # When: add_trade() called
       # Then: stats.ato.total_volume incremented

   def test_continuous_session_fallback():
       # Given: Trade with trading_session="" (empty)
       # When: add_trade() called
       # Then: stats.continuous.total_volume incremented

   def test_session_reset():
       # Given: Stats with ATO/Continuous/ATC data
       # When: reset() called
       # Then: All session breakdowns cleared
   ```

2. **API endpoint validation:**
   ```python
   def test_volume_stats_includes_sessions():
       # Given: Aggregator has session data
       # When: GET /api/market/volume-stats
       # Then: Response includes ato/continuous/atc fields
   ```

### Frontend Tests

3. **Pressure bar rendering:**
   - Test with 50/50 buy/sell ratio → equal bar widths
   - Test with 80/20 buy/sell → red bar 4x wider than green
   - Test with 0 neutral volume → no yellow bar
   - Test tooltip shows correct percentages

4. **Session chart data:**
   - Mock /api/market/volume-stats response
   - Verify 3 bar groups render (ATO/Continuous/ATC)
   - Check stacking: buy (bottom) + sell (middle) + neutral (top)
   - Verify legend items present

5. **Real-time updates:**
   - Start backend with SSI stream
   - Open volume analysis page
   - Watch for 30 seconds
   - Verify: table updates, chart animates, pressure bars change

### Visual QA

6. **Cross-browser testing:**
   - Chrome, Firefox, Safari
   - Check table layout not broken
   - Verify chart renders correctly
   - Test hover tooltips work

7. **Responsive design:**
   - Desktop (1920×1080): full layout
   - Tablet (768×1024): grid collapses
   - Mobile (375×667): horizontal scroll or stacked

8. **Dark theme consistency:**
   - Pressure bars contrast with table background
   - Chart colors match existing components
   - Text readable on dark gray

## Related Code Files

**Test Files to Create:**
- `backend/tests/test_session_aggregator_sessions.py` - Session tracking tests
- `backend/tests/test_market_router_sessions.py` - API endpoint tests

**Manual Testing:**
- Volume analysis page with live data
- Browser dev tools (network tab, console)

## Implementation Steps

1. **Write backend unit tests:**
   ```bash
   cd backend
   ./venv/bin/pytest tests/test_session_aggregator_sessions.py -v
   ```

2. **Write API integration tests:**
   ```bash
   ./venv/bin/pytest tests/test_market_router_sessions.py -v
   ```

3. **Start dev servers:**
   ```bash
   # Terminal 1: Backend
   cd backend && ./venv/bin/uvicorn app.main:app --reload

   # Terminal 2: Frontend
   cd frontend && npm run dev
   ```

4. **Manual testing checklist:**
   - [ ] Open http://localhost:5173/volume-analysis
   - [ ] Verify pressure bars visible in table
   - [ ] Check session chart displays 3 groups
   - [ ] Wait 5 seconds, confirm data updates
   - [ ] Test sorting columns (pressure bar column)
   - [ ] Hover tooltips on pressure bars
   - [ ] Resize browser window (responsive)
   - [ ] Check browser console (no errors)

5. **Performance testing:**
   ```bash
   # Backend response time
   curl -w "\nTime: %{time_total}s\n" http://localhost:8000/api/market/volume-stats

   # Frontend bundle size (should not increase >50KB)
   cd frontend && npm run build
   ls -lh dist/assets/*.js
   ```

6. **Fix any issues found:**
   - Backend: adjust session detection logic
   - Frontend: fix layout/styling bugs
   - Re-run tests until all pass

## Todo List

- [ ] Write SessionAggregator session unit tests
- [ ] Write /api/market/volume-stats API test
- [ ] Run backend test suite (all tests pass)
- [ ] Start dev servers (backend + frontend)
- [ ] Manual testing: pressure bars in table
- [ ] Manual testing: session comparison chart
- [ ] Manual testing: real-time updates (30s watch)
- [ ] Test responsive layout (3 screen sizes)
- [ ] Check browser console (no errors/warnings)
- [ ] Performance check: API response time <50ms
- [ ] Performance check: frontend bundle size delta

## Success Criteria

- All backend unit tests pass
- API integration tests pass
- Pressure bars render correctly with accurate widths
- Session chart displays 3 groups per symbol
- Real-time polling updates components every 5s
- No console errors or warnings
- API response time under 50ms
- No visual regressions in existing components
- Responsive on mobile/tablet/desktop
- Dark theme colors consistent

## Risk Assessment

**Risks:**
- Session detection logic wrong → ATO/ATC trades in wrong bucket
- Frontend types misaligned → TypeScript errors or undefined fields
- Performance regression → Slower API or frontend lag

**Mitigation:**
- Use real SSI stream data for testing (not mocks)
- Validate JSON schema between backend/frontend
- Profile with browser dev tools (React DevTools)

## Security Considerations

- No security implications (feature additions only)
- No new attack vectors introduced

## Next Steps

After completion:
- Update project roadmap (Phase 7 volume enhancements complete)
- Document new API fields in API docs
- Create user guide for new volume features (optional)

## Unresolved Questions

- Should we add session filter dropdown (ATO/Continuous/ATC only view)? → YAGNI, defer to future
- Logarithmic scale for session chart if ATO/ATC too small? → Test with real data first
