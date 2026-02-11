# Phase 3: Performance Profiling

**Priority**: P1
**Status**: Complete
**Effort**: 1.5h

## Overview

Create unified profiling script that measures CPU hotspots, memory usage, asyncio task health, and database connection pool utilization. Outputs JSON results for automated benchmark report generation.

## Context

Performance profiling identifies bottlenecks and establishes baseline metrics. Unlike load testing (external client perspective), profiling measures internal service performance under controlled conditions.

**Profiling Targets**:
- **CPU**: Message processing throughput (cProfile + snakeviz)
- **Memory**: Sustained load memory footprint (tracemalloc)
- **Asyncio**: Task count, pending tasks, event loop lag
- **Database**: Connection pool utilization, query latency
- **Overall**: End-to-end latency from SSI message → WS broadcast

## Architecture

```
profile-performance-benchmarks.py (single script)
├── CPU Profiling (cProfile)
│   ├── Simulate 10,000 SSI messages
│   ├── Measure processor.handle_* throughput
│   └── Generate snakeviz HTML report
│
├── Memory Profiling (tracemalloc)
│   ├── Baseline measurement
│   ├── Process 50,000 messages
│   ├── Track peak memory delta
│   └── Top 10 memory allocators
│
├── Asyncio Monitoring
│   ├── Count active tasks
│   ├── Detect pending/blocked tasks
│   └── Event loop latency measurement
│
├── Database Pool Metrics
│   ├── Active connections
│   ├── Idle connections
│   └── Query timing stats
│
└── JSON Output
    └── results.json for automated report generation
```

## Implementation

### File: `backend/scripts/profile-performance-benchmarks.py`

