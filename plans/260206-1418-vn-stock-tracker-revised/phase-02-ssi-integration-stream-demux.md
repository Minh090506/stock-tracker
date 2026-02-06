# Phase 02: SSI Integration & Stream Demux

## Context Links
- [Plan Overview](./plan.md)
- [SSI WS Data Format](../reports/researcher-260206-1423-ssi-fastconnect-websocket-data-format.md)
- [Phase 01: Project Scaffolding](./phase-01-project-scaffolding.md)

## Overview
- **Priority:** P0
- **Status:** pending
- **Effort:** 5h
- Authenticate with SSI, connect WebSocket via ssi-fc-data, subscribe all channels (X-TRADE, X-Quote, R, MI, B), demux incoming messages by RType, fetch VN30 components list.

## Key Insights
- SSI uses SignalR Hub (`FcMarketDataV2Hub`) NOT raw WebSocket
- Library: `ssi-fc-data` provides `MarketDataStream` class
- Channel format: `{ChannelType}:{Symbol}` (e.g., `X:VNM`, `R:ALL`, `MI:VN30`)
- **NOT** `HOSE.VNM` (old plan was WRONG)
- `MarketDataStream.start()` may be blocking - MUST test and handle
- RType discriminator: `"Trade"`, `"Quote"`, `"R"`, `"MI"`, `"B"`, `"F"`
- Derivative futures naming: `VN30F{YYMM}` (e.g., `VN30F2602`)

## Requirements

### Functional
- Authenticate with SSI API on server startup (JWT token)
- Fetch VN30 component stocks via IndexComponents API
- Connect SSI WebSocket and subscribe to:
  - `X-TRADE:ALL` - trade events for all stocks
  - `X-Quote:ALL` - quote/order book updates
  - `R:ALL` - foreign investor data
  - `MI:VN30` - VN30 index
  - `MI:VNINDEX` - VNINDEX
  - `X:VN30F{YYMM}` - current month futures
  - `B:ALL` - OHLC bars
- Demux messages by RType and dispatch to appropriate handlers
- Auto-reconnect on disconnect with exponential backoff

### Non-Functional
- <100ms from SSI message to parsed model
- Token refresh before expiry
- Graceful shutdown (close SSI WS on app shutdown)

## Architecture
```
App Startup
    ├─ SSIAuthService.authenticate() → JWT token
    ├─ SSIMarketService.fetch_vn30_components() → symbol list
    └─ SSIStreamService.connect()
           ├─ subscribe(channels)
           ├─ on_message → demux by RType:
           │     "Trade" → trade_callbacks
           │     "Quote" → quote_callbacks
           │     "R"     → foreign_callbacks
           │     "MI"    → index_callbacks
           │     "B"     → bar_callbacks
           └─ on_error → log + reconnect
```

## Related Code Files
- `~/projects/stock-tracker/backend/app/services/ssi_auth_service.py` - Auth + token
- `~/projects/stock-tracker/backend/app/services/ssi_market_service.py` - REST (IndexComponents, Securities)
- `~/projects/stock-tracker/backend/app/services/ssi_stream_service.py` - WS stream + demux
- `~/projects/stock-tracker/backend/app/models/schemas.py` - Pydantic models per message type
- `~/projects/stock-tracker/backend/app/main.py` - Lifespan events

## Implementation Steps

