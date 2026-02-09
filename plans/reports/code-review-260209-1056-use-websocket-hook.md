# Code Review: use-websocket.ts Hook

**File:** `/Users/minh/Projects/stock-tracker/frontend/src/hooks/use-websocket.ts`
**Reviewer:** code-reviewer (acb3e39)
**Date:** 2026-02-09
**Lines Analyzed:** 179
**Type Check:** PASS (tsc --noEmit)

---

## Scope
- **Files Reviewed:** `use-websocket.ts`, `use-polling.ts` (comparison)
- **Review Focus:** React hook correctness, WebSocket lifecycle, reconnect logic, fallback polling, edge cases, memory leaks
- **Type Safety:** Full TypeScript coverage, no `any` types

---

## Overall Assessment

**APPROVED with MINOR improvements recommended.**

Hook is well-structured, follows React best practices, implements exponential backoff correctly, and handles cleanup properly. Type safety is strong. A few edge cases could be hardened.

**Strengths:**
- Proper cleanup prevents memory leaks (`unmounted` flag + timer clearing)
- Exponential backoff with max delay cap
- Fallback polling with periodic WS retry (good UX)
- Type-safe generics (`useWebSocket<T>`)
- Follows existing `use-polling.ts` pattern (data/loading/error/status)
- No dependency stale closures (`optsRef.current`)

**Weaknesses:**
- Missing `refresh()` callback (pattern inconsistency vs `use-polling`)
- `status` can desync during fallback transitions
- No rate limiting for rapid reconnects
- Unhandled race: WS connects during fallback poll

---

## Critical Issues

**None.** No security vulnerabilities, data loss risks, or breaking changes detected.

---

## High Priority Findings

### H1. Missing `refresh()` Callback (Pattern Inconsistency)
**Issue:** `use-polling.ts` returns `{data, loading, error, refresh}`. This hook returns `{data, status, error, isLive}` but omits `refresh()`.

**Impact:** Users can't force immediate reconnect/refetch when needed (e.g., after network recovery).

**Fix:**
```typescript
export interface WebSocketResult<T> {
  data: T | null;
  status: ConnectionStatus;
  error: Error | null;
  isLive: boolean;
  refresh: () => void;  // Force reconnect or poll
}

// Inside effect, expose reconnect trigger:
const manualReconnect = useCallback(() => {
  attempts = 0;
  if (ws?.readyState === WebSocket.OPEN) return; // already connected
  stopFallback();
  connect();
}, []);

return { data, status, error, isLive, refresh: manualReconnect };
```

**Severity:** High (feature parity with `use-polling`, common UX need)

---

### H2. Race Condition: WS Opens During Fallback Poll
**Issue:** If WS reconnects while `pollTimer` is active, `stopFallback()` clears `pollTimer` but doesn't abort in-flight `fetcher()` promise.

**Scenario:**
1. Fallback polling starts, `fetcher()` called
2. WS opens mid-poll → `stopFallback()` called
3. `fetcher()` resolves → `setData()` overwrites fresh WS data

**Impact:** Brief data desync (REST data clobbers WS data).

**Fix:**
```typescript
let pollAbort = false;

const stopFallback = () => {
  inFallback = false;
  pollAbort = true;  // Signal abort
  clearInterval(pollTimer);
  clearInterval(retryTimer);
};

const poll = async () => {
  try {
    const result = await fetcher();
    if (!unmounted && !pollAbort) {  // Check abort flag
      setData(result);
      setError(null);
    }
  } catch (err) {
    if (!unmounted && !pollAbort) {
      setError(err instanceof Error ? err : new Error(String(err)));
    }
  }
};

// Reset abort flag in startFallback:
const startFallback = () => {
  pollAbort = false;
  // ...
};
```

**Severity:** High (data correctness)

---

## Medium Priority Improvements

### M1. `status` Desync During Fallback → WS Transition
**Issue:** When `retryTimer` triggers `connect()` while polling, `status` stays `"connected"` (line 116 skips `setStatus("connecting")` if `inFallback=true`). UI never shows "reconnecting" state.

**Fix:**
```typescript
const connect = () => {
  if (unmounted) return;
  setStatus("connecting");  // Always update status
  // ...
};
```

**Trade-off:** Flickers status briefly if WS fails again. Alternative: add `"reconnecting"` status.

**Severity:** Medium (UX clarity)

---

### M2. No Rate Limiting for Manual Reconnects
**Issue:** If `refresh()` is added (H1), rapid calls could DOS server or exhaust client resources.

**Fix:**
```typescript
const lastReconnect = useRef(0);
const MIN_RECONNECT_GAP_MS = 1000;

const manualReconnect = useCallback(() => {
  const now = Date.now();
  if (now - lastReconnect.current < MIN_RECONNECT_GAP_MS) return;
  lastReconnect.current = now;
  // ... reconnect logic
}, []);
```

**Severity:** Medium (DoS prevention)

---