```python
#!/usr/bin/env python3
"""Performance profiling script — CPU, memory, asyncio, DB metrics.

Usage:
    # Full profile (all modes):
    ./backend/scripts/profile-performance-benchmarks.py

    # CPU only:
    ./backend/scripts/profile-performance-benchmarks.py --mode cpu

    # Memory only:
    ./backend/scripts/profile-performance-benchmarks.py --mode memory

    # Output JSON:
    ./backend/scripts/profile-performance-benchmarks.py --output results.json

Outputs:
    - CPU: cpu_profile.prof + cpu_profile.html (snakeviz)
    - Memory: memory_stats.txt
    - JSON: results.json (for benchmark report)
"""

import asyncio
import argparse
import cProfile
import json
import logging
import pstats
import random
import sys
import time
import tracemalloc
from pathlib import Path
from datetime import datetime
from io import StringIO

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.ssi_messages import (
    SSIQuoteMessage,
    SSITradeMessage,
    SSIForeignMessage,
    SSIIndexMessage,
)
from app.services.market_data_processor import MarketDataProcessor

logging.basicConfig(level=logging.WARNING)  # Suppress debug noise


# ============================================================================
# SSI Message Generators
# ============================================================================

VN30_SYMBOLS = ["VNM", "VHM", "VIC", "HPG", "MSN", "VCB", "BID", "CTG", "MBB", "ACB"]


def generate_quote(symbol: str) -> SSIQuoteMessage:
    """Generate realistic quote message."""
    base = random.uniform(50, 150)
    return SSIQuoteMessage(
        symbol=symbol,
        bid_price_1=round(base, 1),
        ask_price_1=round(base + 0.5, 1),
        ref_price=round(base + 0.2, 1),
        ceiling=round(base * 1.07, 1),
        floor=round(base * 0.93, 1),
        bid_vol_1=random.randint(100, 5000),
        ask_vol_1=random.randint(100, 5000),
    )


def generate_trade(symbol: str, price: float) -> SSITradeMessage:
    """Generate realistic trade message."""
    return SSITradeMessage(
        symbol=symbol,
        last_price=price,
        last_vol=random.randint(10, 500),
        trading_session=random.choice(["ATO", "LO", "ATC"]),
        change=random.uniform(-2, 5),
        ratio_change=random.uniform(-1.5, 3.5),
    )


def generate_foreign(symbol: str) -> SSIForeignMessage:
    """Generate realistic foreign message."""
    return SSIForeignMessage(
        symbol=symbol,
        f_buy_vol=random.randint(100, 5000),
        f_sell_vol=random.randint(100, 5000),
        f_buy_val=random.uniform(10000, 500000),
        f_sell_val=random.uniform(10000, 500000),
        total_room=1000000,
        current_room=random.randint(500000, 999000),
    )


def generate_index() -> SSIIndexMessage:
    """Generate realistic index message."""
    return SSIIndexMessage(
        index_id=random.choice(["VN30", "VNINDEX"]),
        index_value=random.uniform(1200, 1300),
        prior_index_value=random.uniform(1190, 1290),
        change=random.uniform(-10, 10),
        ratio_change=random.uniform(-1, 1),
        advances=random.randint(10, 20),
        declines=random.randint(5, 15),
        no_changes=random.randint(0, 5),
        total_volume=random.randint(1000000, 5000000),
    )


# ============================================================================
# CPU Profiling
# ============================================================================

async def simulate_message_processing(proc: MarketDataProcessor, count: int):
    """Simulate processing N messages through processor."""
    # Seed quotes
    for symbol in VN30_SYMBOLS:
        await proc.handle_quote(generate_quote(symbol))

    # Mix of trades, foreign, index
    for i in range(count):
        msg_type = random.choice(["trade", "foreign", "index"])

        if msg_type == "trade":
            symbol = random.choice(VN30_SYMBOLS)
            bid, ask = proc.quote_cache.get_bid_ask(symbol)
            price = random.choice([bid, ask, (bid + ask) / 2])
            await proc.handle_trade(generate_trade(symbol, price))

        elif msg_type == "foreign":
            symbol = random.choice(VN30_SYMBOLS)
            await proc.handle_foreign(generate_foreign(symbol))

        else:  # index
            await proc.handle_index(generate_index())


def profile_cpu(message_count: int = 10000) -> dict:
    """Profile CPU with cProfile for message_count messages.

    Returns dict with:
    - total_time: Total CPU time (seconds)
    - messages_per_second: Throughput
    - top_functions: Top 10 CPU consumers
    """
    print(f"\n=== CPU Profiling ({message_count:,} messages) ===")

    proc = MarketDataProcessor()
    profiler = cProfile.Profile()

    # Profile message processing
    profiler.enable()
    start = time.perf_counter()
    asyncio.run(simulate_message_processing(proc, message_count))
    elapsed = time.perf_counter() - start
    profiler.disable()

    # Save profile
    profiler.dump_stats("cpu_profile.prof")
    print(f"✓ Saved cpu_profile.prof")

    # Generate snakeviz HTML (requires snakeviz installed)
    try:
        import subprocess
        subprocess.run(
            ["snakeviz", "-s", "cpu_profile.prof", "-o", "cpu_profile.html"],
            check=True,
            capture_output=True,
        )
        print(f"✓ Saved cpu_profile.html (open in browser)")
    except Exception:
        print("⚠ snakeviz not installed, skipping HTML generation")

    # Extract stats
    stream = StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.strip_dirs()
    stats.sort_stats("cumulative")
    stats.print_stats(10)

    throughput = message_count / elapsed

    print(f"\nResults:")
    print(f"  Total time: {elapsed:.2f}s")
    print(f"  Throughput: {throughput:.0f} msg/s")
    print(f"  Avg latency: {(elapsed / message_count) * 1000:.2f}ms per message")

    # Parse top functions
    stream.seek(0)
    lines = stream.read().split("\n")
    top_functions = []
    for line in lines[5:15]:  # Skip header, take top 10
        if line.strip():
            parts = line.split()
            if len(parts) >= 6:
                top_functions.append({
                    "function": parts[-1],
                    "cumtime": float(parts[3]) if parts[3].replace(".", "").isdigit() else 0,
                })

    return {
        "total_time": round(elapsed, 3),
        "message_count": message_count,
        "messages_per_second": round(throughput, 1),
        "avg_latency_ms": round((elapsed / message_count) * 1000, 3),
        "top_functions": top_functions,
    }


# ============================================================================
# Memory Profiling
# ============================================================================

def profile_memory(message_count: int = 50000) -> dict:
    """Profile memory usage under sustained load.

    Returns dict with:
    - baseline_mb: Initial memory
    - peak_mb: Peak memory after processing
    - delta_mb: Memory increase
    - top_allocators: Top 10 memory allocations
    """
    print(f"\n=== Memory Profiling ({message_count:,} messages) ===")

    tracemalloc.start()

    # Baseline
    proc = MarketDataProcessor()
    baseline_snapshot = tracemalloc.take_snapshot()
    baseline_mb = sum(stat.size for stat in baseline_snapshot.statistics("lineno")) / 1024 / 1024

    # Process messages
    asyncio.run(simulate_message_processing(proc, message_count))

    # Peak
    peak_snapshot = tracemalloc.take_snapshot()
    peak_mb = sum(stat.size for stat in peak_snapshot.statistics("lineno")) / 1024 / 1024

    # Top allocators
    top_stats = peak_snapshot.compare_to(baseline_snapshot, "lineno")[:10]

    tracemalloc.stop()

    delta_mb = peak_mb - baseline_mb

    print(f"\nResults:")
    print(f"  Baseline: {baseline_mb:.2f} MB")
    print(f"  Peak: {peak_mb:.2f} MB")
    print(f"  Delta: {delta_mb:.2f} MB")

    # Save detailed report
    with open("memory_stats.txt", "w") as f:
        f.write(f"Memory Profiling Report\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write(f"Baseline: {baseline_mb:.2f} MB\n")
        f.write(f"Peak: {peak_mb:.2f} MB\n")
        f.write(f"Delta: {delta_mb:.2f} MB\n\n")
        f.write(f"Top 10 Memory Allocators:\n")
        for i, stat in enumerate(top_stats, 1):
            f.write(f"{i}. {stat}\n")

    print(f"✓ Saved memory_stats.txt")

    top_allocators = []
    for stat in top_stats[:10]:
        top_allocators.append({
            "file": str(stat.traceback),
            "size_kb": round(stat.size_diff / 1024, 2),
        })

    return {
        "baseline_mb": round(baseline_mb, 2),
        "peak_mb": round(peak_mb, 2),
        "delta_mb": round(delta_mb, 2),
        "message_count": message_count,
        "top_allocators": top_allocators,
    }


# ============================================================================
# Asyncio Monitoring
# ============================================================================

async def profile_asyncio() -> dict:
    """Monitor asyncio task health and event loop performance.

    Returns dict with:
    - active_tasks: Count of running tasks
    - pending_tasks: Count of pending tasks
    - event_loop_lag_ms: Event loop scheduling delay
    """
    print(f"\n=== Asyncio Monitoring ===")

    proc = MarketDataProcessor()

    # Spawn background processing
    task = asyncio.create_task(simulate_message_processing(proc, 1000))

    # Measure during processing
    await asyncio.sleep(0.1)  # Let tasks spin up

    all_tasks = asyncio.all_tasks()
    active_count = len([t for t in all_tasks if not t.done()])

    # Measure event loop lag
    start = time.perf_counter()
    await asyncio.sleep(0)  # Yield to event loop
    lag_ms = (time.perf_counter() - start) * 1000

    await task  # Wait for completion

    print(f"\nResults:")
    print(f"  Active tasks: {active_count}")
    print(f"  Event loop lag: {lag_ms:.3f}ms")

    return {
        "active_tasks": active_count,
        "event_loop_lag_ms": round(lag_ms, 3),
    }


# ============================================================================
# Database Pool Metrics (requires DB connection)
# ============================================================================

async def profile_database() -> dict:
    """Profile database connection pool metrics.

    Returns dict with:
    - active_connections: In-use connections
    - idle_connections: Available connections
    - pool_size: Total pool size
    """
    print(f"\n=== Database Pool Metrics ===")

    try:
        from app.database.pool import get_pool

        pool = await get_pool()
        if pool is None:
            print("⚠ Database not available (graceful degradation)")
            return {"status": "unavailable"}

        size = pool.get_size()
        free = pool.get_idle_size()
        active = size - free

        print(f"\nResults:")
        print(f"  Pool size: {size}")
        print(f"  Active: {active}")
        print(f"  Idle: {free}")

        return {
            "status": "connected",
            "pool_size": size,
            "active_connections": active,
            "idle_connections": free,
        }

    except ImportError:
        print("⚠ Database module not available")
        return {"status": "not_configured"}


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Performance profiling suite")
    parser.add_argument(
        "--mode",
        choices=["all", "cpu", "memory", "asyncio", "db"],
        default="all",
        help="Profiling mode (default: all)",
    )
    parser.add_argument(
        "--output",
        default="performance_results.json",
        help="JSON output file (default: performance_results.json)",
    )
    parser.add_argument(
        "--cpu-messages",
        type=int,
        default=10000,
        help="Message count for CPU profiling (default: 10000)",
    )
    parser.add_argument(
        "--memory-messages",
        type=int,
        default=50000,
        help="Message count for memory profiling (default: 50000)",
    )

    args = parser.parse_args()

    results = {
        "timestamp": datetime.now().isoformat(),
        "mode": args.mode,
    }

    # Run profiling modes
    if args.mode in ["all", "cpu"]:
        results["cpu"] = profile_cpu(args.cpu_messages)

    if args.mode in ["all", "memory"]:
        results["memory"] = profile_memory(args.memory_messages)

    if args.mode in ["all", "asyncio"]:
        results["asyncio"] = asyncio.run(profile_asyncio())

    if args.mode in ["all", "db"]:
        results["database"] = asyncio.run(profile_database())

    # Save JSON
    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n✓ Saved {args.output}")
    print(f"\nNext: View CPU profile with: snakeviz cpu_profile.prof")


if __name__ == "__main__":
    main()
```

