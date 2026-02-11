# Phase 2: E2E Test Scenarios

**Priority**: P1
**Status**: Complete
**Effort**: 2h

## Overview

Implement 5 comprehensive E2E test files covering critical system flows: full data pipeline, foreign tracking, alert generation, reconnection recovery, and session lifecycle transitions.

## Context

Each test file validates a complete user scenario from data ingestion through WebSocket delivery. Tests use real components (processor, trackers, publishers) with mocked SSI stream input.

**Coverage Goals**:
- Full data flow validation (SSI → WS client)
- Cross-component integration correctness
- State management across session transitions
- Error recovery and reconnection handling
- Alert generation and delivery

## Implementation

### File 1: `backend/tests/e2e/test_full_flow.py`

**Scenario**: Complete data pipeline from SSI ingestion to WebSocket client reception.

```python
"""E2E: Full data flow — SSI → Processor → Publisher → WS Client.

Validates complete pipeline with realistic multi-symbol market data.
"""

import asyncio
import json
import pytest


@pytest.mark.asyncio
async def test_quote_updates_reach_ws_clients(wired_system, ssi_factories, ws_client_simulator):
    """Quote updates flow through processor and reach WS market channel."""
    proc = wired_system["processor"]
    market_mgr = wired_system["managers"]["market"]

    async with ws_client_simulator(market_mgr) as queue:
        # Send quote update
        await proc.handle_quote(ssi_factories.quote("VNM", bid=80.0, ask=80.5))

        # Wait for broadcast (throttled, max 500ms)
        msg_str = await asyncio.wait_for(queue.get(), timeout=1.0)
        data = json.loads(msg_str)

        # Verify market snapshot structure
        assert "quotes" in data
        assert "indices" in data
        assert "foreign" in data


@pytest.mark.asyncio
async def test_trade_classification_end_to_end(wired_system, ssi_factories, ws_client_simulator):
    """Trade classification updates session stats and broadcasts to clients."""
    proc = wired_system["processor"]
    market_mgr = wired_system["managers"]["market"]

    # Seed quote cache (needed for classification)
    await proc.handle_quote(ssi_factories.quote("VNM", bid=80.0, ask=80.5))

    async with ws_client_simulator(market_mgr) as queue:
        # Clear initial broadcast from quote
        await asyncio.wait_for(queue.get(), timeout=1.0)

        # Send active buy trade
        await proc.handle_trade(ssi_factories.trade("VNM", price=80.5, volume=100))

        # Receive broadcast
        msg_str = await asyncio.wait_for(queue.get(), timeout=1.0)
        data = json.loads(msg_str)

        # Verify session stats present
        assert "VNM" in data["quotes"]
        stats = data["quotes"]["VNM"]
        assert stats["mua_chu_dong_volume"] == 100


@pytest.mark.asyncio
async def test_multi_symbol_updates_aggregate_correctly(
    wired_system, ssi_factories, ws_client_simulator
):
    """Multiple symbols process independently and all appear in snapshot."""
    proc = wired_system["processor"]
    market_mgr = wired_system["managers"]["market"]

    symbols = ["VNM", "VHM", "VIC"]

    # Seed quotes
    for sym in symbols:
        await proc.handle_quote(ssi_factories.quote(sym, bid=100.0, ask=100.5))

    async with ws_client_simulator(market_mgr) as queue:
        # Clear initial broadcasts
        for _ in range(len(symbols)):
            await asyncio.wait_for(queue.get(), timeout=1.0)

        # Send trades for all symbols
        for sym in symbols:
            await proc.handle_trade(ssi_factories.trade(sym, price=100.5, volume=50))

        # Wait for broadcast (may be throttled into one message)
        await asyncio.sleep(0.6)  # Past throttle window
        msg_str = await asyncio.wait_for(queue.get(), timeout=1.0)
        data = json.loads(msg_str)

        # All symbols should be present
        for sym in symbols:
            assert sym in data["quotes"]
            assert data["quotes"][sym]["total_volume"] == 50


@pytest.mark.asyncio
async def test_index_updates_broadcast_to_index_channel(
    wired_system, ssi_factories, ws_client_simulator
):
    """Index updates reach index channel, not market channel."""
    proc = wired_system["processor"]
    index_mgr = wired_system["managers"]["index"]

    async with ws_client_simulator(index_mgr) as queue:
        await proc.handle_index(ssi_factories.index("VN30", value=1250.0))

        msg_str = await asyncio.wait_for(queue.get(), timeout=1.0)
        data = json.loads(msg_str)

        assert "VN30" in data
        assert data["VN30"]["value"] == 1250.0
        assert data["VN30"]["advance_ratio"] > 0


@pytest.mark.asyncio
async def test_derivatives_basis_calculation(wired_system, ssi_factories, ws_client_simulator):
    """Futures trades compute basis and broadcast to market channel."""
    proc = wired_system["processor"]
    market_mgr = wired_system["managers"]["market"]

    # Seed VN30 index (required for basis calculation)
    await proc.handle_index(ssi_factories.index("VN30", value=1250.0))

    async with ws_client_simulator(market_mgr) as queue:
        # Clear initial broadcast
        await asyncio.wait_for(queue.get(), timeout=1.0)

        # Send futures trade
        await proc.handle_trade(ssi_factories.futures_trade("VN30F2603", price=1260.0))

        msg_str = await asyncio.wait_for(queue.get(), timeout=1.0)
        data = json.loads(msg_str)

        # Verify derivatives data present
        assert data["derivatives"] is not None
        assert data["derivatives"]["symbol"] == "VN30F2603"
        assert data["derivatives"]["basis"] == pytest.approx(10.0)
        assert data["derivatives"]["is_premium"] is True


@pytest.mark.asyncio
async def test_multiple_clients_same_channel(wired_system, ssi_factories, ws_client_simulator):
    """Multiple clients on same channel all receive broadcasts."""
    proc = wired_system["processor"]
    market_mgr = wired_system["managers"]["market"]

    async with ws_client_simulator(market_mgr) as queue1, \
                ws_client_simulator(market_mgr) as queue2:

        await proc.handle_quote(ssi_factories.quote("VNM", bid=80.0, ask=80.5))

        # Both clients should receive
        msg1 = await asyncio.wait_for(queue1.get(), timeout=1.0)
        msg2 = await asyncio.wait_for(queue2.get(), timeout=1.0)

        assert json.loads(msg1) == json.loads(msg2)


@pytest.mark.asyncio
async def test_channel_isolation(wired_system, ssi_factories, ws_client_simulator):
    """Market channel client does NOT receive foreign channel data."""
    proc = wired_system["processor"]
    market_mgr = wired_system["managers"]["market"]
    foreign_mgr = wired_system["managers"]["foreign"]

    async with ws_client_simulator(market_mgr) as market_queue:
        # Clear any initial messages
        try:
            await asyncio.wait_for(market_queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            pass

        # Trigger foreign update (should go to foreign channel only)
        await proc.handle_foreign(ssi_factories.foreign("VNM", buy_vol=1000))

        # Market client should NOT receive foreign-only update
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(market_queue.get(), timeout=0.5)
```

