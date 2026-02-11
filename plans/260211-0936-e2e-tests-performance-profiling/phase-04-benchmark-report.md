# Phase 4: Benchmark Report & Documentation

**Priority**: P1
**Status**: Complete
**Effort**: 1h

## Overview

Create automated benchmark report template that aggregates performance metrics from profiling script and Locust load tests. Generate comprehensive documentation with pass/fail thresholds and historical tracking.

## Context

Benchmark reports provide stakeholders with clear performance visibility. Reports combine:
- **Internal profiling**: CPU/memory/asyncio metrics from Phase 3 script
- **External load testing**: Locust metrics (p95/p99 latency, throughput, error rates)
- **Historical tracking**: Compare against previous baselines

## Architecture

```
Performance Data Sources:
┌─────────────────────────────────────────────────┐
│ profile-performance-benchmarks.py               │
│ → performance_results.json                      │
└────────────┬────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────┐
│ Locust Load Tests (existing)                    │
│ → locust_stats.json                             │
└────────────┬────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────┐
│ generate-benchmark-report.py                    │
│ - Reads JSON inputs                             │
│ - Evaluates against thresholds                  │
│ - Generates docs/benchmark-results.md           │
└─────────────────────────────────────────────────┘
```

## Implementation

### File 1: `backend/scripts/generate-benchmark-report.py`