## Usage Examples

```bash
# Full profiling (all modes)
cd /Users/minh/Projects/stock-tracker
./backend/scripts/profile-performance-benchmarks.py

# CPU only (faster)
./backend/scripts/profile-performance-benchmarks.py --mode cpu

# Memory profiling with custom message count
./backend/scripts/profile-performance-benchmarks.py --mode memory --memory-messages 100000

# Output to custom file
./backend/scripts/profile-performance-benchmarks.py --output my_results.json

# View CPU profile interactively
snakeviz cpu_profile.prof
```

## Output Files

```
backend/
├── scripts/
│   └── profile-performance-benchmarks.py
├── cpu_profile.prof                # cProfile binary
├── cpu_profile.html                # snakeviz visualization (if installed)
├── memory_stats.txt                # Detailed memory report
└── performance_results.json        # JSON for automated reports
```

## JSON Output Schema

```json
{
  "timestamp": "2026-02-11T09:36:00",
  "mode": "all",
  "cpu": {
    "total_time": 2.45,
    "message_count": 10000,
    "messages_per_second": 4081.6,
    "avg_latency_ms": 0.245,
    "top_functions": [
      {"function": "handle_trade", "cumtime": 1.234}
    ]
  },
  "memory": {
    "baseline_mb": 12.34,
    "peak_mb": 45.67,
    "delta_mb": 33.33,
    "message_count": 50000,
    "top_allocators": [
      {"file": "session_aggregator.py:42", "size_kb": 1024}
    ]
  },
  "asyncio": {
    "active_tasks": 3,
    "event_loop_lag_ms": 0.123
  },
  "database": {
    "status": "connected",
    "pool_size": 10,
    "active_connections": 2,
    "idle_connections": 8
  }
}
```

## Performance Baselines

**Target Metrics** (for Phase 4 benchmark report):

| Metric | Target | Current |
|--------|--------|---------|
| CPU throughput | >3000 msg/s | TBD |
| Avg latency | <1ms per message | TBD |
| Memory delta | <100MB @ 50K msgs | TBD |
| Event loop lag | <1ms | TBD |
| DB pool utilization | <80% | TBD |

## Success Criteria

- [ ] Script runs without errors in all modes
- [ ] CPU profile generates snakeviz HTML
- [ ] Memory profiling tracks delta correctly
- [ ] Asyncio monitoring detects active tasks
- [ ] Database metrics query pool stats (or graceful skip)
- [ ] JSON output contains all required fields
- [ ] Script completes in <60s for default settings
- [ ] Output files created in backend/ directory

## Dependencies

- cProfile, pstats (stdlib)
- tracemalloc (stdlib)
- asyncio (stdlib)
- snakeviz (optional): `pip install snakeviz`

## Next Phase

Phase 4: Create benchmark report template that auto-fills from this JSON output.