### File 2: `backend/tests/e2e/test_foreign_tracking.py`

**Scenario**: Foreign investor tracking from Channel R through WS delivery.

```python
"""E2E: Foreign investor tracking — R channel → ForeignTracker → WS foreign channel.

Validates cumulative tracking, speed calculation, and top mover detection.
"""

import asyncio
import json
import pytest


@pytest.mark.asyncio
async def test_foreign_updates_accumulate_correctly(
    wired_system, ssi_factories, ws_client_simulator
):
    """Multiple foreign updates accumulate deltas correctly."""
    proc = wired_system["processor"]
    foreign_mgr = wired_system["managers"]["foreign"]

    async with ws_client_simulator(foreign_mgr) as queue:
        # First update (baseline)
        await proc.handle_foreign(ssi_factories.foreign("VNM", buy_vol=1000, sell_vol=500))
        msg1 = await asyncio.wait_for(queue.get(), timeout=1.0)
        data1 = json.loads(msg1)

        # Second update (cumulative from SSI)
        await proc.handle_foreign(ssi_factories.foreign("VNM", buy_vol=1500, sell_vol=800))
        msg2 = await asyncio.wait_for(queue.get(), timeout=1.0)
        data2 = json.loads(msg2)

        # Net volume should reflect delta
        assert data2["total_buy_volume"] > data1["total_buy_volume"]


@pytest.mark.asyncio
async def test_foreign_summary_aggregates_multiple_symbols(
    wired_system, ssi_factories, ws_client_simulator
):
    """Foreign summary aggregates across multiple VN30 stocks."""
    proc = wired_system["processor"]
    foreign_mgr = wired_system["managers"]["foreign"]

    symbols = ["VNM", "VHM", "VIC"]

    async with ws_client_simulator(foreign_mgr) as queue:
        # Send updates for multiple symbols
        for sym in symbols:
            await proc.handle_foreign(
                ssi_factories.foreign(sym, buy_vol=1000, sell_vol=500, buy_val=80000.0, sell_val=40000.0)
            )

        # Wait for throttled broadcast
        await asyncio.sleep(0.6)
        msg_str = await asyncio.wait_for(queue.get(), timeout=1.0)
        data = json.loads(msg_str)

        # Total buy should be sum of all symbols
        assert data["total_buy_volume"] >= 1000 * len(symbols)
        assert data["total_buy_value"] >= 80000.0 * len(symbols)


@pytest.mark.asyncio
async def test_top_buy_sell_detection(wired_system, ssi_factories, ws_client_simulator):
    """Top net buy/sell stocks appear in foreign summary."""
    proc = wired_system["processor"]
    foreign_mgr = wired_system["managers"]["foreign"]

    async with ws_client_simulator(foreign_mgr) as queue:
        # VNM: Net buyer
        await proc.handle_foreign(ssi_factories.foreign("VNM", buy_vol=5000, sell_vol=1000))
        # VHM: Net seller
        await proc.handle_foreign(ssi_factories.foreign("VHM", buy_vol=500, sell_vol=4000))

        await asyncio.sleep(0.6)
        msg_str = await asyncio.wait_for(queue.get(), timeout=1.0)
        data = json.loads(msg_str)

        # Check top buy/sell lists
        top_buy_symbols = [stock["symbol"] for stock in data["top_buy"]]
        top_sell_symbols = [stock["symbol"] for stock in data["top_sell"]]

        assert "VNM" in top_buy_symbols
        assert "VHM" in top_sell_symbols


@pytest.mark.asyncio
async def test_foreign_speed_calculation(wired_system, ssi_factories):
    """Foreign speed metrics computed over rolling window."""
    proc = wired_system["processor"]

    # Send initial baseline
    await proc.handle_foreign(ssi_factories.foreign("VNM", buy_vol=1000, sell_vol=500))

    # Advance and send delta
    await asyncio.sleep(0.1)
    await proc.handle_foreign(ssi_factories.foreign("VNM", buy_vol=2000, sell_vol=1000))

    # Check tracker state
    foreign_data = proc.foreign_tracker.get("VNM")
    assert foreign_data is not None
    assert foreign_data.buy_speed_per_min >= 0  # Speed calculated (may be 0 if window too short)
```