### 1. Create Pydantic models (`models/schemas.py`)
```python
from pydantic import BaseModel
from datetime import datetime
from enum import Enum

# --- SSI Incoming Message Models ---

class SSITradeMessage(BaseModel):
    """Channel X, RType='Trade' - per-trade event"""
    symbol: str              # "VNM", "VN30F2602"
    exchange: str            # "HOSE", "HNX", "DER"
    last_price: float        # LastPrice - trade price
    last_vol: int            # LastVol - PER-TRADE volume (NOT cumulative!)
    total_vol: int           # TotalVol - cumulative session volume
    total_val: float         # TotalVal - cumulative session value
    change: float            # vs RefPrice
    ratio_change: float      # % change
    trading_session: str     # ATO, LO, ATC, PT, C, BREAK, H

class SSIQuoteMessage(BaseModel):
    """Channel X, RType='Quote' - order book snapshot"""
    symbol: str
    exchange: str
    ceiling: float
    floor: float
    ref_price: float
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    bid_price_1: float = 0.0
    bid_vol_1: int = 0
    ask_price_1: float = 0.0
    ask_vol_1: int = 0
    # Levels 2-10 as needed

class SSIForeignMessage(BaseModel):
    """Channel R - foreign investor cumulative data"""
    symbol: str
    f_buy_vol: int = 0       # FBuyVol - CUMULATIVE from market open
    f_sell_vol: int = 0      # FSellVol - CUMULATIVE
    f_buy_val: float = 0.0   # FBuyVal - CUMULATIVE
    f_sell_val: float = 0.0  # FSellVal - CUMULATIVE
    total_room: int = 0
    current_room: int = 0

class SSIIndexMessage(BaseModel):
    """Channel MI - index values"""
    index_id: str            # "VN30", "VNINDEX"
    index_value: float
    prior_index_value: float
    change: float
    ratio_change: float
    total_qtty: int = 0
    advances: int = 0
    declines: int = 0
    no_changes: int = 0

class SSIBarMessage(BaseModel):
    """Channel B - OHLC bar"""
    symbol: str
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: int

# --- App Domain Models (Phase 3) ---

class TradeType(str, Enum):
    MUA_CHU_DONG = "mua_chu_dong"
    BAN_CHU_DONG = "ban_chu_dong"
    NEUTRAL = "neutral"

class ClassifiedTrade(BaseModel):
    symbol: str
    price: float
    volume: int              # PER-TRADE from LastVol
    value: float
    trade_type: TradeType
    bid_price: float
    ask_price: float
    timestamp: datetime

class SessionStats(BaseModel):
    symbol: str
    mua_chu_dong_volume: int = 0
    mua_chu_dong_value: float = 0.0
    ban_chu_dong_volume: int = 0
    ban_chu_dong_value: float = 0.0
    neutral_volume: int = 0
    total_volume: int = 0
    last_updated: datetime | None = None

class ForeignInvestorData(BaseModel):
    symbol: str
    buy_volume: int = 0
    sell_volume: int = 0
    net_volume: int = 0
    buy_value: float = 0.0
    sell_value: float = 0.0
    net_value: float = 0.0
    total_room: int = 0
    current_room: int = 0
    buy_speed_per_min: float = 0.0
    sell_speed_per_min: float = 0.0
    last_updated: datetime | None = None

class IndexData(BaseModel):
    index_id: str
    value: float
    prior_value: float
    change: float
    ratio_change: float
    total_volume: int = 0
    advances: int = 0
    declines: int = 0
    last_updated: datetime | None = None

class BasisPoint(BaseModel):
    timestamp: datetime
    futures_symbol: str
    futures_price: float
    spot_value: float
    basis: float
    is_premium: bool
```

### 2. Create SSI auth service (`services/ssi_auth_service.py`)
- Use `ssi_fc_data.MarketDataClient` for token
- Config from `app.config.settings`
- Store token for stream auth

### 3. Create SSI market service (`services/ssi_market_service.py`)
- `fetch_vn30_components()` via IndexComponents API
- Returns list of VN30 stock symbols
- Called at startup to determine default watchlist

