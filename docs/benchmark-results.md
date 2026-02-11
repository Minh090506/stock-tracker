# Performance Benchmark Report

**Generated**: 2026-02-11 09:56:02

## Summary

**Overall**: ✅ PASS — 2 passed, 0 warnings, 0 failed

**Environment**: Local Development

## CPU Performance

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Throughput | 58,874 msg/s | ≥5000 msg/s | ✅ PASS |
| Avg Latency | 0.017ms | ≤0.5ms | ✅ PASS |
| Total Time | 0.02s | - | - |
| Messages | 1,000 | - | - |

### Top CPU Consumers

| Function | Cumulative Time (s) |
|----------|---------------------|
| `runners.py:160(run)` | 0.017 |
| `base_events.py:655(run_until_complete)` | 0.017 |
| `base_events.py:631(run_forever)` | 0.017 |
| `base_events.py:1922(_run_once)` | 0.017 |
| `runners.py:86(run)` | 0.017 |

## Memory Performance

*Memory profiling data not available.*

## Asyncio Performance

*Asyncio monitoring data not available.*

## Database Pool

*Database not available (app runs in graceful-degradation mode).*

## Recommendations

- All metrics within target — no action required

---

### How to Reproduce

```bash
cd backend
./venv/bin/python scripts/profile-performance-benchmarks.py
./venv/bin/python scripts/generate-benchmark-report.py
```
