-- Order velocity continuous aggregate from tick_data
-- Computes per-symbol buy/sell volume, count, and value per 1-minute bucket.

CREATE MATERIALIZED VIEW order_velocity_1m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', timestamp) AS timestamp,
    symbol,
    coalesce(sum(volume) FILTER (WHERE side = 'mua_chu_dong'), 0)::bigint AS buy_vol,
    coalesce(sum(volume) FILTER (WHERE side = 'ban_chu_dong'), 0)::bigint AS sell_vol,
    (count(*) FILTER (WHERE side = 'mua_chu_dong'))::int AS buy_count,
    (count(*) FILTER (WHERE side = 'ban_chu_dong'))::int AS sell_count,
    coalesce(sum(price * volume * 1000) FILTER (WHERE side = 'mua_chu_dong'), 0)::bigint AS buy_value,
    coalesce(sum(price * volume * 1000) FILTER (WHERE side = 'ban_chu_dong'), 0)::bigint AS sell_value
FROM tick_data
GROUP BY 1, 2
WITH NO DATA;

-- Refresh policy: every 1 minute, covers last 2 hours, excludes last 1 minute
SELECT add_continuous_aggregate_policy('order_velocity_1m',
    start_offset  => INTERVAL '2 hours',
    end_offset    => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute'
);

-- VN30 basket view: aggregate all VN30 stocks per minute
-- Since tick_data only contains VN30 stocks + VN30F (filtered by watchlist),
-- excluding VN30F% gives exactly the VN30 basket. No static symbol list needed.
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
WHERE symbol NOT LIKE 'VN30F%'
GROUP BY timestamp;

-- Backfill existing data
CALL refresh_continuous_aggregate('order_velocity_1m', NULL, NOW());