### 4. Create SSI stream service (`services/ssi_stream_service.py`)
**CRITICAL: Message demux logic**
```python
from typing import Callable, Awaitable
import json, asyncio, logging

logger = logging.getLogger(__name__)

class SSIStreamService:
    def __init__(self, auth_service):
        self._auth = auth_service
        self._stream = None
        self._trade_callbacks: list[Callable] = []
        self._quote_callbacks: list[Callable] = []
        self._foreign_callbacks: list[Callable] = []
        self._index_callbacks: list[Callable] = []
        self._bar_callbacks: list[Callable] = []
        self._background_tasks: set[asyncio.Task] = set()  # prevent GC of tasks

    def on_trade(self, cb): self._trade_callbacks.append(cb)
    def on_quote(self, cb): self._quote_callbacks.append(cb)
    def on_foreign(self, cb): self._foreign_callbacks.append(cb)
    def on_index(self, cb): self._index_callbacks.append(cb)
    def on_bar(self, cb): self._bar_callbacks.append(cb)

    def _dispatch(self, cb, msg):
        """Create tracked async task with error logging."""
        task = asyncio.create_task(cb(msg))
        self._background_tasks.add(task)
        task.add_done_callback(self._task_done)

    def _task_done(self, task: asyncio.Task):
        """Remove task ref + log exceptions."""
        self._background_tasks.discard(task)
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            logger.error(f"Callback error: {exc}", exc_info=exc)

    def _handle_message(self, raw):
        """Demux SSI message by RType field."""
        data = json.loads(raw) if isinstance(raw, str) else raw
        content = data.get("Content", data.get("content", data))
        rtype = content.get("RType", "")

        if rtype == "Trade":
            msg = SSITradeMessage(**self._normalize_fields(content))
            for cb in self._trade_callbacks:
                self._dispatch(cb, msg)
        elif rtype == "Quote":
            msg = SSIQuoteMessage(**self._normalize_fields(content))
            for cb in self._quote_callbacks:
                self._dispatch(cb, msg)
        elif rtype == "R":
            msg = SSIForeignMessage(**self._normalize_fields(content))
            for cb in self._foreign_callbacks:
                self._dispatch(cb, msg)
        elif rtype == "MI":
            msg = SSIIndexMessage(**self._normalize_fields(content))
            for cb in self._index_callbacks:
                self._dispatch(cb, msg)
        elif rtype == "B":
            msg = SSIBarMessage(**self._normalize_fields(content))
            for cb in self._bar_callbacks:
                self._dispatch(cb, msg)

    def _normalize_fields(self, content: dict) -> dict:
        """Convert SSI PascalCase fields to snake_case. Only mapped fields pass through."""
        mapping = {
            "Symbol": "symbol", "Exchange": "exchange",
            "LastPrice": "last_price", "LastVol": "last_vol",
            "TotalVol": "total_vol", "TotalVal": "total_val",
            "Change": "change", "RatioChange": "ratio_change",
            "TradingSession": "trading_session",
            "Ceiling": "ceiling", "Floor": "floor", "RefPrice": "ref_price",
            "Open": "open", "High": "high", "Low": "low",
            "BidPrice1": "bid_price_1", "BidVol1": "bid_vol_1",
            "AskPrice1": "ask_price_1", "AskVol1": "ask_vol_1",
            "FBuyVol": "f_buy_vol", "FSellVol": "f_sell_vol",
            "FBuyVal": "f_buy_val", "FSellVal": "f_sell_val",
            "TotalRoom": "total_room", "CurrentRoom": "current_room",
            "IndexId": "index_id", "IndexValue": "index_value",
            "PriorIndexValue": "prior_index_value",
            "TotalQtty": "total_qtty", "Advances": "advances",
            "Declines": "declines", "NoChanges": "no_changes",
            "Time": "time", "Volume": "volume", "Close": "close",
        }
        return {mapping[k]: v for k, v in content.items() if k in mapping}
```

### 5. Resolve VN30F contracts (current + next month)
```python
from datetime import datetime, timedelta
from calendar import monthrange

def get_futures_symbols() -> list[str]:
    """Return BOTH current month and next month VN30F contract symbols.

    Near expiry (last Thursday of month), next month becomes the active
    contract. Subscribe to both to avoid missing data during rollover.
    """
    now = datetime.now()
    current = f"VN30F{now.strftime('%y%m')}"

    # Next month
    if now.month == 12:
        next_dt = now.replace(year=now.year + 1, month=1, day=1)
    else:
        next_dt = now.replace(month=now.month + 1, day=1)
    next_month = f"VN30F{next_dt.strftime('%y%m')}"

    return [current, next_month]

def get_primary_futures_symbol() -> str:
    """Return the most active contract. During rollover week (last Thursday
    of month onward), prefer next month's contract."""
    now = datetime.now()
    # Find last Thursday of current month
    last_day = monthrange(now.year, now.month)[1]
    last_date = now.replace(day=last_day)
    # Walk back to Thursday (weekday=3)
    offset = (last_date.weekday() - 3) % 7
    last_thursday = last_date - timedelta(days=offset)

    symbols = get_futures_symbols()
    if now.date() >= last_thursday.date():
        return symbols[1]  # next month is primary after rollover
    return symbols[0]  # current month is primary
```

