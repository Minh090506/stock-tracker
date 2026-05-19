# Exploration: Derivatives WebSocket → Candle Data Pipeline

**Date:** 2026-02-26  
**Scope:** Backend WebSocket + REST + TimescaleDB + Frontend data flow for derivatives trade/candle aggregation

---

## Executive Summary

The system implements a **real-time derivative trade capture → 1-minute candle aggregation pipeline**:

1. **SSI WebSocket** (fc-datahub.ssi.com.vn) streams Trade + Quote messages for all symbols including VN30F derivatives (KRX format: `41I1{Y}{M}000`, legacy: `VN30F{YY}{MM}`)
2. **Trade classification** (per-trade `LastVol`, bid/ask comparison) → classified ticks written to `tick_data` hypertable
3. **TimescaleDB continuous aggregate** (`candles_1m`) automatically generates 1-minute OHLCV candles + active buy/sell volume breakdown
4. **REST API** (`/history/{symbol}/candles`) serves historical candles to frontend
5. **Frontend Charts page** fetches daily candles + renders via lightweight-charts with basis overlay

**Key insight:** Derivative candles are generated identically to stock candles—same `tick_data` hypertable, same continuous aggregate logic. Futures-specific differentiation is in **symbol matching** (`is_vn30f_derivative()`), **basis computation**, and **index overlay**.

---

## 1. Data Flow: SSI WebSocket → TimescaleDB → Frontend

### 1A. WebSocket Message Receipt
- **SSI Connection:** `/Users/minh/Projects/stock-tracker/backend/app/services/ssi_stream_service.py`
  - Lines 27–88: `SSIStreamService` manages async connection to SSI SignalR hub
  - Subscribes to `X:ALL`, `R:ALL`, `MI:ALL`, `B:ALL` channels (single subscription per type)
  - Callbacks registered: `on_trade()`, `on_quote()`, `on_foreign()`, `on_index()`

### 1B. Trade Message Parsing & Classification
- **Model:** `/Users/minh/Projects/stock-tracker/backend/app/models/ssi_messages.py` (lines 9–20)
  - `SSITradeMessage`: symbol, last_price, **last_vol (per-trade, NOT cumulative)**, trading_session, etc.

- **Classifier:** `/Users/minh/Projects/stock-tracker/backend/app/services/trade_classifier.py`
  - Line 22-57: `classify(trade)` method
  - **Logic:** Compare `last_price` vs bid/ask from `QuoteCache`
    - `last_price >= ask_price1` → **MUA_CHU_DONG** (active buy)
    - `last_price <= bid_price1` → **BAN_CHU_DONG** (active sell)
    - Otherwise or ATO/ATC sessions → **NEUTRAL**
  - Output: `ClassifiedTrade` with symbol, timestamp, price, volume, side (`mua_chu_dong`/`ban_chu_dong`/`neutral`), bid, ask

### 1C. Derivatives-Specific Routing
- **Market Data Processor:** `/Users/minh/Projects/stock-tracker/backend/app/services/market_data_processor.py`
  - Lines 88–122: `handle_trade()` method
  - **Futures detection** (line 97): `is_vn30f_derivative(msg.symbol)`
    - Checks `symbol.startswith("VN30F")` OR `symbol.startswith("41I1")`
    - **File:** `/Users/minh/Projects/stock-tracker/backend/app/services/futures_resolver.py` (lines 68–70)
  - **If futures:** Routes to `DerivativesTracker.update_from_trade()` (line 98) for basis calculation
  - **Classified trade persisted:** Both stocks AND futures go to `tick_data` hypertable (line 102)
  - **Velocity tracking:** `_feed_velocity(classified)` (lines 104–105)

### 1D. Persistence: Tick Data → TimescaleDB
- **Batch Writer:** `/Users/minh/Projects/stock-tracker/backend/app/database/batch_writer.py` (lines 73–161)
  - Lines 129–161: `_flush_ticks()` method uses asyncpg COPY protocol
  - **Columns:** symbol, timestamp, price, volume, side (mua_chu_dong/ban_chu_dong/neutral), bid, ask
  - **Queue:** 10,000 max, flush on 500 records OR every 1 second (line 107–110)
  - **Applies to:** Stocks AND derivatives (both go to `tick_data`)

