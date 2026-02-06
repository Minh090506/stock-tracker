# Phase 07: Database Persistence

## Context Links
- [Plan Overview](./plan.md)
- [Phase 03: Data Processing](./phase-03-data-processing-core.md)
- [Old plan Phase 08](../260206-1341-stock-tracker-system/phase-08-database-storage.md)

## Overview
- **Priority:** P1
- **Status:** pending
- **Effort:** 5h
- PostgreSQL for persisting trade history, foreign investor snapshots, basis history, alerts, and daily OHLC. Batch inserts for performance. Alembic migrations.

## Key Changes from Old Plan
- Added `foreign_snapshots` table (delta + speed history)
- Added `basis_history` table (futures-spot tracking)
- Added `alerts` table (alert history)
- **Batch inserts** every 1s instead of per-trade (reduces DB load)
- Can start in parallel with Phase 2 (schema + Docker setup)

## Requirements

### Functional
- Store classified trades (symbol, price, volume, trade_type, timestamp)
- Store foreign investor snapshots (cumulative + speed at intervals)
- Store basis history (futures price, spot value, basis)
- Store alerts for review
- Import historical DailyOHLC via SSI REST API
- REST endpoints for historical queries

### Non-Functional
- Batch write latency <50ms per batch (not per-trade)
- Query 1 year of daily OHLC in <500ms
- Connection pooling (asyncpg, 5-20 connections)
- Alembic for schema migrations

## Architecture
```
MarketDataProcessor
    ├─→ In-memory stats (existing, real-time)
    └─→ BatchWriter (collects trades for 1s, then bulk INSERT)
            │
         asyncpg pool ──→ PostgreSQL
            │
         Tables:
         ├── trades (symbol, price, volume, trade_type, timestamp)
         ├── daily_ohlc (symbol, date, open, high, low, close, volume)
         ├── foreign_snapshots (symbol, cumulative vols, speed, timestamp)
         ├── basis_history (futures_symbol, futures_price, spot, basis, timestamp)
         └── alerts (symbol, alert_type, message, severity, timestamp)
```

## Related Code Files
- `~/projects/stock-tracker/backend/app/database/connection.py` - asyncpg pool
- `~/projects/stock-tracker/backend/app/database/batch_writer.py` - **NEW**: Batched inserts
- `~/projects/stock-tracker/backend/app/database/repositories/trade_repository.py`
- `~/projects/stock-tracker/backend/app/database/repositories/foreign_repository.py`
- `~/projects/stock-tracker/backend/app/database/repositories/basis_repository.py`
- `~/projects/stock-tracker/backend/app/database/repositories/alert_repository.py`
- `~/projects/stock-tracker/backend/app/database/repositories/ohlc_repository.py`
- `~/projects/stock-tracker/backend/app/routers/history_router.py`
- `~/projects/stock-tracker/backend/alembic/` - Migration files

## Implementation Steps

### 1. Database connection (`database/connection.py`)
```python
import asyncpg
from app.config import settings

class Database:
    pool: asyncpg.Pool | None = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(
            settings.database_url, min_size=5, max_size=20,
        )

    async def disconnect(self):
        if self.pool:
            await self.pool.close()

db = Database()
```

### 2. SQL schema (migration)
```sql
CREATE TABLE trades (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    price NUMERIC(12,2) NOT NULL,
    volume INTEGER NOT NULL,
    value NUMERIC(18,2) NOT NULL,
    trade_type VARCHAR(20) NOT NULL,
    bid_price NUMERIC(12,2),
    ask_price NUMERIC(12,2),
    traded_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_trades_symbol_time ON trades (symbol, traded_at DESC);

CREATE TABLE daily_ohlc (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    open NUMERIC(12,2),
    high NUMERIC(12,2),
    low NUMERIC(12,2),
    close NUMERIC(12,2),
    volume BIGINT,
    UNIQUE(symbol, date)
);
CREATE INDEX idx_ohlc_symbol_date ON daily_ohlc (symbol, date DESC);

CREATE TABLE foreign_snapshots (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    f_buy_vol BIGINT NOT NULL,
    f_sell_vol BIGINT NOT NULL,
    f_net_vol BIGINT NOT NULL,
    buy_speed_per_min NUMERIC(12,2) DEFAULT 0,
    sell_speed_per_min NUMERIC(12,2) DEFAULT 0,
    captured_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_foreign_snap_symbol ON foreign_snapshots (symbol, captured_at DESC);

CREATE TABLE basis_history (
    id BIGSERIAL PRIMARY KEY,
    futures_symbol VARCHAR(20) NOT NULL,
    futures_price NUMERIC(12,2) NOT NULL,
    spot_value NUMERIC(12,2) NOT NULL,
    basis NUMERIC(12,2) NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_basis_time ON basis_history (captured_at DESC);

CREATE TABLE alerts (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    alert_type VARCHAR(50) NOT NULL,
    message TEXT,
    severity VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_alerts_time ON alerts (created_at DESC);
```

