# Code Review: Router Test Files

**Date:** 2026-02-09
**Reviewer:** code-reviewer agent
**Focus:** `test_market_router.py`, `test_history_router.py`

---

## Scope

**Files reviewed:**
- `/Users/minh/Projects/stock-tracker/backend/tests/test_market_router.py` (201 lines)
- `/Users/minh/Projects/stock-tracker/backend/tests/test_history_router.py` (320 lines)

**Review focus:** New test coverage for REST endpoints (38 tests total)
**Test results:** All 38 tests pass, no regressions in 326-test suite

---

## Overall Assessment

**Quality:** Excellent
**Coverage:** Comprehensive for happy paths, edge cases, validation

Tests demonstrate strong understanding of FastAPI testing patterns, proper isolation from production dependencies (SSI credentials, db), and consistent mock strategies. Code is clean, maintainable, well-organized into test classes.

---

## Positive Observations

### Mock Pattern Excellence
- **Market router:** Clever `sys.modules` patching avoids importing `app.main` (which requires SSI credentials)
- **History router:** Clean lazy-init pattern with `_get_svc()` patching
- **Isolated test apps:** Both use standalone FastAPI instances with no lifespan/db/ssi overhead
- **Consistent fixtures:** Proper `pytest_asyncio.fixture` usage, clear mock setup

### Test Coverage Strengths
- **Happy paths:** All endpoints tested with realistic data
- **Empty states:** Tests verify graceful handling of no-data scenarios
- **Validation:** FastAPI Query constraints tested (422 responses for out-of-bounds params)
- **Case normalization:** Symbol/index uppercasing consistently verified
- **Default vs custom params:** Tests check both default behavior and custom values

### Code Organization
- **Class-based grouping:** Each endpoint gets dedicated test class
- **Descriptive naming:** `test_returns_candle_rows`, `test_empty_result`, etc. are self-documenting
- **Consistent structure:** Setup → execute → assert pattern throughout
- **Domain model usage:** Tests import and construct proper Pydantic models

### Edge Case Handling
- Missing required params (422)
- Invalid date formats (422)
- Limit/days exceeding max (422)
- Empty processor state
- Empty database results

---

## Medium Priority Improvements

### 1. Missing Error Scenario Tests
**Issue:** No tests for internal failures (database errors, processor exceptions)

**Current gaps:**
- Database connection failures
- Service method raising exceptions
- Malformed data from processor/service

**Example missing test:**
```python
@pytest.mark.asyncio
async def test_service_exception_returns_500(self, client, mock_svc):
    mock_svc.get_candles.side_effect = Exception("DB connection lost")
    resp = await client.get(
        "/api/history/VNM/candles",
        params={"start": "2026-02-01", "end": "2026-02-07"},
    )
    assert resp.status_code == 500
```

**Recommendation:** Add 1-2 exception tests per router to verify error handling

---

### 2. Missing Integration Smoke Tests
**Issue:** No tests verify router integration with actual FastAPI app

**Current approach:**
- Tests use isolated `FastAPI()` instances
- Never test with real `app.main.app` (where routers are registered)

**Risk:** Middleware, exception handlers, CORS, auth (future) might behave differently in production

**Recommendation:**
```python
# tests/integration/test_app_smoke.py
@pytest.mark.asyncio
async def test_real_app_includes_routers():
    """Verify routers registered in production app."""
    from app.main import app
    routes = {r.path for r in app.routes}
    assert "/api/market/snapshot" in routes
    assert "/api/history/{symbol}/candles" in routes
```

---

### 3. Test Data Realism
**Issue:** Mock data uses hardcoded values, no date consistency checks

**Examples:**
- `timestamp="2026-02-07T10:00:00"` is static string
- `basis=10.0` lacks context (is this realistic for VN30F?)
- Foreign flow values seem arbitrary

**Recommendation:** Add fixture for realistic test data sets
```python
@pytest.fixture
def realistic_market_data():
    """Returns domain-valid market snapshot."""
    return MarketSnapshot(
        quotes={"VNM": SessionStats(symbol="VNM", mua_chu_dong_volume=100_000)},
        prices={"VNM": PriceData(last_price=80.5, reference=80.0, change=0.5)},
        # ... realistic VN30 index values, typical foreign flows
    )
```