### 6. Wire into main.py lifespan
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auth
    await auth_service.authenticate()
    # Fetch VN30 components
    vn30_symbols = await market_service.fetch_vn30_components()
    # Subscribe channels - BOTH current + next month futures
    futures_symbols = get_futures_symbols()
    channels = [
        "X-TRADE:ALL", "X-Quote:ALL", "R:ALL",
        "MI:VN30", "MI:VNINDEX",
        *[f"X:{fs}" for fs in futures_symbols],  # both months
        "B:ALL",
    ]
    await stream_service.connect(channels)
    yield
    await stream_service.disconnect()
```

### 7. SSI SignalR connection via asyncio.to_thread (DEFAULT)
```python
# SignalR hub.start() is BLOCKING by design (runs its own event loop).
# ALWAYS run in a thread to avoid freezing the async event loop.
import asyncio

async def connect(self, channels: list[str]):
    """Connect SSI stream in background thread. This is the DEFAULT
    approach, not a fallback — SignalR start() blocks the calling thread."""
    channel_string = ",".join(channels)
    self._stream_task = asyncio.create_task(
        asyncio.to_thread(
            self._stream.start,
            self._handle_message,
            self._handle_error,
            channel_string,
        )
    )
```

### 8. Add REST endpoint for VN30 list
```python
@app.get("/api/vn30-components")
async def get_vn30():
    return vn30_symbols  # Cached from startup
```

## Todo List
- [ ] Create all Pydantic models (SSI messages + domain models)
- [ ] Implement SSI auth service with ssi-fc-data
- [ ] Implement SSI market service (IndexComponents for VN30)
- [ ] Implement SSI stream service with demux by RType
- [ ] Implement field normalization (PascalCase → snake_case)
- [ ] Add futures contract symbol resolution (BOTH current + next month)
- [ ] Wire lifespan events (auth → fetch VN30 → connect stream)
- [ ] Verify asyncio.to_thread() works with MarketDataStream.start()
- [ ] Test: auth succeeds and logs confirm
- [ ] Test: stream receives messages (log raw content)
- [ ] Test: demux routes Trade/Quote/R/MI/B correctly
- [ ] Add /api/vn30-components endpoint

## Success Criteria
- Server authenticates with SSI on startup
- Stream connects and receives raw messages (visible in logs)
- Trade messages (RType="Trade") demuxed to trade callbacks
- Quote messages (RType="Quote") demuxed to quote callbacks
- Foreign messages (RType="R") demuxed to foreign callbacks
- Index messages (RType="MI") demuxed to index callbacks
- `/api/vn30-components` returns VN30 stock list

## Risk Assessment
- **MarketDataStream.start() blocking:** MITIGATED. Using `asyncio.to_thread()` as default. If ssi-fc-data has other async issues, may need raw SignalR client.
- **Channel subscription format:** Verify `X-TRADE:ALL` vs `X:ALL` behavior. May need to use `X:ALL` and filter by RType.
- **Field names vary by channel:** PascalCase mapping filters only known fields. Log unmapped keys at DEBUG level to discover missing fields.
- **Token expiry unknown:** Implement periodic re-auth (every 30 min as safety).
- **VN30F rollover:** MITIGATED. Subscribe both current + next month contracts. Primary switches after last Thursday of month.

## Security Considerations
- SSI credentials only in `.env`, loaded via pydantic-settings
- JWT token in-memory only, never logged
- No credentials exposed to frontend

## Next Steps
- Phase 03: Build QuoteCache, TradeClassifier, ForeignTracker, IndexTracker, DerivativesTracker
