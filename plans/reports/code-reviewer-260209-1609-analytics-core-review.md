# Code Review: Analytics Engine Core Module

**Reviewer:** code-reviewer (abbbf0f)
**Date:** 2026-02-09 16:09
**Work Context:** /Users/minh/Projects/stock-tracker
**Plan:** Phase 06 Analytics Engine (partial)

---

## Scope

**Files reviewed:**
- `backend/app/analytics/__init__.py` (6 LOC) — NEW
- `backend/app/analytics/alert_models.py` (38 LOC) — NEW
- `backend/app/analytics/alert_service.py` (96 LOC) — NEW
- `backend/app/main.py` (130 LOC) — MODIFIED (L20, L33)

**Lines analyzed:** 270 total (140 new)
**Review focus:** New analytics module creation, pattern adherence, correctness
**Tests:** 326 existing tests pass, no regressions

---

## Overall Assessment

**APPROVED with minor style fixes required.**

Implementation is **clean, correct, and follows project patterns**. Alert dataclass, enums, and service match existing codebase conventions. Dedup logic verified functional. Subscriber pattern consistent with MarketDataProcessor. All files <200 LOC. No security issues. Python 3.12+ syntax used correctly.

**Quality Score:** 8.5/10

---

## Critical Issues

None.

---

## High Priority Findings

None.

---

## Medium Priority Improvements

### 1. **Linting: Unused Import**
**File:** `alert_service.py:13`
**Issue:** `timedelta` imported but never used
**Impact:** Dead code, minor namespace pollution

```python
# Current
from datetime import datetime, timedelta

# Fix
from datetime import datetime
```

**Action:** Remove `timedelta` import (ruff --fix handles this)

---

### 2. **Linting: Line Length Violations**
**File:** `alert_service.py:48, 54`
**Issue:** Lines exceed 88 chars (project standard)

```python
# L48 (115 chars)
logger.debug("Alert deduped: %s %s (within %ds)", alert.alert_type, alert.symbol, DEDUP_WINDOW_SECONDS)

# L54 (131 chars)
logger.info("Alert registered: [%s] %s %s — %s", alert.severity.value, alert.alert_type.value, alert.symbol, alert.message)
```

**Fix:**
```python
# L48
logger.debug(
    "Alert deduped: %s %s (within %ds)",
    alert.alert_type,
    alert.symbol,
    DEDUP_WINDOW_SECONDS,
)

# L54
logger.info(
    "Alert registered: [%s] %s %s — %s",
    alert.severity.value,
    alert.alert_type.value,
    alert.symbol,
    alert.message,
)
```

**Action:** Reformat long log statements (multi-line)

---

### 3. **Type Checking: Unannotated Methods**
**File:** `alert_service.py:32, 34, 35`
**Issue:** mypy warns about missing type annotations on `__init__`, `subscribe`, `unsubscribe`

```python
# Current
def __init__(self):
def subscribe(self, callback: AlertSubscriber):
def unsubscribe(self, callback: AlertSubscriber):

# Better
def __init__(self) -> None:
def subscribe(self, callback: AlertSubscriber) -> None:
def unsubscribe(self, callback: AlertSubscriber) -> None:
```

**Action:** Add `-> None` return type hints (improves mypy coverage, not critical)

---

## Low Priority Suggestions

### 1. **Default Mutable Argument Anti-pattern**
**File:** `alert_models.py:38`

```python
# Current (technically safe because Pydantic handles this correctly)
data: dict[str, Any] = {}

# More explicit (Pydantic best practice)
data: dict[str, Any] = Field(default_factory=dict)
```

**Reason:** While Pydantic handles `= {}` correctly, `Field(default_factory=dict)` is more explicit and safer if code is copy-pasted to non-Pydantic contexts.

**Priority:** Low (not a bug, just stylistic)

---

### 2. **AlertService.reset_daily() Not Wired to Scheduler**
**File:** `alert_service.py:92`, `main.py`
**Observation:** `reset_daily()` exists but no daily scheduler registered in lifespan

**Expected:** Daily reset at session start (typically 09:00 VN time)
**Current:** Manual reset only

**Action:** Phase 06 follow-up task — wire to APScheduler or manual call at session start

---

### 3. **Subscriber Error Handling Could Be More Granular**
**File:** `alert_service.py:85-90`

```python
# Current
for cb in self._subscribers:
    try:
        cb(alert)
    except Exception:
        logger.exception("Alert subscriber notification error")
```

**Good:** Prevents bad subscriber from killing notification loop
**Enhancement:** Could track failed callback count, auto-unsubscribe after N failures

**Priority:** Low (current approach is defensive and acceptable)

---

## Positive Observations

### 1. **Pattern Consistency**
- Subscriber pattern identical to `MarketDataProcessor` (subscribe/unsubscribe/_notify)
- Plain class with private state, public methods (no unnecessary inheritance)
- Pydantic models with Field defaults match `domain.py` conventions

