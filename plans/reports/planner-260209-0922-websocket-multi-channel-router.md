# Plan Report: WebSocket Multi-Channel Router

**Agent:** planner
**Plan ID:** 260209-0918-websocket-multi-channel-router
**Date:** 2026-02-09
**Status:** Complete

## Summary
Created implementation plan for adding multi-channel WebSocket router with 3 specialized endpoints, token-based authentication, and IP-based rate limiting.

## Plan Location
`/Users/minh/Projects/stock-tracker/plans/260209-0918-websocket-multi-channel-router/`

## Files Created
1. **plan.md** — Overview (60 lines)
2. **phase-01-router-and-auth.md** — Router, auth, rate limiting (350 lines)
3. **phase-02-broadcast-and-wiring.md** — Broadcast loop updates, main.py wiring (200 lines)
4. **phase-03-tests.md** — Test updates for 3 channels, auth, rate limits (380 lines)

## Plan Structure

### Phase 1: Router and Auth (1.5h)
**Deliverables:**
- `backend/app/websocket/router.py` (new, ~180 LOC)
- Config settings: `ws_auth_token`, `ws_max_connections_per_ip`
- 3 WebSocket endpoints: `/ws/market`, `/ws/foreign`, `/ws/index`
- RateLimiter class with IP tracking
- Auth middleware with token validation
- Heartbeat mechanism (copied from endpoint.py)

**Key Implementation:**
- Auth checks BEFORE `ws.accept()` to reject early
- Rate limiter increments on connect, decrements in finally block
- Circular import avoided via import-in-function pattern
- Each endpoint follows same structure (DRY via shared helpers)

### Phase 2: Broadcast and Wiring (1h)
**Deliverables:**
- Updated `broadcast_loop.py` — feeds 3 managers with 3 data types
- Updated `main.py` — 3 ConnectionManager instances, router registration
- Deleted `endpoint.py` (replaced by router.py)

**Key Implementation:**
- Broadcast loop accepts 4 params: processor + 3 managers
- Per-channel client count check before serialization (zero-cost idle)
- Market channel → MarketSnapshot
- Foreign channel → ForeignSummary
- Index channel → dict[str, IndexData] (manual JSON serialization)

### Phase 3: Tests (0.5h)
**Deliverables:**
- Updated `test_websocket_endpoint.py` — all tests work with 3 managers
- New TestAuthentication class (3 tests)
- New TestRateLimiting class (3 tests)
- Updated TestBroadcastLoop (4 tests with 3 channels)

**Key Implementation:**
- Manager fixtures for each channel
- Mock fixtures for ForeignSummary and IndexData
- Auth tests verify token validation and disabled-auth mode
- Rate limit tests verify increment/decrement and threshold enforcement
- Broadcast tests verify JSON serialization for all 3 data types

## Architecture Decisions

### 1. Reuse ConnectionManager (KISS)
- Existing ConnectionManager is generic, per-client queue pattern works for all channels
- Create 3 instances instead of extending class
- Zero changes to connection_manager.py

### 2. Token-Based Auth (YAGNI)
- Simple query param `?token=xxx` sufficient for internal tool
- No user database, no JWT, no OAuth (over-engineering)
- Empty token setting disables auth (dev mode)

### 3. IP-Based Rate Limiting (KISS)
- Simple dict[str, int] tracks connections per IP
- No sliding window, no token bucket (unnecessary complexity)
- Acceptable bypass via proxies (internal tool, trusted network)

### 4. Per-Channel Broadcast (DRY)
- Single broadcast loop with 3 conditional serializations
- Skip serialization when channel has zero clients
- Avoids duplicate broadcast loop tasks

### 5. Manual JSON for Index Channel (Pragmatic)
- IndexData dict needs manual serialization (not a Pydantic model itself)
- `json.dumps({k: v.model_dump() for k, v in indices.items()})`
- Simple, readable, works

## Data Flow

### Market Channel
```
SSI Stream → MarketDataProcessor
→ get_market_snapshot() → MarketSnapshot (Pydantic)
→ model_dump_json() → market_ws_manager.broadcast()
→ Per-client queue → WebSocket send
```

### Foreign Channel
```
SSI Channel R → ForeignInvestorTracker
→ get_foreign_summary() → ForeignSummary (Pydantic)
→ model_dump_json() → foreign_ws_manager.broadcast()
→ Per-client queue → WebSocket send
```

### Index Channel
```
SSI Channel MI → IndexTracker
→ get_all() → dict[str, IndexData]
→ json.dumps(manual dict comp) → index_ws_manager.broadcast()
→ Per-client queue → WebSocket send
```

## Code Changes Summary

### New Files
- `backend/app/websocket/router.py` (~180 LOC)

### Modified Files
- `backend/app/config.py` (+2 settings)
- `backend/app/websocket/broadcast_loop.py` (function signature + 3 channels)
- `backend/app/main.py` (3 managers, router import, lifespan updates)
- `backend/tests/test_websocket_endpoint.py` (fixtures + 10 new tests)

