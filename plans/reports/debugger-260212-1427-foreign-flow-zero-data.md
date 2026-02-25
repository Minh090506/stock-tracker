# Foreign Flow Zero Data Issue - Debug Report

**Date**: 2026-02-12 14:27 VN
**Issue**: Foreign Flow page displays all zeros, "Waiting for data..."
**Status**: ROOT CAUSE IDENTIFIED

## Executive Summary

**Root Cause**: SSI WebSocket connection loss without successful reconnection

**Impact**:
- No foreign flow data displayed (all zeros)
- No real-time market data flowing to any page
- Application continues running but serves stale/zero data
- Users see "Waiting for data..." on Foreign Flow page

**Recommended Solution**:
1. Implement robust SSI reconnection mechanism
2. Add connection health monitoring
3. Add visual indication when SSI is disconnected
4. Consider manual restart endpoint for operators

## Technical Analysis

### Evidence Chain

1. **Frontend Polling Active** ✓
   - `/api/market/foreign-detail` requests every 10s
   - WebSocket `/ws/foreign` connected
   - Hook `use-foreign-flow.ts` properly configured

2. **Backend REST Endpoint Responding** ✓
   - `/api/market/foreign-detail` returns 200 OK
   - Response format correct: `{summary, stocks}`
   - NO parsing errors

3. **Foreign Tracker EMPTY** ✗
   ```
   Foreign tracker: 0 stocks tracked
   Total Buy Value: 0.0
   Total Sell Value: 0.0
   Total Net Value: 0.0
   ```

4. **SSI Messages Received BUT STOPPED** ✗
   ```
   ssi_messages_received_total{channel="trade"} 344091.0
   ssi_messages_received_total{channel="quote"} 344091.0
   ssi_messages_received_total{channel="foreign"} 64074.0  ← STUCK
   ssi_messages_received_total{channel="bar"} 99713.0
   ssi_messages_received_total{channel="index"} 49662.0
   ```

   **Test**: Checked metrics twice 5s apart - ALL counters frozen

5. **SSI Connection LOST** ✗
   ```
   ERROR:websocket:Connection to remote host was lost. - goodbye
   ERROR:SignalRCoreClient:Connection to remote host was lost.
   websocket._exceptions.WebSocketConnectionClosedException
   ```

6. **NO Reconnection Attempt** ✗
   - No "Reconnecting" logs
   - No reconciliation logs
   - Application continues but data pipeline dead

### Timeline

```
10:27 VN (approx) - Container started
10:27 VN - SSI authenticated successfully
10:27 VN - VN30 components fetch returned 0 stocks (separate issue)
10:27 VN - Subscribed to channels: X:ALL, R:ALL, MI:ALL, B:ALL
10:27-XX:XX - Messages flowing (64K foreign, 344K trade/quote)
XX:XX VN - SSI WebSocket connection lost
XX:XX-14:29 - NO data flowing, counters frozen
14:29 VN - Investigation started
```

### Code Flow Analysis

**Normal Flow (WORKING)**:
```
SSI WebSocket → ssi_stream_service._handle_message()
→ parse_message_multi() [Channel R → SSIForeignMessage]
→ registered callbacks
→ processor.handle_foreign(msg)
→ foreign_tracker.update(msg)
→ publisher.notify("foreign")
→ foreign_ws_manager.broadcast()
→ Frontend receives data
```

**Actual Flow (BROKEN)**:
```
SSI WebSocket → CONNECTION LOST
→ No messages
→ No callbacks fired
→ foreign_tracker._session = {}  (empty)
→ get_foreign_summary() returns zeros
→ Frontend receives zeros
```

### Tests Performed

1. **Message Parsing** ✓ WORKS
   ```python
   # Tested with simulated Channel R message
   msg = {'RType': 'R', 'Symbol': 'VNM', 'FBuyVol': 100000, ...}
   results = parse_message_multi(msg)  # SUCCESS
   ```

2. **Foreign Tracker Logic** ✓ WORKS
   ```python
   # Manual injection worked perfectly
   processor.handle_foreign(test_msg)
   # Result: Tracker updated, data accessible
   ```

