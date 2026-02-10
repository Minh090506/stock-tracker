"""Query service for persisted market data (candles, foreign flow, etc.)."""

from datetime import date, datetime

import asyncpg

from app.database.pool import Database


class HistoryService:
    """Read-only queries against TimescaleDB hypertables."""

    def __init__(self, db: Database) -> None:
        self._db = db

    @property
    def _pool(self) -> asyncpg.Pool:
        assert self._db.pool is not None, "Database not connected"
        return self._db.pool

    # -- Candles ---------------------------------------------------------------

    async def get_candles(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> list[dict]:
        """Return 1-minute candles for symbol in date range."""
        rows = await self._pool.fetch(
            """
            SELECT symbol, timestamp, open, high, low, close,
                   volume, active_buy_vol, active_sell_vol
            FROM candles_1m
            WHERE symbol = $1
              AND timestamp >= $2
              AND timestamp < $3 + INTERVAL '1 day'
            ORDER BY timestamp
            """,
            symbol,
            datetime(start.year, start.month, start.day),
            datetime(end.year, end.month, end.day),
        )
        return [dict(r) for r in rows]

    # -- Foreign flow ----------------------------------------------------------

    async def get_foreign_flow(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> list[dict]:
        """Return foreign flow snapshots for symbol in date range."""
        rows = await self._pool.fetch(
            """
            SELECT symbol, timestamp, buy_vol, sell_vol, net_vol,
                   buy_value, sell_value
            FROM foreign_flow
            WHERE symbol = $1
              AND timestamp >= $2
              AND timestamp < $3 + INTERVAL '1 day'
            ORDER BY timestamp
            """,
            symbol,
            datetime(start.year, start.month, start.day),
            datetime(end.year, end.month, end.day),
        )
        return [dict(r) for r in rows]

    async def get_foreign_flow_daily_summary(
        self,
        symbol: str,
        days: int = 30,
    ) -> list[dict]:
        """Aggregate daily foreign net volume for last N days."""
        rows = await self._pool.fetch(
            """
            SELECT date_trunc('day', timestamp) AS day,
                   MAX(buy_vol) AS buy_vol,
                   MAX(sell_vol) AS sell_vol,
                   MAX(net_vol) AS net_vol,
                   MAX(buy_value) AS buy_value,
                   MAX(sell_value) AS sell_value
            FROM foreign_flow
            WHERE symbol = $1
              AND timestamp >= NOW() - ($2 || ' days')::INTERVAL
            GROUP BY day
            ORDER BY day
            """,
            symbol,
            str(days),
        )
        return [dict(r) for r in rows]

    # -- Tick data -------------------------------------------------------------

    async def get_ticks(
        self,
        symbol: str,
        start: date,
        end: date,
        limit: int = 10000,
    ) -> list[dict]:
        """Return classified ticks for symbol in date range."""
        rows = await self._pool.fetch(
            """
            SELECT symbol, timestamp, price, volume, side, bid, ask
            FROM tick_data
            WHERE symbol = $1
              AND timestamp >= $2
              AND timestamp < $3 + INTERVAL '1 day'
            ORDER BY timestamp
            LIMIT $4
            """,
            symbol,
            datetime(start.year, start.month, start.day),
            datetime(end.year, end.month, end.day),
            limit,
        )
        return [dict(r) for r in rows]

    # -- Index snapshots -------------------------------------------------------

    async def get_index_history(
        self,
        index_name: str,
        start: date,
        end: date,
    ) -> list[dict]:
        """Return index snapshots in date range."""
        rows = await self._pool.fetch(
            """
            SELECT index_name, timestamp, value, change_pct, volume
            FROM index_snapshots
            WHERE index_name = $1
              AND timestamp >= $2
              AND timestamp < $3 + INTERVAL '1 day'
            ORDER BY timestamp
            """,
            index_name,
            datetime(start.year, start.month, start.day),
            datetime(end.year, end.month, end.day),
        )
        return [dict(r) for r in rows]

    # -- Derivatives -----------------------------------------------------------

    async def get_derivatives_history(
        self,
        contract: str,
        start: date,
        end: date,
    ) -> list[dict]:
        """Return derivatives price/basis history."""
        rows = await self._pool.fetch(
            """
            SELECT contract, timestamp, price, basis, open_interest
            FROM derivatives
            WHERE contract = $1
              AND timestamp >= $2
              AND timestamp < $3 + INTERVAL '1 day'
            ORDER BY timestamp
            """,
            contract,
            datetime(start.year, start.month, start.day),
            datetime(end.year, end.month, end.day),
        )
        return [dict(r) for r in rows]
