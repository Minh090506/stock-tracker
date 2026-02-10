# Alembic + asyncpg + TimescaleDB Research Report

**Date:** 2026-02-10
**Context:** FastAPI project with asyncpg (no SQLAlchemy ORM), TimescaleDB hypertables, optional DB startup

---

## 1. Alembic with asyncpg (No ORM)

### Minimal Setup

**alembic.ini:**
```ini
[alembic]
script_location = alembic
sqlalchemy.url = postgresql+asyncpg://user:pass@localhost/db
```

**env.py (async template):**
```python
from alembic import context
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

config = context.config
url = config.get_main_option("sqlalchemy.url")

async def run_migrations_online():
    engine = create_async_engine(url, echo=False)

    async with engine.connect() as conn:
        await conn.run_sync(do_run_migrations)

    await engine.dispose()

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=None)
    with context.begin_transaction():
        context.run_migrations()

asyncio.run(run_migrations_online())
```

### Raw SQL Migrations (No ORM)

**migration file:**
```python
def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(10),
            timestamp TIMESTAMPTZ NOT NULL,
            price DECIMAL,
            volume BIGINT
        )
    """)

def downgrade():
    op.execute("DROP TABLE IF EXISTS trades")
```

**Key Insight:** Alembic runs migrations synchronously via `run_sync()` — even with async engine. Use `op.execute()` for raw SQL, `op.get_bind()` returns sync connection.

---

## 2. TimescaleDB Hypertables in Alembic

### Extension + Hypertable Creation

```python
def upgrade():
    # 1. Enable extension
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")

    # 2. Create regular table
    op.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            timestamp TIMESTAMPTZ NOT NULL,
            symbol VARCHAR(10),
            price DECIMAL,
            volume BIGINT
        )
    """)

    # 3. Convert to hypertable
    op.execute("""
        SELECT create_hypertable(
            'trades',
            'timestamp',
            if_not_exists => TRUE,
            migrate_data => TRUE
        )
    """)

def downgrade():
    op.execute("DROP TABLE IF EXISTS trades CASCADE")
    # Extension persists (safe to leave)
```

### Index Caveat

TimescaleDB auto-creates index on time column → Alembic autogenerate may flag it for deletion. **Workaround:** Create time index explicitly in migration before `create_hypertable()`, or ignore in autogenerate.

---

## 3. asyncpg Pool Health Check

### Pattern

```python
import asyncpg
import logging

logger = logging.getLogger(__name__)

async def check_pool_health(pool: asyncpg.Pool) -> bool:
    """Health check via SELECT 1 query."""
    try:
        async with pool.acquire(timeout=5.0) as conn:
            result = await conn.fetchval("SELECT 1")
            return result == 1
    except (asyncpg.PostgresError, TimeoutError, OSError) as e:
        logger.warning(f"DB health check failed: {e}")
        return False
```

### FastAPI Health Endpoint

```python
from fastapi import FastAPI, status

@app.get("/health/db", status_code=status.HTTP_200_OK)
async def db_health():
    if app.state.db_pool is None:
        return {"status": "unavailable", "reason": "pool_not_initialized"}

    healthy = await check_pool_health(app.state.db_pool)
    if healthy:
        return {"status": "ok"}
    return JSONResponse(
        {"status": "degraded", "reason": "connection_failed"},
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE
    )
```

**Pool Config Notes:**
- `max_inactive_connection_lifetime` may not auto-reset — set `timeout` on acquire() explicitly
- Long-running pools can go stale → periodic health checks recommended

---

## 4. Graceful DB-Optional Startup

### Lifespan Pattern

```python
from contextlib import asynccontextmanager
import asyncpg
import logging

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: try DB, continue if fails
    app.state.db_pool = None
    try:
        app.state.db_pool = await asyncpg.create_pool(
            dsn=settings.DATABASE_URL,
            min_size=2,
            max_size=10,
            timeout=10.0
        )
        logger.info("Database pool initialized")
    except (asyncpg.PostgresError, OSError, TimeoutError) as e:
        logger.warning(f"DB unavailable at startup, continuing without persistence: {e}")

    yield  # App runs

    # Shutdown: close pool if exists
    if app.state.db_pool:
        await app.state.db_pool.close()
        logger.info("Database pool closed")

app = FastAPI(lifespan=lifespan)
```

### Dependency Injection (Optional DB)

```python
from typing import Optional

async def get_db_conn() -> Optional[asyncpg.Connection]:
    """Yields DB connection if pool available, else None."""
    if app.state.db_pool is None:
        logger.debug("DB pool unavailable, skipping persistence")
        yield None
        return

    async with app.state.db_pool.acquire() as conn:
        yield conn

@app.post("/trades")
async def create_trade(trade: Trade, conn: Optional[asyncpg.Connection] = Depends(get_db_conn)):
    if conn is None:
        raise HTTPException(503, "Database unavailable")

    await conn.execute("INSERT INTO trades ...")
```

**Key Benefits:**
- App starts even if DB down
- Health checks expose DB status
- Endpoints fail gracefully with 503 when DB unavailable
- Deferred initialization → only endpoints needing DB depend on pool

---

## Unresolved Questions

1. **Alembic async API limitations:** Migrations run sync via `run_sync()` — can long-running DDL block event loop? (Likely no — separate process during deploy)
2. **TimescaleDB chunk tuning:** Default chunk interval (7 days) OK for trades table? Need custom `chunk_time_interval`?
3. **Pool sizing:** `min_size=2, max_size=10` — tune based on expected concurrent queries or leave default?

---

## Sources

- [Alembic Cookbook](https://alembic.sqlalchemy.org/en/latest/cookbook.html)
- [Alembic Discussion: Using Alembic without ORM](https://github.com/sqlalchemy/alembic/discussions/1630)
- [Alembic Discussion: Async migration with asyncpg](https://github.com/sqlalchemy/alembic/discussions/1208)
- [TimescaleDB: create_hypertable() docs](https://docs.timescale.com/use-timescale/latest/hypertables/create/)
- [Alembic Discussion: TimescaleDB hypertable indexes](https://github.com/sqlalchemy/alembic/discussions/1465)
- [asyncpg Usage Documentation](https://magicstack.github.io/asyncpg/current/usage.html)
- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/)
- [FastAPI Discussion: Database initialization only when needed](https://github.com/fastapi/fastapi/discussions/4223)
- [FastAPI Best Practices 2026 Guide](https://fastlaunchapi.dev/blog/fastapi-best-practices-production-2026)
