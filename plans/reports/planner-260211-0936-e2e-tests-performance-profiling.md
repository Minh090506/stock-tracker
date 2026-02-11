# Planning Report: E2E Tests & Performance Profiling

**Planner**: planner-260211-0936
**Date**: 2026-02-11
**Plan Location**: `/Users/minh/Projects/stock-tracker/plans/260211-0936-e2e-tests-performance-profiling/`

---

## Executive Summary

Comprehensive implementation plan for E2E test suite and performance profiling infrastructure. Plan includes 4 phases covering test infrastructure, 5 E2E scenarios, CPU/memory profiling script, and automated benchmark reporting.

**Effort**: 6 hours total
**Priority**: P1 (High)
**Status**: Ready for implementation

---

## Plan Structure

```
plans/260211-0936-e2e-tests-performance-profiling/
├── plan.md                                    # Overview (4 phases, success criteria)
├── phase-01-e2e-test-infrastructure.md        # Fixtures, factories, wired system (1.5h)
├── phase-02-e2e-test-scenarios.md             # 5 test files, 20+ tests (2h)
├── phase-03-performance-profiling.md          # Profiling script (1.5h)
└── phase-04-benchmark-report.md               # Report generator + CI integration (1h)
```

---

## Phase Breakdown

### Phase 1: E2E Test Infrastructure (1.5h)

**Files Created**:
- `backend/tests/e2e/__init__.py`
- `backend/tests/e2e/conftest.py` (~200 LOC)

**Key Components**:
- **Fixtures**: `processor`, `connection_managers`, `wired_system`
- **SSI Factories**: `ssi_factories.quote()`, `.trade()`, `.foreign()`, `.index()`, `.futures_trade()`
- **Test Utilities**: `ws_client_simulator`, `assert_timing`

**Architecture**: Fully wired processor → publisher → managers (all real, SSI mocked at message level)

**Validation**: Smoke test verifies fixtures work before Phase 2

---

### Phase 2: E2E Test Scenarios (2h)

**Files Created** (5 test files, 20+ test methods):

1. **`test_full_flow.py`** (8 tests)
   - Quote/trade updates reach WS clients
   - Trade classification end-to-end
   - Multi-symbol aggregation
   - Index/derivatives channels
   - Multiple clients + channel isolation

2. **`test_foreign_tracking.py`** (4 tests)
   - Foreign updates accumulate correctly
   - Summary aggregates multiple symbols
   - Top buy/sell detection
   - Speed calculation

3. **`test_alert_flow.py`** (3 tests)
   - Volume spike alert generation
   - Foreign acceleration alert
   - Alert deduplication (60s window)

4. **`test_reconnect_recovery.py`** (3 tests)
   - Disconnect status notification
   - Reconnect status notification
   - Data resumes after reconnect

5. **`test_session_lifecycle.py`** (4 tests)
   - ATO trades classified separately
   - Continuous/ATC phase separation
   - Session reset behavior
   - Phase invariant (sum == total)

**Coverage**: Full data flow from SSI ingestion through WS delivery, validates cross-component integration

---

### Phase 3: Performance Profiling (1.5h)

**File Created**:
- `backend/scripts/profile-performance-benchmarks.py` (~400 LOC, executable)

**Profiling Modes**:
1. **CPU** (cProfile + snakeviz)
   - Message throughput (msg/s)
   - Average latency (ms)
   - Top CPU consumers
   - Outputs: `cpu_profile.prof`, `cpu_profile.html`

2. **Memory** (tracemalloc)
   - Baseline → peak delta
   - Top 10 allocators
   - Output: `memory_stats.txt`

3. **Asyncio**
   - Active task count
   - Event loop lag (ms)

4. **Database**
   - Pool size, active/idle connections
   - Utilization percentage

**Output**: `performance_results.json` (structured for Phase 4)

**Usage**:
```bash
# Full profile
./backend/scripts/profile-performance-benchmarks.py

# CPU only
./backend/scripts/profile-performance-benchmarks.py --mode cpu

# Custom output
./backend/scripts/profile-performance-benchmarks.py --output my_results.json
```

---

### Phase 4: Benchmark Report (1h)

**Files Created**:
- `backend/scripts/generate-benchmark-report.py` (~300 LOC)
- `docs/benchmark-results.md` (auto-generated template)

**Features**:
- Reads `performance_results.json` from Phase 3
- Evaluates metrics against thresholds (pass/warning/fail)
- Generates markdown report with:
  - Executive summary (overall status)
  - CPU performance table
  - Memory performance table
  - Asyncio metrics
  - Database metrics
  - Load testing results (optional Locust integration)
  - Baseline comparison (optional)
  - Recommendations

**Thresholds**:
```
CPU:       ≥5000 msg/s (target), ≤0.5ms latency (target)
Memory:    ≤50MB delta @ 50K msgs (target)
Asyncio:   ≤1ms event loop lag (target)
WebSocket: ≤100ms p99 latency (target)
REST:      ≤200ms p95 latency (target)
```

**Usage**:
```bash
# Generate report
./backend/scripts/generate-benchmark-report.py

# With baseline comparison
./backend/scripts/generate-benchmark-report.py --baseline baseline_2026-02-01.json
```

**CI Integration**: GitHub Actions example provided (performance smoke test on master push)

---

## Implementation Guidelines

### Testing Philosophy

**E2E Tests**:
- Mock SSI at stream boundary (factory functions)
- All other components REAL (processor, trackers, publishers)
- Validate data correctness at WS client endpoint
- Target: <30s total runtime for all E2E tests

