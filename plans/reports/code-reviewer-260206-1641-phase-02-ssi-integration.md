# Code Review: Phase 2 SSI Integration Implementation

**Review Date:** 2026-02-06
**Reviewer:** code-reviewer
**Phase:** Phase 2 - SSI Integration & Stream Demux
**Branch:** master (commit 76d6571)

---

## Code Review Summary

### Scope
**Files Reviewed:**
- `backend/app/models/ssi_messages.py` (84 LOC)
- `backend/app/models/domain.py` (84 LOC)
- `backend/app/models/schemas.py` (20 LOC)
- `backend/app/services/ssi_auth_service.py` (62 LOC)
- `backend/app/services/ssi_market_service.py` (80 LOC)
- `backend/app/services/futures_resolver.py` (57 LOC)
- `backend/app/services/ssi_field_normalizer.py` (116 LOC)
- `backend/app/services/ssi_stream_service.py` (182 LOC)
- `backend/app/main.py` (78 LOC)

**Total LOC Analyzed:** ~685 lines
**Review Focus:** Phase 2 implementation (SSI integration, stream demux, thread safety, Python 3.9 compat)
**Updated Plans:** `phase-02-ssi-integration-stream-demux.md`

### Overall Assessment
Implementation is **functionally complete** with solid architecture. Core SSI integration logic correct, proper use of `asyncio.to_thread()` for sync library, correct understanding of LastVol vs TotalVol. Thread-safe callback dispatch implemented correctly. Python 3.9 compatible (uses `Optional[X]` not `X|None`).

**1 CRITICAL issue** found (event loop retrieval), **3 HIGH priority** issues (missing field, error handling, timeouts), **4 MEDIUM priority** improvements identified.

---

## Critical Issues

### **CRITICAL-01: Unsafe Event Loop Retrieval in Thread Context**

**File:** `ssi_stream_service.py:131-134`
**Severity:** Critical — causes `RuntimeError` when callbacks dispatched from non-async thread

**Issue:**
```python
def _schedule_callback(self, cb: MessageCallback, msg):
    """Schedule an async callback on the running event loop from any thread."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop in this thread — get the main loop
        loop = asyncio.get_event_loop()  # ⚠️ WRONG - deprecated, returns new loop in thread
    future = asyncio.run_coroutine_threadsafe(self._run_callback(cb, msg), loop)
```

**Problem:** `asyncio.get_event_loop()` is deprecated in Python 3.10+ and returns a **new event loop** in non-async threads (not the main loop). This causes callbacks to run in wrong/dead loop.

