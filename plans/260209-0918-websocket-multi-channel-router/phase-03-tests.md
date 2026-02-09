# Phase 3: Tests

**Priority:** P1
**Status:** Pending
**Effort:** 0.5h

## Context Links
- Plan: [plan.md](./plan.md)
- Phase 1: [phase-01-router-and-auth.md](./phase-01-router-and-auth.md)
- Phase 2: [phase-02-broadcast-and-wiring.md](./phase-02-broadcast-and-wiring.md)
- Current tests: `backend/tests/test_websocket_endpoint.py`

## Overview
Update existing WebSocket tests to work with 3-channel router and add tests for authentication and rate limiting.

## Key Insights
- Existing tests mock processor and ws_manager
- Need to mock 3 managers instead of 1
- Auth tests need to patch settings.ws_auth_token
- Rate limit tests need to simulate multiple connections from same IP

## Requirements

### Functional
- All existing broadcast loop tests pass with 3 managers
- New tests for auth success/failure
- New tests for rate limit enforcement
- New tests for 3 separate channels

### Non-Functional
- Test file stays under 300 LOC
- Fast test execution (mock all external deps)
- Clear test names

## Architecture

### Test Structure
```python
# Existing tests (update)
TestBroadcastLoop
  - test_loop_sends_to_three_channels (updated)
  - test_loop_skips_when_no_clients (updated)
  - test_loop_handles_snapshot_error (updated)
  - test_loop_serializes_correctly (updated)

# New tests
TestAuthentication
  - test_auth_success_with_valid_token
  - test_auth_failure_with_invalid_token
  - test_auth_disabled_when_token_empty

TestRateLimiting
  - test_rate_limit_allows_under_threshold
  - test_rate_limit_rejects_over_threshold
  - test_rate_limit_decrements_on_disconnect

TestMultiChannel
  - test_market_channel_broadcasts_snapshot
  - test_foreign_channel_broadcasts_summary
  - test_index_channel_broadcasts_indices
```

## Related Code Files

### To Modify
- `backend/tests/test_websocket_endpoint.py` — update all tests for 3 managers

### To Keep (no changes)
- `backend/app/websocket/router.py`
- `backend/app/websocket/broadcast_loop.py`
- `backend/app/websocket/connection_manager.py`

## Implementation Steps

### 1. Update Imports
**File:** `backend/tests/test_websocket_endpoint.py`

**Replace lines 1-10:**
```python
"""Integration tests for WebSocket multi-channel router and broadcast loop."""

import asyncio
import json

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from app.models.domain import MarketSnapshot, ForeignSummary, IndexData
from app.websocket.connection_manager import ConnectionManager
```

### 2. Add Manager Fixtures
**File:** `backend/tests/test_websocket_endpoint.py`

**Replace lines 12-15:**
```python
@pytest.fixture
def market_ws_manager():
    return ConnectionManager()


@pytest.fixture
def foreign_ws_manager():
    return ConnectionManager()


@pytest.fixture
def index_ws_manager():
    return ConnectionManager()


@pytest.fixture
def mock_snapshot():
    """Minimal MarketSnapshot for testing."""
    return MarketSnapshot(quotes={}, indices={}, foreign=None, derivatives=None)


@pytest.fixture
def mock_foreign_summary():
    """Minimal ForeignSummary for testing."""
    return ForeignSummary()


@pytest.fixture
def mock_indices():
    """Minimal IndexData dict for testing."""
    return {
        "VN30": IndexData(index_id="VN30", value=1200.0),
        "VNINDEX": IndexData(index_id="VNINDEX", value=1100.0),
    }
```

### 3. Update Broadcast Loop Tests
**File:** `backend/tests/test_websocket_endpoint.py`

