# VN Stock Tracker

Real-time Vietnamese stock market tracker for VN30 stocks. Foreign investor monitoring, volume analysis, derivatives/basis tracking, and analytics alerts.

## Features

- **Price Board** — real-time VN30 stocks with live pricing, sparklines, and active buy/sell classification
- **Foreign Flow Tracking** — real-time foreign investor buy/sell with speed & acceleration metrics
- **Volume Analysis** — active buy/sell/neutral trade classification per VN30 stock
- **Derivatives Basis** — VN30F futures vs VN30 index spread analysis with convergence tracking
- **Analytics Alerts** — market alerts for volume spikes, price breakouts, foreign acceleration, basis divergence
- **Real-time Data** — SSI FastConnect WebSocket for live market feeds with <5ms latency

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, asyncpg |
| Frontend | React 19, TypeScript, Vite, TailwindCSS v4 |
| Charts | Recharts, TradingView Lightweight Charts |
| Database | TimescaleDB (PostgreSQL 16) |
| Cache | Redis 7 |
| Data Source | SSI FastConnect (WebSocket + REST) |
| Monitoring | Prometheus, Grafana, Node Exporter |
| Deployment | Docker Compose |

## Prerequisites

- Python 3.12+
- Node.js 20+
- Docker & Docker Compose (for containerized setup)
- SSI FastConnect API credentials

## Quick Start

### Docker (recommended)

```bash
cp backend/.env.example backend/.env
# Edit backend/.env with your SSI credentials
docker compose up
```

- Frontend: http://localhost
- Backend API: http://localhost:8000

### Local Development

#### Backend

```bash
cd backend
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env
# Edit .env with your SSI credentials
./venv/bin/uvicorn app.main:app --reload
```

#### Frontend

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:5173
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SSI_CONSUMER_ID` | *(required)* | SSI FastConnect consumer ID |
| `SSI_CONSUMER_SECRET` | *(required)* | SSI FastConnect consumer secret |
| `DATABASE_URL` | `postgresql://stock:stock@localhost:5432/stock_tracker` | PostgreSQL connection string |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed origins |
| `LOG_LEVEL` | `INFO` | Python log level (DEBUG, INFO, WARNING, ERROR) |
| `CHANNEL_R_INTERVAL_MS` | `1000` | Foreign investor update interval (ms) |
| `FUTURES_OVERRIDE` | *(empty)* | Override active futures contract (e.g., `VN30F2603`) |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check + database status |
| GET | `/api/vn30-components` | VN30 component stock symbols |
| GET | `/api/market/snapshot` | Full market data snapshot |
| GET | `/api/market/foreign-detail` | Per-symbol foreign investor data |
| GET | `/api/market/volume-stats` | Per-symbol active buy/sell stats |
| GET | `/api/market/basis-trend` | Futures basis trend (30-min history) |
| GET | `/api/market/alerts` | Alert history with filtering |
| GET | `/api/history/{symbol}/candles` | 1-minute OHLCV candles |
| GET | `/api/history/{symbol}/ticks` | Trade tick history |
| GET | `/api/history/{symbol}/foreign` | Foreign flow snapshots |
| GET | `/api/history/{symbol}/foreign/daily` | Daily foreign summary |
| GET | `/api/history/index/{name}` | Index value history |
| GET | `/api/history/derivatives/{contract}` | Futures history |
| GET | `/metrics` | Prometheus metrics endpoint |

## Architecture

```
SSI FastConnect (WebSocket) ──→ FastAPI Backend ──→ React Frontend
                                      │
                                MarketDataProcessor
                                 ├─ QuoteCache
                                 ├─ TradeClassifier
                                 ├─ SessionAggregator
                                 ├─ ForeignInvestorTracker
                                 ├─ IndexTracker
                                 ├─ DerivativesTracker
                                 └─ AlertService + PriceTracker
                                      │
                        ┌─────────────┼──────────────┐
                        ▼             ▼              ▼
                   TimescaleDB   Prometheus      Node Exporter
                                  (metrics)       (system metrics)
                                      │
                                   Grafana
                                (dashboards)
```

## Project Structure

```
stock-tracker/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry + lifespan
│   │   ├── config.py            # pydantic-settings
│   │   ├── models/              # Pydantic schemas
│   │   ├── services/            # Business logic (11 services)
│   │   ├── routers/             # REST endpoints
│   │   ├── analytics/           # Alert + signal detection
│   │   ├── websocket/           # WebSocket router
│   │   ├── database/            # DB layer (pool.py)
│   │   └── metrics.py           # Prometheus instrumentation
│   ├── tests/
│   ├── alembic/                 # Database migrations
│   ├── scripts/                 # Utility scripts
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/               # 5 dashboard pages
│   │   ├── components/          # UI components
│   │   ├── hooks/               # Data fetching hooks
│   │   └── utils/               # API client, formatters
│   ├── nginx.conf
│   └── Dockerfile
├── monitoring/                  # Prometheus, Grafana configs
├── scripts/                     # Deployment scripts (deploy.sh)
├── db/migrations/               # TimescaleDB schema
└── docker-compose.prod.yml
```

## Testing

```bash
cd backend
# Run all tests (unit + integration)
./venv/bin/pytest -v

# With coverage
./venv/bin/pytest --cov=app --cov-fail-under=80

# E2E tests only
./venv/bin/pytest tests/e2e/ -v

# Load testing
./scripts/run-load-test.sh --users 100 --duration 300
```

## WebSocket Channels

| Channel | Purpose | Frequency |
|---------|---------|-----------|
| `/ws/market` | Full MarketSnapshot (quotes, indices, foreign, derivatives) | Per trade (500ms throttle) |
| `/ws/foreign` | ForeignSummary only (aggregate + top movers) | Per foreign update (500ms throttle) |
| `/ws/index` | VN30/VNINDEX data only | Per index update (500ms throttle) |
| `/ws/alerts` | Real-time alert notifications | On alert generation |

## License

MIT
