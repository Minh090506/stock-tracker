# VN Stock Tracker

Real-time Vietnamese stock market tracker for VN30 stocks with foreign investor monitoring, volume analysis, derivatives/basis tracking, and analytics alerts. Powered by SSI FastConnect WebSocket.

## Features

| Feature | Description |
|---------|-------------|
| **Price Board** | Real-time VN30 quotes with bid/ask, sparklines, session phase indicator |
| **Foreign Flow** | Per-symbol foreign buy/sell with speed, acceleration, sector heatmap |
| **Volume Analysis** | Active buy/sell/neutral classification per stock per session phase (ATO/Continuous/ATC) |
| **Derivatives Basis** | VN30F futures vs VN30 index spread, convergence tracking, open interest |
| **Signals** | Auto-detected alerts: volume spikes, price breakouts, foreign acceleration, basis divergence |
| **Historical Data** | 1-min OHLCV candles, trade ticks, foreign flow, index/derivatives history (TimescaleDB) |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, asyncpg, uvloop |
| Frontend | React 19, TypeScript, Vite, TailwindCSS v4 |
| Charts | Recharts, TradingView Lightweight Charts |
| Database | TimescaleDB (PostgreSQL 16) |
| Data Source | SSI FastConnect (WebSocket + REST) |
| Monitoring | Prometheus, Grafana, Node Exporter |
| Deployment | Docker Compose, Nginx reverse proxy |
| CI/CD | GitHub Actions (pytest 80% coverage gate) |

## Prerequisites

- Docker Engine 20.10+ & Docker Compose 2.0+
- SSI FastConnect API credentials ([register here](https://fc-data.ssi.com.vn/))

For local development:
- Python 3.12+
- Node.js 20+

## Quick Start

### Docker (Recommended)

```bash
git clone <repo-url> && cd stock-tracker
cp .env.example .env
# Edit .env — set SSI_CONSUMER_ID and SSI_CONSUMER_SECRET

# One-command deploy
./scripts/deploy.sh

# Or manually:
docker compose -f docker-compose.prod.yml up -d
```

Access:
- **Dashboard**: http://localhost
- **API**: http://localhost/api/market/snapshot
- **Health**: http://localhost/health
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090

### Local Development

```bash
# Backend
cd backend
python3.12 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env  # configure SSI credentials
./venv/bin/uvicorn app.main:app --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
# Open http://localhost:5173
```

## Project Structure

```
stock-tracker/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI entry + lifespan
│   │   ├── config.py                # Pydantic settings
│   │   ├── metrics.py               # Prometheus metrics
│   │   ├── analytics/               # Alert service + price tracker
│   │   ├── database/                # asyncpg pool + batch writer + history queries
│   │   ├── models/                  # Domain, schemas, SSI messages
│   │   ├── routers/                 # REST endpoints (market + history)
│   │   ├── services/                # 11 business logic services
│   │   └── websocket/               # Multi-channel WS router + publisher
│   ├── tests/                       # 380 tests (84% coverage)
│   ├── alembic/                     # DB migrations
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/                   # 5 dashboard pages
│   │   ├── components/              # Feature components (derivatives, foreign, price-board, signals, volume)
│   │   ├── hooks/                   # 8 data hooks (WS + REST)
│   │   ├── utils/                   # API client, formatters, session logic
│   │   └── types/                   # TypeScript interfaces
│   └── Dockerfile
├── monitoring/
│   ├── prometheus/                  # Scrape config
│   └── grafana/                     # 4 dashboards + provisioning
├── nginx/nginx.conf                 # Reverse proxy rules
├── db/migrations/                   # TimescaleDB schema
├── scripts/
│   ├── deploy.sh                    # One-command deployment
│   └── run-load-test.sh             # Locust test runner
├── docker-compose.prod.yml          # Production (app + monitoring)
├── docker-compose.yml               # Development
├── docker-compose.test.yml          # Load testing
└── .github/workflows/ci.yml         # CI pipeline
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SSI_CONSUMER_ID` | *(required)* | SSI FastConnect consumer ID |
| `SSI_CONSUMER_SECRET` | *(required)* | SSI FastConnect consumer secret |
| `DATABASE_URL` | `postgresql://stock:stock@timescaledb:5432/stock_tracker` | PostgreSQL connection |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed CORS origins |
| `LOG_LEVEL` | `INFO` | Log level (DEBUG/INFO/WARNING/ERROR) |
| `WS_AUTH_TOKEN` | *(empty=disabled)* | WebSocket auth token |
| `WS_MAX_CONNECTIONS_PER_IP` | `5` | Max WS connections per IP |
| `WS_THROTTLE_INTERVAL_MS` | `500` | WS broadcast throttle |
| `CHANNEL_R_INTERVAL_MS` | `1000` | Foreign investor update interval |
| `FUTURES_OVERRIDE` | *(empty)* | Override active VN30F contract |

See [.env.example](../.env.example) for full reference.

## Testing

```bash
# Unit + integration tests (380 tests)
cd backend && ./venv/bin/pytest -v --cov=app --cov-report=term-missing

# Load testing
./scripts/run-load-test.sh rest --users 100 --time 60

# Docker load test (Locust UI at :8089)
docker compose -f docker-compose.test.yml up --scale locust-worker=4
```

## Performance

| Metric | Value | Target |
|--------|-------|--------|
| Message throughput | 58,874 msg/s | ≥5,000 |
| Trade classification | <1ms | <5ms |
| WS p99 latency | 85-95ms | <100ms |
| REST p95 latency | 175-195ms | <200ms |
| Test coverage | 84% | ≥80% |

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](architecture.md) | System design with diagrams |
| [API Reference](api-reference.md) | All REST + WebSocket endpoints |
| [Deployment](deployment.md) | Docker deploy guide, env vars, health checks |
| [Monitoring](monitoring.md) | Grafana dashboards + Prometheus setup |
| [System Architecture](system-architecture.md) | Detailed technical architecture (903 lines) |
| [Code Standards](code-standards.md) | Coding conventions |
| [Development Roadmap](development-roadmap.md) | Phase progress tracking |

## VN Market Color Convention

| Color | Meaning |
|-------|---------|
| Red | Price up |
| Green | Price down |
| Fuchsia | Ceiling price |
| Cyan | Floor price |
| Yellow | Reference price |

## License

MIT
