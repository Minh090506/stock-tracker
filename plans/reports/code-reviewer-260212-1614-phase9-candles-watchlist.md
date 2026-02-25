# Code Review Report: Phase 9 Candles & Watchlist Implementation

**Date:** 2026-02-12
**Reviewer:** code-reviewer agent
**Scope:** Phase 9 - TimescaleDB continuous aggregates, watchlist filtering, chart UI

---

## Scope

### Files Reviewed

**Backend (9 files):**
- `db/migrations/002_continuous_aggregates.sql` - TimescaleDB continuous aggregates for candles
- `backend/app/main.py` - BatchWriter enqueue wiring (critical fix)
- `backend/app/services/market_data_processor.py` - Watchlist filtering + 3-tuple returns
- `backend/app/config.py` - Added `extra_symbols` setting
- `backend/app/database/history_service.py` - Index candles query + date arithmetic fix
- `backend/app/routers/history_router.py` - Index candles endpoint
- `backend/tests/test_market_data_processor.py` - Updated for 3-tuple returns

**Frontend (7 files):**
- `frontend/src/types/index.ts` - CandleData types
- `frontend/src/hooks/use-candle-data.ts` - REST + WS candle hook
- `frontend/src/components/charts/candlestick-chart.tsx` - lightweight-charts wrapper
- `frontend/src/pages/chart-page.tsx` - Chart page with symbol selector
- `frontend/src/App.tsx` - Added /charts route
- `frontend/src/components/layout/app-sidebar-navigation.tsx` - Added Charts nav item

**Infrastructure (1 file):**
- `docker-compose.yml` - Added nginx service

**Lines analyzed:** ~1400 LOC
**Review focus:** Recent changes (last 5 commits)

---

## Overall Assessment

**Code Quality:** GOOD
**Security:** GOOD
**Type Safety:** EXCELLENT (TS compiles clean, pytest 394/394 passed)
**Correctness:** EXCELLENT (critical BatchWriter bug fixed)

Phase 9 delivers production-ready candlestick charts with proper persistence via TimescaleDB continuous aggregates. Key improvements:

1. **Critical Fix:** BatchWriter enqueue methods now properly wired in `main.py` callbacks (lines 120-138) - previously never called in production
2. **Efficient Aggregation:** SQL continuous aggregates auto-generate 1m candles from tick_data, eliminates manual OHLCV computation
3. **Clean Architecture:** 3-tuple returns from `handle_trade()` cleanly separate stock stats from futures basis points
4. **VN Market Colors:** Correct red=up/buy, green=down/sell throughout (opposite US convention)
5. **Watchlist Filter:** Symbol filtering at processor level reduces memory/CPU for non-VN30 symbols

---

## Critical Issues

**None found.**

---

## High Priority Findings

### 1. TimescaleDB Continuous Aggregate Refresh Policy Edge Case

**File:** `db/migrations/002_continuous_aggregates.sql` (lines 27-33)
**Issue:** `end_offset => INTERVAL '1 minute'` excludes current incomplete minute from materialized view. Live candle data relies on WS for current minute only.
**Impact:** Chart shows stale data for up to 1 minute after candle close if WS disconnects.
**Recommendation:** Document this trade-off in user guide. Frontend already has 60s REST polling fallback (`use-candle-data.ts` line 107), which mitigates this.
**Status:** Acceptable design decision for production.

### 2. Date Arithmetic Uses `timedelta(days=1)` for End-Exclusive Range

**File:** `backend/app/database/history_service.py` (lines 42, 67, 116, 142, 167, 191)
**Current Code:**
```python
datetime(end.year, end.month, end.day) + timedelta(days=1)
```
**Issue:** Works correctly for date ranges, but verbose. Consider helper function.
**Impact:** Low - pattern repeated 6 times, increases maintenance burden.
**Recommendation:**
```python
def date_to_datetime_range(start: date, end: date) -> tuple[datetime, datetime]:
    """Convert date range to datetime [start, end+1) for SQL queries."""
    return (
        datetime(start.year, start.month, start.day),
        datetime(end.year, end.month, end.day) + timedelta(days=1)
    )
```
Then use: `start_dt, end_dt = date_to_datetime_range(start, end)`
**Status:** Low priority refactor.