**Profiling**:
- Internal service performance under controlled load
- Complements external load testing (Locust)
- Establishes performance baselines
- Outputs JSON for automation

### File Naming Conventions

**Python test files**: Use snake_case (Python language constraint)
- `test_full_flow.py`
- `conftest.py`

**Scripts**: Use kebab-case with descriptive names
- `profile-performance-benchmarks.py` ✅
- `generate-benchmark-report.py` ✅

### Key Patterns from Existing Tests

**From `test_data_processor_integration.py`**:
- Use pytest fixtures for processor setup
- Seed quotes before trades (classifier needs bid/ask)
- Verify invariants (phase sum == total)
- Use `pytest.approx()` for float comparisons

**From `test_websocket.py`**:
- Use `httpx.AsyncClient` with `TestClient` for WS testing
- Mock settings with `patch()` context manager
- Validate JSON structure with `json.loads()`
- Test channel isolation (market vs foreign)

**From Locust suite**:
- Structure: `locustfile.py` imports all scenario users
- Scenarios: market_stream, foreign_flow, burst_test, reconnect_storm
- Performance baselines: p99 < 100ms WS, p95 < 200ms REST

---

## Success Criteria Summary

### Phase 1
- [ ] `conftest.py` created with all fixtures
- [ ] SSI factories support all message types
- [ ] `wired_system` fixture successfully wires components
- [ ] Smoke test passes

### Phase 2
- [ ] All 5 test files pass (20+ tests)
- [ ] E2E tests complete in <30s
- [ ] No flaky tests (verified with 3x runs)
- [ ] Coverage adds 5%+ to integration tests

### Phase 3
- [ ] Script runs in all modes (cpu, memory, asyncio, db)
- [ ] CPU profile generates snakeviz HTML
- [ ] JSON output contains all required fields
- [ ] Script completes in <60s for defaults

### Phase 4
- [ ] Report generator reads JSON and evaluates thresholds
- [ ] Markdown report generated in `docs/`
- [ ] Pass/warning/fail statuses accurate
- [ ] Recommendations section actionable
- [ ] Baseline comparison works

---

## Dependencies

**New**:
- snakeviz (optional): `pip install snakeviz`

**Existing**:
- pytest + pytest-asyncio
- httpx (for WS testing)
- cProfile, pstats, tracemalloc (stdlib)
- asyncio (stdlib)

---

## Risks & Mitigation

**Low Risk** — Non-blocking implementation:
- E2E tests use existing patterns
- Profiling uses stdlib modules
- No production code changes

**Mitigation**:
- Isolated E2E fixtures (no shared state)
- Profile script runs separately (not in CI initially)
- Template-based report generation

---

## Integration Points

### With Existing Codebase

**Uses**:
- `MarketDataProcessor` (all services wired)
- `DataPublisher` (event-driven broadcasting)
- `ConnectionManager` (WS client management)
- `AlertService` + `PriceTracker` (Phase 6 analytics)
- SSI message models (`ssi_messages.py`)

**Extends**:
- Test suite: `backend/tests/e2e/` (new directory)
- Scripts: `backend/scripts/` (2 new scripts)
- Docs: `docs/benchmark-results.md` (new file)

### With CI/CD

**GitHub Actions Integration** (optional Phase 4 task):
- Add `performance-smoke-test` job after backend tests
- Run CPU profiling with 1000 messages (fast)
- Check throughput threshold (≥3000 msg/s)
- Upload artifacts for historical tracking

---

## Performance Baselines (To Be Established)

| Metric | Target | Status |
|--------|--------|--------|
| CPU throughput | ≥5000 msg/s | 🔜 TBD |
| Avg latency | ≤0.5ms | 🔜 TBD |
| Memory delta @ 50K | ≤50MB | 🔜 TBD |
| Event loop lag | ≤1ms | 🔜 TBD |
| WS p99 latency | ≤100ms | ✅ 85-95ms (Locust) |
| REST p95 latency | ≤200ms | ✅ 175-195ms (Locust) |

**Note**: WS/REST metrics already validated by existing Locust suite (Phase 8B). Internal profiling will establish CPU/memory baselines.

---

## Execution Order

1. **Phase 1** → Implement fixtures, verify with smoke test
2. **Phase 2** → Implement 5 E2E test files incrementally, run after each
3. **Phase 3** → Implement profiling script, test all modes
4. **Phase 4** → Implement report generator, generate initial baseline

**Parallel Track** (optional): CI integration can be added after Phase 4 completion

---

## Documentation Updates

After completion, update:
- `docs/system-architecture.md` → Add "Testing Strategy" section referencing E2E tests
- `README.md` → Add performance benchmarking section
- `docs/deployment-guide.md` → Reference benchmark reports

---

## Unresolved Questions

None — plan is complete and ready for implementation.

---

## Next Steps

1. Delegate to `implementer` agent with Phase 1 (E2E infrastructure)
2. After Phase 1 passes, continue with Phase 2 (E2E scenarios)
3. After Phase 2 passes, implement Phase 3 (profiling script)
4. After Phase 3 works, implement Phase 4 (report generator)
5. Delegate to `tester` agent for full E2E + profiling validation
6. Delegate to `code-reviewer` agent for code review
7. Delegate to `docs-manager` agent to update system architecture docs

---

**Plan Status**: ✅ Complete and ready for implementation
**Location**: `/Users/minh/Projects/stock-tracker/plans/260211-0936-e2e-tests-performance-profiling/`
