"""High-throughput batch writer using asyncpg COPY protocol.

Collects records into bounded asyncio.Queues (maxsize=10000) and flushes
every 1s or when batch reaches 500 records. On queue full, drops oldest
with warning. Graceful shutdown flushes remaining records.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone

from app.database.pool import Database
from app.metrics import db_write_duration_seconds
from app.models.domain import (
    BasisPoint,
    ClassifiedTrade,
    ForeignInvestorData,
    IndexData,
)

logger = logging.getLogger(__name__)

MAX_QUEUE_SIZE = 10_000
FLUSH_BATCH_SIZE = 500


class BatchWriter:
    """Batches domain objects and bulk-inserts via COPY protocol."""

    def __init__(
        self,
        db: Database,
        flush_interval: float = 1.0,
    ) -> None:
        self._db = db
        self._interval = flush_interval
        self._tick_queue: asyncio.Queue[ClassifiedTrade] = asyncio.Queue(
            maxsize=MAX_QUEUE_SIZE,
        )
        self._foreign_queue: asyncio.Queue[ForeignInvestorData] = asyncio.Queue(
            maxsize=MAX_QUEUE_SIZE,
        )
        self._index_queue: asyncio.Queue[IndexData] = asyncio.Queue(
            maxsize=MAX_QUEUE_SIZE,
        )
        self._basis_queue: asyncio.Queue[BasisPoint] = asyncio.Queue(
            maxsize=MAX_QUEUE_SIZE,
        )
        self._task: asyncio.Task | None = None
        self._running = False

    # -- Public API -----------------------------------------------------------

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._flush_loop())
        logger.info("BatchWriter started (interval=%.1fs)", self._interval)

    async def stop(self) -> None:
        """Cancel loop and flush remaining records."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        # Final flush
        await self._flush_all()
        logger.info("BatchWriter stopped — final flush complete")

    def enqueue_tick(self, trade: ClassifiedTrade) -> None:
        self._enqueue_safe(self._tick_queue, trade, "tick")

    def enqueue_foreign(self, data: ForeignInvestorData) -> None:
        self._enqueue_safe(self._foreign_queue, data, "foreign")

    def enqueue_index(self, data: IndexData) -> None:
        self._enqueue_safe(self._index_queue, data, "index")

    def enqueue_basis(self, bp: BasisPoint) -> None:
        self._enqueue_safe(self._basis_queue, bp, "basis")

    # -- Internal -------------------------------------------------------------

    def _enqueue_safe(self, queue: asyncio.Queue, item: object, label: str) -> None:
        """Put item in queue. If full, drop oldest and warn."""
        if queue.full():
            try:
                queue.get_nowait()
                logger.warning(
                    "BatchWriter %s queue full (%d), dropped oldest",
                    label,
                    MAX_QUEUE_SIZE,
                )
            except asyncio.QueueEmpty:
                pass
        try:
            queue.put_nowait(item)
        except asyncio.QueueFull:
            logger.error(
                "BatchWriter %s queue still full after drop — discarding new record",
                label,
            )

    async def _flush_loop(self) -> None:
        while self._running:
            await asyncio.sleep(self._interval)
            await self._flush_all()

    async def _flush_all(self) -> None:
        self._db.update_pool_metrics()
        await self._flush_ticks()
        await self._flush_foreign()
        await self._flush_index()
        await self._flush_basis()

    @staticmethod
    def _drain(queue: asyncio.Queue, max_items: int = FLUSH_BATCH_SIZE) -> list:
        items: list = []
        while not queue.empty() and len(items) < max_items:
            try:
                items.append(queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        return items

    async def _flush_ticks(self) -> None:
        batch = self._drain(self._tick_queue)
        if not batch:
            return
        records = [
            (
                t.symbol,
                t.timestamp,
                t.price,
                t.volume,
                t.trade_type.value,
                t.bid_price,
                t.ask_price,
            )
            for t in batch
        ]
        try:
            start = time.monotonic()
            async with self._db.pool.acquire() as conn:
                await conn.copy_records_to_table(
                    "tick_data",
                    columns=[
                        "symbol", "timestamp", "price", "volume",
                        "side", "bid", "ask",
                    ],
                    records=records,
                )
            db_write_duration_seconds.labels(table="tick_data").observe(
                time.monotonic() - start,
            )
            logger.debug("Flushed %d ticks via COPY", len(records))
        except Exception:
            logger.exception("Failed to flush ticks (%d records)", len(records))

    async def _flush_foreign(self) -> None:
        batch = self._drain(self._foreign_queue)
        if not batch:
            return
        now = datetime.now(timezone.utc)
        records = [
            (
                d.symbol,
                d.last_updated or now,
                d.buy_volume,
                d.sell_volume,
                d.net_volume,
                d.buy_value,
                d.sell_value,
            )
            for d in batch
        ]
        try:
            start = time.monotonic()
            async with self._db.pool.acquire() as conn:
                await conn.copy_records_to_table(
                    "foreign_flow",
                    columns=[
                        "symbol", "timestamp", "buy_vol", "sell_vol",
                        "net_vol", "buy_value", "sell_value",
                    ],
                    records=records,
                )
            db_write_duration_seconds.labels(table="foreign_flow").observe(
                time.monotonic() - start,
            )
            logger.debug("Flushed %d foreign records via COPY", len(records))
        except Exception:
            logger.exception("Failed to flush foreign (%d records)", len(records))

    async def _flush_index(self) -> None:
        batch = self._drain(self._index_queue)
        if not batch:
            return
        now = datetime.now(timezone.utc)
        records = [
            (
                d.index_id,
                d.last_updated or now,
                d.value,
                d.ratio_change,
                d.total_volume,
            )
            for d in batch
        ]
        try:
            start = time.monotonic()
            async with self._db.pool.acquire() as conn:
                await conn.copy_records_to_table(
                    "index_snapshots",
                    columns=[
                        "index_name", "timestamp", "value",
                        "change_pct", "volume",
                    ],
                    records=records,
                )
            db_write_duration_seconds.labels(table="index_snapshots").observe(
                time.monotonic() - start,
            )
            logger.debug("Flushed %d index snapshots via COPY", len(records))
        except Exception:
            logger.exception("Failed to flush index (%d records)", len(records))

    async def _flush_basis(self) -> None:
        batch = self._drain(self._basis_queue)
        if not batch:
            return
        records = [
            (
                b.futures_symbol,
                b.timestamp,
                b.futures_price,
                b.basis,
                0,  # open_interest — not yet available from stream
            )
            for b in batch
        ]
        try:
            start = time.monotonic()
            async with self._db.pool.acquire() as conn:
                await conn.copy_records_to_table(
                    "derivatives",
                    columns=[
                        "contract", "timestamp", "price",
                        "basis", "open_interest",
                    ],
                    records=records,
                )
            db_write_duration_seconds.labels(table="derivatives").observe(
                time.monotonic() - start,
            )
            logger.debug("Flushed %d derivatives via COPY", len(records))
        except Exception:
            logger.exception("Failed to flush derivatives (%d records)", len(records))
