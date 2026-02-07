# Phase 6: README Update

## Context
- [README.md](/Users/minh/Projects/stock-tracker/README.md) -- basic 64-line README with quick start + project structure
- Project has matured: 3 dashboard pages, 11 backend services, Docker Compose, 232+ tests
- Existing README missing: feature list, API docs, architecture diagram, env vars reference

## Overview
- **Priority:** P2
- **Status:** pending
- **Effort:** 1h
- **Depends on:** Phase 4 (env config) + Phase 5 (Docker Compose)

Comprehensive README update covering features, prerequisites, setup, Docker, env vars, API, and architecture.

## Requirements

**Functional:**
- Project description with feature highlights
- Prerequisites list
- Local development setup (backend + frontend, step by step)
- Docker Compose quick start
- Environment variables reference table
- API endpoints summary
- Brief architecture overview

**Non-functional:**
- Under 200 lines (concise, not a novel)
- Copy-pasteable commands

## Related Code Files

**Modify:**
- `README.md` -- rewrite

## Implementation Steps

### Step 1: Rewrite README.md

Structure:

```markdown
# VN Stock Tracker

Real-time Vietnamese stock market tracker for VN30 stocks.
Foreign investor monitoring, volume analysis, derivatives/basis tracking, and analytics alerts.

## Features

- **Foreign Flow Tracking** -- real-time foreign investor buy/sell with speed & acceleration metrics
- **Volume Analysis** -- active buy/sell/neutral trade classification per VN30 stock
- **Signals** -- market alerts for foreign acceleration, basis divergence, volume anomalies
- **Derivatives Basis** -- VN30F futures vs VN30 index spread analysis
- **Real-time Data** -- SSI FastConnect WebSocket for live market feeds

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, asyncpg |
| Frontend | React 19, TypeScript, Vite, TailwindCSS v4 |
| Charts | Recharts, TradingView Lightweight Charts |
| Database | TimescaleDB (PostgreSQL 16) |
| Data Source | SSI FastConnect (WebSocket + REST) |
| Deployment | Docker Compose |

## Prerequisites

- Python 3.12+
- Node.js 20+
- Docker & Docker Compose (for containerized setup)
- SSI FastConnect API credentials

## Quick Start

### Docker (recommended)

    cp backend/.env.example backend/.env
    # Edit backend/.env with your SSI credentials
    docker compose up

    Frontend: http://localhost
    Backend API: http://localhost:8000

### Local Development

#### Backend

    cd backend
    python3 -m venv venv
    ./venv/bin/pip install -r requirements.txt
    cp .env.example .env
    # Edit .env with your SSI credentials
    ./venv/bin/uvicorn app.main:app --reload

#### Frontend

    cd frontend
    npm install
    npm run dev

    Open http://localhost:5173

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SSI_CONSUMER_ID` | (required) | SSI FastConnect consumer ID |
| `SSI_CONSUMER_SECRET` | (required) | SSI FastConnect consumer secret |
| `DATABASE_URL` | `postgresql://stock:stock@localhost:5432/stock_tracker` | PostgreSQL connection string |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed origins |
| `LOG_LEVEL` | `INFO` | Python log level (DEBUG, INFO, WARNING, ERROR) |
| `CHANNEL_R_INTERVAL_MS` | `1000` | Foreign investor update interval (ms) |
| `FUTURES_OVERRIDE` | (empty) | Override active futures contract (e.g., `VN30F2603`) |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/vn30-components` | VN30 component stock symbols |
| GET | `/api/market/snapshot` | Unified market data snapshot |
| GET | `/api/market/foreign` | Foreign investor summary |

## Architecture

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

## Project Structure

    stock-tracker/
    ├── backend/
    │   ├── app/
    │   │   ├── main.py              # FastAPI entry + lifespan
    │   │   ├── config.py            # pydantic-settings
    │   │   ├── models/              # Pydantic schemas
    │   │   ├── services/            # Business logic (11 services)
    │   │   ├── routers/             # REST endpoints
    │   │   ├── websocket/           # WS server
    │   │   └── database/            # DB layer (asyncpg)
    │   ├── tests/                   # 232+ tests
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
    └── docker-compose.yml

## Testing

    cd backend
    ./venv/bin/pytest -v

## License

MIT
```

## Todo List

- [ ] Rewrite `README.md` with comprehensive content
- [ ] Verify all commands are copy-pasteable
- [ ] Verify API endpoint list matches actual routes
- [ ] Keep under 200 lines

## Success Criteria
- New developer can set up the project from README alone (Docker or local)
- All listed commands work as documented
- Environment variables table is complete and accurate
- Architecture section gives high-level understanding in 10 seconds

## Risk Assessment
- **Low risk**: Documentation only, no code changes
- **Note**: API endpoints list may need updating as more routes are added
