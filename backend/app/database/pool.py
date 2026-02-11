"""Asyncpg connection pool manager for TimescaleDB."""

import asyncio
import logging

import asyncpg

from app.config import settings
from app.metrics import db_pool_active_connections

logger = logging.getLogger(__name__)


class Database:
    """Manages asyncpg connection pool lifecycle."""

    pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self.pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=settings.db_pool_min,
            max_size=settings.db_pool_max,
        )
        logger.info(
            "Database pool created (min=%d, max=%d)",
            settings.db_pool_min,
            settings.db_pool_max,
        )

    async def disconnect(self) -> None:
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Database pool closed")

    def update_pool_metrics(self) -> None:
        """Update Prometheus gauge with current pool active connections."""
        if self.pool:
            db_pool_active_connections.set(self.pool.get_size() - self.pool.get_idle_size())

    async def health_check(self) -> bool:
        """Return True if pool can execute a simple query within 5s."""
        if not self.pool:
            return False
        try:
            async with self.pool.acquire() as conn:
                await asyncio.wait_for(conn.fetchval("SELECT 1"), timeout=5.0)
            self.update_pool_metrics()
            return True
        except Exception:
            logger.warning("Database health check failed", exc_info=True)
            return False


# Singleton used across the app
db = Database()