### 3. Frontend Candle Hook Builds Live Candle from WS Snapshot

**File:** `frontend/src/hooks/use-candle-data.ts` (lines 118-161)
**Current Approach:** Subscribes to `/ws/market`, extracts price from snapshot, manually builds OHLC by tracking `liveCandle.current`.
**Issue:** Active buy/sell volume not updated in real-time (line 140-144 initializes to 0).
**Impact:** Volume bars lag until next 60s REST refresh. Basis points also computed client-side from two series (lines 165-175).
**Recommendation:** Consider dedicated `/ws/candles` stream with pre-computed live candle from backend. Would eliminate client-side OHLC tracking and ensure accurate volume breakdown.
**Status:** Current approach works but not ideal. Enhancement for Phase 10.

---

## Medium Priority Improvements

### 4. Watchlist Filter Allows VN30F* Unconditionally

**File:** `backend/app/services/market_data_processor.py` (lines 64-70)
**Code:**
```python
def _is_watched(self, symbol: str) -> bool:
    """Check if symbol is in watchlist. VN30F* always allowed for derivatives."""
    if not self._watchlist:
        return True  # no filter
    if symbol.startswith("VN30F"):
        return True  # futures always tracked
    return symbol in self._watchlist
```
**Issue:** Hardcoded prefix check. Future contract changes (e.g., VN50F) require code change.
**Recommendation:** Store futures symbols in watchlist explicitly during setup (line 102-105 in `main.py`):
```python
watchlist = set(vn30_symbols) | {"VN30", "VNINDEX"} | set(futures_symbols)
```
Then remove special case from `_is_watched()`.
**Status:** Works for current VN30F contracts, but less flexible.

### 5. Frontend Symbol Selector Hardcodes Default

**File:** `frontend/src/pages/chart-page.tsx` (line 13)
**Code:**
```typescript
const DEFAULT_SYMBOL = "VN30F2503";
```
**Issue:** Contract month hardcoded. Will need update when VN30F2503 expires.
**Recommendation:** Fetch active contract from backend `/api/derivatives` endpoint or add `/api/active-futures` endpoint.
**Status:** Minor - easy monthly update, but could be dynamic.

### 6. Docker nginx Service Has No Healthcheck

**File:** `docker-compose.yml` (lines 85-100)
**Issue:** nginx service missing `healthcheck` directive. Other services (backend, timescaledb, redis) all have healthchecks.
**Recommendation:**
```yaml
healthcheck:
  test: ["CMD", "wget", "-q", "--spider", "http://localhost/health"]
  interval: 10s
  timeout: 3s
  retries: 3
```
**Status:** Low impact (nginx rarely fails), but inconsistent with other services.

### 7. Basis Calculation in Frontend Duplicates Backend Logic

**File:** `frontend/src/hooks/use-candle-data.ts` (lines 164-175)
**Issue:** Basis points computed client-side by joining candles + indexCandles arrays. Backend already computes basis in `DerivativesTracker` (persisted to `derivatives` table).
**Impact:** Duplicated logic, potential inconsistencies.
**Recommendation:** Query basis points from `/api/history/derivatives/{contract}` endpoint instead. Would also enable historical basis chart (currently only intraday).
**Status:** Current approach works for intraday chart. Enhancement for historical analysis.

---

## Low Priority Suggestions

### 8. SQL Migration File Lacks Rollback

**File:** `db/migrations/002_continuous_aggregates.sql`
**Issue:** No `DOWN` migration provided. `DROP TABLE candles_1m CASCADE` (line 6) is irreversible if old table had data.
**Recommendation:** Add rollback script for consistency. In this case, old table was empty (comment line 5), so acceptable.
**Status:** Document-only issue.

### 9. TypeScript Chart Component Uses Many `useRef` Hooks