### M3. Uninitialized Timer Variables
**Issue:** Lines 60-62 declare `reconnectTimer`, `pollTimer`, `retryTimer` without initializing. TypeScript infers `undefined` initially, but runtime may reference before assignment (unlikely but unsafe).

**Fix:**
```typescript
let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
let pollTimer: ReturnType<typeof setInterval> | undefined;
let retryTimer: ReturnType<typeof setInterval> | undefined;

// Cleanup:
return () => {
  unmounted = true;
  if (reconnectTimer) clearTimeout(reconnectTimer);
  stopFallback();
  // ...
};
```

**Severity:** Medium (type safety hardening)

---

### M4. `fallbackFetcher` Errors Don't Block WS Retry
**Issue:** If `fetcher()` throws repeatedly during fallback, `retryTimer` keeps attempting WS reconnects. If backend is truly down, this wastes resources.

**Recommendation:** Add circuit breaker (stop WS retries after N consecutive REST failures).

**Severity:** Medium (resource efficiency)

---

## Low Priority Suggestions

### L1. Missing JSDoc for Public API
**Issue:** Hook and types lack JSDoc comments for IntelliSense.

**Fix:**
```typescript
/**
 * WebSocket hook with auto-reconnect and REST polling fallback.
 * @template T - Message payload type
 * @param channel - WebSocket channel (market | foreign | index)
 * @param options - Configuration (token, fallback fetcher, intervals)
 * @returns {WebSocketResult<T>} data, status, error, isLive, refresh
 */
export function useWebSocket<T>(...) { ... }
```

**Severity:** Low (DX improvement)

---

### L2. Magic Numbers in Constants
**Issue:** `WS_RETRY_INTERVAL = 30_000` hardcoded. Should be configurable via options.

**Fix:**
```typescript
export interface UseWebSocketOptions<T> {
  // ...
  wsRetryIntervalMs?: number;  // Default: 30000
}
```

**Severity:** Low (flexibility)

---

### L3. Binary Frame Handling Undocumented
**Issue:** Comment says "binary ping frames auto-handled by browser" (line 130-136), but code silently ignores all non-JSON. Logging would help debugging.

**Recommendation:**
```typescript
ws.onmessage = (e) => {
  if (typeof e.data !== "string") return; // Binary frame, browser handles ping
  try {
    const msg = JSON.parse(e.data);
    if (msg?.type === "status") return;
    setData(msg as T);
  } catch (err) {
    console.warn(`[WebSocket] Invalid JSON on /ws/${channel}:`, e.data);
  }
};
```

**Severity:** Low (observability)

---

## Positive Observations

1. **No Memory Leaks:** `unmounted` flag guards all state updates, timers cleared in cleanup
2. **Exponential Backoff:** Correctly implements `2^attempts * BASE_DELAY_MS` with max cap
3. **Fallback UX:** Periodic WS retry during polling prevents permanent fallback
4. **Type Safety:** Full generic coverage, no `any`, proper `Error` coercion
5. **YAGNI Compliance:** No over-engineering, clear separation of concerns
6. **Ref Pattern:** `optsRef.current` avoids stale closure bug with `fallbackFetcher`

---

## Recommended Actions

### Immediate (Before Merge)
1. **Add `refresh()` callback** (H1) — required for pattern consistency
2. **Fix WS-during-poll race** (H2) — data correctness issue
3. **Initialize timer variables** (M3) — type safety

### Short-Term (Next PR)
4. **Fix status desync** (M1) — better UX
5. **Add rate limiting** (M2) — DoS prevention
6. **Add JSDoc** (L1) — DX improvement

### Optional (Future)
7. Circuit breaker for REST failures (M4)
8. Configurable `wsRetryIntervalMs` (L2)
9. Debug logging for binary/malformed frames (L3)

---

## Metrics
- **Type Coverage:** 100% (no `any`)
- **Linting Issues:** 0 (tsc passes)
- **Complexity:** Medium (175 LOC, 3 timers, 2 async flows)
- **Test Coverage:** Unknown (no tests found)

---

## Edge Cases Verified

✅ Unmount during reconnect delay → timers cleared
✅ Unmount during fallback poll → `unmounted` flag prevents state update
✅ Rapid channel switches → new effect cancels previous via cleanup
✅ Token change mid-session → effect re-runs, old WS closed
✅ `fallbackFetcher` undefined → fallback skipped gracefully
⚠️ WS opens during poll → race condition (H2)
⚠️ Manual reconnect spam → no rate limit (M2)

---

## Unresolved Questions

1. Should `status = "connected"` during fallback (line 84)? Alternative: add `"polling"` status for clarity
2. Should fallback polling start immediately or wait for first failure? Current: waits for 3 reconnect attempts
3. Do we need metrics/telemetry (reconnect count, fallback duration)? Not in scope for MVP
4. Should `onclose` fire reconnect if close code = 1000 (normal closure)? Current: always reconnects

---

**Conclusion:** High-quality implementation with minor edge case gaps. Fix H1-H2 before production use. M1-M3 recommended for next iteration.
