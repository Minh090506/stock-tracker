# Phase 7: Testing + Review

## Overview

- **Priority**: P1
- **Status**: pending
- **Effort**: 30m

## Backend Testing

### Verify new endpoints

```bash
cd backend
./venv/bin/python -m pytest tests/ -v
```

Test file: `backend/tests/test_market_router.py` (~40 lines)

```python
"""Tests for /api/market/* REST endpoints."""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

@pytest.mark.asyncio
async def test_snapshot_returns_200(client):
    resp = await client.get("/api/market/snapshot")
    assert resp.status_code == 200
    data = resp.json()
    assert "quotes" in data
    assert "indices" in data

@pytest.mark.asyncio
async def test_foreign_detail_returns_200(client):
    resp = await client.get("/api/market/foreign-detail")
    assert resp.status_code == 200
    data = resp.json()
    assert "summary" in data
    assert "stocks" in data

@pytest.mark.asyncio
async def test_volume_stats_returns_200(client):
    resp = await client.get("/api/market/volume-stats")
    assert resp.status_code == 200
    assert "stats" in resp.json()
```

### Frontend Build Verification

```bash
cd frontend
npm run build
```

Must compile without TypeScript errors.

## Code Review Checklist

- [ ] Backend: No circular imports (lazy import pattern used)
- [ ] Backend: All Pydantic models serialize to JSON correctly (datetime -> ISO)
- [ ] Frontend: All types match backend response shapes
- [ ] Frontend: No unused imports (TS strict mode catches this)
- [ ] Frontend: All components <200 lines
- [ ] Frontend: kebab-case file names
- [ ] Frontend: VN color convention applied consistently
- [ ] Frontend: `usePolling` cleanup on unmount (no memory leaks)
- [ ] Frontend: Error boundaries around chart components

## Todo

- [ ] Write backend endpoint tests
- [ ] Run `pytest` -- all pass
- [ ] Run `npm run build` -- no errors
- [ ] Delegate to `code-reviewer` agent
- [ ] Fix any review findings

## Success Criteria

- All existing 232+ backend tests still pass
- New endpoint tests pass (3 minimum)
- Frontend builds successfully
- Code review approval
