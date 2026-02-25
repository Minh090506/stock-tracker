# Phase 1: Data Layer — Order Velocity Continuous Aggregate

## Context Links

- [Brainstorm](../reports/brainstorm-260224-1055-order-velocity-correlation-vn30f.md)
- [Existing aggregate](../../db/migrations/002_continuous_aggregates.sql) — `candles_1m` pattern
- [Alembic migration](../../backend/alembic/versions/001_create_hypertables.py) — migration pattern
- [tick_data schema](../../db/migrations/001_create_hypertables.sql)

## Overview

- **Priority**: P1 (foundation for all subsequent phases)
- **Status**: pending
- **Effort**: 2h
- **Description**: Create `order_velocity_1m` continuous aggregate from `tick_data` and a `vn30_basket_velocity_1m` regular view for VN30 basket aggregation.

## Key Insights

- `tick_data` already has `side` column (`mua_chu_dong`/`ban_chu_dong`/`neutral`) -- perfect for FILTER clauses
- TimescaleDB continuous aggregates cannot nest (can't build aggregate on aggregate) -- basket view must be a regular VIEW on top of the continuous aggregate
- `candles_1m` aggregate already exists with same `GROUP BY time_bucket('1 minute', timestamp), symbol` pattern
- VN30 symbols available at startup via `vn30_symbols` in `main.py` -- basket view can filter by a static list or use a helper table
- `price * volume * 1000` for value calculation (VN stock prices in thousands VND)

## Requirements

### Functional
- Aggregate buy/sell volume, count, and value per symbol per minute from `tick_data`
- Provide VN30 basket aggregate (SUM across 30 stocks) per minute
- Auto-refresh every minute with 2-hour lookback

### Non-Functional
- No impact on existing `candles_1m` aggregate performance
- Idempotent migration (safe to re-run)

## Architecture

```
tick_data (hypertable)
    |
    +---> order_velocity_1m (continuous aggregate)
              |
              +---> vn30_basket_velocity_1m (regular VIEW, filtered by VN30 symbols)
```

### order_velocity_1m schema

| Column | Type | Description |
|--------|------|-------------|
| timestamp | TIMESTAMPTZ | 1-min bucket |
| symbol | VARCHAR(10) | Stock/futures symbol |
| buy_vol | BIGINT | SUM(volume) WHERE side='mua_chu_dong' |
| sell_vol | BIGINT | SUM(volume) WHERE side='ban_chu_dong' |
| buy_count | INT | COUNT(*) WHERE side='mua_chu_dong' |
| sell_count | INT | COUNT(*) WHERE side='ban_chu_dong' |
| buy_value | BIGINT | SUM(price*volume*1000) WHERE side='mua_chu_dong' |
| sell_value | BIGINT | SUM(price*volume*1000) WHERE side='ban_chu_dong' |

### vn30_basket_velocity_1m schema

Same columns minus `symbol` -- aggregated across all VN30 symbols per minute bucket.

## Related Code Files

### Files to Create
- `db/migrations/003_order_velocity_aggregate.sql` — raw SQL migration
- `backend/alembic/versions/003_order_velocity_aggregate.py` — Alembic migration

### Files to Reference (read-only)
- `db/migrations/002_continuous_aggregates.sql` — pattern for continuous aggregate + policy
- `backend/alembic/versions/001_create_hypertables.py` — Alembic `op.execute()` pattern
- `db/migrations/001_create_hypertables.sql` — `tick_data` schema

## Implementation Steps

### Step 1: Create raw SQL migration file

`db/migrations/003_order_velocity_aggregate.sql`:

```sql
-- Order velocity continuous aggregate from tick_data
-- Computes per-symbol buy/sell volume, count, and value per 1-minute bucket.

CREATE MATERIALIZED VIEW order_velocity_1m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', timestamp) AS timestamp,
    symbol,
    coalesce(sum(volume) FILTER (WHERE side = 'mua_chu_dong'), 0)::bigint AS buy_vol,
    coalesce(sum(volume) FILTER (WHERE side = 'ban_chu_dong'), 0)::bigint AS sell_vol,
    count(*) FILTER (WHERE side = 'mua_chu_dong')::int AS buy_count,
    count(*) FILTER (WHERE side = 'ban_chu_dong')::int AS sell_count,
    coalesce(sum(price * volume * 1000) FILTER (WHERE side = 'mua_chu_dong'), 0)::bigint AS buy_value,
    coalesce(sum(price * volume * 1000) FILTER (WHERE side = 'ban_chu_dong'), 0)::bigint AS sell_value
FROM tick_data
GROUP BY 1, 2
WITH NO DATA;

SELECT add_continuous_aggregate_policy('order_velocity_1m',
    start_offset  => INTERVAL '2 hours',
    end_offset    => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute'
);

-- VN30 basket view: aggregate all VN30 stocks per minute
-- Uses a static symbol list approach. To update VN30 composition,
-- recreate this view (happens rarely — quarterly rebalance).
CREATE OR REPLACE VIEW vn30_basket_velocity_1m AS
SELECT
    timestamp,
    sum(buy_vol)::bigint   AS buy_vol,
    sum(sell_vol)::bigint  AS sell_vol,
    sum(buy_count)::int    AS buy_count,
    sum(sell_count)::int   AS sell_count,
    sum(buy_value)::bigint AS buy_value,
    sum(sell_value)::bigint AS sell_value
FROM order_velocity_1m
WHERE symbol NOT LIKE 'VN30F%'  -- exclude futures, keep only stocks
GROUP BY timestamp;

-- Backfill existing data
CALL refresh_continuous_aggregate('order_velocity_1m', NULL, NOW());
```

**Design note on basket view**: Using `NOT LIKE 'VN30F%'` instead of explicit symbol list. Since the watchlist already filters `tick_data` to only VN30 stocks + VN30F, excluding VN30F% gives us exactly the VN30 basket. No need to maintain a static list or helper table.

### Step 2: Create Alembic migration

`backend/alembic/versions/003_order_velocity_aggregate.py`:
- `revision = "003"`, `down_revision = "001"` (002 is SQL-only)
- `upgrade()`: Execute the continuous aggregate + policy + basket view SQL via `op.execute()`
- `downgrade()`: `DROP VIEW IF EXISTS vn30_basket_velocity_1m; DROP MATERIALIZED VIEW IF EXISTS order_velocity_1m;`

### Step 3: Test migration locally

```bash
cd backend
./venv/bin/alembic upgrade head
# Verify: psql -c "\d+ order_velocity_1m"
# Verify: psql -c "\d+ vn30_basket_velocity_1m"
```

## Todo List

- [ ] Write `db/migrations/003_order_velocity_aggregate.sql`
- [ ] Write `backend/alembic/versions/003_order_velocity_aggregate.py`
- [ ] Test migration on local TimescaleDB
- [ ] Verify continuous aggregate refresh policy is active
- [ ] Verify basket view returns correct aggregation

## Success Criteria

- `order_velocity_1m` materializes correctly from existing `tick_data`
- `vn30_basket_velocity_1m` returns per-minute basket aggregation
- Continuous aggregate refresh policy runs every 1 minute
- Alembic `upgrade head` and `downgrade` both succeed
- No performance degradation on existing queries

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Continuous aggregate policy conflicts with existing `candles_1m` | Low | Medium | Different view names, independent policies |
| `price * volume * 1000` overflow for large trades | Very Low | Low | BIGINT handles up to 9.2 quintillion |
| Basket view includes non-VN30 stocks if watchlist changes | Low | Low | Watchlist already scoped to VN30 + VN30F only |

## Security Considerations

- No user input in migrations -- SQL injection not applicable
- Read-only views -- no write path exposed

## Next Steps

- Phase 2 depends on this: `CorrelationEngine` queries `order_velocity_1m` for historical data
- Phase 3 REST endpoint queries this aggregate directly