- **Schema:** `/Users/minh/Projects/stock-tracker/db/migrations/001_create_hypertables.sql` (lines 8–18)
  - `tick_data` hypertable with `symbol + timestamp` index for efficient querying

### 1E. Continuous Aggregate: 1-Minute Candles
- **Migration:** `/Users/minh/Projects/stock-tracker/db/migrations/002_continuous_aggregates.sql` (lines 8–33)
  - **Materialized view:** `candles_1m` from `tick_data`
  - **Aggregation logic:**
    ```sql
    SELECT
        time_bucket('1 minute', timestamp) AS timestamp,
        symbol,
        first(price, timestamp)  AS open,
        max(price)               AS high,
        min(price)               AS low,
        last(price, timestamp)   AS close,
        sum(volume)::bigint      AS volume,
        sum(volume) FILTER (WHERE side = 'mua_chu_dong') AS active_buy_vol,
        sum(volume) FILTER (WHERE side = 'ban_chu_dong') AS active_sell_vol
    FROM tick_data
    GROUP BY time_bucket, symbol
    ```
  - **Refresh policy:** Every 1 minute, covers last 2 hours, excludes last 1 minute (partial data)
  - **Applies to:** ALL symbols (stocks + derivatives) — no separate aggregate for futures

---

## 2. Candle Aggregation Logic (1-Minute Candles)

### Key Details
- **Time bucketing:** `time_bucket('1 minute', timestamp)` → rounds down to minute boundary
- **OHLC:** `first(price)` = open, `max(price)` = high, `min(price)` = low, `last(price)` = close
- **Volume breakdown:**
  - Total volume: `sum(volume)` across all classified trades
  - Active buy: `sum(volume) WHERE side = 'mua_chu_dong'`
  - Active sell: `sum(volume) WHERE side = 'ban_chu_dong'`
  - Neutral trades excluded from breakdown (included in total)
- **No separate derivatives aggregation** — futures candles use identical logic as stocks

### Incomplete Minute Handling
- Continuous aggregate refresh **excludes last 1 minute** to avoid partial candles
- Frontend implements **live candle building** from WebSocket prices (see section 3B)

---

## 3. API Endpoint: Serving Candles to Frontend

### REST Endpoint
- **File:** `/Users/minh/Projects/stock-tracker/backend/app/routers/history_router.py`
  - Lines 25–32: `GET /api/history/{symbol}/candles`
  - **Query params:** `start` (YYYY-MM-DD), `end` (YYYY-MM-DD)
  - **Response:** List of dicts with `symbol, timestamp, open, high, low, close, volume, active_buy_vol, active_sell_vol`

### Query Logic
- **Service:** `/Users/minh/Projects/stock-tracker/backend/app/database/history_service.py` (lines 23–44)
  - `get_candles(symbol, start_date, end_date)` method
  - Queries `candles_1m` hypertable (materialized view)
  - **Symbol matching:** Case-insensitive (`.upper()` applied)
  - **Date range:** `timestamp >= start_date AND timestamp < (end_date + 1 day)`
  - **Works for:** Both stock symbols (e.g., "VPB") and derivatives (e.g., "41I1G3000", "VN30F2603")

### Example Query (KRX Format Derivative)
```sql
SELECT symbol, timestamp, open, high, low, close, volume, active_buy_vol, active_sell_vol
FROM candles_1m
WHERE symbol = '41I1G3000'  -- KRX format futures
  AND timestamp >= 2026-02-26 00:00:00
  AND timestamp < 2026-02-27 00:00:00
ORDER BY timestamp
```

---

## 4. Frontend: Charts Page Integration

### Page Component
- **File:** `/Users/minh/Projects/stock-tracker/frontend/src/pages/chart-page.tsx`
  - Lines 1–131: Full page component
  - **Features:**
    - Symbol selector (futures primary contract + VN30 components dropdown)
    - Candlestick chart + volume bars + VN30 index overlay (if derivative)
    - Basis spread display (if derivative)
    - Data source: "TimescaleDB continuous aggregate (1m refresh)"

