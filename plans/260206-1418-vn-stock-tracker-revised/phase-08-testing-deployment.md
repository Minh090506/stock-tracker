# Phase 08: Testing & Deployment

## Context Links
- [Plan Overview](./plan.md)
- All previous phases

## Overview
- **Priority:** P1
- **Status:** pending
- **Effort:** 4h
- Unit tests for critical processing logic, integration tests, Docker production build, error handling, logging.

## Requirements

### Functional
- Unit tests for trade classifier, foreign delta tracker, basis calculator, alert service
- Integration test: SSI mock message → classified trade → broadcast
- Docker production build (multi-stage for frontend, gunicorn for backend)
- Structured logging (JSON)
- Graceful error handling throughout

### Non-Functional
- >80% coverage on processing layer (services/)
- Docker images <500MB
- Health check endpoint for monitoring

## Test Priorities (by business criticality)

### 1. Trade Classification (HIGHEST)
```python
def test_mua_chu_dong():
    """Price >= ask → mua chu dong"""
    cache = QuoteCache()
    cache.update(SSIQuoteMessage(symbol="VNM", bid_price_1=78.0, ask_price_1=78.5, ...))
    classifier = TradeClassifier(cache)
    trade = SSITradeMessage(symbol="VNM", last_price=78.5, last_vol=1000, ...)
    result = classifier.classify(trade)
    assert result.trade_type == TradeType.MUA_CHU_DONG
    assert result.volume == 1000  # per-trade, NOT cumulative

def test_ban_chu_dong():
    """Price <= bid → ban chu dong"""
    ...

def test_neutral_between_bid_ask():
    """bid < price < ask → neutral"""
    ...

def test_neutral_during_ato():
    """ATO session → always neutral regardless of price"""
    ...

def test_neutral_no_cached_quote():
    """No quote cached yet → neutral (bid/ask = 0)"""
    ...

def test_uses_last_vol_not_total_vol():
    """CRITICAL: Verify volume comes from last_vol, not total_vol"""
    trade = SSITradeMessage(symbol="VNM", last_vol=500, total_vol=100000, ...)
    result = classifier.classify(trade)
    assert result.volume == 500  # NOT 100000
```

### 2. Foreign Delta Computation
```python
def test_delta_from_cumulative():
    """Second update computes correct delta from cumulative"""
    tracker = ForeignInvestorTracker()
    tracker.update(SSIForeignMessage(symbol="VNM", f_buy_vol=1000, f_sell_vol=500))
    tracker.update(SSIForeignMessage(symbol="VNM", f_buy_vol=1500, f_sell_vol=600))
    # delta_buy = 500, delta_sell = 100

def test_speed_calculation():
    """Speed = volume per minute over rolling 5 min window"""
    ...

def test_first_update_uses_absolute():
    """First update: delta = cumulative value itself"""
    ...
```

### 3. Basis Calculation
```python
def test_basis_premium():
    """futures > spot → positive basis, is_premium=True"""
    ...

def test_basis_discount():
    """futures < spot → negative basis, is_premium=False"""
    ...

def test_basis_no_spot():
    """No VN30 index value yet → returns None"""
    ...
```

### 4. Alert Threshold Logic
```python
def test_foreign_threshold_alert():
    """Net volume > 50K → alert triggered"""
    ...

def test_acceleration_alert():
    """Speed doubles → critical alert"""
    ...

def test_divergence_bearish():
    """Price up + NN selling → bearish divergence alert"""
    ...

def test_cooldown_prevents_spam():
    """Same alert type/symbol within 2 min → suppressed"""
    ...

def test_no_alerts_first_5_min():
    """Skip alerts during session initialization"""
    ...
```

### 5. WebSocket Connection Manager
```python
def test_subscribe_unsubscribe():
    ...

def test_broadcast_to_group():
    ...

def test_dead_connection_cleanup():
    ...
```

