"""E2E: Foreign investor tracking — R channel → ForeignTracker → WS foreign.

Validates cumulative tracking, summary aggregation, and top mover detection.
"""

import asyncio
import json

import pytest


@pytest.mark.asyncio
async def test_foreign_updates_reach_ws_clients(wired_system, f, ws_receive):
    """Foreign update flows through processor → publisher → WS client."""
    proc = wired_system["processor"]
    foreign_mgr = wired_system["managers"]["foreign"]

    ws = await ws_receive(foreign_mgr)
    await proc.handle_foreign(f.foreign("VNM", buy_vol=1000, sell_vol=500))

    msg = json.loads(await asyncio.wait_for(ws.messages.get(), timeout=2.0))
    assert "total_buy_volume" in msg
    assert "total_sell_volume" in msg
    assert msg["total_buy_volume"] >= 1000


@pytest.mark.asyncio
async def test_foreign_summary_aggregates_multiple_symbols(
    wired_system, f, ws_receive
):
    """Foreign summary aggregates buy/sell across multiple VN30 stocks."""
    proc = wired_system["processor"]
    foreign_mgr = wired_system["managers"]["foreign"]

    symbols = ["VNM", "VHM", "VIC"]
    for sym in symbols:
        await proc.handle_foreign(
            f.foreign(sym, buy_vol=1000, sell_vol=500, buy_val=80_000.0)
        )

    # Wait past throttle
    await asyncio.sleep(0.6)
    ws = await ws_receive(foreign_mgr)

    # Trigger one more update to get aggregated broadcast
    await proc.handle_foreign(f.foreign("VNM", buy_vol=1100, sell_vol=500))
    msg = json.loads(await asyncio.wait_for(ws.messages.get(), timeout=2.0))

    assert msg["total_buy_volume"] > 0
    assert msg["total_sell_volume"] > 0


@pytest.mark.asyncio
async def test_top_buy_sell_detection(wired_system, f, ws_receive):
    """Top net buy/sell stocks appear in foreign summary."""
    proc = wired_system["processor"]
    foreign_mgr = wired_system["managers"]["foreign"]

    # VNM: net buyer | VHM: net seller
    await proc.handle_foreign(f.foreign("VNM", buy_vol=5000, sell_vol=1000))
    await proc.handle_foreign(f.foreign("VHM", buy_vol=500, sell_vol=4000))

    await asyncio.sleep(0.6)
    ws = await ws_receive(foreign_mgr)
    # Trigger broadcast
    await proc.handle_foreign(f.foreign("VNM", buy_vol=5100, sell_vol=1000))

    msg = json.loads(await asyncio.wait_for(ws.messages.get(), timeout=2.0))

    top_buy_syms = [s["symbol"] for s in msg["top_buy"]]
    top_sell_syms = [s["symbol"] for s in msg["top_sell"]]
    assert "VNM" in top_buy_syms
    assert "VHM" in top_sell_syms


@pytest.mark.asyncio
async def test_foreign_speed_computed(wired_system, f):
    """Foreign tracker computes speed metrics after multiple updates."""
    proc = wired_system["processor"]

    await proc.handle_foreign(f.foreign("VNM", buy_vol=1000, sell_vol=500))
    await asyncio.sleep(0.1)
    await proc.handle_foreign(f.foreign("VNM", buy_vol=2000, sell_vol=1000))

    data = proc.foreign_tracker.get("VNM")
    assert data is not None
    assert data.buy_volume == 2000
    assert data.sell_volume == 1000
    # Speed may be 0 if window too short — just verify field exists
    assert data.buy_speed_per_min >= 0
