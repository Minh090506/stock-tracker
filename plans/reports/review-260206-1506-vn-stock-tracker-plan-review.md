# Plan Review: VN Stock Tracker (Revised)

**Plan:** `plans/260206-1418-vn-stock-tracker-revised/`
**Reviewer:** Orchestrator
**Date:** 2026-02-06

---

## Summary

8-phase plan for real-time VN30 stock tracker. Python FastAPI + React + PostgreSQL. SSI FastConnect as sole data source. Covers stock board, index tracking, derivatives/basis, foreign investor monitoring, active buy/sell classification, and analytics alerts. Total estimated effort: 38h.

## Strengths

1. **Well-corrected from old plan** - Clear diff table showing what was wrong (TotalVol, HOSE.VNM format, missing vnstock) and what's fixed
2. **Per-trade classification fixed** - Uses `LastVol` (per-trade) instead of `TotalVol` (cumulative). Critical correctness fix.
3. **SSI-only simplification** - Removed vnstock + TCBS dependencies. Single data source = less fragility
4. **Comprehensive domain coverage** - 6 features: stock board, indices, derivatives, foreign tracking, buy/sell classification, analytics
5. **Batch DB writes** - 1s flush interval, avoids per-trade INSERT overhead
6. **Foreign delta computation** - Correctly handles cumulative → delta conversion from Channel R
7. **Alert system with cooldown** - Prevents spam, skip first 5 min initialization
8. **Clean WS protocol** - Well-defined message types with snapshot on connect
9. **VN market conventions** - Correct color coding (red=up, green=down, fuchsia=ceiling, cyan=floor)

## Critical Issues

### 1. Python kebab-case filenames - BLOCKER
**Affected:** ALL phases (2-7)

Plan specifies kebab-case filenames for Python modules:
- `ssi-auth-service.py`, `ssi-stream-service.py`, `quote-cache.py`, `trade-classifier.py`, etc.

**Problem:** Python cannot import modules with hyphens. `from app.services.ssi-auth-service import ...` is a SyntaxError.

**Fix:** Use snake_case: `ssi_auth_service.py`, `quote_cache.py`, `trade_classifier.py`, etc. Or use underscored kebab: keep descriptive naming but with underscores.

### 2. `_normalize_fields` filter logic - BUG
**Affected:** Phase 02, line 278 of ssi-stream-service

```python
return {mapping.get(k, k): v for k, v in content.items() if mapping.get(k, k)}
```

**Problem:** Unmapped SSI fields (e.g., `RType`, `MarketId`, etc.) pass through with PascalCase keys, then fail Pydantic validation since models only define snake_case fields.

**Fix:** Filter to only mapped keys:
```python
return {mapping[k]: v for k, v in content.items() if k in mapping}
```

### 3. Fire-and-forget asyncio tasks
**Affected:** Phase 02, stream service demux

```python
asyncio.create_task(cb(msg))  # No reference stored, no error handling
```

**Problem:** Tasks may be garbage collected before completion. Exceptions silently swallowed.

**Fix:** Store task references in a set, add `task.add_done_callback()` for error logging.

### 4. VN30F contract rollover not handled
**Affected:** Phase 02, `get_current_futures_symbol()`

```python
def get_current_futures_symbol() -> str:
    return f"VN30F{now.strftime('%y%m')}"
```

**Problem:** Near expiry (3rd Thursday of month), the active contract transitions to next month. On expiry week, this function returns the wrong contract symbol.

**Fix:** Either subscribe to both current + next month contracts, or implement rollover detection (check if current month contract still has volume).

### 5. MarketDataStream.start() blocking - should be primary path
**Affected:** Phase 02

Plan notes `start()` may block as a risk, with `asyncio.to_thread()` as backup. Given SignalR's nature, **blocking is the expected behavior**.

**Fix:** Make `asyncio.to_thread()` the DEFAULT implementation, not a fallback. Test confirms/denies.

## Medium Issues

### 6. No SSI reconnection data reconciliation
When WS reconnects after disconnect, foreign cumulative values may have jumped. First delta after reconnect could be huge and incorrect. Need to detect reconnection and skip first foreign update (treat as initialization).

