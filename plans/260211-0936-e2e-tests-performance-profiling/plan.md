---
title: "E2E Tests & Performance Profiling"
description: "Comprehensive E2E test suite and performance profiling infrastructure"
status: complete
priority: P1
effort: 6h
branch: master
tags: [testing, e2e, performance, profiling, pytest]
created: 2026-02-11
---

# E2E Tests & Performance Profiling Implementation Plan

## Overview

Add comprehensive E2E test coverage and performance profiling infrastructure to validate full system behavior under realistic conditions and establish performance baselines.

## Objectives

1. **E2E Test Coverage**: End-to-end scenarios covering SSI stream → processor → WebSocket clients
2. **Performance Profiling**: CPU, memory, asyncio task monitoring with automated report generation
3. **Benchmark Documentation**: Auto-generated performance reports with baseline metrics
4. **Integration with CI**: Performance smoke tests in GitHub Actions

## Architecture Context

```
SSI Mock → MarketDataProcessor → DataPublisher → WS ConnectionManager → Test Client
           ├─ QuoteCache
           ├─ TradeClassifier
           ├─ SessionAggregator
           ├─ ForeignInvestorTracker
           ├─ IndexTracker
           └─ DerivativesTracker
```

## Current Test Coverage

- **Unit Tests**: 19 files (isolated service tests)
- **Integration Tests**: 3 files (test_data_processor_integration.py, test_websocket.py, etc.)
- **Load Tests**: Locust suite (backend/tests/load/)

## Phases

### Phase 1: E2E Test Infrastructure (1.5h)
**Status**: ✅ Complete
**File**: `phase-01-e2e-test-infrastructure.md`

- Create `backend/tests/e2e/` directory
- Implement `conftest.py` with shared fixtures
- SSI message factory functions
- Wired processor + publisher + WS managers fixture

### Phase 2: E2E Test Scenarios (2h)
**Status**: ✅ Complete
**File**: `phase-02-e2e-test-scenarios.md`

- `test_full_flow.py`: SSI → processor → WS push → client receives
- `test_foreign_tracking.py`: Channel R → ForeignTracker → WS foreign channel
- `test_alert_flow.py`: Anomaly → AlertService → WS alert channel
- `test_reconnect_recovery.py`: Connection failure → auto-reconnect → data resumes
- `test_session_lifecycle.py`: Pre-market → ATO → Continuous → ATC state transitions

### Phase 3: Performance Profiling (1.5h)
**Status**: ✅ Complete
**File**: `phase-03-performance-profiling.md`

- Single `backend/scripts/profile.py` script
- cProfile + snakeviz for CPU profiling
- tracemalloc for memory profiling
- asyncio task monitoring
- DB connection pool metrics
- JSON output for automation

### Phase 4: Benchmark Report (1h)
**Status**: ✅ Complete
**File**: `phase-04-benchmark-report.md`

- Template: `docs/benchmark-results.md`
- Auto-generated from profiling + Locust results
- Performance baselines with pass/fail thresholds
- CI integration for smoke tests

## Success Criteria

- [ ] All 5 E2E test files pass (15+ test methods)
- [ ] E2E tests run in <30s total
- [ ] Profiling script outputs JSON results
- [ ] Benchmark report template auto-fills from profiling data
- [ ] CI runs E2E smoke tests on master push
- [ ] Performance baselines documented:
  - Message processing: <5ms per trade
  - WS broadcast: <100ms p99 latency
  - Memory: <100MB under sustained load
  - CPU: <50% single core at 1000 msg/s

## Dependencies

- pytest + pytest-asyncio
- httpx.AsyncClient for WS testing
- cProfile, tracemalloc (stdlib)
- snakeviz (pip install)
- Existing Locust suite for load baselines

## Risk Assessment

**Low Risk**:
- E2E tests use existing patterns from integration tests
- Profiling uses stdlib modules (no new deps)
- Non-blocking: doesn't modify production code

**Mitigation**:
- Keep E2E fixtures isolated (no shared state between tests)
- Profile script runs separately (not in CI initially)
- Benchmark report template-based (no code generation)

## Next Steps After Completion

1. Phase 9: Real-time charting improvements
2. Phase 10: Historical data analytics
3. Ongoing: Monitor performance regressions in CI