**Impact:**
- Callbacks never execute when stream runs in background thread
- Silent failure (no errors, but handlers don't fire)
- Breaks entire demux system

**Root Cause:** SSI stream runs in thread (via `asyncio.to_thread()`), so `_handle_message()` callback executes in thread context where `get_running_loop()` raises `RuntimeError`.

**Fix Required:**
```python
def _schedule_callback(self, cb: MessageCallback, msg):
    """Schedule callback on main event loop from any thread."""
    # Store main loop ref at service init (in async context)
    # Or use threading to find main thread's loop
    import threading
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # Called from thread — find main event loop
        main_loop = None
        for thread in threading.enumerate():
            if hasattr(thread, '_target') and thread._target is None:
                # Main thread
                try:
                    main_loop = asyncio._get_running_loop()  # Get from main
                except AttributeError:
                    pass
        if main_loop is None:
            # Fallback: store loop at service init
            main_loop = self._main_loop
        loop = main_loop
    future = asyncio.run_coroutine_threadsafe(self._run_callback(cb, msg), loop)
```

**Better Fix:** Store main event loop at service initialization:
```python
class SSIStreamService:
    def __init__(self, auth_service, market_service):
        self._auth = auth_service
        self._market = market_service
        self._main_loop = None  # Set in connect()
        # ... rest of init

    async def connect(self, channels: List[str]):
        """Connect SSI stream in a background thread."""
        self._main_loop = asyncio.get_running_loop()  # Store main loop ref
        # ... rest of connect logic

    def _schedule_callback(self, cb: MessageCallback, msg):
        """Schedule callback on main event loop from any thread."""
        loop = self._main_loop  # Use stored loop ref
        if loop is None:
            logger.error("Main loop not set — cannot schedule callback")
            return
        asyncio.run_coroutine_threadsafe(self._run_callback(cb, msg), loop)
```

---

## High Priority Findings

### **HIGH-01: Missing TotalVal Field in SSIIndexMessage**

**File:** `ssi_messages.py:60-72`, `ssi_field_normalizer.py:64`
**Severity:** High — field mapping exists but model field missing

**Issue:**
```python
# ssi_field_normalizer.py:64
FIELD_MAP = {
    ...
    "TotalQtty": "total_qtty",  # ✓ Mapped
    # Missing TotalVal mapping!
}

# ssi_messages.py:68
class SSIIndexMessage(BaseModel):
    total_qtty: int = 0
    total_val: float = 0.0  # ✓ Field exists in model
```

**Problem:** Plan spec (line 123) shows `TotalVal` field exists in SSI MI messages, model has `total_val` field, but normalizer doesn't map `TotalVal` → `total_val`.

**Impact:** Index total value always 0.0 (default), analytics using index volume value will fail.

**Fix:**
```python
# ssi_field_normalizer.py:64
FIELD_MAP = {
    ...
    "TotalQtty": "total_qtty",
    "TotalVal": "total_val",  # ADD THIS
    "Advances": "advances",
    ...
}
```

---

### **HIGH-02: Missing SSI Credentials Validation at Startup**

**File:** `ssi_auth_service.py:41-62`
**Severity:** High — silent failure if credentials missing/invalid

**Issue:**
```python
async def authenticate(self) -> str:
    """Authenticate with SSI and store JWT token."""
    logger.info("Authenticating with SSI FastConnect...")
    result = await asyncio.to_thread(
        self.client.access_token, self.config
    )
    # ... parse token ...
    if self._token:
        logger.info("SSI authentication successful")
    else:
        logger.error("SSI authentication failed — no token received")  # Just logs error
    return self._token  # Returns empty string on failure
```

**Problem:**
- No validation that `ssi_consumer_id`/`ssi_consumer_secret` are set
- On auth failure, service continues startup (returns empty string)
- Stream connection will fail later with cryptic SignalR error

**Impact:** App starts but cannot connect to SSI, requires reading logs to diagnose.

**Fix:**
```python
async def authenticate(self) -> str:
    """Authenticate with SSI and store JWT token."""
    # Validate credentials exist
    if not self.config.get("consumerID") or not self.config.get("consumerSecret"):
        raise ValueError(
            "SSI credentials missing. Set SSI_CONSUMER_ID and SSI_CONSUMER_SECRET env vars."
        )

    logger.info("Authenticating with SSI FastConnect...")
    try:
        result = await asyncio.to_thread(
            self.client.access_token, self.config
        )
        # ... parse token ...
        if not self._token:
            raise RuntimeError("SSI authentication failed — no token received")
        logger.info("SSI authentication successful")
        return self._token
    except Exception as e:
        logger.error("SSI authentication failed: %s", e)
        raise  # Fail fast on startup
```

**Also update main.py lifespan:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await auth_service.authenticate()
    except Exception as e:
        logger.critical("Failed to authenticate with SSI: %s. Exiting.", e)
        raise SystemExit(1) from e
    # ... rest of startup
```

---

### **HIGH-03: No Timeout on asyncio.to_thread() Calls**

**File:** `ssi_auth_service.py:48`, `ssi_market_service.py:33,52`, `ssi_stream_service.py:78`
**Severity:** High — blocking startup/operations if SSI API hangs

**Issue:**
```python
# ssi_auth_service.py:48
result = await asyncio.to_thread(
    self.client.access_token, self.config
)  # No timeout — hangs forever if SSI unresponsive

# ssi_stream_service.py:78
self._stream_task = asyncio.create_task(
    asyncio.to_thread(
        self._stream.start,
        self._handle_message,
        self._handle_error,
        channel_str,
    )
)  # No timeout — blocks lifespan startup if SSI down
```

**Problem:** If SSI API is down/slow, `asyncio.to_thread()` blocks indefinitely. Server startup hangs silently.

**Impact:**
- Server appears frozen during startup
- No health check response
- Deployment failures (Docker healthcheck timeout)

**Fix:** Wrap with `asyncio.wait_for()`:
```python
# ssi_auth_service.py
async def authenticate(self) -> str:
    """Authenticate with SSI and store JWT token."""
    logger.info("Authenticating with SSI FastConnect...")
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(self.client.access_token, self.config),
            timeout=10.0  # 10s timeout
        )
        # ... rest of logic
    except asyncio.TimeoutError:
        logger.error("SSI authentication timed out after 10s")
        raise RuntimeError("SSI authentication timeout") from None