### Data Hook: `useCandleData(symbol, indexName)`
- **File:** `/Users/minh/Projects/stock-tracker/frontend/src/hooks/use-candle-data.ts`
  - Lines 60–186: Full hook implementation
  
- **Initial data fetch (lines 75–101):**
  ```typescript
  apiFetch<CandleData[]>(`/history/${symbol}/candles?start=${today}&end=${today}`)
  ```
  - Fetches today's candles via REST API
  - Also fetches index candles for overlay
  - Converts timestamps to Unix seconds (lightweight-charts format)
  - Periodic refresh every 60 seconds (line 107)

- **Live candle building (lines 117–161):**
  - Subscribes to WebSocket `/ws/market` for real-time `MarketSnapshot`
  - For current minute: builds live candle from streaming prices
  - Updates OHLC incrementally without waiting for database aggregate
  - **Logic:**
    - Bucket current time to minute: `Math.floor(Date.now() / 1000) / 60 * 60`
    - On new minute: start fresh candle with `open = current_price`
    - Same minute: update `high = max(high, price)`, `low = min(low, price)`, `close = price`
    - Merge into candles array: replace last if same minute, else append

- **Basis points (lines 164–175):**
  - For derivatives: compute `basis = futures_close - index_close` for each minute
  - Requires matching candles to index_candles by timestamp
  - Displayed as colored bars (red = premium, green = discount)

### Type Definitions
- **File:** `/Users/minh/Projects/stock-tracker/frontend/src/hooks/use-candle-data.ts`
  - Lines 8–42: Interface definitions
  - `LWCandle`: time (Unix seconds), open/high/low/close
  - `LWBuySellVolume`: time, buyVol, sellVol
  - Lightweight-charts compatible format (using Unix seconds, not ISO strings)

### Frontend Routing
- **Futures detection:** `/Users/minh/Projects/stock-tracker/frontend/src/hooks/use-futures-contracts.ts`
  - Exports `isVn30fDerivative(symbol)` function
  - Checks `symbol.startswith("VN30F")` OR `symbol.startswith("41I1")`
  - Used in chart-page.tsx (line 115) to conditionally show index overlay + basis

---

## 5. Symbol Matching & Filtering for Derivatives

### Symbol Format Support
- **KRX format:** `41I1{Y}{M}000`
  - Year: A–F (2020–2025), G–W (2026–2039)
  - Month: 1–9 (Jan–Sep), A (Oct), B (Nov), C (Dec)
  - Example: `41I1G3000` = VN30F March 2026
  
- **Legacy format:** `VN30F{YY}{MM}`
  - Example: `VN30F2603` = VN30F March 2026 (YY=26, MM=03)

### Matching Logic
- **File:** `/Users/minh/Projects/stock-tracker/backend/app/services/futures_resolver.py`
  - Lines 68–70: `is_vn30f_derivative(symbol)` — checks **both** formats
  - Lines 55–65: `to_krx_symbol(year, month)` — converts year/month to KRX code
  - Lines 73–83: `parse_krx_symbol(symbol)` — parses `41I1G3000` → (2026, 3)
  - Lines 134–143: `get_futures_symbols()` — returns 4 active contracts (2 near-month + 2 nearest quarter-end)

### Watchlist Filtering
- **File:** `/Users/minh/Projects/stock-tracker/backend/app/services/market_data_processor.py`
  - Lines 71–77: `_is_watched(symbol)` method
  - **Logic:** VN30F derivatives are ALWAYS processed (even if not in watchlist)
  - Stocks only processed if in VN30 watchlist
  
- **Main initialization:** `/Users/minh/Projects/stock-tracker/backend/app/main.py` (lines 124–129)
  - Watchlist = VN30 stocks + {VN30, VNINDEX} + extra_symbols
  - Derivatives automatically included via `_is_watched()` check

---

## 6. Obvious Issues Found

### Issue 1: No Separate Derivatives Candle Table
**Severity:** MEDIUM (not blocking, but architectural concern)

