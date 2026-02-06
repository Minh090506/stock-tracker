# VN Stock Tracker

Real-time Vietnamese stock market tracker for VN30 stocks with foreign investor monitoring, derivatives/basis analysis, and analytics alerts.

## Tech Stack

- **Backend:** Python 3.12+, FastAPI, asyncpg, SSI FastConnect
- **Frontend:** React 19, TypeScript, Vite, TailwindCSS v4, TradingView Lightweight Charts
- **Database:** PostgreSQL 16
- **Deployment:** Docker Compose

## Quick Start

### Local Development

```bash
# Backend
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Edit with your SSI credentials
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

### Docker

```bash
cp backend/.env.example backend/.env  # Edit with your SSI credentials
docker compose up
```

## Project Structure

```
stock-tracker/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI entry point
│   │   ├── config.py        # pydantic-settings
│   │   ├── models/          # Pydantic schemas
│   │   ├── services/        # Business logic
│   │   ├── routers/         # REST endpoints
│   │   ├── websocket/       # WS server
│   │   └── database/        # DB layer
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   ├── nginx.conf
│   └── Dockerfile
└── docker-compose.yml
```

## Environment Variables

See `backend/.env.example` for all required configuration.