# ssi_market_service.py
async def fetch_vn30_components(self) -> List[str]:
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                self._client.index_components,
                self._config,
                {"indexCode": "VN30", "pageSize": 50, "pageIndex": 1},
            ),
            timeout=10.0
        )
        # ... rest
    except asyncio.TimeoutError:
        logger.error("VN30 fetch timed out")
        return []
```

**Note:** Stream connection timeout is harder (SignalR blocks indefinitely). Consider background task with startup timeout:
```python
# main.py lifespan
async def lifespan(app: FastAPI):
    await auth_service.authenticate()
    vn30_symbols = await market_service.fetch_vn30_components()

    # Start stream connection with timeout
    connect_task = asyncio.create_task(stream_service.connect(channels))
    try:
        await asyncio.wait_for(connect_task, timeout=15.0)
    except asyncio.TimeoutError:
        logger.error("Stream connection timed out — running degraded")
        # Continue startup without stream (degraded mode)

    yield
    await stream_service.disconnect()
```

---

## Medium Priority Improvements

### **MEDIUM-01: No Logging Level Configuration**

**File:** All files
**Issue:** Hardcoded `logger = logging.getLogger(__name__)` without global config. No way to control log verbosity (DEBUG for dev, INFO for prod).

**Recommendation:**
```python
# main.py - add at startup
import logging

# Configure logging at app startup
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
```

---

### **MEDIUM-02: No Connection State Tracking**

**File:** `ssi_stream_service.py`
**Issue:** No public property to check if stream is connected/disconnected/reconnecting.

**Impact:**
- Cannot implement health check endpoint showing SSI connection status
- Frontend cannot display "Connecting..." vs "Connected" state

**Recommendation:**
```python
class SSIStreamService:
    def __init__(self, ...):
        self._connection_state = "disconnected"  # disconnected|connecting|connected|reconnecting

    @property
    def connection_state(self) -> str:
        return self._connection_state

    async def connect(self, channels):
        self._connection_state = "connecting"
        # ... after successful connect ...
        self._connection_state = "connected"

# main.py - add health endpoint
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "ssi_connection": stream_service.connection_state,
        "vn30_stocks": len(vn30_symbols)
    }
```

---

### **MEDIUM-03: No Metrics for Callback Performance**

**File:** `ssi_stream_service.py:138-147`
**Issue:** No timing metrics for callback execution. If a callback hangs, no visibility.

**Recommendation:** Add timing instrumentation:
```python
async def _run_callback(self, cb: MessageCallback, msg):
    """Execute a callback with error isolation and timing."""
    start = time.perf_counter()
    task = asyncio.current_task()
    if task:
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
    try:
        await cb(msg)
        duration = time.perf_counter() - start
        if duration > 0.05:  # 50ms threshold
            logger.warning("Slow callback for %s: %.2fms", type(msg).__name__, duration * 1000)
    except Exception:
        logger.exception("Callback error for %s", type(msg).__name__)
