"""Create order_velocity_1m continuous aggregate and vn30_basket_velocity_1m view.

Revision ID: 003
Revises: 001
Create Date: 2026-02-24
"""
from typing import Sequence, Union

from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Per-symbol buy/sell velocity aggregate (volume, count, value) per 1-min bucket
    op.execute("""
        CREATE MATERIALIZED VIEW order_velocity_1m
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 minute', timestamp) AS timestamp,
            symbol,
            coalesce(sum(volume) FILTER (WHERE side = 'mua_chu_dong'), 0)::bigint AS buy_vol,
            coalesce(sum(volume) FILTER (WHERE side = 'ban_chu_dong'), 0)::bigint AS sell_vol,
            (count(*) FILTER (WHERE side = 'mua_chu_dong'))::int AS buy_count,
            (count(*) FILTER (WHERE side = 'ban_chu_dong'))::int AS sell_count,
            coalesce(sum(price * volume * 1000) FILTER (WHERE side = 'mua_chu_dong'), 0)::bigint
                AS buy_value,
            coalesce(sum(price * volume * 1000) FILTER (WHERE side = 'ban_chu_dong'), 0)::bigint
                AS sell_value
        FROM tick_data
        GROUP BY 1, 2
        WITH NO DATA
    """)

    op.execute("""
        SELECT add_continuous_aggregate_policy('order_velocity_1m',
            start_offset  => INTERVAL '2 hours',
            end_offset    => INTERVAL '1 minute',
            schedule_interval => INTERVAL '1 minute'
        )
    """)

    # VN30 basket: sum across all VN30 stocks (exclude VN30F futures)
    op.execute("""
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
        GROUP BY timestamp
    """)

    # Backfill existing tick_data
    op.execute("CALL refresh_continuous_aggregate('order_velocity_1m', NULL, NOW())")


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS vn30_basket_velocity_1m")
    op.execute("SELECT remove_continuous_aggregate_policy('order_velocity_1m', if_not_exists => TRUE)")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS order_velocity_1m CASCADE")