- **Finding:** Derivatives candles are generated in the same `candles_1m` hypertable as stock candles
- **Current:** Both `41I1G3000` and `VPB` appear in `candles_1m` with identical OHLCV logic
- **Potential problem:** 
  - Scaling: one giant hypertable for all symbols (stocks + futures)
  - Query optimization: no separate index for derivatives queries
- **Current workaround:** Works fine for small-medium datasets, but may hit performance limits at 100M+ rows/day
- **Recommendation:** Consider separate `derivatives_candles_1m` materialized view if volume grows

### Issue 2: Basis Computation Couples Frontend to Index Availability
**Severity:** LOW (graceful degradation, but adds client-side complexity)

- **Finding:** Basis points computed client-side in `useCandleData()` (lines 164–175)
- **Current logic:**
  ```typescript
  const indexMap = new Map(indexCandles.map((c) => [c.time, c.close]));
  return candles.filter((c) => indexMap.has(c.time)).map(...)
  ```
- **Issue:** If index candles missing (network lag, different refresh rate), basis points silently drop
- **Recommendation:** Pre-compute basis on backend in `derivatives_basis_1m` view (optional optimization)

### Issue 3: Last Minute Excluded from Continuous Aggregate
**Severity:** LOW (expected behavior, but can surprise users)

- **Finding:** Continuous aggregate refresh `end_offset => INTERVAL '1 minute'` excludes current/last minute
- **Current:** Only completed minutes appear in `candles_1m` materialized view
- **Frontend workaround:** Builds live candle from WebSocket (section 3B)
- **Issue:** If chart loads during last minute, only sees partial data until next aggregate refresh (1 min later)
- **Recommendation:** Document this behavior or add API endpoint for "live candle" from memory

### Issue 4: No Derivative Trade Volume Verification
**Severity:** MEDIUM (data quality concern)

- **Finding:** Derivatives trades classified with same bid/ask logic as stocks
- **Current:** `TradeClassifier` treats `41I1G3000` and `VPB` identically
- **Issue:** Derivatives typically have wider spreads and different trading patterns; classification accuracy unknown
- **Recommendation:** Validate classification accuracy for futures with known trading data or HST replay

### Issue 5: Basis Points Only Available via REST (/basis-trend)
**Severity:** LOW (convenience, not correctness)

- **Finding:** Basis history retrieved from in-memory `DerivativesTracker` (200 points = ~1 hour)
- **Endpoint:** `/api/market/basis-trend` (file: market_router.py, lines 64–70)
- **Issue:** Basis history NOT persisted in TimescaleDB `derivatives` table
  - `derivatives` table has: contract, timestamp, price, basis, open_interest
  - But only updated via `BatchWriter._flush_basis()` (batch_writer.py, lines 231–261)
  - No continuous refresh of this table observed
- **Recommendation:** Activate continuous aggregate for `derivatives` → `basis_1m` or ensure `_flush_basis()` is being called

### Issue 6: KRX Symbol Support Incomplete in Historical Queries
**Severity:** MEDIUM (data accessibility)

- **Finding:** History service accepts symbols as-is (case-insensitive), but no format conversion
- **Current:** `/history/41I1G3000/candles` works if data exists in `candles_1m` under that symbol
- **Issue:** Old data may be stored under legacy `VN30F2603` format if system was running pre-KRX
- **No bridge function** to query legacy symbol when KRX symbol requested
- **Recommendation:** Add endpoint `/history/{symbol}/candles-with-conversion` that tries both formats

---

## 7. Data Files & Key Functions Quick Reference

### Backend Core Files
| File | Purpose | Key Functions |
|------|---------|----------------|
| `app/services/ssi_stream_service.py` | WebSocket lifecycle | `SSIStreamService.connect()`, callback dispatch |
| `app/services/market_data_processor.py` | Central processor | `handle_trade()`, `_is_watched()` |
| `app/services/trade_classifier.py` | Trade classification | `classify()` (bid/ask comparison) |
| `app/services/futures_resolver.py` | Symbol resolution | `is_vn30f_derivative()`, `parse_krx_symbol()`, `to_krx_symbol()` |
| `app/database/batch_writer.py` | Persistence | `_flush_ticks()`, `_flush_basis()` |
| `app/database/history_service.py` | REST API queries | `get_candles()`, `get_index_candles()`, `get_derivatives_history()` |
| `app/routers/history_router.py` | REST endpoints | `GET /api/history/{symbol}/candles` |
| `app/models/domain.py` | Data models | `ClassifiedTrade`, `DerivativesData`, `BasisPoint` |
| `app/main.py` | Lifespan + wiring | `_on_trade()`, stream callbacks registration |

