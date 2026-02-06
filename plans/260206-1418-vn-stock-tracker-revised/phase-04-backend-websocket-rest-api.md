# Phase 04: Backend WebSocket Server + REST API

## Context Links
- [Plan Overview](./plan.md)
- [Phase 03: Data Processing](./phase-03-data-processing-core.md)
- [Old plan Phase 04](../260206-1341-stock-tracker-system/phase-04-backend-websocket-server.md)

## Overview
- **Priority:** P0
- **Status:** pending
- **Effort:** 4h
- Build WebSocket server for React clients with group-based broadcasting. State snapshot on connect. REST endpoints for VN30 list, session stats, foreign data. Extended protocol with index, derivatives, and alert message types.

## Key Changes from Old Plan
- Added message types: `index`, `derivatives`, `alert`
- Broadcast index/derivatives alongside trades and foreign
- REST `/api/vn30-components` for VN30 stock list
- Throttled broadcast (batch every 100ms) to avoid flooding clients

## Requirements

### Functional
- WebSocket endpoint at `/ws/market`
- Clients subscribe/unsubscribe to symbols
- Server broadcasts: trade, foreign, index, derivatives, alert
- State snapshot on connect (recent trades + stats + foreign + indices + basis)
- Heartbeat 30s
- REST endpoints: `/api/vn30-components`, `/api/session-stats`, `/api/foreign`

### Non-Functional
- 20+ concurrent connections (team <5, but allow headroom)
- Broadcast latency <50ms
- Dead connection cleanup via heartbeat

## Architecture
```
React Client ──ws──→ /ws/market
                        │
                   ConnectionManager
                   ┌────┴────────────┐
                   │  groups:        │
                   │   "VNM": [ws1]  │
                   │   "FPT": [ws2]  │
                   │   "__all__": [*] │  ← for index/derivatives/alerts
                   └────┬────────────┘
                        │
             MarketDataProcessor (Phase 03)
                   broadcasts to groups
```

## WS Protocol

```json
// Client → Server: Subscribe
{"action": "subscribe", "symbols": ["VNM", "FPT", "BID"]}

// Client → Server: Unsubscribe
{"action": "unsubscribe", "symbols": ["BID"]}

// Server → Client: Trade update (per-symbol subscribers)
{"type": "trade", "data": {
  "symbol": "VNM", "price": 78.5, "volume": 1000,
  "tradeType": "mua_chu_dong",
  "muaTotal": 500000, "banTotal": 480000, "timestamp": "..."
}}

// Server → Client: Foreign update (per-symbol subscribers)
{"type": "foreign", "data": {
  "symbol": "VNM", "buyVol": 50000, "sellVol": 30000,
  "netVol": 20000, "buySpeedPerMin": 1200, "sellSpeedPerMin": 800
}}

// Server → Client: Index update (ALL subscribers)
{"type": "index", "data": {
  "indexId": "VN30", "value": 1238.76, "change": 12.6,
  "ratioChange": 1.03, "advances": 18, "declines": 10
}}

// Server → Client: Derivatives update (ALL subscribers)
{"type": "derivatives", "data": {
  "futuresSymbol": "VN30F2602", "futuresPrice": 1242.3,
  "spotValue": 1238.76, "basis": 3.54, "isPremium": true
}}

// Server → Client: Alert (ALL subscribers)
{"type": "alert", "data": {
  "symbol": "VCB", "alertType": "foreign_threshold",
  "message": "NN mua rong 100K co phieu", "severity": "high"
}}

// Server → Client: Snapshot (on connect, per subscribed symbol)
{"type": "snapshot", "data": {
  "symbol": "VNM",
  "sessionStats": {...}, "foreignData": {...},
  "indices": {"VN30": {...}, "VNINDEX": {...}},
  "basis": {...}
}}

// Server → Client: Ping
{"type": "ping"}
```

## Related Code Files
- `~/projects/stock-tracker/backend/app/websocket/connection_manager.py`
- `~/projects/stock-tracker/backend/app/websocket/market_handler.py`
- `~/projects/stock-tracker/backend/app/routers/market_router.py`
- `~/projects/stock-tracker/backend/app/main.py`

## Implementation Steps

### 1. ConnectionManager (`websocket/connection_manager.py`)
Same as old plan but add `broadcast_to_all()` for index/derivatives/alerts.

### 2. MarketHandler (`websocket/market_handler.py`)
Handle subscribe/unsubscribe + snapshot delivery + heartbeat.

### 3. Wire processor output → broadcast
```python
async def on_trade_processed(classified, stats):
    if classified:
        await ws_manager.broadcast_to_group(classified.symbol, {
            "type": "trade",
            "data": {
                "symbol": classified.symbol,
                "price": classified.price,
                "volume": classified.volume,
                "tradeType": classified.trade_type.value,
                "muaTotal": stats.mua_chu_dong_volume,
                "banTotal": stats.ban_chu_dong_volume,
                "timestamp": classified.timestamp.isoformat(),
            }
        })

async def on_foreign_updated(data: ForeignInvestorData):
    await ws_manager.broadcast_to_group(data.symbol, {
        "type": "foreign",
        "data": data.model_dump(mode="json"),
    })

async def on_index_updated(data: IndexData):
    await ws_manager.broadcast_to_all({
        "type": "index",
        "data": data.model_dump(mode="json"),
    })

async def on_basis_updated(bp: BasisPoint):
    await ws_manager.broadcast_to_all({
        "type": "derivatives",
        "data": bp.model_dump(mode="json"),
    })
```

### 4. REST endpoints (`routers/market_router.py`)
```python
@router.get("/api/vn30-components")
@router.get("/api/session-stats")
@router.get("/api/session-stats/{symbol}")
@router.get("/api/foreign")
@router.get("/api/foreign/{symbol}")
@router.get("/api/indices")
@router.get("/api/derivatives/basis")
```

### 5. Broadcast throttling
Batch messages per symbol every 100ms to avoid overwhelming clients during high-frequency trading.

## Todo List
- [ ] Implement ConnectionManager with group + broadcast_to_all
- [ ] Implement MarketHandler with subscribe/unsubscribe/snapshot
- [ ] Wire processor outputs to broadcast functions
- [ ] Add heartbeat (30s ping)
- [ ] Add REST endpoints for stats/foreign/indices/basis
- [ ] Add broadcast throttling (100ms batch)
- [ ] Test with wscat: connect → subscribe → receive snapshot
- [ ] Test trade broadcast to correct group only
- [ ] Test index/derivatives broadcast to all clients

## Success Criteria
- Client connects, subscribes, receives snapshot immediately
- Live trades broadcast only to subscribers of that symbol
- Index/derivatives updates broadcast to ALL connected clients
- Dead connections cleaned up within 30s
- REST endpoints return current state

## Risk Assessment
- **Broadcast bottleneck:** Use asyncio.gather for parallel sends
- **Large snapshot:** Limit to subscribed symbols only (not full VN30)
- **Message ordering:** Include timestamp, client-side ordering

## Next Steps
- Phase 05: Frontend Dashboard