```

---

### **MEDIUM-04: Missing SSI Response Format Documentation**

**File:** `ssi_field_normalizer.py`, `ssi_auth_service.py`
**Issue:** Code assumes SSI response formats (`{"data": {"accessToken": "..."}}`), but no docs showing actual SSI response structure.

**Recommendation:** Add docstring examples:
```python
# ssi_auth_service.py
async def authenticate(self) -> str:
    """Authenticate with SSI and store JWT token.

    SSI Response Format:
    {
        "status": 200,
        "data": {
            "accessToken": "eyJhbG...",
            "expiresIn": 3600,
            ...
        }
    }

    Returns the access token string.
    """
```

---

## Low Priority Suggestions

### **LOW-01: Futures Rollover Logic Complexity**

**File:** `futures_resolver.py:46-50`
**Issue:** Rollover calculation assumes last Thursday. VN derivatives expire 3rd Thursday (not last Thursday).

**Current Code:**
```python
# Walk back to Thursday (weekday=3)
offset = (last_date.weekday() - 3) % 7
last_thursday = last_date - timedelta(days=offset)
```

**Correct (3rd Thursday):**
```python
from datetime import datetime

def get_third_thursday(year: int, month: int) -> datetime:
    """Return 3rd Thursday of given month."""
    first = datetime(year, month, 1)
    # Find first Thursday
    first_thu_offset = (3 - first.weekday()) % 7
    first_thursday = first + timedelta(days=first_thu_offset)
    third_thursday = first_thursday + timedelta(weeks=2)
    return third_thursday
```

**Note:** Plan mentions "last Thursday" but VN market rules specify 3rd Thursday. Verify with SSI docs.

---

### **LOW-02: IndexData Model Missing in Plan**

**File:** `domain.py:62-73`
**Issue:** `IndexData` model exists but plan Phase 2 spec (line 176-188) shows slightly different field names (`total_volume` vs `total_qtty`).

**Current Model:**
```python
class IndexData(BaseModel):
    total_volume: int = 0  # ← Name mismatch
