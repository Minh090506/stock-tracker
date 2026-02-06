# Phase 01: Project Scaffolding

## Context Links
- [Plan Overview](./plan.md)
- [SSI WS Data Format](../reports/researcher-260206-1423-ssi-fastconnect-websocket-data-format.md)

## Overview
- **Priority:** P0
- **Status:** pending
- **Effort:** 3h
- Monorepo setup, dependency installation, Docker Compose (FastAPI + PostgreSQL), config management with pydantic-settings.

## Requirements

### Functional
- Monorepo with `backend/` and `frontend/` directories
- Backend: FastAPI app skeleton with health check
- Frontend: React 19 + Vite + TailwindCSS v4 skeleton
- Docker Compose: FastAPI, PostgreSQL, frontend dev server
- Config: `.env` for SSI credentials + DB URL

### Non-Functional
- Backend starts with `uvicorn` and returns 200 on `/health`
- Frontend starts with `npm run dev` and shows placeholder page
- Docker Compose `up` brings all services online

## Architecture
```
~/projects/stock-tracker/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                          # FastAPI app + lifespan
│   │   ├── config.py                        # pydantic-settings
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── schemas.py                   # All Pydantic models
│   │   ├── services/                        # Business logic (Phase 2-6)
│   │   ├── routers/                         # REST endpoints (Phase 4)
│   │   ├── websocket/                       # WS server (Phase 4)
│   │   └── database/                        # DB layer (Phase 7)
│   ├── tests/
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── index.css                        # TailwindCSS v4 import
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── types/
│   │   │   └── index.ts
│   │   └── utils/
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── .gitignore
└── README.md
```

## Related Code Files
- `~/projects/stock-tracker/backend/app/main.py` - FastAPI app entry point
- `~/projects/stock-tracker/backend/app/config.py` - Settings via pydantic-settings
- `~/projects/stock-tracker/backend/requirements.txt` - Python deps
- `~/projects/stock-tracker/frontend/package.json` - Node deps
- `~/projects/stock-tracker/frontend/vite.config.ts` - Vite config with WS proxy
- `~/projects/stock-tracker/docker-compose.yml` - All services

## Implementation Steps

### 1. Create project directories
```bash
mkdir -p ~/projects/stock-tracker/{backend/app/{models,services,routers,websocket,database},backend/tests,frontend/src/{components,hooks,types,utils}}
```

### 2. Backend requirements.txt
```
fastapi>=0.115.0
uvicorn[standard]>=0.34.0
pydantic>=2.10.0
pydantic-settings>=2.7.0
websockets>=14.0
ssi-fc-data>=1.0.0
asyncpg>=0.30.0
python-dotenv>=1.0.0
httpx>=0.28.0
```

**NO vnstock** - SSI Channel R provides foreign data directly.

### 3. Backend config.py
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # SSI FastConnect
    ssi_consumer_id: str
    ssi_consumer_secret: str
    ssi_base_url: str = "https://fc-data.ssi.com.vn/"
    ssi_stream_url: str = "https://fc-data.ssi.com.vn/"

    # Database
    database_url: str = "postgresql://stock:stock@localhost:5432/stock_tracker"

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

settings = Settings()
```

### 4. Backend main.py (skeleton)
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup - Phase 2 will add SSI connection here
    yield
    # Shutdown - Phase 2 will add cleanup here

app = FastAPI(
    title="VN Stock Tracker",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok"}
```

### 5. Backend .env.example
```
SSI_CONSUMER_ID=your_consumer_id
SSI_CONSUMER_SECRET=your_consumer_secret
DATABASE_URL=postgresql://stock:stock@localhost:5432/stock_tracker
```

### 6. Frontend package.json
Key deps: `react`, `react-dom`, `lightweight-charts`, `@tailwindcss/vite`

### 7. Frontend vite.config.ts
```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
});
```

### 8. Docker Compose
```yaml
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    env_file: ./backend/.env
    depends_on: [postgres]

  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: stock
      POSTGRES_PASSWORD: stock
      POSTGRES_DB: stock_tracker
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]

  frontend:
    build: ./frontend
    ports: ["5173:5173"]

volumes:
  pgdata:
```

### 9. Frontend App.tsx placeholder
```tsx
export default function App() {
  return (
    <div className="min-h-screen bg-gray-950 text-white flex items-center justify-center">
      <h1 className="text-2xl font-bold">VN Stock Tracker</h1>
    </div>
  );
}
```

### 10. Init git + Python venv
```bash
cd ~/projects/stock-tracker
git init
python3 -m venv backend/venv
source backend/venv/bin/activate
pip install -r backend/requirements.txt
cd frontend && npm install
```

## Todo List
- [ ] Create monorepo directory structure
- [ ] Create backend requirements.txt (NO vnstock)
- [ ] Create config.py with pydantic-settings
- [ ] Create main.py skeleton with health endpoint
- [ ] Create .env.example
- [ ] Create frontend with React 19 + Vite + TailwindCSS v4
- [ ] Create vite.config.ts with backend proxy
- [ ] Create docker-compose.yml (FastAPI + PostgreSQL + frontend)
- [ ] Create .gitignore
- [ ] Test: backend returns 200 on /health
- [ ] Test: frontend renders placeholder

## Success Criteria
- `uvicorn app.main:app --reload` starts, `curl localhost:8000/health` returns `{"status":"ok"}`
- `npm run dev` starts frontend at localhost:5173
- `docker compose up` brings all 3 services online
- `.env.example` documents all required env vars

## Risk Assessment
- **ssi-fc-data install issues:** May have native deps; test pip install first
- **TailwindCSS v4 breaking changes:** Use `@tailwindcss/vite` plugin (zero config)

## Next Steps
- Phase 02: Connect SSI WebSocket and subscribe to all channels
