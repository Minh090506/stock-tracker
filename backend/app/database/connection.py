"""Asyncpg connection pool manager for TimescaleDB."""

import logging

import asyncpg

from app.config import settings

logger = logging.getLogger(__name__)


class Database:
    """Manages asyncpg connection pool lifecycle."""

    pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self.pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=5,
            max_size=20,
        )
        logger.info("Database pool created (min=5, max=20)")

    async def disconnect(self) -> None:
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Database pool closed")


# Singleton used across the app
db = Database()
