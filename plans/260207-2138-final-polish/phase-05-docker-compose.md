# Phase 5: Docker Compose (Full Stack)

## Context
- [docker-compose.yml](/Users/minh/Projects/stock-tracker/docker-compose.yml) -- 3 services: backend, timescaledb, frontend
- [backend/Dockerfile](/Users/minh/Projects/stock-tracker/backend/Dockerfile) -- python:3.12-slim, uvicorn
- [frontend/Dockerfile](/Users/minh/Projects/stock-tracker/frontend/Dockerfile) -- multi-stage node build + nginx
- [nginx.conf](/Users/minh/Projects/stock-tracker/frontend/nginx.conf) -- API proxy + WS upgrade
- [main.py](/Users/minh/Projects/stock-tracker/backend/app/main.py) -- lifespan starts both API server AND stream collection in same process
- No Redis, no separate data-collector

## Overview
- **Priority:** P1
- **Status:** pending
- **Effort:** 1.5h
- **Depends on:** Phase 4 (env config)

Enhance docker-compose.yml for production readiness: add Redis for future caching/pub-sub, health checks for all services, restart policies, resource limits, and proper networking.

## Key Design Decision: Single Backend vs Data Collector Split

**Decision: Keep single backend process.** Rationale:
- Current `lifespan` in main.py starts both API and stream collection in one process
- Splitting requires significant refactoring (shared state, IPC via Redis pub/sub)
- YAGNI: single backend handles both fine for single-instance deployment
- Redis added for future use (session cache, rate limiting) but NOT for splitting services yet

If scaling is needed later, the split is straightforward:
1. Backend serves API only (remove stream from lifespan)
2. Data-collector runs stream collection, publishes to Redis
3. Backend subscribes to Redis for real-time data

## Requirements

**Functional:**
- Redis service available for future caching
- Health checks on all services
- Production-ready restart policies
- Proper service dependencies with health conditions

**Non-functional:**
- Resource limits to prevent runaway memory
- Named network for clarity
- Volume persistence for database

## Related Code Files

**Modify:**
- `docker-compose.yml` -- add Redis, health checks, resource limits, networking

## Implementation Steps

### Step 1: Update docker-compose.yml

```yaml
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file: ./backend/.env
    environment:
      - DATABASE_URL=postgresql://stock:stock@timescaledb:5432/stock_tracker
      - CORS_ORIGINS=http://localhost
    depends_on:
      timescaledb:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 15s
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 512M
    networks:
      - app-network

  timescaledb:
    image: timescale/timescaledb:latest-pg16
    environment:
      POSTGRES_USER: stock
      POSTGRES_PASSWORD: stock
      POSTGRES_DB: stock_tracker
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./db/migrations:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U stock -d stock_tracker"]
      interval: 5s
      timeout: 3s
      retries: 5
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 1G
    networks:
      - app-network

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 128M
    networks:
      - app-network

  frontend:
    build: ./frontend
    ports:
      - "80:80"
    depends_on:
      backend:
        condition: service_healthy
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 128M
    networks:
      - app-network

volumes:
  pgdata:
  redis-data:

networks:
  app-network:
    driver: bridge
```

### Step 2: Add curl to backend Dockerfile

The health check uses `curl`. Add it to the Dockerfile:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Alternative: use Python for health check instead of curl to avoid extra package:
```yaml
test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
```
This avoids installing curl. Prefer this approach for smaller image size.

### Step 3: Verify nginx.conf proxy targets

Current `nginx.conf` uses `backend:8000` which matches the service name. No changes needed -- Docker Compose DNS resolves service names within the network.

## Todo List

- [ ] Update `docker-compose.yml` with Redis, health checks, resource limits, networking
- [ ] Choose health check approach for backend (curl vs python)
- [ ] Add `redis-data` volume
- [ ] Add `app-network` bridge network
- [ ] Verify `docker compose config` parses correctly
- [ ] Test `docker compose up` starts all services with health checks passing

## Success Criteria
- `docker compose up` starts 4 services: backend, timescaledb, redis, frontend
- All health checks pass within 30 seconds
- Frontend accessible at http://localhost
- Backend API accessible via nginx proxy at http://localhost/api/
- Redis responds to PING
- Services restart automatically on failure

## Risk Assessment
- **Low risk**: Additive changes to existing compose file
- **Edge case**: Backend health check may fail during SSI authentication (long startup). Mitigated by `start_period: 15s`
- **Note**: Redis is included but NOT actively used by backend yet. Ready for future phases.
