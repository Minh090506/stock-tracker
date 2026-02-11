"""E2E: Reconnect recovery — SSI disconnect → reconnect → data resumes.

Validates disconnect/reconnect status messages to WS clients
and data flow resumption after reconnection.
"""

import asyncio
import json

import pytest


@pytest.mark.asyncio
async def test_disconnect_notifies_clients(wired_system, ws_receive):
    """SSI disconnect broadcasts status message to all connected clients."""
    publisher = wired_system["publisher"]
    market_mgr = wired_system["managers"]["market"]

    ws = await ws_receive(market_mgr)
    publisher.on_ssi_disconnect()

    msg = json.loads(await asyncio.wait_for(ws.messages.get(), timeout=1.0))
    assert msg["type"] == "status"
    assert msg["connected"] is False


@pytest.mark.asyncio
async def test_reconnect_notifies_clients(wired_system, ws_receive):
    """SSI reconnect broadcasts connected status after disconnect."""
    publisher = wired_system["publisher"]
    market_mgr = wired_system["managers"]["market"]

    ws = await ws_receive(market_mgr)

    # Disconnect then reconnect
    publisher.on_ssi_disconnect()
    await asyncio.wait_for(ws.messages.get(), timeout=1.0)  # drain disconnect

    publisher.on_ssi_reconnect()
    msg = json.loads(await asyncio.wait_for(ws.messages.get(), timeout=1.0))
    assert msg["type"] == "status"
    assert msg["connected"] is True


@pytest.mark.asyncio
async def test_data_resumes_after_reconnect(wired_system, f, ws_receive):
    """After reconnect, new market data flows to clients normally."""
    proc = wired_system["processor"]
    publisher = wired_system["publisher"]
    market_mgr = wired_system["managers"]["market"]

    # Seed quote BEFORE connecting (no broadcast captured)
    await proc.handle_quote(f.quote("VNM", bid=80.0, ask=80.5))

    ws = await ws_receive(market_mgr)

    # Disconnect/reconnect cycle
    publisher.on_ssi_disconnect()
    await asyncio.wait_for(ws.messages.get(), timeout=1.0)
    publisher.on_ssi_reconnect()
    await asyncio.wait_for(ws.messages.get(), timeout=1.0)

    # New trade after reconnect
    await proc.handle_trade(f.trade("VNM", price=80.5, volume=100))
    msg = json.loads(await asyncio.wait_for(ws.messages.get(), timeout=2.0))

    assert "quotes" in msg
    assert "VNM" in msg["quotes"]


@pytest.mark.asyncio
async def test_disconnect_reaches_all_channels(wired_system, ws_receive):
    """Disconnect status reaches clients on all channels."""
    publisher = wired_system["publisher"]
    managers = wired_system["managers"]

    # Connect clients on market, foreign, and index channels
    ws_market = await ws_receive(managers["market"])
    ws_foreign = await ws_receive(managers["foreign"])
    ws_index = await ws_receive(managers["index"])

    publisher.on_ssi_disconnect()

    for ws in [ws_market, ws_foreign, ws_index]:
        msg = json.loads(await asyncio.wait_for(ws.messages.get(), timeout=1.0))
        assert msg["type"] == "status"
        assert msg["connected"] is False
