# VN Stock Tracker

Real-time Vietnamese stock market tracker for VN30 stocks. Foreign investor monitoring, volume analysis, derivatives/basis tracking, and analytics alerts.

## Features

- **Foreign Flow Tracking** — real-time foreign investor buy/sell with speed & acceleration metrics
- **Volume Analysis** — active buy/sell/neutral trade classification per VN30 stock
- **Signals** — market alerts for foreign acceleration, basis divergence, volume anomalies
- **Derivatives Basis** — VN30F futures vs VN30 index spread analysis
- **Real-time Data** — SSI FastConnect WebSocket for live market feeds

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, asyncpg |
| Frontend | React 19, TypeScript, Vite, TailwindCSS v4 |
| Charts | Recharts, TradingView Lightweight Charts |
| Database | TimescaleDB (PostgreSQL 16) |
| Cache | Redis 7 |
| Data Source | SSI FastConnect (WebSocket + REST) |
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
| GET | `/health` | Health check |
| GET | `/api/vn30-components` | VN30 component stock symbols |
| GET | `/api/market/snapshot` | Full market data snapshot |
| GET | `/api/market/foreign-detail` | Per-symbol foreign investor data |
| GET | `/api/market/volume-stats` | Per-symbol active buy/sell stats |
| GET | `/api/history/{symbol}/candles` | 1-minute OHLCV candles |
| GET | `/api/history/{symbol}/ticks` | Trade tick history |
| GET | `/api/history/{symbol}/foreign` | Foreign flow snapshots |
| GET | `/api/history/{symbol}/foreign/daily` | Daily foreign summary |
| GET | `/api/history/index/{name}` | Index value history |
| GET | `/api/history/derivatives/{contract}` | Futures history |

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
                                 └─ DerivativesTracker
                                      │
                                 TimescaleDB
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
│   │   └── database/            # DB layer (asyncpg + batch writer)
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/               # 3 dashboard pages
│   │   ├── components/          # UI components
│   │   ├── hooks/               # Data fetching hooks
│   │   └── utils/               # API client, formatters
│   ├── nginx.conf
│   └── Dockerfile
├── db/migrations/               # TimescaleDB schema
└── docker-compose.yml
```

## Testing

```bash
cd backend
./venv/bin/pytest -v
```

## License

MIT