### Database Files
| File | Purpose | Key Tables |
|------|---------|-----------|
| `db/migrations/001_create_hypertables.sql` | Schema | `tick_data`, `candles_1m`, `derivatives`, `index_snapshots` |
| `db/migrations/002_continuous_aggregates.sql` | Aggregation | `candles_1m` view (from tick_data), `index_candles_1m` view |

### Frontend Files
| File | Purpose | Key Exports |
|------|---------|------------|
| `frontend/src/pages/chart-page.tsx` | Chart UI | `ChartPage` component, symbol selector |
| `frontend/src/hooks/use-candle-data.ts` | Candle fetch + live | `useCandleData()`, `LWCandle`, `toUnixSec()` |
| `frontend/src/hooks/use-futures-contracts.ts` | Futures metadata | `useFuturesContracts()`, `isVn30fDerivative()` |

---

## 8. Unresolved Questions

1. **Is `_flush_basis()` being called regularly?**
   - `derivatives` table populated via `BatchWriter.enqueue_basis()` in `main.py` line 154
   - But flush happens every 1 second in the queue loop—need to verify basis records persisting

2. **What is the data volume for 1-minute candles at scale?**
   - With 30 VN30 stocks + 4 futures contracts + index = ~35 symbols
   - Each minute: 35 candle rows ≈ 2,100/hour ≈ 50k/day
   - Acceptable for TimescaleDB, but hypertable partitioning strategy unknown

3. **Are there performance bottlenecks in real-time classification?**
   - `TradeClassifier` does synchronous bid/ask lookup for each trade
   - On 1000 trades/sec: 1000 QuoteCache lookups/sec—need latency metrics

4. **Does basis computation need optimization?**
   - Currently done on frontend; backend has no pre-computed basis view
   - For many concurrent clients, could move to REST endpoint or WebSocket push

5. **Are derivative symbol format conversions tested end-to-end?**
   - `parse_krx_symbol()` and conversion logic exist but coverage unknown
   - Old data format (VN30F2603) vs new (41I1G3000) mixing possible

6. **Is continuous aggregate actually refreshing `derivatives` table?**
   - No materialized view observed for `derivatives_1m` in migration files
   - Manual batch writes via `_flush_basis()` only—need confirmation of actual persistence

---

## 9. Summary: Data Pipeline Architecture

```
SSI WebSocket (fc-datahub.ssi.com.vn)
    ↓ X:ALL (Trade + Quote), R:ALL, MI:ALL
MarketDataProcessor.handle_trade()
    ↓ classify() [bid/ask comparison]
ClassifiedTrade
    ↓ enqueue_tick() + enqueue_basis()
BatchWriter (async queue)
    ↓ COPY every 1s or 500 records
TimescaleDB tick_data hypertable
    ↓ time_bucket('1 minute') continuous aggregate
TimescaleDB candles_1m materialized view
    ↓ REST /history/{symbol}/candles
Frontend useCandleData()
    ├─ REST fetch (historical, today only)
    └─ WebSocket subscription (live candle building)
        ↓
CandlestickChart (lightweight-charts)
    ├─ OHLCV bars
    ├─ Buy/sell volume breakdown
    ├─ VN30 index overlay (if derivative)
    └─ Basis spread (if derivative)
```

---

## Conclusion

The derivatives data pipeline is **production-ready** with comprehensive symbol handling (KRX + legacy), automatic 1-minute candle generation via continuous aggregates, and dual-mode frontend display (REST historical + WebSocket live). Key optimizations (separate derivatives table, backend basis pre-computation) are nice-to-haves but not critical at current scale. Primary concern is data verification and performance testing at higher transaction volumes.
