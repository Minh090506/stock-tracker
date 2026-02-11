"""E2E test fixtures — wired processor, publisher, managers, SSI factories.

Provides:
- FakeWebSocket: lightweight WS stub for ConnectionManager
- processor: MarketDataProcessor with all services
- wired_system: processor → DataPublisher → ConnectionManagers
- ssi_factories: message builder functions
- ws_receive: helper to receive broadcast from a ConnectionManager
"""

import asyncio
import json

import pytest
import pytest_asyncio
from starlette.websockets import WebSocketState

from app.models.ssi_messages import (
    SSIForeignMessage,
    SSIIndexMessage,
    SSIQuoteMessage,
    SSITradeMessage,
)
from app.services.market_data_processor import MarketDataProcessor
from app.websocket.connection_manager import ConnectionManager
from app.websocket.data_publisher import DataPublisher


# ============================================================================
# FakeWebSocket — lightweight stub for ConnectionManager
# ============================================================================


class FakeWebSocket:
    """Minimal WebSocket stub that works with ConnectionManager.

    ConnectionManager calls: await ws.accept(), await ws.send_text(data),
    ws.client_state, and await ws.close(). This stub captures sent messages
    in an asyncio.Queue for test assertions.
    """

    def __init__(self):
        self.messages: asyncio.Queue[str] = asyncio.Queue()
        self.client_state = WebSocketState.CONNECTING

    async def accept(self):
        self.client_state = WebSocketState.CONNECTED

    async def send_text(self, data: str):
        await self.messages.put(data)

    async def close(self, code: int = 1000, reason: str | None = None):
        self.client_state = WebSocketState.DISCONNECTED


# ============================================================================
# Core Fixtures
# ============================================================================


@pytest.fixture
def processor():
    """Fresh MarketDataProcessor with all services initialized."""
    return MarketDataProcessor()


@pytest.fixture
def connection_managers():
    """ConnectionManager instances for all WS channels."""
    return {
        "market": ConnectionManager(),
        "foreign": ConnectionManager(),
        "index": ConnectionManager(),
        "alerts": ConnectionManager(),
    }


@pytest_asyncio.fixture
async def wired_system(processor, connection_managers):
    """Fully wired system: processor → publisher → managers.

    Returns dict with processor, publisher, managers.
    """
    publisher = DataPublisher(
        processor,
        market_mgr=connection_managers["market"],
        foreign_mgr=connection_managers["foreign"],
        index_mgr=connection_managers["index"],
        alerts_mgr=connection_managers["alerts"],
    )
    publisher.start()
    processor.subscribe(publisher.notify)

    yield {
        "processor": processor,
        "publisher": publisher,
        "managers": connection_managers,
    }

    publisher.stop()
    # Disconnect all fake clients
    for mgr in connection_managers.values():
        await mgr.disconnect_all()


# ============================================================================
# WS Client Helper
# ============================================================================


@pytest.fixture
def ws_receive():
    """Connect a FakeWebSocket to a manager and receive messages.

    Usage:
        ws = await ws_receive(manager)
        msg = await asyncio.wait_for(ws.messages.get(), timeout=1.0)
    """

    async def _connect(manager: ConnectionManager) -> FakeWebSocket:
        ws = FakeWebSocket()
        await manager.connect(ws)
        return ws

    return _connect


# ============================================================================
# SSI Message Factories
# ============================================================================


class SSIMessageFactories:
    """Builder functions for SSI messages with realistic defaults."""

    @staticmethod
    def quote(
        symbol: str,
        bid: float = 80.0,
        ask: float = 80.5,
        ref: float | None = None,
        ceiling: float | None = None,
        floor: float | None = None,
    ) -> SSIQuoteMessage:
        ref = ref or round(bid + 0.2, 1)
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
        total_room: int = 1_000_000,
        current_room: int = 500_000,
    ) -> SSIForeignMessage:
        buy_val = buy_val or buy_vol * 80.0
        sell_val = sell_val or sell_vol * 80.0
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
            total_volume=1_000_000,
        )

    @staticmethod
    def futures_trade(
        symbol: str = "VN30F2603",
        price: float = 1260.0,
        volume: int = 10,
        change: float = 5.0,
        ratio_change: float = 0.4,
    ) -> SSITradeMessage:
        return SSITradeMessage(
            symbol=symbol,
            last_price=price,
            last_vol=volume,
            change=change,
            ratio_change=ratio_change,
        )


@pytest.fixture
def f():
    """SSI message factories (short alias)."""
    return SSIMessageFactories()