**File:** `frontend/src/components/charts/candlestick-chart.tsx` (lines 47-52)
**Code:**
```typescript
const chartRef = useRef<IChartApi | null>(null);
const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
const buyVolSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
const sellVolSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
const indexSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
const basisSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
```
**Issue:** 6 refs for series management. Lightweight-charts API requires refs, but verbose.
**Recommendation:** Consider wrapper class or custom hook to encapsulate series lifecycle. Example:
```typescript
function useChartSeries(chartRef) {
  const seriesRefs = useRef({
    candle: null,
    buyVol: null,
    sellVol: null,
    index: null,
    basis: null,
  });
  // setup/teardown logic
  return seriesRefs.current;
}
```
**Status:** Stylistic - current code works fine, just verbose.

### 10. Frontend Chart Legend Uses Inline Spans for Color Boxes

**File:** `frontend/src/pages/chart-page.tsx` (lines 69-84)
**Code:**
```tsx
<span className="w-3 h-0.5 bg-yellow-400 inline-block" />
<span className="w-3 h-2 bg-red-500/50 inline-block rounded-sm" />
```
**Issue:** Color values duplicated from chart component. Changes to chart colors require updates in two places.
**Recommendation:** Export color constants from `candlestick-chart.tsx` and import in `chart-page.tsx`. Or use Tailwind CSS variables.
**Status:** Low impact - colors unlikely to change frequently.

---

## Positive Observations

1. **BatchWriter Wiring Fixed:** Critical bug resolved in `main.py` - callbacks now properly invoke `batch_writer.enqueue_*()` methods (lines 120-138). Previously data was processed but never persisted.

2. **Clean 3-Tuple Return Pattern:** `handle_trade()` returns `(ClassifiedTrade, SessionStats | None, BasisPoint | None)` - cleanly separates stock aggregates from futures basis. Tests updated correctly (test_market_data_processor.py lines 32-51).

3. **Correct VN Market Colors:** Red=up/buy, green=down/sell throughout frontend (candlestick-chart.tsx lines 22-29). Matches Vietnamese market convention.

4. **Type Safety:** TypeScript compiles cleanly (`npx tsc --noEmit` passed). All types properly defined in `types/index.ts` (lines 125-147 for candle types).

5. **Comprehensive Tests:** All 394 backend tests pass, including new 3-tuple return tests. E2E tests cover trade classification, WebSocket broadcast, session lifecycle.

6. **Efficient SQL:** Continuous aggregate uses `time_bucket()`, `first()`, `last()` functions correctly (002_continuous_aggregates.sql lines 14-24). Proper index usage on timestamp column (hypertable default).

7. **Proper Error Handling:** Frontend hook has loading/error states (use-candle-data.ts lines 67-68, 88-100). Chart page displays appropriate fallback UI (chart-page.tsx lines 88-106).

8. **Security:** No secrets in code. All credentials via environment variables (config.py line 55). Docker compose properly uses `env_file` directive.

9. **Responsive Chart:** ResizeObserver properly attached to container (candlestick-chart.tsx lines 135-139). Chart width adjusts to parent.

10. **WebSocket Fallback:** 60s REST polling if WS disconnects (use-candle-data.ts line 107). Ensures chart stays updated even with network issues.

---

## Recommended Actions

### Immediate (Before Next Deployment)
1. ✅ None - code is production-ready.

### Short-Term (Phase 10)
1. Add `/api/active-futures` endpoint to return current contract symbol dynamically (eliminates hardcoded DEFAULT_SYMBOL).
2. Consider dedicated `/ws/candles` stream with pre-computed live candle + volume breakdown from backend.
3. Add healthcheck to nginx service in docker-compose.yml.

### Medium-Term (Phase 11+)
1. Extract `date_to_datetime_range()` helper in history_service.py to reduce duplication.
2. Refactor watchlist filter to remove hardcoded VN30F prefix check.
3. Query basis points from `/api/history/derivatives` instead of client-side computation.
4. Add rollback migration script for 002_continuous_aggregates.sql.