### Deleted Files
- `backend/app/websocket/endpoint.py` (52 LOC, replaced by router.py)

### Net LOC Change
- Added: ~180 (router) + ~50 (broadcast updates) + ~200 (tests) = +430 LOC
- Removed: ~52 (endpoint) = -52 LOC
- **Net: +378 LOC**

## Security Considerations

### Acceptable Risks (Internal Tool)
- Token in URL query params (visible in logs, browser history)
- IP-based rate limiting (bypassed with proxies)
- No encryption beyond WSS/HTTPS
- No user sessions or advanced auth

### Mitigations
- Document token visibility limitation
- Use strong random token in production
- Rate limit prevents basic DoS
- Auth failures logged with IP address

## Testing Strategy

### Unit Tests
- RateLimiter class methods (check, increment, decrement)
- Auth helper functions (valid/invalid token, disabled mode)
- Broadcast loop with 3 managers

### Integration Tests
- Full WebSocket connection flow per channel
- Auth rejection before handshake
- Rate limit enforcement across multiple connections
- JSON serialization correctness per channel

### Manual Testing Checklist
- [ ] Connect to `/ws/market` with valid token → receives MarketSnapshot
- [ ] Connect to `/ws/foreign` with valid token → receives ForeignSummary
- [ ] Connect to `/ws/index` with valid token → receives IndexData dict
- [ ] Connect without token (auth enabled) → rejected with 403
- [ ] Exceed rate limit → rejected with 429
- [ ] 6th connection from same IP rejected (default limit=5)
- [ ] Disconnect decrements rate limiter count

## Performance Impact

### Broadcast Loop
- **Before:** 1 serialization per iteration (MarketSnapshot only)
- **After:** 3 serializations per iteration (if all channels have clients)
- **Mitigation:** Per-channel client count check, skip if zero clients
- **Expected:** Negligible impact (serialization is fast, <5ms per model)

### Memory
- **Before:** 1 ConnectionManager with N clients
- **After:** 3 ConnectionManagers with potentially 3N clients
- **Expected:** Minor increase (50-100KB per client queue)

### Network
- **Before:** All clients receive full snapshot (~50KB/msg)
- **After:** Clients can subscribe to smaller payloads
  - Foreign: ~5KB/msg
  - Index: ~2KB/msg
- **Expected:** Reduced bandwidth for filtered clients

## Constraints Honored

### YAGNI
- No user auth system (token-based sufficient)
- No advanced rate limiting (simple IP counter works)
- No WebSocket compression (HTTP/2 handles it)
- No channel subscriptions API (3 endpoints simpler than pub/sub)

### KISS
- Reuse ConnectionManager (no inheritance, no abstraction)
- Single broadcast loop (not 3 separate tasks)
- Manual JSON serialization for dict (no custom encoder)
- Shared helpers via functions (not base classes)

### DRY
- 3 endpoints share _authenticate, _check_rate_limit, _heartbeat helpers
- Broadcast loop conditionally serializes per channel (no code duplication)
- Tests use fixtures for managers and mock data

### File Size
- router.py: ~180 LOC (target: <200)
- broadcast_loop.py: ~60 LOC (target: <200)
- main.py: ~130 LOC (target: <200)
- test_websocket_endpoint.py: ~400 LOC (target: <500 for tests)

## Risks and Mitigation

### Risk: Circular Import (High)
**Mitigation:** Import managers inside endpoint functions (proven pattern from endpoint.py)

### Risk: Rate Limiter Memory Leak (Medium)
**Mitigation:** Always decrement in finally block, defaultdict prevents KeyError

### Risk: Token Exposure in Logs (Low)
**Mitigation:** Document limitation, acceptable for internal tool

### Risk: Test Flakiness (Low)
**Mitigation:** Avoid exact call count assertions, use `>=`, cancel tasks in finally

### Risk: Breaking Existing Tests (Medium)
**Mitigation:** Update all broadcast loop tests to accept 3 managers, add new fixtures

## Success Criteria Checklist
- [ ] 3 WebSocket endpoints respond with correct data types
- [ ] Auth rejects invalid tokens before handshake
- [ ] Rate limiter enforces per-IP connection limits
- [ ] Broadcast loop feeds 3 managers correctly
- [ ] All 247 existing tests pass
- [ ] 10+ new tests for auth/rate limit pass
- [ ] Files stay under 200 LOC
- [ ] No code duplication
- [ ] No syntax errors
- [ ] Linter passes

## Next Steps
1. Delegate to `coder` agent to implement Phase 1
2. Delegate to `coder` agent to implement Phase 2
3. Delegate to `tester` agent to run Phase 3 tests
4. Delegate to `code-reviewer` agent to review implementation
5. Delegate to `docs-manager` agent to update system architecture docs

## Unresolved Questions
None — plan is implementation-ready.

---

**Plan complete.** Ready for implementation.
