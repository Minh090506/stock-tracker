"""Tests for BatchWriter — queue management, drain, enqueue overflow."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.database.batch_writer import BatchWriter, MAX_QUEUE_SIZE, FLUSH_BATCH_SIZE
from app.database.pool import Database
from app.models.domain import (
    BasisPoint,
    ClassifiedTrade,
    ForeignInvestorData,
    IndexData,
    TradeType,
)


def _make_trade(symbol: str = "VNM", price: float = 80.0) -> ClassifiedTrade:
    return ClassifiedTrade(
        symbol=symbol,
        price=price,
        volume=100,
        value=price * 100,
        trade_type=TradeType.MUA_CHU_DONG,
        bid_price=79.5,
        ask_price=80.0,
        timestamp=datetime.now(timezone.utc),
    )


def _make_foreign(symbol: str = "VNM") -> ForeignInvestorData:
    return ForeignInvestorData(
        symbol=symbol,
        buy_volume=1000,
        sell_volume=500,
        net_volume=500,
        buy_value=80000.0,
        sell_value=40000.0,
        last_updated=datetime.now(timezone.utc),
    )


def _make_index(index_id: str = "VN30") -> IndexData:
    return IndexData(
        index_id=index_id,
        value=1200.5,
        prior_value=1190.0,
        ratio_change=0.88,
        total_volume=150_000_000,
        last_updated=datetime.now(timezone.utc),
    )


def _make_basis() -> BasisPoint:
    return BasisPoint(
        timestamp=datetime.now(timezone.utc),
        futures_symbol="VN30F2603",
        futures_price=1210.0,
        spot_value=1200.5,
        basis=9.5,
        is_premium=True,
    )


@pytest.fixture
def mock_db():
    db = MagicMock(spec=Database)
    db.pool = None
    return db


@pytest.fixture
def writer(mock_db):
    return BatchWriter(mock_db, flush_interval=1.0)


class TestEnqueue:
    def test_enqueue_tick_adds_to_queue(self, writer):
        trade = _make_trade()
        writer.enqueue_tick(trade)
        assert writer._tick_queue.qsize() == 1

    def test_enqueue_foreign_adds_to_queue(self, writer):
        writer.enqueue_foreign(_make_foreign())
        assert writer._foreign_queue.qsize() == 1

    def test_enqueue_index_adds_to_queue(self, writer):
        writer.enqueue_index(_make_index())
        assert writer._index_queue.qsize() == 1

    def test_enqueue_basis_adds_to_queue(self, writer):
        writer.enqueue_basis(_make_basis())
        assert writer._basis_queue.qsize() == 1

    def test_enqueue_multiple(self, writer):
        for _ in range(10):
            writer.enqueue_tick(_make_trade())
        assert writer._tick_queue.qsize() == 10


class TestEnqueueOverflow:
    def test_drop_oldest_when_full(self, mock_db):
        """When queue is full, oldest record should be dropped."""
        bw = BatchWriter(mock_db)
        # Fill tick queue to capacity
        for i in range(MAX_QUEUE_SIZE):
            bw.enqueue_tick(_make_trade(price=float(i)))
        assert bw._tick_queue.qsize() == MAX_QUEUE_SIZE

        # Add one more — should drop oldest and add new
        bw.enqueue_tick(_make_trade(price=99999.0))
        assert bw._tick_queue.qsize() == MAX_QUEUE_SIZE


class TestDrain:
    def test_drain_empty_queue(self, writer):
        items = writer._drain(writer._tick_queue)
        assert items == []

    def test_drain_returns_all_items(self, writer):
        for _ in range(5):
            writer.enqueue_tick(_make_trade())
        items = writer._drain(writer._tick_queue)
        assert len(items) == 5
        assert writer._tick_queue.qsize() == 0

    def test_drain_respects_max_items(self, writer):
        for _ in range(FLUSH_BATCH_SIZE + 100):
            writer.enqueue_tick(_make_trade())
        items = writer._drain(writer._tick_queue, max_items=FLUSH_BATCH_SIZE)
        assert len(items) == FLUSH_BATCH_SIZE
        assert writer._tick_queue.qsize() == 100


class TestFlushTicks:
    @pytest.mark.asyncio
    async def test_flush_calls_copy(self, mock_db):
        mock_conn = AsyncMock()
        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_db.pool = mock_pool

        bw = BatchWriter(mock_db)
        bw.enqueue_tick(_make_trade())
        await bw._flush_ticks()

        mock_conn.copy_records_to_table.assert_called_once()
        call_kwargs = mock_conn.copy_records_to_table.call_args
        assert call_kwargs[1]["columns"] == [
            "symbol", "timestamp", "price", "volume", "side", "bid", "ask",
        ]

    @pytest.mark.asyncio
    async def test_flush_empty_noop(self, mock_db):
        bw = BatchWriter(mock_db)
        # Should not raise even with no pool
        await bw._flush_ticks()

    @pytest.mark.asyncio
    async def test_flush_exception_logged(self, mock_db):
        mock_pool = MagicMock()
        mock_pool.acquire.side_effect = RuntimeError("pool error")
        mock_db.pool = mock_pool

        bw = BatchWriter(mock_db)
        bw.enqueue_tick(_make_trade())
        # Should not raise — exception is caught and logged
        await bw._flush_ticks()


class TestFlushForeign:
    @pytest.mark.asyncio
    async def test_flush_calls_copy(self, mock_db):
        mock_conn = AsyncMock()
        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_db.pool = mock_pool

        bw = BatchWriter(mock_db)
        bw.enqueue_foreign(_make_foreign())
        await bw._flush_foreign()

        mock_conn.copy_records_to_table.assert_called_once()
        assert mock_conn.copy_records_to_table.call_args[0][0] == "foreign_flow"


class TestFlushIndex:
    @pytest.mark.asyncio
    async def test_flush_calls_copy(self, mock_db):
        mock_conn = AsyncMock()
        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_db.pool = mock_pool

        bw = BatchWriter(mock_db)
        bw.enqueue_index(_make_index())
        await bw._flush_index()

        mock_conn.copy_records_to_table.assert_called_once()
        assert mock_conn.copy_records_to_table.call_args[0][0] == "index_snapshots"


class TestFlushBasis:
    @pytest.mark.asyncio
    async def test_flush_calls_copy(self, mock_db):
        mock_conn = AsyncMock()
        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_db.pool = mock_pool

        bw = BatchWriter(mock_db)
        bw.enqueue_basis(_make_basis())
        await bw._flush_basis()

        mock_conn.copy_records_to_table.assert_called_once()
        assert mock_conn.copy_records_to_table.call_args[0][0] == "derivatives"


class TestStartStop:
    @pytest.mark.asyncio
    async def test_start_creates_task(self, writer):
        await writer.start()
        assert writer._task is not None
        assert writer._running is True
        await writer.stop()
        assert writer._running is False

    @pytest.mark.asyncio
    async def test_stop_flushes_remaining(self, mock_db):
        mock_conn = AsyncMock()
        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_db.pool = mock_pool

        bw = BatchWriter(mock_db, flush_interval=60.0)  # long interval
        await bw.start()
        bw.enqueue_tick(_make_trade())
        bw.enqueue_foreign(_make_foreign())
        await bw.stop()

        # Both tick and foreign should have been flushed during stop
        assert mock_conn.copy_records_to_table.call_count == 2
