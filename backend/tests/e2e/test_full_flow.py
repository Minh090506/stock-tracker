"""E2E: Full data flow — SSI → Processor → Publisher → WS Client.

Validates complete pipeline: quote/trade/index/derivatives processing
through DataPublisher throttle to ConnectionManager broadcast.
"""

import asyncio
import json

import pytest


@pytest.mark.asyncio
async def test_quote_updates_reach_ws_clients(wired_system, f, ws_receive):
    """Quote update flows through processor → publisher → WS client."""
    proc = wired_system["processor"]
    market_mgr = wired_system["managers"]["market"]

    ws = await ws_receive(market_mgr)
    await proc.handle_quote(f.quote("VNM", bid=80.0, ask=80.5))

    msg = json.loads(await asyncio.wait_for(ws.messages.get(), timeout=2.0))
    assert "quotes" in msg
    assert "indices" in msg
    assert "foreign" in msg


@pytest.mark.asyncio
async def test_trade_classification_end_to_end(wired_system, f, ws_receive):
    """Trade at ask price → classified as mua_chu_dong → broadcast."""
    proc = wired_system["processor"]
    market_mgr = wired_system["managers"]["market"]

    # Seed quote cache BEFORE connecting client (no broadcast captured)
    await proc.handle_quote(f.quote("VNM", bid=80.0, ask=80.5))

    # Connect after quote seed — next broadcast will be the trade
    ws = await ws_receive(market_mgr)

    # Active buy trade (price == ask)
    await proc.handle_trade(f.trade("VNM", price=80.5, volume=100))
    msg = json.loads(await asyncio.wait_for(ws.messages.get(), timeout=2.0))

    assert "VNM" in msg["quotes"]
    assert msg["quotes"]["VNM"]["mua_chu_dong_volume"] == 100


@pytest.mark.asyncio
async def test_multi_symbol_updates(wired_system, f, ws_receive):
    """Multiple symbols process independently and all appear in snapshot."""
    proc = wired_system["processor"]
    market_mgr = wired_system["managers"]["market"]
    symbols = ["VNM", "VHM", "VIC"]

    # Seed quotes BEFORE connecting (no broadcasts captured)
    for sym in symbols:
        await proc.handle_quote(f.quote(sym, bid=100.0, ask=100.5))

    ws = await ws_receive(market_mgr)

    # Send trades for all symbols
    for sym in symbols:
        await proc.handle_trade(f.trade(sym, price=100.5, volume=50))

    # Wait past throttle window for aggregated broadcast
    await asyncio.sleep(0.6)
    # Get the latest message (may have multiple due to throttle)
    msg = None
    while not ws.messages.empty():
        msg = json.loads(ws.messages.get_nowait())
    if msg is None:
        msg = json.loads(await asyncio.wait_for(ws.messages.get(), timeout=2.0))

    for sym in symbols:
        assert sym in msg["quotes"]
        assert msg["quotes"][sym]["total_volume"] == 50


@pytest.mark.asyncio
async def test_index_updates_broadcast_to_index_channel(wired_system, f, ws_receive):
    """Index updates reach index channel clients."""
    proc = wired_system["processor"]
    index_mgr = wired_system["managers"]["index"]

    ws = await ws_receive(index_mgr)
    await proc.handle_index(f.index("VN30", value=1250.0))

    msg = json.loads(await asyncio.wait_for(ws.messages.get(), timeout=2.0))
    assert "VN30" in msg
    assert msg["VN30"]["value"] == 1250.0


@pytest.mark.asyncio
async def test_derivatives_basis_calculation(wired_system, f, ws_receive):
    """Futures trade computes basis against VN30 spot and broadcasts."""
    proc = wired_system["processor"]
    market_mgr = wired_system["managers"]["market"]

    # Seed VN30 index (required for basis)
    await proc.handle_index(f.index("VN30", value=1250.0))
    # Seed futures quote
    await proc.handle_quote(
        f.quote("VN30F2603", bid=1258.0, ask=1262.0, ref=1255.0)
    )

    ws = await ws_receive(market_mgr)
    # Drain initial broadcasts
    await asyncio.sleep(0.6)
    while not ws.messages.empty():
        ws.messages.get_nowait()

    # Futures trade
    await proc.handle_trade(f.futures_trade("VN30F2603", price=1260.0))

    msg = json.loads(await asyncio.wait_for(ws.messages.get(), timeout=2.0))
    assert msg["derivatives"] is not None
    assert msg["derivatives"]["symbol"] == "VN30F2603"
    # Basis = 1260.0 - 1250.0 = 10.0
    assert msg["derivatives"]["basis"] == pytest.approx(10.0)
    assert msg["derivatives"]["is_premium"] is True


@pytest.mark.asyncio
async def test_multiple_clients_same_channel(wired_system, f, ws_receive):
    """Multiple clients on same channel all receive broadcasts."""
    proc = wired_system["processor"]
    market_mgr = wired_system["managers"]["market"]

    ws1 = await ws_receive(market_mgr)
    ws2 = await ws_receive(market_mgr)

    await proc.handle_quote(f.quote("VNM", bid=80.0, ask=80.5))

    msg1 = await asyncio.wait_for(ws1.messages.get(), timeout=2.0)
    msg2 = await asyncio.wait_for(ws2.messages.get(), timeout=2.0)
    assert json.loads(msg1) == json.loads(msg2)


@pytest.mark.asyncio
async def test_channel_isolation(wired_system, f, ws_receive):
    """Foreign channel update does NOT reach market channel client."""
    proc = wired_system["processor"]
    market_mgr = wired_system["managers"]["market"]

    ws = await ws_receive(market_mgr)
    # Drain any initial messages
    await asyncio.sleep(0.2)
    while not ws.messages.empty():
        ws.messages.get_nowait()

    # Only foreign update — should not trigger market broadcast
    await proc.handle_foreign(f.foreign("VNM", buy_vol=1000))

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(ws.messages.get(), timeout=0.5)