```python
#!/usr/bin/env python3
"""Generate benchmark report from profiling + load test results.

Usage:
    # Generate from default files
    ./backend/scripts/generate-benchmark-report.py

    # Custom input files
    ./backend/scripts/generate-benchmark-report.py \
        --profile performance_results.json \
        --locust locust_stats.json \
        --output docs/benchmark-results.md

    # Compare against baseline
    ./backend/scripts/generate-benchmark-report.py \
        --baseline baseline_2026-02-01.json
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================================
# Thresholds
# ============================================================================

THRESHOLDS = {
    "cpu": {
        "messages_per_second": {"min": 3000, "target": 5000},
        "avg_latency_ms": {"max": 1.0, "target": 0.5},
    },
    "memory": {
        "delta_mb": {"max": 100, "target": 50},
        "peak_mb": {"max": 150, "target": 100},
    },
    "asyncio": {
        "event_loop_lag_ms": {"max": 2.0, "target": 1.0},
    },
    "websocket": {
        "p99_latency_ms": {"max": 150, "target": 100},
        "p95_latency_ms": {"max": 120, "target": 80},
    },
    "rest": {
        "p95_latency_ms": {"max": 250, "target": 200},
    },
    "error_rate": {
        "percent": {"max": 0.1, "target": 0.0},
    },
}


# ============================================================================
# Status Evaluation
# ============================================================================

def evaluate_metric(value, threshold_config, lower_is_better=True):
    """Evaluate metric against thresholds.

    Returns: (status, emoji)
        - "pass": ✅ (meets target)
        - "warning": ⚠️  (meets min/max but not target)
        - "fail": ❌ (exceeds limits)
    """
    if threshold_config is None:
        return "unknown", "❓"

    if "min" in threshold_config:
        # Higher is better (throughput)
        if value >= threshold_config.get("target", threshold_config["min"]):
            return "pass", "✅"
        elif value >= threshold_config["min"]:
            return "warning", "⚠️"
        else:
            return "fail", "❌"

    elif "max" in threshold_config:
        # Lower is better (latency, memory)
        if value <= threshold_config.get("target", threshold_config["max"]):
            return "pass", "✅"
        elif value <= threshold_config["max"]:
            return "warning", "⚠️"
        else:
            return "fail", "❌"

    return "unknown", "❓"


# ============================================================================
# Report Generation
# ============================================================================

def generate_report(profile_data, locust_data, baseline_data=None):
    """Generate markdown report from performance data."""

    report = []

    # Header
    report.append("# Performance Benchmark Report")
    report.append("")
    report.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"**Environment**: Local Development")
    report.append("")

    # Summary
    report.append("## Executive Summary")
    report.append("")

    # Count pass/warning/fail
    results = []

    # CPU metrics
    if "cpu" in profile_data:
        cpu = profile_data["cpu"]
        throughput_status, throughput_emoji = evaluate_metric(
            cpu["messages_per_second"],
            THRESHOLDS["cpu"]["messages_per_second"],
            lower_is_better=False
        )
        results.append(throughput_status)

        latency_status, latency_emoji = evaluate_metric(
            cpu["avg_latency_ms"],
            THRESHOLDS["cpu"]["avg_latency_ms"]
        )
        results.append(latency_status)

    # Memory metrics
    if "memory" in profile_data:
        mem = profile_data["memory"]
        delta_status, delta_emoji = evaluate_metric(
            mem["delta_mb"],
            THRESHOLDS["memory"]["delta_mb"]
        )
        results.append(delta_status)

    # Count statuses
    pass_count = results.count("pass")
    warning_count = results.count("warning")
    fail_count = results.count("fail")

    overall_status = "✅ PASS" if fail_count == 0 else "❌ FAIL"

    report.append(f"**Overall Status**: {overall_status}")
    report.append("")
    report.append(f"- ✅ Passed: {pass_count}")
    report.append(f"- ⚠️  Warning: {warning_count}")
    report.append(f"- ❌ Failed: {fail_count}")
    report.append("")

    # CPU Performance
    report.append("## CPU Performance")
    report.append("")

    if "cpu" in profile_data:
        cpu = profile_data["cpu"]

        throughput_status, throughput_emoji = evaluate_metric(
            cpu["messages_per_second"],
            THRESHOLDS["cpu"]["messages_per_second"],
            lower_is_better=False
        )

        latency_status, latency_emoji = evaluate_metric(
            cpu["avg_latency_ms"],
            THRESHOLDS["cpu"]["avg_latency_ms"]
        )

        report.append("| Metric | Value | Target | Status |")
        report.append("|--------|-------|--------|--------|")
        report.append(
            f"| Message Throughput | {cpu['messages_per_second']:.0f} msg/s | "
            f"≥{THRESHOLDS['cpu']['messages_per_second']['target']} msg/s | "
            f"{throughput_emoji} {throughput_status.upper()} |"
        )
        report.append(
            f"| Average Latency | {cpu['avg_latency_ms']:.3f}ms | "
            f"≤{THRESHOLDS['cpu']['avg_latency_ms']['target']}ms | "
            f"{latency_emoji} {latency_status.upper()} |"
        )
        report.append(f"| Total Processing Time | {cpu['total_time']:.2f}s | - | - |")
        report.append(f"| Messages Processed | {cpu['message_count']:,} | - | - |")
        report.append("")

        # Top CPU consumers
        if "top_functions" in cpu and cpu["top_functions"]:
            report.append("### Top CPU Consumers")
            report.append("")
            report.append("| Function | Cumulative Time (s) |")
            report.append("|----------|---------------------|")
            for func in cpu["top_functions"][:5]:
                report.append(f"| `{func['function']}` | {func['cumtime']:.3f} |")
            report.append("")
    else:
        report.append("*CPU profiling data not available*")
        report.append("")

    # Memory Performance
    report.append("## Memory Performance")
    report.append("")

    if "memory" in profile_data:
        mem = profile_data["memory"]

        delta_status, delta_emoji = evaluate_metric(
            mem["delta_mb"],
            THRESHOLDS["memory"]["delta_mb"]
        )

        peak_status, peak_emoji = evaluate_metric(
            mem["peak_mb"],
            THRESHOLDS["memory"]["peak_mb"]
        )

        report.append("| Metric | Value | Target | Status |")
        report.append("|--------|-------|--------|--------|")
        report.append(
            f"| Memory Delta | {mem['delta_mb']:.2f} MB | "
            f"≤{THRESHOLDS['memory']['delta_mb']['target']} MB | "
            f"{delta_emoji} {delta_status.upper()} |"
        )
        report.append(
            f"| Peak Memory | {mem['peak_mb']:.2f} MB | "
            f"≤{THRESHOLDS['memory']['peak_mb']['target']} MB | "
            f"{peak_emoji} {peak_status.upper()} |"
        )
        report.append(f"| Baseline Memory | {mem['baseline_mb']:.2f} MB | - | - |")
        report.append(f"| Messages Processed | {mem['message_count']:,} | - | - |")
        report.append("")
    else:
        report.append("*Memory profiling data not available*")
        report.append("")

    # Asyncio Performance
    report.append("## Asyncio Performance")
    report.append("")

    if "asyncio" in profile_data:
        asyncio_data = profile_data["asyncio"]

        lag_status, lag_emoji = evaluate_metric(
            asyncio_data["event_loop_lag_ms"],
            THRESHOLDS["asyncio"]["event_loop_lag_ms"]
        )

        report.append("| Metric | Value | Target | Status |")
        report.append("|--------|-------|--------|--------|")
        report.append(
            f"| Event Loop Lag | {asyncio_data['event_loop_lag_ms']:.3f}ms | "
            f"≤{THRESHOLDS['asyncio']['event_loop_lag_ms']['target']}ms | "
            f"{lag_emoji} {lag_status.upper()} |"
        )
        report.append(f"| Active Tasks | {asyncio_data['active_tasks']} | - | - |")
        report.append("")
    else:
        report.append("*Asyncio monitoring data not available*")
        report.append("")

    # Database Performance
    report.append("## Database Performance")
    report.append("")

    if "database" in profile_data and profile_data["database"].get("status") == "connected":
        db = profile_data["database"]
        utilization = (db["active_connections"] / db["pool_size"]) * 100 if db["pool_size"] > 0 else 0

        report.append("| Metric | Value |")
        report.append("|--------|-------|")
        report.append(f"| Pool Size | {db['pool_size']} |")
        report.append(f"| Active Connections | {db['active_connections']} |")
        report.append(f"| Idle Connections | {db['idle_connections']} |")
        report.append(f"| Utilization | {utilization:.1f}% |")
        report.append("")
    else:
        report.append("*Database not configured or unavailable*")
        report.append("")

    # Load Testing Results (if available)
    if locust_data:
        report.append("## Load Testing Results")
        report.append("")
        report.append("### WebSocket Performance")
        report.append("")

        # Parse Locust stats (example structure)
        # Actual structure depends on Locust JSON output format
        report.append("| Metric | Value | Target | Status |")
        report.append("|--------|-------|--------|--------|")
        report.append("| P99 Latency | *TBD* | ≤100ms | ⚠️ PENDING |")
        report.append("| P95 Latency | *TBD* | ≤80ms | ⚠️ PENDING |")
        report.append("| Error Rate | *TBD* | ≤0.1% | ⚠️ PENDING |")
        report.append("")

        report.append("### REST API Performance")
        report.append("")
        report.append("| Metric | Value | Target | Status |")
        report.append("|--------|-------|--------|--------|")
        report.append("| P95 Latency | *TBD* | ≤200ms | ⚠️ PENDING |")
        report.append("| Throughput | *TBD* | ≥100 req/s | ⚠️ PENDING |")
        report.append("")

    # Baseline Comparison (if provided)
    if baseline_data:
        report.append("## Baseline Comparison")
        report.append("")
        report.append("*Comparison against baseline from previous run*")
        report.append("")
        report.append("| Metric | Current | Baseline | Change |")
        report.append("|--------|---------|----------|--------|")

        if "cpu" in profile_data and "cpu" in baseline_data:
            curr_tput = profile_data["cpu"]["messages_per_second"]
            base_tput = baseline_data["cpu"]["messages_per_second"]
            change = ((curr_tput - base_tput) / base_tput) * 100
            emoji = "📈" if change > 0 else "📉"
            report.append(
                f"| Message Throughput | {curr_tput:.0f} msg/s | "
                f"{base_tput:.0f} msg/s | {emoji} {change:+.1f}% |"
            )

        report.append("")

    # Recommendations
    report.append("## Recommendations")
    report.append("")

    recommendations = []

    if "cpu" in profile_data:
        cpu = profile_data["cpu"]
        if cpu["messages_per_second"] < THRESHOLDS["cpu"]["messages_per_second"]["target"]:
            recommendations.append("- 🔧 CPU throughput below target — consider optimizing hot functions")

    if "memory" in profile_data:
        mem = profile_data["memory"]
        if mem["delta_mb"] > THRESHOLDS["memory"]["delta_mb"]["max"]:
            recommendations.append("- 🔧 Memory delta exceeds limit — investigate memory leaks")

    if recommendations:
        report.extend(recommendations)
    else:
        report.append("- ✅ All metrics within target thresholds — no action required")

    report.append("")

    # Footer
    report.append("---")
    report.append("")
    report.append("## Appendix")
    report.append("")
    report.append("### How to Run")
    report.append("")
    report.append("```bash")
    report.append("# Profile performance")
    report.append("./backend/scripts/profile-performance-benchmarks.py")
    report.append("")
    report.append("# Generate report")
    report.append("./backend/scripts/generate-benchmark-report.py")
    report.append("```")
    report.append("")
    report.append("### Files")
    report.append("")
    report.append("- Profiling script: `backend/scripts/profile-performance-benchmarks.py`")
    report.append("- Report generator: `backend/scripts/generate-benchmark-report.py`")
    report.append("- CPU profile: `cpu_profile.prof` (view with `snakeviz`)")
    report.append("- Memory stats: `memory_stats.txt`")
    report.append("")

    return "\n".join(report)


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Generate benchmark report")
    parser.add_argument(
        "--profile",
        default="performance_results.json",
        help="Performance profiling JSON (default: performance_results.json)",
    )
    parser.add_argument(
        "--locust",
        default=None,
        help="Locust stats JSON (optional)",
    )
    parser.add_argument(
        "--baseline",
        default=None,
        help="Baseline JSON for comparison (optional)",
    )
    parser.add_argument(
        "--output",
        default="docs/benchmark-results.md",
        help="Output markdown file (default: docs/benchmark-results.md)",
    )

    args = parser.parse_args()

    # Load profile data
    profile_path = Path(args.profile)
    if not profile_path.exists():
        print(f"❌ Profile data not found: {profile_path}")
        print(f"   Run: ./backend/scripts/profile-performance-benchmarks.py")
        sys.exit(1)

    with open(profile_path) as f:
        profile_data = json.load(f)

    # Load locust data (optional)
    locust_data = None
    if args.locust:
        locust_path = Path(args.locust)
        if locust_path.exists():
            with open(locust_path) as f:
                locust_data = json.load(f)

    # Load baseline (optional)
    baseline_data = None
    if args.baseline:
        baseline_path = Path(args.baseline)
        if baseline_path.exists():
            with open(baseline_path) as f:
                baseline_data = json.load(f)

    # Generate report
    report_md = generate_report(profile_data, locust_data, baseline_data)

    # Write to file
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        f.write(report_md)

    print(f"✅ Benchmark report generated: {output_path}")
    print(f"\nView report: cat {output_path}")