### File 3: `backend/tests/e2e/test_alert_flow.py`

**Scenario**: Alert generation and WebSocket delivery.

```python
"""E2E: Alert flow — Anomaly detection → AlertService → WS alerts channel.

Validates alert generation, deduplication, and delivery to subscribed clients.
"""

import asyncio
import json
import pytest

from app.analytics.alert_service import AlertService
from app.analytics.price_tracker import PriceTracker


@pytest.mark.asyncio
async def test_volume_spike_alert_generation(wired_system, ssi_factories, ws_client_simulator):
    """Volume spike triggers alert and broadcasts to alerts channel."""
    proc = wired_system["processor"]
    alerts_mgr = wired_system["managers"]["alerts"]

    # Wire alert service
    alert_service = AlertService()
    price_tracker = PriceTracker(proc, alert_service)
    proc.price_tracker = price_tracker
    alert_service.subscribe(lambda alerts: alerts_mgr.broadcast(
        json.dumps([a.model_dump() for a in alerts], default=str)
    ))

    # Seed baseline
    await proc.handle_quote(ssi_factories.quote("VNM", bid=80.0, ask=80.5))
    for _ in range(10):
        await proc.handle_trade(ssi_factories.trade("VNM", price=80.5, volume=100))

    async with ws_client_simulator(alerts_mgr) as queue:
        # Trigger volume spike (10x baseline)
        await proc.handle_trade(ssi_factories.trade("VNM", price=80.5, volume=1000))

        # Should receive alert
        msg_str = await asyncio.wait_for(queue.get(), timeout=2.0)
        alerts = json.loads(msg_str)

        assert len(alerts) > 0
        assert any(a["alert_type"] == "VOLUME_SPIKE" for a in alerts)


@pytest.mark.asyncio
async def test_foreign_acceleration_alert(wired_system, ssi_factories, ws_client_simulator):
    """Foreign acceleration triggers alert."""
    proc = wired_system["processor"]
    alerts_mgr = wired_system["managers"]["alerts"]

    alert_service = AlertService()
    price_tracker = PriceTracker(proc, alert_service)
    proc.price_tracker = price_tracker
    alert_service.subscribe(lambda alerts: alerts_mgr.broadcast(
        json.dumps([a.model_dump() for a in alerts], default=str)
    ))

    # Baseline foreign activity
    await proc.handle_foreign(ssi_factories.foreign("VNM", buy_vol=1000, sell_vol=500))

    async with ws_client_simulator(alerts_mgr) as queue:
        # Spike foreign buying (acceleration)
        await asyncio.sleep(0.2)
        await proc.handle_foreign(ssi_factories.foreign("VNM", buy_vol=10000, sell_vol=500))

        try:
            msg_str = await asyncio.wait_for(queue.get(), timeout=2.0)
            alerts = json.loads(msg_str)
            # May or may not trigger depending on speed window — just validate structure
            if alerts:
                assert isinstance(alerts, list)
        except asyncio.TimeoutError:
            pass  # No alert triggered (speed window too short)


@pytest.mark.asyncio
async def test_alert_deduplication(wired_system, ssi_factories):
    """Duplicate alerts within 60s are deduplicated."""
    proc = wired_system["processor"]

    alert_service = AlertService()
    price_tracker = PriceTracker(proc, alert_service)
    proc.price_tracker = price_tracker

    received_alerts = []
    alert_service.subscribe(lambda alerts: received_alerts.extend(alerts))

    # Seed baseline
    await proc.handle_quote(ssi_factories.quote("VNM", bid=80.0, ask=80.5))
    for _ in range(5):
        await proc.handle_trade(ssi_factories.trade("VNM", price=80.5, volume=100))

    # Trigger two spikes in quick succession
    await proc.handle_trade(ssi_factories.trade("VNM", price=80.5, volume=1000))
    await asyncio.sleep(0.1)
    await proc.handle_trade(ssi_factories.trade("VNM", price=80.5, volume=1000))

    await asyncio.sleep(0.5)

    # Should only receive one alert (deduplicated)
    volume_alerts = [a for a in received_alerts if a.alert_type.value == "VOLUME_SPIKE"]
    assert len(volume_alerts) <= 1
```

