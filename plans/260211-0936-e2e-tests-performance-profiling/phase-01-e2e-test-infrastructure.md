# Phase 1: E2E Test Infrastructure

**Priority**: P1
**Status**: Complete
**Effort**: 1.5h

## Overview

Create foundational E2E test infrastructure with shared fixtures, SSI message factories, and fully wired processor/publisher/manager setup for realistic end-to-end testing.

## Context

E2E tests simulate the entire data flow from SSI stream ingestion through WebSocket broadcast to client reception. Unlike unit tests (isolated services with mocks) or integration tests (multi-service but limited scope), E2E tests wire ALL components together and verify complete scenarios.

**Testing Philosophy**:
- Mock SSI at the stream service boundary (use factory functions, not real SSI connection)
- All other components REAL (processor, trackers, publisher, connection managers)
- Validate data correctness at client WS endpoint (final output verification)

## Architecture

```
Test Fixture Setup:
┌─────────────────────────────────────────────────────┐
│ SSI Message Factories (Pydantic model builders)     │
└────────────┬────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────┐
│ MarketDataProcessor (real instance)                 │
│  ├─ QuoteCache                                      │
│  ├─ TradeClassifier                                 │
│  ├─ SessionAggregator                               │
│  ├─ ForeignInvestorTracker                          │
│  ├─ IndexTracker                                    │
│  └─ DerivativesTracker                              │
└────────────┬────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────┐
│ DataPublisher (wired to processor.subscribe)        │
└────────────┬────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────┐
│ ConnectionManager instances (market, foreign, etc.) │
└─────────────────────────────────────────────────────┘
```

## Implementation

### File 1: `backend/tests/e2e/__init__.py`

Empty marker file for pytest discovery.

```python
"""End-to-end tests — full system integration scenarios."""
```

### File 2: `backend/tests/e2e/conftest.py`

Shared fixtures for all E2E tests.

```python
"""E2E test fixtures — wired processor, publisher, managers, SSI factories.

Fixtures:
- processor: MarketDataProcessor with all services initialized
- wired_system: Processor + DataPublisher + ConnectionManagers wired
- ssi_factories: Message builder functions for SSI messages
"""

import asyncio
import pytest
from datetime import datetime

from app.models.ssi_messages import (
    SSIQuoteMessage,
    SSITradeMessage,
    SSIForeignMessage,
    SSIIndexMessage,
)
from app.services.market_data_processor import MarketDataProcessor
from app.websocket.connection_manager import ConnectionManager
from app.websocket.data_publisher import DataPublisher


# ============================================================================
# Core Fixtures
# ============================================================================

@pytest.fixture
def processor():
    """Fresh MarketDataProcessor with all services initialized."""
    return MarketDataProcessor()


@pytest.fixture
def connection_managers():
    """ConnectionManager instances for all channels."""
    return {
        "market": ConnectionManager(),
        "foreign": ConnectionManager(),
        "index": ConnectionManager(),
        "alerts": ConnectionManager(),
    }


@pytest.fixture
async def wired_system(processor, connection_managers):
    """Fully wired system: processor → publisher → managers.

    Returns dict with:
    - processor: MarketDataProcessor
    - publisher: DataPublisher
    - managers: dict[channel → ConnectionManager]
    """
    publisher = DataPublisher(
        processor,
        market_mgr=connection_managers["market"],
        foreign_mgr=connection_managers["foreign"],
        index_mgr=connection_managers["index"],
        alerts_mgr=connection_managers["alerts"],
    )

    # Start publisher (captures event loop)
    publisher.start()

    # Wire processor to publisher
    processor.subscribe(publisher.notify)

    yield {
        "processor": processor,
        "publisher": publisher,
        "managers": connection_managers,
    }

    # Cleanup
    publisher.stop()


# ============================================================================
# SSI Message Factories
# ============================================================================

@pytest.fixture
def ssi_factories():
    """Factory functions for creating SSI messages with realistic defaults.

    Usage:
        factories = ssi_factories
        quote = factories.quote("VNM", bid=80.0, ask=80.5)
        trade = factories.trade("VNM", price=80.5, volume=100)
    """

    class SSIMessageFactories:
        """Builder functions for SSI messages."""

        @staticmethod
        def quote(
            symbol: str,
            bid: float = 80.0,
            ask: float = 80.5,
            ref: float | None = None,
            ceiling: float | None = None,
            floor: float | None = None,
        ) -> SSIQuoteMessage:
            """Create SSIQuoteMessage with realistic defaults."""
            ref = ref or bid + 0.2
            ceiling = ceiling or round(ref * 1.07, 1)
            floor = floor or round(ref * 0.93, 1)

            return SSIQuoteMessage(
                symbol=symbol,
                bid_price_1=bid,
                ask_price_1=ask,
                ref_price=ref,
                ceiling=ceiling,
                floor=floor,
                bid_vol_1=1000,
                ask_vol_1=1000,
            )

        @staticmethod
        def trade(
            symbol: str,
            price: float,
            volume: int = 100,
            session: str = "LO",
            change: float = 0.0,
            ratio_change: float = 0.0,
        ) -> SSITradeMessage:
            """Create SSITradeMessage."""
            return SSITradeMessage(
                symbol=symbol,
                last_price=price,
                last_vol=volume,
                trading_session=session,
                change=change,
                ratio_change=ratio_change,
            )

        @staticmethod
        def foreign(
            symbol: str,
            buy_vol: int = 1000,
            sell_vol: int = 800,
            buy_val: float | None = None,
            sell_val: float | None = None,
            total_room: int = 1000000,
            current_room: int = 500000,
        ) -> SSIForeignMessage:
            """Create SSIForeignMessage."""
            buy_val = buy_val or (buy_vol * 80.0)
            sell_val = sell_val or (sell_vol * 80.0)

            return SSIForeignMessage(
                symbol=symbol,
                f_buy_vol=buy_vol,
                f_sell_vol=sell_vol,
                f_buy_val=buy_val,
                f_sell_val=sell_val,
                total_room=total_room,
                current_room=current_room,
            )

        @staticmethod
        def index(
            index_id: str = "VN30",
            value: float = 1250.0,
            prior_value: float = 1245.0,
            advances: int = 15,
            declines: int = 10,
            no_changes: int = 5,
        ) -> SSIIndexMessage:
            """Create SSIIndexMessage."""
            change = value - prior_value
            ratio_change = (change / prior_value) * 100 if prior_value else 0.0

            return SSIIndexMessage(
                index_id=index_id,
                index_value=value,
                prior_index_value=prior_value,
                change=change,
                ratio_change=ratio_change,
                advances=advances,
                declines=declines,
                no_changes=no_changes,
                total_volume=1000000,
            )

        @staticmethod
        def futures_trade(
            symbol: str = "VN30F2603",
            price: float = 1260.0,
            volume: int = 10,
            change: float = 5.0,
            ratio_change: float = 0.4,
        ) -> SSITradeMessage:
            """Create VN30F futures trade message."""
            return SSITradeMessage(
                symbol=symbol,
                last_price=price,
                last_vol=volume,
                change=change,
                ratio_change=ratio_change,
            )

    return SSIMessageFactories()


# ============================================================================
# Helper Utilities
# ============================================================================

@pytest.fixture
def ws_client_simulator():
    """Simulate WebSocket client receiving messages.

    Usage:
        async with ws_client_simulator(manager) as receive_queue:
            # Trigger broadcast
            manager.broadcast('{"test": true}')
            msg = await asyncio.wait_for(receive_queue.get(), timeout=1.0)
    """

    class WSClientSimulator:
        def __init__(self, manager: ConnectionManager):
            self.manager = manager
            self.queue = asyncio.Queue()
            self.client_id = None

        async def __aenter__(self):
            """Connect to manager and return receive queue."""
            self.client_id = await self.manager.connect(self.queue)
            return self.queue

        async def __aexit__(self, *args):
            """Disconnect from manager."""
            if self.client_id:
                await self.manager.disconnect(self.client_id)

    return WSClientSimulator


# ============================================================================
# Timing Utilities
# ============================================================================

@pytest.fixture
def assert_timing():
    """Assert operation completes within time budget.

    Usage:
        async with assert_timing(max_ms=100):
            await some_operation()
    """

    class TimingAssertion:
        def __init__(self, max_ms: int):
            self.max_ms = max_ms
            self.start = None

        async def __aenter__(self):
            self.start = asyncio.get_event_loop().time()
            return self

        async def __aexit__(self, *args):
            elapsed_ms = (asyncio.get_event_loop().time() - self.start) * 1000
            assert elapsed_ms < self.max_ms, (
                f"Operation took {elapsed_ms:.1f}ms, expected <{self.max_ms}ms"
            )

    return TimingAssertion
```

