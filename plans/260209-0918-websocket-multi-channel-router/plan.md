---
title: "WebSocket Multi-Channel Router"
description: "Add 3 WebSocket channels with auth and rate limiting"
status: complete
priority: P2
effort: 3h
branch: master
tags: [websocket, authentication, rate-limiting, backend]
created: 2026-02-09
completed: 2026-02-09
---

# WebSocket Multi-Channel Router

## Overview
Add multi-channel WebSocket router with 3 specialized endpoints for real-time data streaming, plus token-based authentication and IP-based rate limiting.

## Current Architecture
- Single endpoint `/ws/market` broadcasts full MarketSnapshot every 1s
- Generic ConnectionManager with per-client queues
- No authentication or rate limiting
- Broadcast loop started in app lifespan

## Target Architecture
**3 WebSocket Channels:**
- `/ws/market` — full MarketSnapshot (VN30 quotes + indices + foreign + derivatives)
- `/ws/foreign` — ForeignSummary only (aggregate + top movers)
- `/ws/index` — IndexData for VN30 + VNINDEX only

**Security:**
- Token-based auth via query param `?token=xxx`
- IP-based rate limiting (configurable max connections per IP)
- Reject unauthorized connections before accepting WebSocket

**Implementation:**
- New `router.py` with 3 endpoints
- Auth middleware extracts and validates token
- Rate limiter tracks connections per IP
- Broadcast loop feeds 3 separate ConnectionManagers
- Delete `endpoint.py` (migrated to router)

## Data Sources Available
- `MarketDataProcessor.get_market_snapshot()` → MarketSnapshot
- `MarketDataProcessor.get_foreign_summary()` → ForeignSummary
- `IndexTracker.get_all()` → dict[str, IndexData]

## Phases

### Phase 1: Router and Auth (1.5h) ✅ COMPLETE
[phase-01-router-and-auth.md](./phase-01-router-and-auth.md)
- ✅ Create `websocket/router.py` with 3 endpoints
- ✅ Auth middleware with token validation
- ✅ IP-based rate limiter
- ✅ Config settings for token and rate limits

### Phase 2: Broadcast and Wiring (1h) ✅ COMPLETE
[phase-02-broadcast-and-wiring.md](./phase-02-broadcast-and-wiring.md)
- ✅ Update broadcast_loop to feed 3 managers
- ✅ Register router in main.py
- ✅ Delete endpoint.py
- ✅ Update lifespan to start 3-channel broadcast

### Phase 3: Tests (0.5h) ✅ COMPLETE
[phase-03-tests.md](./phase-03-tests.md)
- ✅ Update existing WebSocket tests
- ✅ Add auth/rate limit tests
- ✅ Verify 3 channels broadcast correctly

## Success Criteria
- ✅ 3 WebSocket endpoints respond with correct data types
- ✅ Unauthorized connections rejected before handshake
- ✅ Rate limiter enforces per-IP connection limits
- ✅ All tests pass (254 total, was 247, +7 net new)
- ✅ No code duplication (DRY via `_ws_lifecycle` helper)

## Review Results
**Date:** 2026-02-09
**Status:** ✅ APPROVED FOR MERGE
**Report:** [code-reviewer-260209-0918-websocket-multi-channel-router.md](../reports/code-reviewer-260209-0918-websocket-multi-channel-router.md)

**Summary:**
- Implementation complete, all tests passing
- DRY refactor with `_ws_lifecycle` eliminates 45 LOC duplication
- Zero-cost idle optimization working correctly
- Security model appropriate for internal tool
- Minor recommendation: Update `.env.example` before commit

## Constraints
- Python 3.12, snake_case files
- Files under 200 LOC
- Reuse existing ConnectionManager
- Zero breaking changes to existing endpoints