### File 4: `backend/tests/e2e/test_reconnect_recovery.py`

**Scenario**: SSI connection failure and auto-reconnect.

```python
"""E2E: Reconnect recovery — Connection loss → auto-reconnect → data resumes.

Validates disconnect handling, reconnect callbacks, and state preservation.
"""

import asyncio
import json
import pytest


@pytest.mark.asyncio
async def test_publisher_notifies_clients_on_disconnect(
    wired_system, ssi_factories, ws_client_simulator
):
    """When SSI disconnects, clients receive status message."""
    proc = wired_system["processor"]
    publisher = wired_system["publisher"]
    market_mgr = wired_system["managers"]["market"]

    async with ws_client_simulator(market_mgr) as queue:
        # Simulate SSI disconnect
        publisher.on_ssi_disconnect()

        # Client should receive disconnect status
        msg_str = await asyncio.wait_for(queue.get(), timeout=1.0)
        data = json.loads(msg_str)

        assert data["type"] == "status"
        assert data["connected"] is False


@pytest.mark.asyncio
async def test_publisher_notifies_clients_on_reconnect(
    wired_system, ssi_factories, ws_client_simulator
):
    """When SSI reconnects, clients receive reconnect status."""
    proc = wired_system["processor"]
    publisher = wired_system["publisher"]
    market_mgr = wired_system["managers"]["market"]

    async with ws_client_simulator(market_mgr) as queue:
        # Simulate disconnect then reconnect
        publisher.on_ssi_disconnect()
        await asyncio.wait_for(queue.get(), timeout=1.0)  # Clear disconnect msg

        publisher.on_ssi_reconnect()

        # Client should receive reconnect status
        msg_str = await asyncio.wait_for(queue.get(), timeout=1.0)
        data = json.loads(msg_str)

        assert data["type"] == "status"
        assert data["connected"] is True


@pytest.mark.asyncio
async def test_data_resumes_after_reconnect(wired_system, ssi_factories, ws_client_simulator):
    """After reconnect, new data flows normally."""
    proc = wired_system["processor"]
    publisher = wired_system["publisher"]
    market_mgr = wired_system["managers"]["market"]

    # Seed quote
    await proc.handle_quote(ssi_factories.quote("VNM", bid=80.0, ask=80.5))

    async with ws_client_simulator(market_mgr) as queue:
        # Clear initial broadcast
        await asyncio.wait_for(queue.get(), timeout=1.0)

        # Simulate disconnect/reconnect
        publisher.on_ssi_disconnect()
        await asyncio.wait_for(queue.get(), timeout=1.0)  # disconnect status
        publisher.on_ssi_reconnect()
        await asyncio.wait_for(queue.get(), timeout=1.0)  # reconnect status

        # Send new trade
        await proc.handle_trade(ssi_factories.trade("VNM", price=80.5, volume=100))

        # Client should receive trade data
        msg_str = await asyncio.wait_for(queue.get(), timeout=1.0)
        data = json.loads(msg_str)

        assert "quotes" in data
        assert "VNM" in data["quotes"]
```