```

**Plan Spec (line 187):**
```python
total_qtty: int = 0
```

**Recommendation:** Align naming. Both SSI message (`total_qtty`) and domain model should match, OR add clarifying comment why renamed.

---

## Positive Observations

1. **Correct LastVol Usage** — Trade classifier foundation correct (per-trade volume, not cumulative). Critical for accuracy.

2. **Thread-Safe Callback Dispatch** — `run_coroutine_threadsafe()` usage correct. Background task tracking prevents GC (`_background_tasks` set).

3. **Python 3.9 Compatible** — Uses `Optional[X]` not `X|None`. Clean imports.

4. **Clean Separation of Concerns** — Field normalization isolated in dedicated module. Demux logic clean. Models properly split (SSI raw vs domain).

5. **Futures Dual Subscription** — Subscribes both current+next month to avoid rollover data gaps. Smart.

6. **Graceful Shutdown** — `disconnect()` cancels tasks properly, cleans up background tasks.

7. **Pydantic Defaults** — All fields have sensible defaults (0.0, 0, ""), prevents validation errors on partial messages.

8. **Error Isolation** — Callback exceptions logged but don't crash service (`_run_callback` try/except).

9. **Config via pydantic-settings** — Clean env var loading, type-safe.

10. **Reconnect Reconciliation** — `reconcile_after_reconnect()` method prepared for Phase 3 foreign tracker re-seeding. Good foresight.

---

## Recommended Actions

**CRITICAL (must fix before testing):**
1. Fix event loop retrieval in `_schedule_callback()` — store main loop at service init
2. Add timeout to all `asyncio.to_thread()` calls (10s for REST, 15s for stream connect)
3. Add missing `TotalVal` field mapping in `ssi_field_normalizer.py`

**HIGH (fix before Phase 3):**
4. Add SSI credentials validation at startup (fail fast if missing)
5. Raise exceptions on auth failure (don't silently continue)
6. Add connection state tracking for health checks

**MEDIUM (improve before production):**
7. Configure logging levels (DEBUG for dev, INFO for prod)
8. Add callback timing metrics (warn on >50ms)
9. Document SSI response formats in docstrings

**LOW (nice to have):**
10. Verify futures expiry is 3rd Thursday (not last Thursday)
11. Align `total_volume` vs `total_qtty` naming between models

---

## Test Coverage

**Status:** No tests written yet (tests/__init__.py empty)

**Required Tests (from plan Todo List):**
- [ ] Auth succeeds and logs confirm
- [ ] Stream receives messages (log raw content)
- [ ] Demux routes Trade/Quote/R/MI/B correctly
- [ ] After reconnect, first foreign delta is correct

**Recommended Integration Tests:**
1. **test_ssi_auth.py** — Mock SSI access_token, verify token stored
2. **test_ssi_market.py** — Mock IndexComponents API, verify VN30 list parsing
3. **test_field_normalizer.py** — Unit test PascalCase→snake_case mapping
4. **test_stream_demux.py** — Mock SSI messages, verify callbacks fire per RType
5. **test_futures_resolver.py** — Unit test current+next month contract naming
6. **test_main_lifespan.py** — Mock SSI services, verify startup sequence

**Thread Safety Tests:**
7. Test callback dispatch from thread context (verify correct event loop)
8. Test concurrent callback execution (no race conditions)

---

## Security Considerations

**PASSED:**
- ✓ SSI credentials loaded from .env (not hardcoded)
- ✓ JWT token in-memory only (not logged)
- ✓ No credentials exposed to frontend
- ✓ CORS restricted to localhost:5173 (dev only)

**RECOMMENDATIONS:**
- Add `.env` to .gitignore (already done ✓)
- Use secrets manager for production (Docker secrets, AWS Secrets Manager)
- Add CORS origin validation from settings (not hardcoded)

---

## Performance Analysis

**Estimated Throughput:**
- SSI sends ~1-5 messages/sec during trading hours (30 VN30 stocks)
- Demux overhead: JSON parse + field normalization <1ms per message
- Callback dispatch: `run_coroutine_threadsafe` ~0.5ms overhead
- **Total latency budget:** <5ms from SSI→parsed model (well under plan's <100ms requirement)

**Bottlenecks:**
- None identified at this scale
- Callback execution time depends on Phase 3 trackers (not in scope)

**Optimization Opportunities:**
- Field normalization dict comprehension is O(n) fields — acceptable (<100 fields/msg)
- Consider caching `FIELD_MAP` lookups if profiling shows overhead (unlikely)

---

## Metrics

- **Code Quality:** Good (clean separation, error handling, type hints)
- **Thread Safety:** Mostly Safe (1 critical issue with event loop)
- **Python 3.9 Compat:** Pass (no `X|None` syntax, uses `Optional[X]`)
- **Plan Compliance:** 90% (1 missing field mapping, reconnect reconciliation partial)
- **Test Coverage:** 0% (no tests written)
- **Security:** Good (credentials handled safely)
- **Performance:** Excellent (well under <100ms latency requirement)

---

## Unresolved Questions

1. **Event loop lifecycle:** Confirm main loop persists for entire app lifetime (FastAPI uvicorn worker model). If using multiple workers, each needs separate SSI connection.

2. **SSI reconnect behavior:** Does ssi-fc-data auto-reconnect? Plan mentions it but no hook visible in code. May need manual reconnect detection.

3. **Channel R frequency:** Plan says 1000ms default but actual SSI interval unknown. Need live testing to confirm.

4. **Futures expiry:** Plan says "last Thursday" but VN market uses 3rd Thursday. Which is correct?

5. **Missing TotalVal in MI messages:** Assumption based on plan spec. Verify SSI actually sends `TotalVal` field in IndexMessage.

6. **SSI error response format:** What does SSI return on auth failure? Does `client.access_token()` raise exception or return error dict?

7. **Stream start() blocking behavior:** Does `stream.start()` block until connection established, or return immediately? Affects timeout strategy.

8. **Callback execution order:** If 10 Trade messages arrive in burst, are callbacks executed serially or parallel? Current code dispatches all in parallel (fire-and-forget tasks).