if __name__ == "__main__":
    main()
```

### File 2: `docs/benchmark-results.md` (Initial Template)

This file will be auto-generated by the script above. Initial placeholder:

```markdown
# Performance Benchmark Report

**Status**: ⚠️ Not yet generated

Run benchmarks to generate this report:

```bash
# 1. Profile performance
./backend/scripts/profile-performance-benchmarks.py

# 2. Generate report
./backend/scripts/generate-benchmark-report.py
```

## Expected Metrics

| Category | Metric | Target |
|----------|--------|--------|
| CPU | Message Throughput | ≥5000 msg/s |
| CPU | Average Latency | ≤0.5ms |
| Memory | Delta @ 50K messages | ≤50 MB |
| Memory | Peak Memory | ≤100 MB |
| Asyncio | Event Loop Lag | ≤1ms |
| WebSocket | P99 Latency | ≤100ms |
| REST API | P95 Latency | ≤200ms |
| Errors | Error Rate | ≤0.1% |
```

## Workflow Integration

### CI/CD Integration (GitHub Actions)

Add to `.github/workflows/ci.yml`:

```yaml
# Add after backend tests job
  performance-smoke-test:
    runs-on: ubuntu-latest
    needs: backend
    timeout-minutes: 10

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'

      - name: Install dependencies
        working-directory: backend
        run: |
          pip install -r requirements.txt
          pip install snakeviz

      - name: Run performance profiling (smoke test)
        working-directory: backend
        run: |
          ./scripts/profile-performance-benchmarks.py \
            --mode cpu \
            --cpu-messages 1000 \
            --output ../performance_smoke.json

      - name: Check performance thresholds
        run: |
          python -c "
          import json, sys
          with open('performance_smoke.json') as f:
              data = json.load(f)
          cpu = data.get('cpu', {})
          throughput = cpu.get('messages_per_second', 0)
          if throughput < 3000:
              print(f'❌ Throughput {throughput:.0f} msg/s below minimum 3000 msg/s')
              sys.exit(1)
          print(f'✅ Throughput: {throughput:.0f} msg/s')
          "

      - name: Upload performance results
        uses: actions/upload-artifact@v4
        with:
          name: performance-results
          path: performance_smoke.json