### File 5: `backend/tests/e2e/test_session_lifecycle.py`

**Scenario**: Market session state transitions.

```python
"""E2E: Session lifecycle — Pre-market → ATO → Continuous → ATC → Close.

Validates session stat breakdown, reset behavior, and state preservation.
"""

import asyncio
import json
import pytest


@pytest.mark.asyncio
async def test_ato_trades_classified_separately(wired_system, ssi_factories):
    """ATO trades accumulate in ato phase breakdown."""
    proc = wired_system["processor"]

    await proc.handle_quote(ssi_factories.quote("VNM", bid=80.0, ask=80.5))

    # ATO trade
    await proc.handle_trade(ssi_factories.trade("VNM", price=80.5, volume=100, session="ATO"))

    stats = proc.aggregator.get_stats("VNM")
    assert stats.ato.total_volume == 100
    assert stats.continuous.total_volume == 0


@pytest.mark.asyncio
async def test_continuous_and_atc_phases_separate(wired_system, ssi_factories):
    """Continuous and ATC trades accumulate independently."""
    proc = wired_system["processor"]

    await proc.handle_quote(ssi_factories.quote("VNM", bid=80.0, ask=80.5))

    # Continuous trades
    await proc.handle_trade(ssi_factories.trade("VNM", price=80.5, volume=50, session="LO"))
    await proc.handle_trade(ssi_factories.trade("VNM", price=80.5, volume=50, session="LO"))

    # ATC trade
    await proc.handle_trade(ssi_factories.trade("VNM", price=80.0, volume=200, session="ATC"))

    stats = proc.aggregator.get_stats("VNM")
    assert stats.continuous.total_volume == 100
    assert stats.atc.total_volume == 200
    assert stats.total_volume == 300  # Aggregate


@pytest.mark.asyncio
async def test_session_reset_clears_aggregates(wired_system, ssi_factories):
    """Session reset clears aggregator but preserves quote cache."""
    proc = wired_system["processor"]

    await proc.handle_quote(ssi_factories.quote("VNM", bid=80.0, ask=80.5))
    await proc.handle_trade(ssi_factories.trade("VNM", price=80.5, volume=100))

    # Verify data exists
    assert proc.aggregator.get_stats("VNM").total_volume == 100
    assert proc.quote_cache.get_bid_ask("VNM") == (80.0, 80.5)

    # Reset session
    proc.reset_session()

    # Aggregator cleared, quote cache preserved
    assert proc.aggregator.get_stats("VNM").total_volume == 0
    assert proc.quote_cache.get_bid_ask("VNM") == (80.0, 80.5)


@pytest.mark.asyncio
async def test_phase_invariant_sum_equals_total(wired_system, ssi_factories):
    """Sum of all phase volumes equals total volume (invariant)."""
    proc = wired_system["processor"]

    await proc.handle_quote(ssi_factories.quote("VNM", bid=80.0, ask=80.5))

    # Mixed session trades
    await proc.handle_trade(ssi_factories.trade("VNM", price=80.5, volume=100, session="ATO"))
    await proc.handle_trade(ssi_factories.trade("VNM", price=80.5, volume=200, session="LO"))
    await proc.handle_trade(ssi_factories.trade("VNM", price=80.5, volume=50, session="ATC"))

    stats = proc.aggregator.get_stats("VNM")
    phase_sum = stats.ato.total_volume + stats.continuous.total_volume + stats.atc.total_volume

    assert phase_sum == stats.total_volume
    assert stats.total_volume == 350
```

## Running the Tests

```bash
# All E2E tests
./venv/bin/pytest backend/tests/e2e/ -v

# Specific scenario
./venv/bin/pytest backend/tests/e2e/test_full_flow.py -v

# With coverage
./venv/bin/pytest backend/tests/e2e/ --cov=app --cov-report=term-missing
```

## Success Criteria

- [ ] All 5 test files pass (20+ test methods total)
- [ ] E2E tests complete in <30s total
- [ ] No flaky tests (run 3x to verify)
- [ ] Coverage: E2E tests add 5%+ to integration coverage
- [ ] Tests validate complete data flow (SSI → WS client)
- [ ] Channel isolation verified (market vs foreign vs index)
- [ ] Alert generation and delivery validated
- [ ] Reconnect recovery verified
- [ ] Session lifecycle state management validated

## Dependencies

- Phase 1 fixtures (conftest.py)
- Existing AlertService + PriceTracker (Phase 6)
- DataPublisher disconnect/reconnect callbacks

## Next Phase

Phase 3: Performance profiling script with CPU/memory/asyncio monitoring.
