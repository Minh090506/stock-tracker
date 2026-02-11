#!/usr/bin/env python3
"""Generate benchmark report from profiling JSON results.

Usage:
    ./venv/bin/python scripts/generate-benchmark-report.py
    ./venv/bin/python scripts/generate-benchmark-report.py --profile results.json
    ./venv/bin/python scripts/generate-benchmark-report.py --baseline baseline.json

Reads performance_results.json (from profile-performance-benchmarks.py)
and generates docs/benchmark-results.md with pass/warning/fail evaluation.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# ============================================================================
# Thresholds — min/target for higher-is-better, max/target for lower-is-better
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
}


def _evaluate(value: float, cfg: dict) -> tuple[str, str]:
    """Evaluate a metric value against threshold config.

    Returns (status, emoji) where status is pass/warning/fail.
    """
    if "min" in cfg:
        # Higher is better (throughput)
        if value >= cfg.get("target", cfg["min"]):
            return "PASS", "✅"
        if value >= cfg["min"]:
            return "WARNING", "⚠️"
        return "FAIL", "❌"

    if "max" in cfg:
        # Lower is better (latency, memory)
        if value <= cfg.get("target", cfg["max"]):
            return "PASS", "✅"
        if value <= cfg["max"]:
            return "WARNING", "⚠️"
        return "FAIL", "❌"

    return "UNKNOWN", "❓"


def _generate(profile: dict, baseline: dict | None = None) -> str:
    """Build markdown report from profiling data."""
    lines: list[str] = []
    statuses: list[str] = []

    lines.append("# Performance Benchmark Report")
    lines.append("")
    lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Environment**: Local Development")
    lines.append("")

    # --- CPU ---
    lines.append("## CPU Performance")
    lines.append("")

    if "cpu" in profile:
        cpu = profile["cpu"]
        t_status, t_emoji = _evaluate(
            cpu["messages_per_second"], THRESHOLDS["cpu"]["messages_per_second"]
        )
        l_status, l_emoji = _evaluate(
            cpu["avg_latency_ms"], THRESHOLDS["cpu"]["avg_latency_ms"]
        )
        statuses.extend([t_status, l_status])

        lines.append("| Metric | Value | Target | Status |")
        lines.append("|--------|-------|--------|--------|")
        lines.append(
            f"| Throughput | {cpu['messages_per_second']:,.0f} msg/s "
            f"| ≥{THRESHOLDS['cpu']['messages_per_second']['target']} msg/s "
            f"| {t_emoji} {t_status} |"
        )
        lines.append(
            f"| Avg Latency | {cpu['avg_latency_ms']:.3f}ms "
            f"| ≤{THRESHOLDS['cpu']['avg_latency_ms']['target']}ms "
            f"| {l_emoji} {l_status} |"
        )
        lines.append(
            f"| Total Time | {cpu['total_time_s']:.2f}s | - | - |"
        )
        lines.append(
            f"| Messages | {cpu['message_count']:,} | - | - |"
        )
        lines.append("")

        if cpu.get("top_functions"):
            lines.append("### Top CPU Consumers")
            lines.append("")
            lines.append("| Function | Cumulative Time (s) |")
            lines.append("|----------|---------------------|")
            for fn in cpu["top_functions"][:5]:
                lines.append(f"| `{fn['function']}` | {fn['cumtime']:.3f} |")
            lines.append("")
    else:
        lines.append("*CPU profiling data not available.*")
        lines.append("")

    # --- Memory ---
    lines.append("## Memory Performance")
    lines.append("")

    if "memory" in profile:
        mem = profile["memory"]
        d_status, d_emoji = _evaluate(
            mem["delta_mb"], THRESHOLDS["memory"]["delta_mb"]
        )
        p_status, p_emoji = _evaluate(
            mem["peak_mb"], THRESHOLDS["memory"]["peak_mb"]
        )
        statuses.extend([d_status, p_status])

        lines.append("| Metric | Value | Target | Status |")
        lines.append("|--------|-------|--------|--------|")
        lines.append(
            f"| Memory Delta | {mem['delta_mb']:.2f} MB "
            f"| ≤{THRESHOLDS['memory']['delta_mb']['target']} MB "
            f"| {d_emoji} {d_status} |"
        )
        lines.append(
            f"| Peak Memory | {mem['peak_mb']:.2f} MB "
            f"| ≤{THRESHOLDS['memory']['peak_mb']['target']} MB "
            f"| {p_emoji} {p_status} |"
        )
        lines.append(f"| Baseline | {mem['baseline_mb']:.2f} MB | - | - |")
        lines.append(f"| Messages | {mem['message_count']:,} | - | - |")
        lines.append("")
    else:
        lines.append("*Memory profiling data not available.*")
        lines.append("")

    # --- Asyncio ---
    lines.append("## Asyncio Performance")
    lines.append("")

    if "asyncio" in profile:
        aio = profile["asyncio"]
        lag_status, lag_emoji = _evaluate(
            aio["event_loop_lag_ms"], THRESHOLDS["asyncio"]["event_loop_lag_ms"]
        )
        statuses.append(lag_status)

        lines.append("| Metric | Value | Target | Status |")
        lines.append("|--------|-------|--------|--------|")
        lines.append(
            f"| Event Loop Lag | {aio['event_loop_lag_ms']:.3f}ms "
            f"| ≤{THRESHOLDS['asyncio']['event_loop_lag_ms']['target']}ms "
            f"| {lag_emoji} {lag_status} |"
        )
        lines.append(f"| Active Tasks | {aio['active_tasks']} | - | - |")
        lines.append("")
    else:
        lines.append("*Asyncio monitoring data not available.*")
        lines.append("")

    # --- Database ---
    lines.append("## Database Pool")
    lines.append("")

    db = profile.get("database", {})
    if db.get("status") == "connected":
        util = (db["active_connections"] / db["pool_size"]) * 100 if db["pool_size"] else 0
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Pool Size | {db['pool_size']} |")
        lines.append(f"| Active | {db['active_connections']} |")
        lines.append(f"| Idle | {db['idle_connections']} |")
        lines.append(f"| Utilization | {util:.1f}% |")
        lines.append("")
    else:
        lines.append("*Database not available (app runs in graceful-degradation mode).*")
        lines.append("")

    # --- Baseline comparison ---
    if baseline and "cpu" in profile and "cpu" in baseline:
        lines.append("## Baseline Comparison")
        lines.append("")
        lines.append("| Metric | Current | Baseline | Change |")
        lines.append("|--------|---------|----------|--------|")

        curr_t = profile["cpu"]["messages_per_second"]
        base_t = baseline["cpu"]["messages_per_second"]
        pct = ((curr_t - base_t) / base_t) * 100 if base_t else 0
        arrow = "📈" if pct > 0 else "📉"
        lines.append(
            f"| Throughput | {curr_t:,.0f} msg/s | {base_t:,.0f} msg/s "
            f"| {arrow} {pct:+.1f}% |"
        )

        if "memory" in profile and "memory" in baseline:
            curr_d = profile["memory"]["delta_mb"]
            base_d = baseline["memory"]["delta_mb"]
            dpct = ((curr_d - base_d) / base_d) * 100 if base_d else 0
            arrow = "📉" if dpct < 0 else "📈"  # less memory = better
            lines.append(
                f"| Memory Delta | {curr_d:.2f} MB | {base_d:.2f} MB "
                f"| {arrow} {dpct:+.1f}% |"
            )
        lines.append("")

    # --- Executive summary (at top, but computed last) ---
    pass_n = statuses.count("PASS")
    warn_n = statuses.count("WARNING")
    fail_n = statuses.count("FAIL")
    overall = "✅ PASS" if fail_n == 0 else "❌ FAIL"

    summary = [
        "## Summary",
        "",
        f"**Overall**: {overall} — {pass_n} passed, {warn_n} warnings, {fail_n} failed",
        "",
    ]

    # --- Recommendations ---
    recs = []
    if "cpu" in profile:
        if profile["cpu"]["messages_per_second"] < THRESHOLDS["cpu"]["messages_per_second"]["target"]:
            recs.append("- Optimize CPU hotspot functions (see Top CPU Consumers)")
    if "memory" in profile:
        if profile["memory"]["delta_mb"] > THRESHOLDS["memory"]["delta_mb"]["target"]:
            recs.append("- Investigate memory growth — check top allocators in memory_stats.txt")

    lines.append("## Recommendations")
    lines.append("")
    if recs:
        lines.extend(recs)
    else:
        lines.append("- All metrics within target — no action required")
    lines.append("")

    # --- How to run ---
    lines.append("---")
    lines.append("")
    lines.append("### How to Reproduce")
    lines.append("")
    lines.append("```bash")
    lines.append("cd backend")
    lines.append("./venv/bin/python scripts/profile-performance-benchmarks.py")
    lines.append("./venv/bin/python scripts/generate-benchmark-report.py")
    lines.append("```")
    lines.append("")

    # Insert summary after header
    header = lines[:3]  # title + blank + generated line
    body = lines[3:]
    return "\n".join(header + [""] + summary + body)


def main():
    parser = argparse.ArgumentParser(description="Generate benchmark report")
    parser.add_argument(
        "--profile", default="performance_results.json",
        help="Profiling JSON input (default: performance_results.json)",
    )
    parser.add_argument(
        "--baseline", default=None,
        help="Baseline JSON for comparison (optional)",
    )
    parser.add_argument(
        "--output", default=None,
        help="Output markdown (default: docs/benchmark-results.md)",
    )
    args = parser.parse_args()

    # Resolve output path relative to repo root
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent.parent
    output_path = Path(args.output) if args.output else repo_root / "docs" / "benchmark-results.md"

    # Load profile data
    profile_path = Path(args.profile)
    if not profile_path.exists():
        print(f"❌ Not found: {profile_path}")
        print("   Run: ./venv/bin/python scripts/profile-performance-benchmarks.py")
        sys.exit(1)

    with open(profile_path) as fh:
        profile = json.load(fh)

    # Load baseline (optional)
    baseline = None
    if args.baseline:
        bp = Path(args.baseline)
        if bp.exists():
            with open(bp) as fh:
                baseline = json.load(fh)

    report = _generate(profile, baseline)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report)
    print(f"✅ Report generated: {output_path}")


if __name__ == "__main__":
    main()