---

### 4. Missing Concurrent Request Tests
**Issue:** No tests verify thread-safety of shared processor state

**Market router risk:** Multiple simultaneous `/snapshot` calls reading same `MarketDataProcessor`
**History router risk:** Multiple calls to `_get_svc()` lazy init

**Recommendation:**
```python
@pytest.mark.asyncio
async def test_concurrent_snapshot_requests(client, mock_processor):
    """Verify no race conditions on processor access."""
    tasks = [client.get("/api/market/snapshot") for _ in range(10)]
    responses = await asyncio.gather(*tasks)
    assert all(r.status_code == 200 for r in responses)
    assert mock_processor.get_market_snapshot.call_count == 10
```

---

### 5. Response Schema Validation
**Issue:** Tests check individual fields, not full Pydantic schema compliance

**Current pattern:**
```python
assert data["prices"]["VNM"]["last_price"] == 80.5  # spot-check
```

**Better approach:**
```python
from app.models.domain import MarketSnapshot

snapshot = MarketSnapshot.model_validate(resp.json())  # full schema check
assert snapshot.prices["VNM"].last_price == 80.5
```

**Benefit:** Catches missing fields, wrong types, failed validations

---

## Low Priority Suggestions

### 1. Docstring Consistency
**Current:** First-line module docstrings present, no function docstrings
**Suggestion:** Add brief docstrings to complex test scenarios for clarity

### 2. Fixture Naming
**Current:** `mock_processor`, `mock_svc` are generic
**Alternative:** `processor_mock`, `history_svc_mock` (noun-first for autocomplete)
**Impact:** Low, existing names are acceptable

### 3. Test Ordering
**Current:** Grouped by endpoint, happy path first
**Alternative:** Could group by severity (happy → validation → errors)
**Impact:** Minimal, current organization is clear

### 4. Parametrize Opportunities
**Example:** Symbol uppercasing tests repeat pattern across multiple endpoints
```python
@pytest.mark.parametrize("endpoint,symbol", [
    ("/api/history/vnm/candles", "VNM"),
    ("/api/history/fpt/ticks", "FPT"),
])
async def test_symbols_uppercased(client, mock_svc, endpoint, symbol):
    # shared uppercasing test logic
```

**Benefit:** DRY, easier to add new endpoints
**Cost:** Slightly less readable for newcomers

---

## Critical Issues

**None found.** No security vulnerabilities, data loss risks, or breaking changes.

---

## Metrics

- **Test count:** 38 new tests (11.6% of total 326-test suite)
- **Coverage:** 100% of router endpoints tested
- **Pass rate:** 100% (38/38)
- **Type safety:** No mypy errors in test files (pre-existing issues in dependencies only)
- **Execution time:** 0.19s for 38 tests (very fast)

---

## Recommended Actions

### High Priority (before production deployment)
1. Add exception handling tests (1-2 per router, ~10 tests total)
2. Create integration smoke test verifying routers registered in `app.main`

### Medium Priority (next sprint)
3. Add concurrent request tests for thread-safety verification
4. Implement response schema validation using Pydantic models

### Low Priority (technical debt backlog)
5. Consider parametrized tests for repeated patterns (uppercasing, empty states)
6. Add realistic test data fixtures for domain context

---

## Conclusion

**Summary:** High-quality test implementation with excellent isolation patterns, comprehensive coverage of happy paths and validation, well-organized structure. Primary gap is lack of error scenario testing (database failures, service exceptions).

**Risk level:** Low for current functionality, medium for production deployment without exception tests.

**Recommendation:** Add exception handling tests before merging to production branch. Consider integration smoke tests before first deployment.

---

## Unresolved Questions

1. Are there plans for authentication/authorization on these endpoints? (Would require auth tests)
2. Should rate limiting be tested for public-facing APIs?
3. Is there a CI/CD pipeline running coverage reports? (Recommended: pytest-cov threshold check)