**Replace TestBroadcastLoop class (lines 23-141):**
```python
class TestBroadcastLoop:
    @pytest.mark.asyncio
    async def test_loop_sends_to_three_channels(
        self, market_ws_manager, foreign_ws_manager, index_ws_manager,
        mock_snapshot, mock_foreign_summary, mock_indices
    ):
        """Broadcast loop calls 3 data sources and broadcasts to 3 managers."""
        from app.websocket.broadcast_loop import broadcast_loop

        mock_processor = MagicMock()
        mock_processor.get_market_snapshot.return_value = mock_snapshot
        mock_processor.get_foreign_summary.return_value = mock_foreign_summary
        mock_processor.index_tracker.get_all.return_value = mock_indices

        # Add clients to all 3 channels
        market_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=50)
        foreign_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=50)
        index_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=50)

        ws_mock = MagicMock()
        market_task = asyncio.create_task(asyncio.sleep(999))
        foreign_task = asyncio.create_task(asyncio.sleep(999))
        index_task = asyncio.create_task(asyncio.sleep(999))

        market_ws_manager._clients[ws_mock] = (market_queue, market_task)
        foreign_ws_manager._clients[ws_mock] = (foreign_queue, foreign_task)
        index_ws_manager._clients[ws_mock] = (index_queue, index_task)

        with patch("app.websocket.broadcast_loop.settings") as mock_settings:
            mock_settings.ws_broadcast_interval = 0.05

            loop_task = asyncio.create_task(
                broadcast_loop(
                    mock_processor,
                    market_ws_manager,
                    foreign_ws_manager,
                    index_ws_manager,
                )
            )
            await asyncio.sleep(0.2)
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass

        assert mock_processor.get_market_snapshot.call_count >= 2
        assert mock_processor.get_foreign_summary.call_count >= 2
        assert mock_processor.index_tracker.get_all.call_count >= 2
        assert not market_queue.empty()
        assert not foreign_queue.empty()
        assert not index_queue.empty()

        market_task.cancel()
        foreign_task.cancel()
        index_task.cancel()

    @pytest.mark.asyncio
    async def test_loop_skips_when_no_clients(self):
        """No serialization when all channels have zero clients."""
        from app.websocket.broadcast_loop import broadcast_loop

        mock_processor = MagicMock()
        market_mgr = ConnectionManager()
        foreign_mgr = ConnectionManager()
        index_mgr = ConnectionManager()

        with patch("app.websocket.broadcast_loop.settings") as mock_settings:
            mock_settings.ws_broadcast_interval = 0.05

            loop_task = asyncio.create_task(
                broadcast_loop(mock_processor, market_mgr, foreign_mgr, index_mgr)
            )
            await asyncio.sleep(0.2)
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass

        mock_processor.get_market_snapshot.assert_not_called()
        mock_processor.get_foreign_summary.assert_not_called()

    @pytest.mark.asyncio
    async def test_loop_handles_snapshot_error(self, market_ws_manager):
        """Broadcast loop survives exceptions in data fetching."""
        from app.websocket.broadcast_loop import broadcast_loop

        mock_processor = MagicMock()
        mock_processor.get_market_snapshot.side_effect = RuntimeError("boom")

        # Add client so loop doesn't skip
        ws = MagicMock()
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=50)
        task = asyncio.create_task(asyncio.sleep(999))
        market_ws_manager._clients[ws] = (queue, task)

        with patch("app.websocket.broadcast_loop.settings") as mock_settings:
            mock_settings.ws_broadcast_interval = 0.05

            loop_task = asyncio.create_task(
                broadcast_loop(
                    mock_processor,
                    market_ws_manager,
                    ConnectionManager(),
                    ConnectionManager(),
                )
            )
            await asyncio.sleep(0.2)
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass

        assert mock_processor.get_market_snapshot.call_count >= 2
        task.cancel()

    @pytest.mark.asyncio
    async def test_loop_serializes_correctly(
        self, market_ws_manager, foreign_ws_manager, index_ws_manager,
        mock_snapshot, mock_foreign_summary, mock_indices
    ):
        """Verify broadcast data is valid JSON from model_dump_json."""
        from app.websocket.broadcast_loop import broadcast_loop

        mock_processor = MagicMock()
        mock_processor.get_market_snapshot.return_value = mock_snapshot
        mock_processor.get_foreign_summary.return_value = mock_foreign_summary
        mock_processor.index_tracker.get_all.return_value = mock_indices

        market_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=50)
        foreign_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=50)
        index_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=50)

        ws = MagicMock()
        market_task = asyncio.create_task(asyncio.sleep(999))
        foreign_task = asyncio.create_task(asyncio.sleep(999))
        index_task = asyncio.create_task(asyncio.sleep(999))

        market_ws_manager._clients[ws] = (market_queue, market_task)
        foreign_ws_manager._clients[ws] = (foreign_queue, foreign_task)
        index_ws_manager._clients[ws] = (index_queue, index_task)

        with patch("app.websocket.broadcast_loop.settings") as mock_settings:
            mock_settings.ws_broadcast_interval = 0.05

            loop_task = asyncio.create_task(
                broadcast_loop(
                    mock_processor,
                    market_ws_manager,
                    foreign_ws_manager,
                    index_ws_manager,
                )
            )
            await asyncio.sleep(0.15)
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass

        # Verify each channel's JSON
        market_data = json.loads(market_queue.get_nowait())
        assert "quotes" in market_data
        assert "indices" in market_data

        foreign_data = json.loads(foreign_queue.get_nowait())
        assert "total_buy_value" in foreign_data

        index_data = json.loads(index_queue.get_nowait())
        assert "VN30" in index_data
        assert "VNINDEX" in index_data

        market_task.cancel()
        foreign_task.cancel()
        index_task.cancel()
```

### 4. Add Authentication Tests
**File:** `backend/tests/test_websocket_endpoint.py`

