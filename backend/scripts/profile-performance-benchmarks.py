#!/usr/bin/env python3
"""Performance profiling — CPU hotspots, memory usage, asyncio health, DB pool.

Usage:
    ./venv/bin/python scripts/profile-performance-benchmarks.py
    ./venv/bin/python scripts/profile-performance-benchmarks.py --mode cpu
    ./venv/bin/python scripts/profile-performance-benchmarks.py --mode memory
    ./venv/bin/python scripts/profile-performance-benchmarks.py --output results.json

Outputs:
    - cpu_profile.prof (cProfile binary, view with snakeviz)
    - memory_stats.txt (top allocators)
    - performance_results.json (structured JSON for report generation)
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
from datetime import datetime
from io import StringIO
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.ssi_messages import (
    SSIForeignMessage,
    SSIIndexMessage,
    SSIQuoteMessage,
    SSITradeMessage,
)
from app.services.market_data_processor import MarketDataProcessor

logging.basicConfig(level=logging.WARNING)

# Symbols used for simulated data
VN30_SYMBOLS = [
    "VNM", "VHM", "VIC", "HPG", "MSN",
    "VCB", "BID", "CTG", "MBB", "ACB",
]


# ============================================================================
# Message generators
# ============================================================================


def _rand_quote(symbol: str) -> SSIQuoteMessage:
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


def _rand_trade(symbol: str, price: float) -> SSITradeMessage:
    return SSITradeMessage(
        symbol=symbol,
        last_price=price,
        last_vol=random.randint(10, 500),
        trading_session=random.choice(["ATO", "LO", "ATC"]),
        change=random.uniform(-2, 5),
        ratio_change=random.uniform(-1.5, 3.5),
    )


def _rand_foreign(symbol: str) -> SSIForeignMessage:
    return SSIForeignMessage(
        symbol=symbol,
        f_buy_vol=random.randint(100, 5000),
        f_sell_vol=random.randint(100, 5000),
        f_buy_val=random.uniform(10000, 500000),
        f_sell_val=random.uniform(10000, 500000),
        total_room=1_000_000,
        current_room=random.randint(500000, 999000),
    )


def _rand_index() -> SSIIndexMessage:
    return SSIIndexMessage(
        index_id=random.choice(["VN30", "VNINDEX"]),
        index_value=random.uniform(1200, 1300),
        prior_index_value=random.uniform(1190, 1290),
        change=random.uniform(-10, 10),
        ratio_change=random.uniform(-1, 1),
        advances=random.randint(10, 20),
        declines=random.randint(5, 15),
        no_changes=random.randint(0, 5),
        total_volume=random.randint(1_000_000, 5_000_000),
    )


# ============================================================================
# Simulated processing
# ============================================================================


async def _simulate_messages(proc: MarketDataProcessor, count: int):
    """Push N mixed messages through the processor."""
    # Seed quotes first
    for symbol in VN30_SYMBOLS:
        await proc.handle_quote(_rand_quote(symbol))

    for _ in range(count):
        kind = random.choice(["trade", "trade", "foreign", "index"])
        if kind == "trade":
            sym = random.choice(VN30_SYMBOLS)
            bid, ask = proc.quote_cache.get_bid_ask(sym)
            price = random.choice([bid, ask, (bid + ask) / 2])
            await proc.handle_trade(_rand_trade(sym, price))
        elif kind == "foreign":
            await proc.handle_foreign(_rand_foreign(random.choice(VN30_SYMBOLS)))
        else:
            await proc.handle_index(_rand_index())


# ============================================================================
# CPU profiling
# ============================================================================


def profile_cpu(message_count: int = 10_000) -> dict:
    """cProfile the message processing pipeline. Returns metrics dict."""
    print(f"\n=== CPU Profiling ({message_count:,} messages) ===")

    proc = MarketDataProcessor()
    profiler = cProfile.Profile()

    profiler.enable()
    start = time.perf_counter()
    asyncio.run(_simulate_messages(proc, message_count))
    elapsed = time.perf_counter() - start
    profiler.disable()

    # Save binary profile
    profiler.dump_stats("cpu_profile.prof")
    print("  Saved cpu_profile.prof")

    # Try snakeviz HTML export
    try:
        import subprocess
        subprocess.run(
            ["snakeviz", "--server", "--open", "cpu_profile.prof"],
            check=False, capture_output=True, timeout=5,
        )
    except Exception:
        pass  # snakeviz optional

    # Parse top functions
    buf = StringIO()
    stats = pstats.Stats(profiler, stream=buf)
    stats.strip_dirs().sort_stats("cumulative").print_stats(10)

    throughput = message_count / elapsed
    avg_latency_ms = (elapsed / message_count) * 1000

    print(f"  Total time:  {elapsed:.2f}s")
    print(f"  Throughput:  {throughput:,.0f} msg/s")
    print(f"  Avg latency: {avg_latency_ms:.3f}ms/msg")

    top_functions = []
    buf.seek(0)
    lines = buf.read().split("\n")
    for line in lines[5:15]:
        parts = line.split()
        if len(parts) >= 6:
            try:
                top_functions.append({
                    "function": parts[-1],
                    "cumtime": float(parts[3]),
                })
            except (ValueError, IndexError):
                pass

    return {
        "total_time_s": round(elapsed, 3),
        "message_count": message_count,
        "messages_per_second": round(throughput, 1),
        "avg_latency_ms": round(avg_latency_ms, 3),
        "top_functions": top_functions[:5],
    }


# ============================================================================
# Memory profiling
# ============================================================================


def profile_memory(message_count: int = 50_000) -> dict:
    """tracemalloc snapshot before/after sustained load. Returns metrics dict."""
    print(f"\n=== Memory Profiling ({message_count:,} messages) ===")

    tracemalloc.start()

    proc = MarketDataProcessor()
    baseline = tracemalloc.take_snapshot()
    baseline_mb = sum(s.size for s in baseline.statistics("lineno")) / 1024 / 1024

    asyncio.run(_simulate_messages(proc, message_count))

    peak = tracemalloc.take_snapshot()
    peak_mb = sum(s.size for s in peak.statistics("lineno")) / 1024 / 1024
    delta_mb = peak_mb - baseline_mb

    top_stats = peak.compare_to(baseline, "lineno")[:10]
    tracemalloc.stop()

    print(f"  Baseline: {baseline_mb:.2f} MB")
    print(f"  Peak:     {peak_mb:.2f} MB")
    print(f"  Delta:    {delta_mb:.2f} MB")

    # Write detailed report
    with open("memory_stats.txt", "w") as fh:
        fh.write(f"Memory Profiling Report — {datetime.now().isoformat()}\n\n")
        fh.write(f"Baseline: {baseline_mb:.2f} MB\n")
        fh.write(f"Peak:     {peak_mb:.2f} MB\n")
        fh.write(f"Delta:    {delta_mb:.2f} MB\n\n")
        fh.write("Top 10 Allocators:\n")
        for i, stat in enumerate(top_stats, 1):
            fh.write(f"  {i}. {stat}\n")
    print("  Saved memory_stats.txt")

    top_allocators = [
        {"location": str(s.traceback), "size_kb": round(s.size_diff / 1024, 2)}
        for s in top_stats[:5]
    ]

    return {
        "baseline_mb": round(baseline_mb, 2),
        "peak_mb": round(peak_mb, 2),
        "delta_mb": round(delta_mb, 2),
        "message_count": message_count,
        "top_allocators": top_allocators,
    }


# ============================================================================
# Asyncio monitoring
# ============================================================================


async def profile_asyncio() -> dict:
    """Measure asyncio event loop lag and task count during processing."""
    print("\n=== Asyncio Monitoring ===")

    proc = MarketDataProcessor()
    task = asyncio.create_task(_simulate_messages(proc, 1000))

    await asyncio.sleep(0.05)  # let tasks spin up

    all_tasks = asyncio.all_tasks()
    active_count = len([t for t in all_tasks if not t.done()])

    # Measure event loop scheduling lag
    t0 = time.perf_counter()
    await asyncio.sleep(0)
    lag_ms = (time.perf_counter() - t0) * 1000

    await task

    print(f"  Active tasks:    {active_count}")
    print(f"  Event loop lag:  {lag_ms:.3f}ms")

    return {
        "active_tasks": active_count,
        "event_loop_lag_ms": round(lag_ms, 3),
    }


# ============================================================================
# Database pool metrics
# ============================================================================


async def profile_database() -> dict:
    """Read asyncpg pool stats. Graceful skip if DB unavailable."""
    print("\n=== Database Pool Metrics ===")

    try:
        from app.database.pool import db

        if db.pool is None:
            print("  DB pool not initialized — skipping")
            return {"status": "unavailable"}

        size = db.pool.get_size()
        free = db.pool.get_idle_size()
        active = size - free

        print(f"  Pool size: {size}")
        print(f"  Active:    {active}")
        print(f"  Idle:      {free}")

        return {
            "status": "connected",
            "pool_size": size,
            "active_connections": active,
            "idle_connections": free,
        }
    except Exception as exc:
        print(f"  DB unavailable: {exc}")
        return {"status": "unavailable"}


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
        "--output", default="performance_results.json",
        help="JSON output path (default: performance_results.json)",
    )
    parser.add_argument(
        "--cpu-messages", type=int, default=10_000,
        help="Message count for CPU profiling (default: 10000)",
    )
    parser.add_argument(
        "--memory-messages", type=int, default=50_000,
        help="Message count for memory profiling (default: 50000)",
    )
    args = parser.parse_args()

    results = {"timestamp": datetime.now().isoformat(), "mode": args.mode}

    if args.mode in ("all", "cpu"):
        results["cpu"] = profile_cpu(args.cpu_messages)

    if args.mode in ("all", "memory"):
        results["memory"] = profile_memory(args.memory_messages)

    if args.mode in ("all", "asyncio"):
        results["asyncio"] = asyncio.run(profile_asyncio())

    if args.mode in ("all", "db"):
        results["database"] = asyncio.run(profile_database())

    output = Path(args.output)
    output.write_text(json.dumps(results, indent=2))
    print(f"\n=== Saved {output} ===")


if __name__ == "__main__":
    main()