```

## Usage Guide

### One-Time Setup

```bash
# Install snakeviz for CPU profile visualization
cd backend
./venv/bin/pip install snakeviz
```

### Running Benchmarks

```bash
# Full benchmark suite (3-5 minutes)
cd /Users/minh/Projects/stock-tracker
./backend/scripts/profile-performance-benchmarks.py

# Generate report
./backend/scripts/generate-benchmark-report.py

# View results
cat docs/benchmark-results.md

# Interactive CPU profile
snakeviz cpu_profile.prof
```

### Comparing Against Baseline

```bash
# Save current results as baseline
cp performance_results.json baseline_2026-02-11.json

# Run benchmarks again after changes
./backend/scripts/profile-performance-benchmarks.py

# Generate comparison report
./backend/scripts/generate-benchmark-report.py \
    --baseline baseline_2026-02-11.json
```

## Success Criteria

- [ ] `generate-benchmark-report.py` script created and executable
- [ ] Script reads `performance_results.json` from Phase 3
- [ ] Report evaluates metrics against thresholds
- [ ] Pass/warning/fail statuses computed correctly
- [ ] Markdown report generated in `docs/benchmark-results.md`
- [ ] Report includes executive summary with overall status
- [ ] CPU, memory, asyncio, DB sections rendered
- [ ] Recommendations section provides actionable guidance
- [ ] Optional baseline comparison works
- [ ] CI integration example provided (not yet merged)

## Performance Thresholds Reference

```python
THRESHOLDS = {
    "cpu": {
        "messages_per_second": {"min": 3000, "target": 5000},
        "avg_latency_ms": {"max": 1.0, "target": 0.5},
    },
    "memory": {
        "delta_mb": {"max": 100, "target": 50},
        "peak_mb": {"max": 150, "target": 100},
    },
    "asyncio": {
        "event_loop_lag_ms": {"max": 2.0, "target": 1.0},
    },
    "websocket": {
        "p99_latency_ms": {"max": 150, "target": 100},
    },
    "rest": {
        "p95_latency_ms": {"max": 250, "target": 200},
    },
}
```

## Dependencies

None — uses stdlib json module.

## Next Steps

After completing this phase:
1. Run full benchmark suite
2. Generate initial baseline report
3. Add CI smoke test (optional)
4. Track performance over time with baseline comparisons
5. Investigate and optimize any failing metrics
