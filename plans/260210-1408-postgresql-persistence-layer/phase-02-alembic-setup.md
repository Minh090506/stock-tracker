# Phase 2: Alembic Migration Setup

## Overview
- **Priority:** P2
- **Status:** complete
- **Est:** 45 min

Set up Alembic for raw-SQL migrations (no SQLAlchemy ORM). Wrap existing `db/migrations/001_create_hypertables.sql` as initial Alembic migration. Future schema changes go through Alembic.

## Key Insights
- Alembic requires sync DB driver -- use `psycopg2-binary` alongside existing `asyncpg`
- No SQLAlchemy models needed; `op.execute()` for raw SQL
- Existing SQL file has TimescaleDB-specific commands (`create_hypertable`) that must run after `CREATE EXTENSION`
- `docker-compose.yml` currently mounts `db/migrations/` to `/docker-entrypoint-initdb.d/` -- Alembic replaces this for managed environments

## Related Code Files

**Create:**
- `backend/alembic.ini`
- `backend/alembic/env.py`
- `backend/alembic/script.py.mako`
- `backend/alembic/versions/001_create_hypertables.py`

**Modify:**
- `backend/requirements.txt` — add alembic, psycopg2-binary

**Reference (read-only):**
- `db/migrations/001_create_hypertables.sql` — source SQL for initial migration

## Implementation Steps

### Step 1: Add dependencies
Append to `backend/requirements.txt`:
```
alembic>=1.14.0
psycopg2-binary>=2.9.0
```

Install:
```bash
cd backend && ./venv/bin/pip install alembic psycopg2-binary
```

### Step 2: Create alembic.ini
File: `backend/alembic.ini`

```ini
[alembic]
script_location = alembic
# Override via env var or CLI: -x sqlalchemy.url=postgresql://...
sqlalchemy.url = postgresql://stock:stock@localhost:5432/stock_tracker

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

### Step 3: Create alembic/env.py
File: `backend/alembic/env.py`

Minimal sync-only setup. Reads `DATABASE_URL` from env (falls back to alembic.ini).

```python
"""Alembic env — raw SQL migrations, no SQLAlchemy ORM."""

import os
from logging.config import fileConfig

from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url from DATABASE_URL env var if set
db_url = os.environ.get("DATABASE_URL")
if db_url:
    # asyncpg URL -> psycopg2: replace postgresql:// prefix (no +asyncpg)
    if "+asyncpg" in db_url:
        db_url = db_url.replace("+asyncpg", "")
    config.set_main_option("sqlalchemy.url", db_url)


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of executing."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=None, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against live database."""
    from sqlalchemy import engine_from_config, pool

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### Step 4: Create script.py.mako
File: `backend/alembic/script.py.mako`

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

### Step 5: Create initial migration
File: `backend/alembic/versions/001_create_hypertables.py`

Wrap the exact SQL from `db/migrations/001_create_hypertables.sql`. Use `op.execute()` for each statement. Downgrade drops tables in reverse order.

```python
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

    # tick_data
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

    # candles_1m
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

    # foreign_flow
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

    # index_snapshots
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

    # derivatives
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
    for table in ["derivatives", "index_snapshots", "foreign_flow",
                   "candles_1m", "tick_data"]:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
```

### Step 6: Verify
```bash
cd backend && ./venv/bin/alembic --help  # confirms install
cd backend && ./venv/bin/alembic history  # shows revision 001
```

## Todo List
- [ ] Add `alembic>=1.14.0` and `psycopg2-binary>=2.9.0` to requirements.txt
- [ ] Install new deps in venv
- [ ] Create `backend/alembic.ini`
- [ ] Create `backend/alembic/env.py`
- [ ] Create `backend/alembic/script.py.mako`
- [ ] Create `backend/alembic/versions/001_create_hypertables.py`
- [ ] Verify `alembic history` shows revision chain
- [ ] Test `alembic upgrade head` against local TimescaleDB (if running)

## Success Criteria
- `./venv/bin/alembic history` lists revision `001`
- `./venv/bin/alembic upgrade head` creates all 5 hypertables on fresh DB
- `./venv/bin/alembic downgrade base` drops all 5 tables
- Existing `db/migrations/001_create_hypertables.sql` left untouched (still used by docker-compose dev)

## Risk Assessment
- **psycopg2-binary vs psycopg2** — binary avoids libpq compile dependency; fine for containerized deploy
- **SQLAlchemy as Alembic dep** — Alembic pulls in SQLAlchemy automatically; only used for connection, not ORM
- **Existing DB with tables** — `IF NOT EXISTS` / `if_not_exists => TRUE` makes migration idempotent; safe to stamp existing DBs with `alembic stamp head`

## Security
- `DATABASE_URL` env var overrides `alembic.ini` default -- no credentials in committed config for prod