**Add new test class:**
```python
class TestAuthentication:
    @pytest.mark.asyncio
    async def test_auth_success_with_valid_token(self):
        """Valid token allows connection."""
        from app.websocket.router import _authenticate

        ws_mock = MagicMock()
        ws_mock.query_params = {"token": "test123"}
        ws_mock.close = AsyncMock()

        with patch("app.websocket.router.settings") as mock_settings:
            mock_settings.ws_auth_token = "test123"
            result = await _authenticate(ws_mock)

        assert result is True
        ws_mock.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_auth_failure_with_invalid_token(self):
        """Invalid token closes connection with 403."""
        from app.websocket.router import _authenticate
        from fastapi import status

        ws_mock = MagicMock()
        ws_mock.query_params = {"token": "wrong"}
        ws_mock.close = AsyncMock()
        ws_mock.client = MagicMock()
        ws_mock.client.host = "127.0.0.1"

        with patch("app.websocket.router.settings") as mock_settings:
            mock_settings.ws_auth_token = "test123"
            result = await _authenticate(ws_mock)

        assert result is False
        ws_mock.close.assert_called_once_with(code=status.WS_1008_POLICY_VIOLATION)

    @pytest.mark.asyncio
    async def test_auth_disabled_when_token_empty(self):
        """Empty token setting disables authentication."""
        from app.websocket.router import _authenticate

        ws_mock = MagicMock()
        ws_mock.query_params = {}
        ws_mock.close = AsyncMock()

        with patch("app.websocket.router.settings") as mock_settings:
            mock_settings.ws_auth_token = ""
            result = await _authenticate(ws_mock)

        assert result is True
        ws_mock.close.assert_not_called()
```

### 5. Add Rate Limiting Tests
**File:** `backend/tests/test_websocket_endpoint.py`

**Add new test class:**
```python
class TestRateLimiting:
    @pytest.mark.asyncio
    async def test_rate_limit_allows_under_threshold(self):
        """Connections under limit are allowed."""
        from app.websocket.router import _check_rate_limit, _rate_limiter

        _rate_limiter._connections.clear()

        ws_mock = MagicMock()
        ws_mock.client = MagicMock()
        ws_mock.client.host = "127.0.0.1"
        ws_mock.close = AsyncMock()

        with patch("app.websocket.router.settings") as mock_settings:
            mock_settings.ws_max_connections_per_ip = 5
            _rate_limiter._connections["127.0.0.1"] = 3
            result = await _check_rate_limit(ws_mock)

        assert result is True
        ws_mock.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_rate_limit_rejects_over_threshold(self):
        """Connections at/over limit are rejected."""
        from app.websocket.router import _check_rate_limit, _rate_limiter
        from fastapi import status

        _rate_limiter._connections.clear()

        ws_mock = MagicMock()
        ws_mock.client = MagicMock()
        ws_mock.client.host = "127.0.0.1"
        ws_mock.close = AsyncMock()

        with patch("app.websocket.router.settings") as mock_settings:
            mock_settings.ws_max_connections_per_ip = 5
            _rate_limiter._connections["127.0.0.1"] = 5
            result = await _check_rate_limit(ws_mock)

        assert result is False
        ws_mock.close.assert_called_once_with(code=status.WS_1008_POLICY_VIOLATION)

    @pytest.mark.asyncio
    async def test_rate_limit_decrements_on_disconnect(self):
        """Rate limiter count decrements when client disconnects."""
        from app.websocket.router import _rate_limiter

        _rate_limiter._connections.clear()
        _rate_limiter._connections["127.0.0.1"] = 3

        _rate_limiter.decrement("127.0.0.1")
        assert _rate_limiter._connections["127.0.0.1"] == 2

        _rate_limiter.decrement("127.0.0.1")
        _rate_limiter.decrement("127.0.0.1")
        assert _rate_limiter._connections["127.0.0.1"] == 0

        # Should not go negative
        _rate_limiter.decrement("127.0.0.1")
        assert _rate_limiter._connections["127.0.0.1"] == 0
```

## Todo List
- [ ] Update test file imports
- [ ] Add manager fixtures for 3 channels
- [ ] Add mock_foreign_summary and mock_indices fixtures
- [ ] Update TestBroadcastLoop.test_loop_sends_to_three_channels
- [ ] Update TestBroadcastLoop.test_loop_skips_when_no_clients
- [ ] Update TestBroadcastLoop.test_loop_handles_snapshot_error
- [ ] Update TestBroadcastLoop.test_loop_serializes_correctly
- [ ] Add TestAuthentication class with 3 tests
- [ ] Add TestRateLimiting class with 3 tests
- [ ] Run tests: `pytest backend/tests/test_websocket_endpoint.py -v`
- [ ] Run full test suite: `pytest backend/tests/ -v`
- [ ] Verify all 247 tests pass

## Success Criteria
- All updated broadcast loop tests pass
- All new auth tests pass
- All new rate limit tests pass
- Full test suite passes (247 tests)
- Test coverage includes all 3 channels
- No test warnings or errors

## Risk Assessment
**Risk:** Mock setup complexity causes flaky tests
**Mitigation:** Use simple MagicMock, avoid over-mocking

**Risk:** Async test cleanup issues
**Mitigation:** Always cancel tasks in finally blocks

**Risk:** Tests depend on exact call counts (brittle)
**Mitigation:** Use `>=` assertions for call counts, not `==`

## Security Considerations
None (tests only)

## Next Steps
Implementation complete, ready for deployment