3. **REST Endpoint** ✓ WORKS
   ```bash
   GET /api/market/foreign-detail
   # Returns valid JSON with empty stocks array
   ```

4. **Message Flow** ✗ BROKEN
   ```
   Metrics frozen for 5+ seconds = no messages flowing
   ```

### Related Issues Found

1. **VN30 Components Empty**
   ```
   INFO: VN30 components: 0 stocks — []
   ```
   - `fetch_vn30_components()` returns empty array
   - May affect filtering logic (needs investigation)
   - Securities snapshot DOES return 100 stocks
   - But lacks foreign fields (FBuyVol, FSellVol)

2. **Missing Reconnection Logic**
   - `ssi_stream_service.py` has `reconcile_after_reconnect()` method
   - But no evidence of it being called after disconnect
   - `ssi-fc-data` library should auto-reconnect per docs
   - Auto-reconnect appears to fail silently

## Data Pipeline Verification

### Backend Files (All Present & Correct)

**Core Processing**:
- `/app/services/foreign_investor_tracker.py` ✓
- `/app/services/market_data_processor.py` ✓
- `/app/services/ssi_stream_service.py` ✓
- `/app/services/ssi_field_normalizer.py` ✓

**Models**:
- `/app/models/ssi_messages.py` (SSIForeignMessage) ✓
- `/app/models/domain.py` (ForeignInvestorData, ForeignSummary) ✓

**Endpoints**:
- `/app/routers/market_router.py` (GET /api/market/foreign-detail) ✓
- `/app/websocket/router.py` (WebSocket /ws/foreign) ✓
- `/app/websocket/broadcast_loop.py` ✓

**Main App**:
- `/app/main.py` (callback registration lines 115-118) ✓

### Frontend Files (All Present & Correct)

**Hooks**:
- `/frontend/src/hooks/use-foreign-flow.ts` ✓
- `/frontend/src/hooks/use-websocket.ts` ✓
- `/frontend/src/hooks/use-polling.ts` ✓

**Pages**:
- `/frontend/src/pages/foreign-flow-page.tsx` ✓

**Components** (all 7 components present):
- `foreign-flow-summary-cards.tsx`
- `foreign-flow-detail-table.tsx`
- `foreign-net-flow-heatmap.tsx`
- `foreign-top-movers-bar-chart.tsx`
- `foreign-cumulative-flow-chart.tsx`
- `foreign-sector-bar-chart.tsx`
- `foreign-top-stocks-tables.tsx`

## SSI FastConnect Configuration

**Subscribed Channels** (from logs):
```
X:ALL  - Combined Trade+Quote ✓
R:ALL  - Foreign room data ✓
MI:ALL - Market indices ✓
B:ALL  - OHLC bars ✓
```

**Message Counts (Frozen)**:
- Trade: 344,091
- Quote: 344,091
- Foreign: 64,074 ← TARGET CHANNEL
- Bar: 99,713
- Index: 49,662

**Channel R Expected Data**:
```python
SSIForeignMessage:
  symbol: str
  f_buy_vol: int      # Cumulative foreign buy volume
  f_sell_vol: int     # Cumulative foreign sell volume
  f_buy_val: float    # Cumulative foreign buy value
  f_sell_val: float   # Cumulative foreign sell value
  total_room: int
  current_room: int
```

## Actionable Recommendations

### Immediate Fixes (Priority 1)

1. **Restart Docker Backend Container**
   ```bash
   docker restart stock-backend
   ```
   - Will re-establish SSI connection
   - Should start receiving foreign flow data
   - TEMPORARY fix until reconnection logic fixed

2. **Add Connection Health Monitoring**
   - Expose SSI connection status in `/metrics`
   - Add Prometheus alert for stuck message counters
   - Add Grafana dashboard for connection health

3. **Add Frontend Disconnect Indicator**
   - Detect when `summary.total_buy_value === 0 && summary.total_sell_value === 0`
   - Show "SSI Disconnected" warning banner
   - Auto-retry every 30s

### Long-term Improvements (Priority 2)