### 2. **Dedup Logic Correctness**
- Key choice `(alert_type, symbol)` prevents spam per-symbol
- 60s cooldown reasonable for market alerts
- Manual test confirms: first alert accepted, second rejected ✓

### 3. **Thread Safety (Acceptable for Current Use)**
- Used from single-threaded asyncio context (FastAPI lifespan)
- No concurrent writes expected (all alerts registered from stream callbacks)
- If future multi-threading needed: `_buffer` → `deque` with lock, `_cooldowns` → dict with lock

### 4. **Import Resolution**
- All imports work at runtime ✓
- No circular dependencies
- Package `__all__` exports correct symbols

### 5. **File Size Management**
- All files <100 LOC (well under 200 LOC limit)
- Separation: models (38 LOC), service (96 LOC), init (6 LOC)

### 6. **Python 3.12+ Syntax**
- `dict[str, Any]` instead of `Dict[str, Any]` ✓
- `X | None` instead of `Optional[X]` ✓
- Enum str mixin for JSON serialization ✓

---

## Security Audit

**No issues found.**

- No user input processed (alerts generated from internal SSI stream)
- No SQL injection risk (no database queries)
- No XSS risk (backend service, no HTML rendering)
- Logging does not expose sensitive data (symbol/message only)
- No credentials or secrets in code

---

## Performance Analysis

**Alert registration: <1ms** (deque append + dict lookup)
**Dedup check: O(1)** (dict lookup)
**Filtering: O(n)** where n = buffer size (max 500)
**Subscriber notify: O(s)** where s = subscriber count (expected <10)

**Conclusion:** Meets <10ms requirement from Phase 06 spec.

---

## Build & Deployment Validation

**Compilation:** ✓ All `.py` files compile without syntax errors
**Runtime imports:** ✓ `from app.analytics import *` succeeds
**Test suite:** ✓ 326 existing tests pass (no regressions)
**Type checking:** ⚠️ 3 minor warnings (unannotated returns — see Medium Priority #3)

---

## Task Completeness Verification

**Phase 06 Progress:**
- [x] Alert dataclass with id, type, severity, symbol, message, timestamp, data
- [x] AlertType enum (4 types: foreign_acceleration, basis_divergence, volume_spike, price_breakout)
- [x] AlertSeverity enum (info, warning, critical)
- [x] AlertService with deque buffer (maxlen=500)
- [x] Dedup logic (60s cooldown per alert_type+symbol)
- [x] Subscribe/notify pattern
- [x] Filtering by type/severity
- [x] reset_daily method
- [ ] **NOT YET:** AlertService wired to MarketDataProcessor (no alert generation logic)
- [ ] **NOT YET:** PriceTracker for divergence detection
- [ ] **NOT YET:** Alert REST endpoint (GET /api/alerts)
- [ ] **NOT YET:** Alert WebSocket broadcast
- [ ] **NOT YET:** Daily scheduler for reset_daily()

**Status:** Phase 06 **20% complete** (core models + service shell done, no analytics logic yet)

---

## Recommended Actions

**Immediate (required before merge):**
1. ✅ Fix unused `timedelta` import (`ruff check --fix`)
2. ✅ Reformat long logger lines (L48, L54)
3. ⚠️ Add `-> None` type hints to `__init__`, `subscribe`, `unsubscribe` (optional but recommended)

**Follow-up (Phase 06 continuation):**
4. Wire alert generation logic to MarketDataProcessor foreign/basis callbacks
5. Create PriceTracker for divergence detection
6. Add REST endpoint `GET /api/alerts?type=&severity=&limit=`
7. Broadcast alerts to WebSocket clients
8. Wire `reset_daily()` to scheduler or manual session-start hook
9. Write unit tests for AlertService (dedup, filtering, subscriber pattern)

**Phase tracking:**
- Update `plans/260206-1418-vn-stock-tracker-revised/phase-06-analytics-engine.md` status → "in_progress"
- Create TODO checklist for remaining alert generation logic

---

## Metrics

- **Type Coverage:** Not measured (no mypy --strict run)
- **Test Coverage:** 0% for new analytics module (no tests yet)
- **Linting Issues:** 3 (1 unused import, 2 line length)
- **Compilation:** ✅ Pass
- **Runtime:** ✅ Pass (manual smoke test)

---

## Unresolved Questions

1. **Alert persistence:** Should alerts be stored in TimescaleDB for historical analysis? (Not in Phase 06 spec)
2. **Alert rate limiting:** Should there be a global alert rate limit (e.g., max 10 alerts/sec) to prevent WS flood?
3. **Severity escalation:** Should repeated alerts within 5 min escalate from INFO → WARNING → CRITICAL?

---

## Conclusion

**Status:** APPROVED pending style fixes (3 linting issues)

Core analytics module structure is solid. Dedup logic works. Patterns match codebase conventions. No security/performance issues. Ready for alert generation logic wiring (Phase 06 continuation).

**Next steps:** Fix linting, proceed with alert rule implementation.