## File Structure

```
backend/tests/e2e/
├── __init__.py                    # Empty marker
├── conftest.py                    # Shared fixtures (above)
├── test_full_flow.py              # Phase 2
├── test_foreign_tracking.py       # Phase 2
├── test_alert_flow.py             # Phase 2
├── test_reconnect_recovery.py     # Phase 2
└── test_session_lifecycle.py      # Phase 2
```

## Success Criteria

- [ ] `conftest.py` created with all fixtures
- [ ] SSI message factories support all message types
- [ ] `wired_system` fixture successfully wires processor → publisher → managers
- [ ] `ws_client_simulator` can connect and receive broadcasts
- [ ] `assert_timing` utility validates operation latency
- [ ] pytest discovers `backend/tests/e2e/` directory
- [ ] Fixtures can be imported in test files

## Testing the Infrastructure

Simple smoke test to verify fixtures work:

```python
# backend/tests/e2e/test_smoke.py
"""Smoke test — verify E2E fixtures work."""

import pytest


@pytest.mark.asyncio
async def test_wired_system_fixture(wired_system):
    """Verify wired_system fixture initializes correctly."""
    assert wired_system["processor"] is not None
    assert wired_system["publisher"] is not None
    assert len(wired_system["managers"]) == 4


@pytest.mark.asyncio
async def test_ssi_factories(ssi_factories):
    """Verify SSI factories produce valid messages."""
    quote = ssi_factories.quote("VNM", bid=80.0, ask=80.5)
    assert quote.symbol == "VNM"
    assert quote.bid_price_1 == 80.0

    trade = ssi_factories.trade("VNM", price=80.5, volume=100)
    assert trade.symbol == "VNM"
    assert trade.last_price == 80.5


@pytest.mark.asyncio
async def test_ws_client_simulator(connection_managers, ws_client_simulator):
    """Verify WS client simulator can receive broadcasts."""
    manager = connection_managers["market"]

    async with ws_client_simulator(manager) as queue:
        manager.broadcast('{"test": true}')
        msg = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert msg == '{"test": true}'
```

Run: `./venv/bin/pytest backend/tests/e2e/test_smoke.py -v`

## Dependencies

None — all fixtures use existing app components.

## Next Phase

Phase 2 implements actual E2E test scenarios using these fixtures.