### 6. Frontend Utilities
```typescript
// price-color.ts
test('ceiling price → fuchsia', () => ...)
test('floor price → cyan', () => ...)
test('above ref → red', () => ...)
test('below ref → green', () => ...)
test('at ref → yellow', () => ...)

// format.ts
test('formatVolume: 1500000 → "1.5M"', () => ...)
test('formatPrice: 78.5 → "78.50"', () => ...)
```

## Docker Production Build

### Backend Dockerfile
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ app/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

### Frontend Dockerfile (multi-stage)
```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json .
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
```

### Nginx WebSocket Config (`frontend/nginx.conf`)
```nginx
# Handles static frontend + WebSocket proxy to backend.
# CRITICAL: WebSocket requires explicit Upgrade/Connection headers.

server {
    listen 80;
    server_name _;

    # Frontend static files
    root /usr/share/nginx/html;
    index index.html;

    # SPA fallback - all non-API/WS routes serve index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # REST API proxy
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket proxy - requires upgrade headers
    location /ws/ {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # WS timeout settings - keep connection alive during market hours
        proxy_read_timeout 3600s;   # 1 hour - covers full trading session
        proxy_send_timeout 3600s;
        proxy_connect_timeout 10s;
    }

    # Health check for Docker/load balancer
    location /health {
        proxy_pass http://backend:8000;
    }
}
```

**Key nginx WS config points:**
- `proxy_http_version 1.1` required for WebSocket (HTTP/1.0 doesn't support Upgrade)
- `Upgrade` + `Connection "upgrade"` headers forward the WebSocket handshake
- `proxy_read_timeout 3600s` prevents nginx from closing idle WS connections during market hours
- Backend heartbeat (30s) keeps the connection active within nginx timeout

### docker-compose.yml (production)
```yaml
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    env_file: ./backend/.env
    depends_on: [postgres]
    restart: unless-stopped

  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: stock
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: stock_tracker
    volumes: ["pgdata:/var/lib/postgresql/data"]
    restart: unless-stopped

  frontend:
    build: ./frontend
    ports: ["80:80"]
    depends_on: [backend]
    restart: unless-stopped

volumes:
  pgdata:
```

## Logging
```python
import logging
import json

# Structured JSON logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[logging.StreamHandler()]
)

# Key log events:
# - SSI auth success/failure
# - SSI stream connect/disconnect/reconnect
# - Trade classification stats (periodic: X trades/min, Y% mua, Z% ban)
# - Foreign data update frequency
# - Alert generated
# - DB batch write stats (X trades written in Yms)
# - WS client connect/disconnect count
```

## Todo List
- [ ] Write unit tests for TradeClassifier (5+ test cases)
- [ ] Write unit tests for ForeignInvestorTracker (delta + speed)
- [ ] Write unit tests for DerivativesTracker (basis)
- [ ] Write unit tests for AlertService (threshold + cooldown)
- [ ] Write unit tests for ConnectionManager
- [ ] Write frontend utility tests (price-color, format)
- [ ] Create production Dockerfiles (backend + frontend)
- [ ] Create nginx.conf with WebSocket proxy (Upgrade headers, 1h timeout)
- [ ] Create production docker-compose.yml
- [ ] Add structured logging
- [ ] Add error handling (try/except in all async callbacks)
- [ ] Test Docker Compose production build
- [ ] Test end-to-end during market hours

## Success Criteria
- All unit tests pass with >80% coverage on services/
- Docker Compose production build starts cleanly
- Backend health check returns 200
- Frontend loads from nginx
- Logs structured and informative
- Graceful handling of SSI disconnects

## Risk Assessment
- **SSI credentials in Docker:** Use env_file, never bake into image
- **PostgreSQL password:** Use env var, not hardcoded in compose
- **Nginx WS proxy:** MITIGATED. nginx.conf provided with Upgrade/Connection headers, 1h read timeout

## Verification (End-to-End)
1. `docker compose up -d` → all services start
2. Open browser → dashboard loads VN30 board
3. During market hours: prices update live, foreign data flows, basis calculated
4. Trigger mock foreign surge → alert appears in feed
5. Check PostgreSQL: trades being persisted in batches
6. Kill backend → frontend shows "reconnecting" → restart backend → auto-reconnect