4. **Implement Robust Reconnection**
   ```python
   # In ssi_stream_service.py
   async def _monitor_connection_health(self):
       """Detect and recover from connection loss"""
       last_msg_count = 0
       while True:
           await asyncio.sleep(60)  # Check every minute
           current_count = get_total_messages()
           if current_count == last_msg_count:
               logger.warning("No messages for 60s - reconnecting SSI")
               await self.reconnect()
           last_msg_count = current_count
   ```

5. **Add Manual Recovery Endpoint**
   ```python
   @router.post("/api/admin/reconnect-ssi")
   async def reconnect_ssi():
       """Manual SSI reconnection trigger for operators"""
       await stream_service.disconnect()
       await stream_service.connect(channels)
       return {"status": "reconnecting"}
   ```

6. **Investigate VN30 Component Fetch Failure**
   - `fetch_vn30_components()` returns empty array
   - May be SSI API change or auth scope issue
   - Currently doesn't affect foreign tracking (tracks ALL stocks)
   - But may cause issues if filtering is added later

7. **Add Message Flow Metrics**
   ```python
   # Track messages per minute per channel
   ssi_messages_per_minute{channel="foreign"}

   # Alert if rate drops to zero for >2 minutes
   ALERT SSINoMessages
     IF rate(ssi_messages_per_minute[2m]) == 0
   ```

### Preventive Measures (Priority 3)

8. **Add Integration Tests for Reconnection**
   ```python
   # tests/e2e/test_reconnection.py
   async def test_reconnect_after_disconnect():
       # Simulate SSI disconnect
       # Verify auto-reconnect within 30s
       # Verify data flowing after reconnect
   ```

9. **Add Daily Health Report**
   - Email/Slack alert if SSI was disconnected
   - Report: uptime %, total disconnects, avg reconnect time
   - Track foreign flow data completeness

10. **Add Connection Status to /health Endpoint**
    ```python
    @app.get("/health")
    async def health():
        return {
            "status": "healthy",
            "ssi_connected": stream_service.is_connected(),
            "last_message_at": stream_service.last_message_time,
            "uptime_pct": calculate_uptime()
        }
    ```

## Supporting Evidence

### Docker Container Status
```
stock-backend        Up 4 hours (healthy)
stock-frontend       Up 4 hours
stock-timescaledb    Up 4 hours (healthy)
stock-nginx          Up 4 hours (unhealthy)
```

### Metrics Snapshot (14:29 VN)
```
ssi_messages_received_total{channel="trade"} 344091.0
ssi_messages_received_total{channel="quote"} 344091.0
ssi_messages_received_total{channel="foreign"} 64074.0
ssi_messages_received_total{channel="bar"} 99713.0
ssi_messages_received_total{channel="index"} 49662.0
```

### Error Log Extract
```
websocket._exceptions.WebSocketConnectionClosedException: Connection to remote host was lost.
ERROR:SignalRCoreClient: Connection to remote host was lost.
ERROR:websocket: Connection to remote host was lost. - goodbye
```

## Unresolved Questions

1. **When did the SSI connection drop?**
   - Need to add timestamps to error logs
   - Estimate: Between container start (10:27) and investigation (14:29)
   - Could be minutes or hours ago

2. **Why didn't ssi-fc-data auto-reconnect?**
   - Library documentation claims auto-reconnect
   - May need explicit reconnect handling
   - May be threading issue (asyncio.to_thread context)

3. **Is VN30 component fetch failure related?**
   - Empty VN30 list vs empty foreign tracker
   - Both use SSI REST API
   - May indicate broader SSI API issue or auth problem

4. **Should foreign tracker filter by VN30 or track ALL stocks?**
   - Current: appears to track all stocks receiving Channel R
   - VN30 list empty but not blocking
   - Design decision needed

5. **What is the expected Channel R message frequency?**
   - During trading hours (9:00-15:00 VN)
   - 64K messages in ~4 hours = ~267 msg/min = ~4.5 msg/sec
   - Seems reasonable for ~400 stocks × 1 update/min each

---

**Prepared by**: Debugger Agent
**Report ID**: debugger-260212-1427-foreign-flow-zero-data
**Next Steps**: Restart backend container, implement reconnection monitoring
