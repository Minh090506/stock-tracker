"""Create TimescaleDB hypertables.

Revision ID: 001
Revises: None
Create Date: 2026-02-10
"""
from typing import Sequence, Union

from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")

    # tick_data: per-trade classified ticks
    op.execute("""
        CREATE TABLE IF NOT EXISTS tick_data (
            symbol     VARCHAR(10) NOT NULL,
            timestamp  TIMESTAMPTZ NOT NULL,
            price      NUMERIC(12, 2) NOT NULL,
            volume     INTEGER NOT NULL,
            side       VARCHAR(20) NOT NULL,
            bid        NUMERIC(12, 2),
            ask        NUMERIC(12, 2)
        )
    """)
    op.execute(
        "SELECT create_hypertable('tick_data', 'timestamp', if_not_exists => TRUE)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_tick_symbol_time "
        "ON tick_data (symbol, timestamp DESC)"
    )

    # candles_1m: 1-minute OHLCV bars with active buy/sell breakdown
    op.execute("""
        CREATE TABLE IF NOT EXISTS candles_1m (
            symbol          VARCHAR(10) NOT NULL,
            timestamp       TIMESTAMPTZ NOT NULL,
            open            NUMERIC(12, 2) NOT NULL,
            high            NUMERIC(12, 2) NOT NULL,
            low             NUMERIC(12, 2) NOT NULL,
            close           NUMERIC(12, 2) NOT NULL,
            volume          BIGINT NOT NULL DEFAULT 0,
            active_buy_vol  BIGINT NOT NULL DEFAULT 0,
            active_sell_vol BIGINT NOT NULL DEFAULT 0,
            UNIQUE (symbol, timestamp)
        )
    """)
    op.execute(
        "SELECT create_hypertable('candles_1m', 'timestamp', if_not_exists => TRUE)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_candles_symbol_time "
        "ON candles_1m (symbol, timestamp DESC)"
    )

    # foreign_flow: foreign investor activity snapshots
    op.execute("""
        CREATE TABLE IF NOT EXISTS foreign_flow (
            symbol     VARCHAR(10) NOT NULL,
            timestamp  TIMESTAMPTZ NOT NULL,
            buy_vol    BIGINT NOT NULL DEFAULT 0,
            sell_vol   BIGINT NOT NULL DEFAULT 0,
            net_vol    BIGINT NOT NULL DEFAULT 0,
            buy_value  NUMERIC(18, 2) NOT NULL DEFAULT 0,
            sell_value NUMERIC(18, 2) NOT NULL DEFAULT 0
        )
    """)
    op.execute(
        "SELECT create_hypertable('foreign_flow', 'timestamp', if_not_exists => TRUE)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_foreign_symbol_time "
        "ON foreign_flow (symbol, timestamp DESC)"
    )

    # index_snapshots: VN30 / VNINDEX snapshots
    op.execute("""
        CREATE TABLE IF NOT EXISTS index_snapshots (
            index_name VARCHAR(20) NOT NULL,
            timestamp  TIMESTAMPTZ NOT NULL,
            value      NUMERIC(12, 2) NOT NULL,
            change_pct NUMERIC(8, 4) NOT NULL DEFAULT 0,
            volume     BIGINT NOT NULL DEFAULT 0
        )
    """)
    op.execute(
        "SELECT create_hypertable('index_snapshots', 'timestamp', "
        "if_not_exists => TRUE)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_index_name_time "
        "ON index_snapshots (index_name, timestamp DESC)"
    )

    # derivatives: VN30F futures with basis and open interest
    op.execute("""
        CREATE TABLE IF NOT EXISTS derivatives (
            contract      VARCHAR(20) NOT NULL,
            timestamp     TIMESTAMPTZ NOT NULL,
            price         NUMERIC(12, 2) NOT NULL,
            basis         NUMERIC(12, 2) NOT NULL DEFAULT 0,
            open_interest BIGINT NOT NULL DEFAULT 0
        )
    """)
    op.execute(
        "SELECT create_hypertable('derivatives', 'timestamp', if_not_exists => TRUE)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_deriv_contract_time "
        "ON derivatives (contract, timestamp DESC)"
    )


def downgrade() -> None:
    for table in [
        "derivatives", "index_snapshots", "foreign_flow",
        "candles_1m", "tick_data",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