### 3. BatchWriter (`database/batch_writer.py`)
```python
"""Collect records and bulk INSERT every 1 second. Avoids per-trade DB writes."""
import asyncio
from collections import deque

class BatchWriter:
    def __init__(self, db: Database, flush_interval: float = 1.0):
        self._db = db
        self._interval = flush_interval
        self._trade_queue: deque = deque()
        self._foreign_queue: deque = deque()
        self._basis_queue: deque = deque()
        self._alert_queue: deque = deque()
        self._task: asyncio.Task | None = None

    async def start(self):
        self._task = asyncio.create_task(self._flush_loop())

    async def _flush_loop(self):
        while True:
            await asyncio.sleep(self._interval)
            await self._flush_trades()
            await self._flush_foreign()
            await self._flush_basis()
            await self._flush_alerts()

    def enqueue_trade(self, trade: ClassifiedTrade):
        self._trade_queue.append(trade)

    def enqueue_foreign(self, data: ForeignInvestorData):
        self._foreign_queue.append(data)

    def enqueue_basis(self, bp: BasisPoint):
        self._basis_queue.append(bp)

    def enqueue_alert(self, alert: Alert):
        self._alert_queue.append(alert)

    async def _flush_trades(self):
        if not self._trade_queue:
            return
        batch = []
        while self._trade_queue:
            batch.append(self._trade_queue.popleft())
        async with self._db.pool.acquire() as conn:
            await conn.executemany("""
                INSERT INTO trades (symbol, price, volume, value, trade_type, bid_price, ask_price, traded_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """, [(t.symbol, t.price, t.volume, t.value,
                   t.trade_type.value, t.bid_price, t.ask_price, t.timestamp)
                  for t in batch])

    # Similar _flush_foreign, _flush_basis, _flush_alerts methods

    async def stop(self):
        if self._task:
            self._task.cancel()
        # Final flush
        await self._flush_trades()
        await self._flush_foreign()
        await self._flush_basis()
        await self._flush_alerts()
```

### 4. Repositories (trade, foreign, ohlc, basis, alert)
Simple query wrappers for historical data retrieval.

### 5. History router (`routers/history_router.py`)
```python
@router.get("/api/history/{symbol}/daily")     # Daily OHLC
@router.get("/api/history/{symbol}/trades")     # Trade history for a date
@router.get("/api/history/{symbol}/foreign")    # Foreign investor history
@router.get("/api/history/basis")               # Basis history
@router.get("/api/history/alerts")              # Alert history
```

### 6. Wire into lifespan + processor
```python
# Lifespan
await db.connect()
batch_writer = BatchWriter(db)
await batch_writer.start()

# Processor callbacks
async def on_trade(classified, stats):
    batch_writer.enqueue_trade(classified)
    # ... existing broadcast logic

async def on_foreign(data):
    batch_writer.enqueue_foreign(data)

# Shutdown
await batch_writer.stop()
await db.disconnect()
```

### 7. OHLC import service
Use SSI REST API `DailyOHLC` endpoint to backfill historical data for VN30 stocks.

## Todo List
- [ ] Create database connection module (asyncpg pool)
- [ ] Create SQL migration (trades, daily_ohlc, foreign_snapshots, basis_history, alerts)
- [ ] Implement BatchWriter (1s flush interval)
- [ ] Implement trade repository (bulk insert + query)
- [ ] Implement foreign repository
- [ ] Implement basis repository
- [ ] Implement alert repository
- [ ] Implement OHLC repository + SSI DailyOHLC importer
- [ ] Create history router (REST endpoints)
- [ ] Wire BatchWriter into processor pipeline
- [ ] Wire DB into app lifespan (connect/disconnect)
- [ ] Add PostgreSQL to docker-compose.yml (if not done in Phase 1)
- [ ] Test batch inserts under load
- [ ] Test historical query performance (<500ms for 1 year OHLC)

## Success Criteria
- Trades batch-inserted every 1s without impacting real-time latency
- Historical OHLC queryable per symbol
- Foreign snapshots stored with speed data
- Basis history tracked
- Alerts persisted for review
- Docker Compose brings up PostgreSQL automatically

## Risk Assessment
- **Batch write failure:** If DB is down, trades accumulate in memory. Add max queue size + warning log.
- **Disk space:** ~18M trade rows/year for VN30 at moderate frequency. Manageable.
- **Connection pool exhaustion:** 20 connections should be sufficient for <5 users + batch writer.
- **Migration conflicts:** Use Alembic with sequential revision IDs.

## Next Steps
- Phase 08: Testing & Deployment