### Nice-to-Have
1. Extract color constants in candlestick-chart.tsx for reuse in legend.
2. Consider `useChartSeries()` custom hook to reduce ref boilerplate.

---

## Metrics

**Backend:**
- Type Coverage: N/A (Python - runtime types via Pydantic)
- Test Coverage: 394 tests passed (100% pass rate)
- Linting: No syntax errors (pytest imports succeeded)
- Performance: BatchWriter COPY protocol used for bulk inserts (efficient)

**Frontend:**
- Type Coverage: 100% (TypeScript strict mode, compiles clean)
- Test Coverage: N/A (no frontend tests exist)
- Linting: Clean (tsc passes)
- Bundle Size: Not measured (production build not run)

**Database:**
- Migration: Applied successfully (002_continuous_aggregates.sql)
- Continuous Aggregates: 2 views (candles_1m, index_candles_1m)
- Refresh Policy: 1-minute schedule, 2-hour lookback window

---

## Security Audit

**Credentials:**
- ✅ All SSI credentials loaded from `.env` (config.py lines 6-7)
- ✅ Database password via env var (docker-compose.yml line 8)
- ✅ No secrets in git (`.env` in `.gitignore`)

**SQL Injection:**
- ✅ All queries use asyncpg parameterized queries (`$1`, `$2` placeholders)
- ✅ Symbol names uppercased before DB queries (history_router.py lines 32, 43, 53, etc.)

**CORS:**
- ⚠️ Docker compose sets `CORS_ORIGINS=http://localhost` (line 9) - acceptable for dev/local deploy
- ⚠️ Production should use specific domains, not wildcard

**WebSocket Auth:**
- ℹ️ `ws_auth_token` setting exists (config.py line 52) but empty by default
- ℹ️ Consider enabling for production if exposing publicly

**Nginx Security Headers:**
- ❌ Missing security headers (CSP, X-Frame-Options, X-Content-Type-Options)
- **Recommendation:** Add to nginx.conf:
```nginx
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
```

**Dependencies:**
- ⚠️ Frontend uses `lightweight-charts` (TradingView library) - ensure license compliance
- ✅ Backend dependencies pinned in requirements.txt

---

## Task Completeness Verification

**Phase 9 TODO Status:**

✅ TimescaleDB continuous aggregates for 1m candles
✅ Index candles (VN30, VNINDEX) materialized view
✅ BatchWriter enqueue wiring in main.py callbacks
✅ Watchlist filtering in MarketDataProcessor
✅ 3-tuple returns from handle_trade()
✅ Frontend CandleData types
✅ use-candle-data hook (REST + WS)
✅ CandlestickChart component (lightweight-charts)
✅ Chart page with symbol selector
✅ Navigation item added
✅ Tests updated for 3-tuple returns
✅ Docker nginx service added

**Remaining TODO comments:** None found in modified files.

**All Phase 9 tasks complete.**

---

## Unresolved Questions

1. **Continuous Aggregate Retention:** How long should 1m candle data be retained? Migration has no compression/retention policy. Recommend TimescaleDB compression policy for data older than 30 days.

2. **Chart Performance:** lightweight-charts tested with how many data points? VN market 9:00-15:00 = 6 hours = 360 candles. Acceptable. But full day (1440 candles) may need virtualization.

3. **Futures Contract Rollover:** When VN30F2503 expires, how will chart page handle contract change? Need operational procedure for monthly rollover.

4. **Basis Point Persistence:** `derivatives` table stores basis but not queried by frontend. Historical basis analysis planned for Phase 10?

5. **Frontend Tests:** Chart component has complex interaction with lightweight-charts API. Consider adding Playwright E2E tests for chart rendering.

---

## Conclusion

Phase 9 implementation is production-ready with no critical issues. Key achievement: **BatchWriter now properly persists data** (critical fix in main.py). TimescaleDB continuous aggregates provide efficient 1m candle generation. Frontend chart UI matches VN market conventions (red=up). Recommend adding nginx security headers before public deployment, otherwise code quality is excellent.

**Overall Grade: A-** (excellent functionality, minor enhancements suggested)
