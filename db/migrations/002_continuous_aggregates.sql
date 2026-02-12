-- Phase 9: Continuous Aggregates for 1-minute candle generation
-- Replaces empty candles_1m table with auto-computed view from tick_data.
-- Also adds index_candles_1m from index_snapshots.

-- 1. Drop the empty candles_1m table (never had write logic)
DROP TABLE IF EXISTS candles_1m CASCADE;

-- 2. Create 1-minute candle continuous aggregate from tick_data
--    Covers both VN30 stocks AND VN30F futures (both written to tick_data).
--    Columns match original candles_1m schema for backward compatibility.
CREATE MATERIALIZED VIEW candles_1m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', timestamp) AS timestamp,
    symbol,
    first(price, timestamp)  AS open,
    max(price)               AS high,
    min(price)               AS low,
    last(price, timestamp)   AS close,
    sum(volume)::bigint      AS volume,
    coalesce(sum(volume) FILTER (WHERE side = 'mua_chu_dong'), 0)::bigint AS active_buy_vol,
    coalesce(sum(volume) FILTER (WHERE side = 'ban_chu_dong'), 0)::bigint AS active_sell_vol
FROM tick_data
GROUP BY 1, 2
WITH NO DATA;

-- Refresh policy: every 1 minute, covers last 2 hours, excludes last 1 minute
-- (incomplete minute excluded to avoid partial candles in materialized view)
SELECT add_continuous_aggregate_policy('candles_1m',
    start_offset  => INTERVAL '2 hours',
    end_offset    => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute'
);

-- 3. Create 1-minute index candle continuous aggregate from index_snapshots
--    For VN30 / VNINDEX line/candle charts.
CREATE MATERIALIZED VIEW index_candles_1m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', timestamp) AS timestamp,
    index_name,
    first(value, timestamp)  AS open,
    max(value)               AS high,
    min(value)               AS low,
    last(value, timestamp)   AS close,
    last(volume, timestamp)::bigint AS volume
FROM index_snapshots
GROUP BY 1, 2
WITH NO DATA;

SELECT add_continuous_aggregate_policy('index_candles_1m',
    start_offset  => INTERVAL '2 hours',
    end_offset    => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute'
);

-- 4. Backfill existing data (if any tick_data/index_snapshots exist)
CALL refresh_continuous_aggregate('candles_1m', NULL, NOW());
CALL refresh_continuous_aggregate('index_candles_1m', NULL, NOW());
