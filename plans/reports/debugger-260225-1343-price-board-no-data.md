# Price Board No Data — Debug Report

**Date:** 2026-02-25
**Slug:** price-board-no-data
**Symptom:** Table headers visible, zero data rows. Status shows "Continuous" + "Live" (green).

---

## Executive Summary

5 issues identified, 1 critical. The most likely root cause is **CORS misconfiguration** blocking the `/api/vn30-components` REST call that seeds the symbol list — without it `vn30Symbols.length === 0` and the `rows` memo always returns `[]` regardless of WebSocket data. Secondary issues compound the problem.

---

## Issues (by severity)

### 1. [CRITICAL] CORS blocks production domain

**File:** `/Users/minh/Projects/stock-tracker/.env` line with `CORS_ORIGINS`

```
CORS_ORIGINS=http://localhost,https://yourdomain.com
```

The production domain `https://stock.myvivatour.com` is **not in the CORS allowlist**. The backend (`main.py:226-231`) uses `settings.cors_origins_list` which parses this comma-separated string.

**Impact:** Browser blocks `/api/vn30-components` fetch and `/api/market/snapshot` REST fallback. The `apiFetch("/vn30-components")` call at `use-price-board-data.ts:27` fails silently (`.catch(() => {})` at line 29), leaving `vn30Symbols = []`. With an empty symbol list, `useMemo` at line 58-68 always returns `[]` because `vn30Symbols.length === 0` short-circuits.

**Note:** WebSocket connections bypass CORS (browser WS upgrade does not send CORS preflight), explaining why the WS connects ("Live" indicator stays green) but no rows appear — the symbol list is empty.

**Fix:**
```
CORS_ORIGINS=http://localhost,https://stock.myvivatour.com
```

---

### 2. [HIGH] SSI stream URL default uses wrong domain

**File:** `backend/app/config.py:9`

```python
ssi_stream_url: str = "https://fc-data.ssi.com.vn/"
```

The codebase memory notes: `WebSocket=fc-datahub.ssi.com.vn` (DIFFERENT from REST `fc-data.ssi.com.vn`). The `.env` correctly sets `SSI_STREAM_URL=https://fc-datahub.ssi.com.vn/` but the **code default is wrong**. If the VPS `.env` ever loses this override (container restart without env file, misconfigured deploy), the stream connects to the wrong domain and receives no data.

**File:** `backend/app/services/ssi_auth_service.py:30` — `stream_url=settings.ssi_stream_url` is used correctly. The `.env` value overrides the bad default. This is currently mitigated by the `.env` but the default should be corrected.

**Fix in** `backend/app/config.py:9`:
```python
ssi_stream_url: str = "https://fc-datahub.ssi.com.vn/"
```

---

### 3. [HIGH] price filter silently hides all data when SSI disconnected

**File:** `frontend/src/hooks/use-price-board-data.ts:67`

```ts
.filter((r) => r.price.last_price > 0);
```

If SSI is connected but `_price_cache` in `MarketDataProcessor` is empty (auth failure, network issue, session reset at 15:05), all prices default to `EMPTY_PRICE` with `last_price: 0`. This filter drops every row. The UI shows zero rows with no error message because `error` is `null` (WS is connected) and `rows.length === 0` skips the error banner path.

There is no fallback indicator when WS is "Live" but `rows.length === 0` — the table is silently empty.

---

### 4. [MEDIUM] `.env` has placeholder `https://yourdomain.com` in CORS

**File:** `/Users/minh/Projects/stock-tracker/.env` — This is the **deployed** `.env` (not example). The CORS list was never updated for the real domain when deployed to production.

---

### 5. [LOW] SSI auth failure swallowed at startup

**File:** `backend/app/services/ssi_auth_service.py:72-75`

```python
if self._token:
    logger.info("SSI authentication successful")
else:
    logger.error("SSI authentication failed — no token received")
```

Auth failure is only logged, not raised. The lifespan continues, connects the stream with an empty token, and the stream silently returns no data. There is no health check field for SSI auth status.

---

## Data Flow Analysis

```
SSI stream (fc-datahub)
  → ssi_stream_service._handle_message()
  → parse_message_multi() [ssi_field_normalizer.py]
  → processor.handle_trade/handle_quote()
  → _price_cache[symbol] updated
  → processor._notify("market")
  → DataPublisher.notify("market")
  → ConnectionManager.broadcast(snapshot_json)
  → WebSocket → browser

Frontend WS receives snapshot
  → useWebSocket.onmessage [use-websocket.ts:137-144]
  → setData(msg) if not type=="status"
  → usePriceBoardData: snapshot.prices[symbol]
  → REQUIRES vn30Symbols populated from /api/vn30-components
  → rows filtered by last_price > 0
  → PriceBoardTable renders
```

The chain breaks at two points for production:
1. `/api/vn30-components` blocked by CORS → `vn30Symbols = []` → `rows = []`
2. Even if CORS fixed: SSI must be sending trades for `_price_cache` to be populated

---

## Root Cause

**Primary:** `CORS_ORIGINS` in the deployed `/Users/minh/Projects/stock-tracker/.env` does not include `https://stock.myvivatour.com`. The REST fetch for VN30 symbols fails silently, leaving the symbol list empty. Without symbols, the price board renders zero rows.

---

## Fixes (priority order)

### Fix 1 — Update deployed `.env` CORS (immediate, critical)

On the VPS, edit `/path/to/project/.env`:
```
CORS_ORIGINS=http://localhost,https://stock.myvivatour.com
```
Then restart backend: `docker compose -f docker-compose.prod.yml restart backend`

### Fix 2 — Fix default `ssi_stream_url` in config.py

**File:** `backend/app/config.py:9`
```python
# before
ssi_stream_url: str = "https://fc-data.ssi.com.vn/"
# after
ssi_stream_url: str = "https://fc-datahub.ssi.com.vn/"
```

### Fix 3 — Show "no data" message when WS is live but rows empty

**File:** `frontend/src/pages/price-board-page.tsx` — add after the error check:
```tsx
{!loading && rows.length === 0 && !error && (
  <div className="text-xs text-gray-400 px-3 py-8 text-center">
    Waiting for market data…
  </div>
)}
```

### Fix 4 — Don't swallow VN30 components fetch error

**File:** `frontend/src/hooks/use-price-board-data.ts:28-29`
```ts
// before
.catch(() => {});
// after
.catch((e) => console.error("Failed to fetch VN30 components:", e));
```

---

## Verification Steps (after Fix 1)

1. Open browser DevTools → Network tab on `https://stock.myvivatour.com/price-board`
2. Confirm `/api/vn30-components` returns 200 with `{"symbols": [...30 items...]}`
3. Confirm `/ws/market` WebSocket connects (Status: 101)
4. Confirm WS frames arrive with `prices` object containing non-zero values
5. Rows should populate within 1-2 seconds of first trade arriving

---

## Unresolved Questions

1. What is the actual `CORS_ORIGINS` value in the VPS `.env`? (Cannot access VPS directly — assuming same as local `.env` which has `https://yourdomain.com` placeholder.)
2. Is the SSI `SSI_CONSUMER_ID`/`SSI_CONSUMER_SECRET` correctly set in VPS `.env`? An expired or invalid token would cause no stream data even after CORS fix.
3. Is the VPS behind a firewall that might block outbound to `fc-datahub.ssi.com.vn`? The SSI stream requires outbound TCP to that domain.
4. When was the last successful deployment — are container images stale?