### 7. BatchWriter unbounded queue growth
Risk assessment mentions this but no implementation. If DB is down, trade queue grows unbounded → OOM.

**Fix:** Add `maxlen` to deques or drop old records with warning when queue exceeds threshold.

### 8. `executemany` vs `copy_records_to_table`
asyncpg's `executemany` is significantly slower than `copy_records_to_table` for bulk inserts. For a 1s batch of potentially hundreds of trades, `copy` is the better choice.

### 9. Missing nginx.conf for frontend WS proxy
Phase 08 references `nginx.conf` for WS proxying but doesn't provide the config. WS upgrade headers (`Upgrade`, `Connection`) must be explicitly forwarded.

### 10. No frontend reconnection state handling
When WS reconnects, should stale data be cleared? Should a fresh snapshot be requested? Current plan doesn't address post-reconnect data consistency.

## Minor Issues

11. **Alembic setup steps missing** - Phase 07 mentions Alembic but doesn't detail `alembic init` or migration workflow
12. **No rate limiting** on REST endpoints (acceptable for internal tool, note for future)
13. **No Docker HEALTHCHECK** in Dockerfiles
14. **Foreign history deque maxlen=600** assumes 1 msg/sec but Channel R frequency is unknown
15. **Frontend test framework not specified** (presumably Vitest since Vite is used)
16. **No CI/CD pipeline** mentioned in Phase 08
17. **Missing React error boundaries** for crash resilience
18. **`deque` for `_basis_history` maxlen=3600** - comment says "~1h at 1/sec" but basis updates depend on futures trade frequency, which varies greatly

## Architecture Assessment

**Overall: SOLID.** The data flow is clean:
```
SSI → Demux → Cache/Classify/Track → Broadcast → React
                                   → BatchWrite → PostgreSQL
```

Dependencies between phases are well-mapped. Phase 7 (DB) can run in parallel with Phase 2 (schema setup) - good optimization opportunity.

## Effort Assessment

| Phase | Estimated | Assessment |
|-------|-----------|------------|
| P1: Scaffolding | 3h | Realistic |
| P2: SSI Integration | 5h | **6-7h** - SignalR behavior unknown, may need raw client |
| P3: Data Processing | 6h | Realistic |
| P4: Backend WS + REST | 4h | Realistic |
| P5: Frontend | 6h | **7-8h** - Many components, TradingView integration |
| P6: Analytics | 5h | Realistic |
| P7: Database | 5h | Realistic |
| P8: Testing | 4h | **5-6h** - 80% coverage target is ambitious |
| **Total** | **38h** | **~42-46h** realistic |

Phase 2 and Phase 5 are most likely to exceed estimates due to unknowns (SignalR blocking behavior, TradingView Charts API).

## Recommendations

1. **Fix Python filenames** to snake_case before implementation - affects every import statement
2. **Fix `_normalize_fields`** filter logic - will cause runtime errors immediately
3. **Make `asyncio.to_thread()`** the default SSI connection strategy
4. **Add reconnection handling** - skip first foreign delta after reconnect
5. **Subscribe both current + next month VN30F** contracts to handle rollover
6. **Cap BatchWriter queues** at ~10K records with drop-oldest policy
7. **Use `copy_records_to_table`** instead of `executemany` for batch inserts
8. **Create nginx.conf** template in Phase 01 scaffolding

## Verdict

**APPROVE with fixes.** Plan is well-structured and technically sound. The 5 critical issues are all implementation bugs, not architectural problems. Fix them during Phase 2-3 implementation and proceed.

## Resolved Questions

1. **Channel R update frequency:** Unknown at build time. Configurable via `CHANNEL_R_INTERVAL_MS` env (default 1000ms). Speed calculation adapts to actual observed interval.
2. **ssi-fc-data async support:** Treat as sync-only. Always wrap with `asyncio.to_thread()` — this is the default strategy, not a fallback.
3. **VN30F contract listing:** No SSI API for active contract. Use pattern `VN30F{YYMM}`, subscribe both current+next month. `FUTURES_OVERRIDE` env for manual control during rollover edge cases.
4. **HNX/UPCoM scope:** MVP targets HOSE VN30 only. Schema includes `exchange` field so data model supports future expansion to HNX/UPCoM without migration.
