# Phase 1: Pool Configuration + Health Check

## Overview
- **Priority:** P1 (blocks Phase 4)
- **Status:** complete
- **Est:** 45 min

Rename `connection.py` -> `pool.py`, add configurable pool sizes via env vars, add `health_check()` method. Update all imports across codebase.

## Key Insights
- 7 files import from `app.database.connection` (app code + tests)
- Current pool hardcoded min=5, max=20 -- too aggressive for dev, too small for prod
- No health check exists; needed for `/health` endpoint DB status reporting

## Related Code Files

**Modify:**
- `backend/app/database/connection.py` -> renamed to `backend/app/database/pool.py`
- `backend/app/database/__init__.py` — update import path
- `backend/app/database/batch_writer.py` — line 12: `from app.database.connection import Database`
- `backend/app/database/history_service.py` — line 7: `from app.database.connection import Database`
- `backend/app/main.py` — line 14: `from app.database.connection import db`
- `backend/app/routers/history_router.py` — line 7: `from app.database.connection import db`
- `backend/app/config.py` — add pool size settings
- `backend/.env.example` — add DB_POOL_MIN, DB_POOL_MAX
- `backend/tests/test_history_service.py` — line 8: `from app.database.connection import Database`
- `backend/tests/test_batch_writer.py` — line 10: `from app.database.connection import Database`

## Implementation Steps

### Step 1: Add pool config to Settings
In `backend/app/config.py`, add inside `Settings` class after `database_url`:
```python
db_pool_min: int = 2
db_pool_max: int = 10
```

### Step 2: Rename connection.py -> pool.py
```bash
cd backend && git mv app/database/connection.py app/database/pool.py
```

### Step 3: Update pool.py content
In `backend/app/database/pool.py`:
- Import `settings` pool sizes into `connect()`
- Add `async def health_check(self) -> bool` method
- Use `asyncio.wait_for` with 5s timeout on `SELECT 1`

Updated `Database` class:
```python
class Database:
    """Manages asyncpg connection pool lifecycle."""

    pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self.pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=settings.db_pool_min,
            max_size=settings.db_pool_max,
        )
        logger.info(
            "Database pool created (min=%d, max=%d)",
            settings.db_pool_min, settings.db_pool_max,
        )

    async def disconnect(self) -> None:
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Database pool closed")

    async def health_check(self) -> bool:
        """Return True if pool can execute a simple query within 5s."""
        if not self.pool:
            return False
        try:
            async with self.pool.acquire() as conn:
                await asyncio.wait_for(conn.fetchval("SELECT 1"), timeout=5.0)
            return True
        except Exception:
            logger.warning("Database health check failed", exc_info=True)
            return False
```

Note: Add `import asyncio` at top.

### Step 4: Update all imports (search-and-replace)
In each of these files, change:
- `from app.database.connection import Database` -> `from app.database.pool import Database`
- `from app.database.connection import Database, db` -> `from app.database.pool import Database, db`
- `from app.database.connection import db` -> `from app.database.pool import db`

Files:
1. `backend/app/database/__init__.py`
2. `backend/app/database/batch_writer.py`
3. `backend/app/database/history_service.py`
4. `backend/app/main.py`
5. `backend/app/routers/history_router.py`
6. `backend/tests/test_history_service.py`
7. `backend/tests/test_batch_writer.py`

### Step 5: Update .env.example
Append:
```
# Database pool
DB_POOL_MIN=2
DB_POOL_MAX=10
```

### Step 6: Verify
```bash
cd backend && ./venv/bin/python -c "from app.database.pool import db; print('OK')"
cd backend && ./venv/bin/pytest tests/test_batch_writer.py tests/test_history_service.py -v
```

## Todo List
- [ ] Add `db_pool_min`, `db_pool_max` to `config.py` Settings
- [ ] `git mv connection.py pool.py`
- [ ] Add `health_check()` and configurable pool sizes in `pool.py`
- [ ] Update imports in `__init__.py`
- [ ] Update imports in `batch_writer.py`
- [ ] Update imports in `history_service.py`
- [ ] Update imports in `main.py`
- [ ] Update imports in `history_router.py`
- [ ] Update imports in `test_history_service.py`
- [ ] Update imports in `test_batch_writer.py`
- [ ] Update `.env.example`
- [ ] Run existing tests -- all pass

## Success Criteria
- `from app.database.pool import db, Database` works
- `db.health_check()` returns `True` when connected, `False` otherwise
- Pool sizes driven by env vars `DB_POOL_MIN`, `DB_POOL_MAX`
- All existing tests pass with zero changes to test logic (only import path)

## Risk Assessment
- **Import breakage** — mitigated by comprehensive grep of all `connection` imports (7 files identified)
- **Git history** — using `git mv` preserves rename tracking
