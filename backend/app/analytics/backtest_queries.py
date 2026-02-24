"""SQL queries for backtest analysis (all parameterized, no user-supplied SQL)."""

VELOCITY_PRICE_SQL = """
SELECT
    v.timestamp,
    (v.buy_vol - v.sell_vol)::float AS net_velocity,
    v.buy_vol::float / NULLIF(v.buy_vol + v.sell_vol, 0) AS imbalance_ratio,
    c.close::float AS vn30f_price,
    EXTRACT(HOUR FROM v.timestamp)::int AS hour_of_day,
    EXTRACT(MINUTE FROM v.timestamp)::int AS minute_of_hour
FROM order_velocity_1m v
JOIN candles_1m c ON v.timestamp = c.timestamp AND c.symbol = $1
WHERE v.symbol = $1
  AND v.timestamp BETWEEN $2 AND $3
  AND EXTRACT(HOUR FROM v.timestamp) BETWEEN 9 AND 14
ORDER BY v.timestamp
"""

BASKET_VELOCITY_PRICE_SQL = """
SELECT
    v.timestamp,
    (v.buy_vol - v.sell_vol)::float AS net_velocity,
    v.buy_vol::float / NULLIF(v.buy_vol + v.sell_vol, 0) AS imbalance_ratio,
    c.close::float AS vn30f_price,
    EXTRACT(HOUR FROM v.timestamp)::int AS hour_of_day,
    EXTRACT(MINUTE FROM v.timestamp)::int AS minute_of_hour
FROM vn30_basket_velocity_1m v
JOIN candles_1m c ON v.timestamp = c.timestamp AND c.symbol = $1
WHERE v.timestamp BETWEEN $2 AND $3
  AND EXTRACT(HOUR FROM v.timestamp) BETWEEN 9 AND 14
ORDER BY v.timestamp
"""

TRADING_DAYS_SQL = """
SELECT COUNT(DISTINCT date_trunc('day', timestamp))::int AS days
FROM candles_1m
WHERE symbol = $1
  AND timestamp >= NOW() - make_interval(days => $2)
"""
