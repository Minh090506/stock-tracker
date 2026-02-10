# Deployment Guide

## Production Docker Deployment

This guide covers deploying the VN Stock Tracker to production using Docker Compose with three containerized services: Nginx (reverse proxy), Backend (FastAPI), and Frontend (React).

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- `.env` file configured with credentials and settings

## Quick Start

```bash
# Navigate to project root
cd /path/to/stock-tracker

# Copy and configure environment
cp .env.example .env
# Edit .env with SSI credentials and settings

# Build and start all services
docker-compose -f docker-compose.prod.yml up -d

# Verify health
curl http://localhost/health

# View logs
docker-compose -f docker-compose.prod.yml logs -f
```

## Architecture Overview

The production deployment consists of three Docker containers on a shared bridge network:

```
┌──────────────────────────────────────────┐
│          Nginx (Reverse Proxy)           │
│  Port 80 → Frontend / Backend / WS       │
└──────────┬───────────────────────────────┘
           │ (app-network)
      ┌────┴────────────────────┐
      ▼                         ▼
┌───────────┐           ┌──────────────┐
│ Frontend  │           │ Backend      │
│ (Static)  │           │ (FastAPI)    │
│ :80       │           │ :8000        │
└───────────┘           └──────────────┘
```

### Service Definitions

#### Nginx (Reverse Proxy)

**Image**: `nginx:alpine` (lightweight, ~9MB)

**Ports**:
- External: `80`
- Internal: `80`

**Configuration**:
- Mounts `./nginx/nginx.conf` for routing rules
- Routes requests to frontend (static) or backend (API/WS)
- Handles WebSocket upgrade headers for `/ws` endpoints
- Health check validates backend availability

**Startup**:
```yaml
depends_on:
  backend:
    condition: service_healthy  # Wait for backend readiness
  frontend:
    condition: service_started   # Wait for frontend to start
```

**Routing Rules** (`nginx/nginx.conf`):
```
/                → frontend:80      (static HTML/JS)
/api/*          → backend:8000     (REST endpoints)
/ws             → backend:8000     (WebSocket with upgrade)
= /health       → backend:8000     (no access logs)
```

#### Backend (FastAPI)

**Dockerfile**: `backend/Dockerfile` (multi-stage)

**Build Strategy**:
1. **Builder stage**: Python 3.12 slim + pip install requirements
2. **Runtime stage**: Copy app + non-root user

**Runtime Configuration**:
- User: `stock` (UID 1000, non-root for security)
- Port: `8000` (exposed internally only)
- Process: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --lifespan on`

**Features**:
- uvloop for 10-40% faster I/O
- Startup/shutdown hooks via FastAPI lifespan context
- async/await pattern for concurrency

**Health Check**:
```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
  interval: 15s
  timeout: 5s
  retries: 3
  start_period: 30s
```

**Resource Limits**:
```yaml
deploy:
  resources:
    limits:
      memory: 1G           # Maximum
    reservations:
      memory: 512M         # Minimum reserved
```

**Environment**:
- Reads `.env` file via `env_file` directive
- Required: `SSI_CONSUMER_ID`, `SSI_CONSUMER_SECRET`, `DATABASE_URL`

#### Frontend (React + Nginx)

**Dockerfile**: `frontend/Dockerfile` (multi-stage)

**Build Strategy**:
1. **Builder stage**: Node 20 + npm install + `npm run build`
2. **Runtime stage**: Nginx Alpine + static bundle from `dist/`

**Static Configuration**:
- Serves compiled React SPA from `/dist` folder
- Gzip compression enabled
- Cache headers set (`max-age=3600` for assets)
- No backend proxy (handled by main Nginx)

**Port**: `80` (exposed internally only, mapped via Nginx)

**Resource Limits**:
```yaml
deploy:
  resources:
    limits:
      memory: 128M
    reservations:
      memory: 64M
```

## Configuration

### Environment Variables (`.env`)

Create `.env` in project root with:

```bash
# ============================================
# SSI FastConnect (REQUIRED)
# ============================================
SSI_CONSUMER_ID=your_id_here
SSI_CONSUMER_SECRET=your_secret_here
SSI_BASE_URL=https://fc-data.ssi.com.vn/
SSI_STREAM_URL=https://fc-data.ssi.com.vn/

# ============================================
# Database (Phase 7)
# ============================================
DATABASE_URL=postgresql://stock:stock@timescaledb:5432/stock_tracker

# ============================================
# Application
# ============================================
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=false
LOG_LEVEL=INFO

# ============================================
# CORS
# ============================================
CORS_ORIGINS=http://localhost,https://yourdomain.com

# ============================================
# Market Data
# ============================================
CHANNEL_R_INTERVAL_MS=1000
FUTURES_OVERRIDE=

# ============================================
# WebSocket
# ============================================
WS_THROTTLE_INTERVAL_MS=500
WS_HEARTBEAT_INTERVAL=30.0
WS_HEARTBEAT_TIMEOUT=10.0
WS_QUEUE_SIZE=50
WS_AUTH_TOKEN=
WS_MAX_CONNECTIONS_PER_IP=5
```

**Template Location**: `.env.example`

### Docker Ignore Files

**`backend/.dockerignore`**:
```
.git
.pytest_cache
.coverage
*.pyc
__pycache__
venv
.env
.DS_Store
```

**`frontend/.dockerignore`**:
```
.git
node_modules
dist
.env.local
.DS_Store
```

## Running Containers

### Start Services

```bash
# Development
docker-compose -f docker-compose.dev.yml up

# Production
docker-compose -f docker-compose.prod.yml up -d
```

### View Logs

```bash
# All services
docker-compose -f docker-compose.prod.yml logs -f

# Specific service
docker-compose -f docker-compose.prod.yml logs -f backend
docker-compose -f docker-compose.prod.yml logs -f frontend
docker-compose -f docker-compose.prod.yml logs -f nginx
```

### Stop Services

```bash
docker-compose -f docker-compose.prod.yml down

# Remove volumes (data cleanup)
docker-compose -f docker-compose.prod.yml down -v
```

### Rebuild Images

```bash
# Full rebuild
docker-compose -f docker-compose.prod.yml build --no-cache

# Specific service
docker-compose -f docker-compose.prod.yml build --no-cache backend
```

## Health Checks

### Verify Deployment

```bash
# Nginx health (via backend /health)
curl http://localhost/health

# Backend API
curl http://localhost/api/market/snapshot

# Frontend (static)
curl http://localhost/ | head -20
```

### Container Status

```bash
# List running containers
docker-compose -f docker-compose.prod.yml ps

# Inspect service health
docker-compose -f docker-compose.prod.yml exec nginx wget --no-verbose --tries=1 --spider http://localhost/health
```

## Troubleshooting

### Backend Fails to Start

**Symptom**: Backend container exits immediately

**Solution**:
1. Check logs: `docker-compose logs backend`
2. Verify `.env` file has SSI credentials
3. Ensure PORT 8000 isn't already in use

### Nginx Shows "Bad Gateway" (502)

**Symptom**: `curl http://localhost/api/*` returns 502

**Cause**: Backend hasn't started or health check failed

**Solution**:
```bash
# Wait for backend to be healthy
docker-compose -f docker-compose.prod.yml exec backend python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Check Nginx logs
docker-compose -f docker-compose.prod.yml logs nginx
```

### WebSocket Connection Fails

**Symptom**: Frontend can't connect to `/ws/market`

**Verify**:
1. Nginx includes WebSocket upgrade headers (`proxy_set_header Upgrade $http_upgrade`)
2. Backend health check passes
3. WS_AUTH_TOKEN not required (or client provides correct token)

```bash
# Test WebSocket directly
docker-compose -f docker-compose.prod.yml exec backend curl -i \
  -N -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  http://localhost:8000/ws/market
```

### Frontend Shows Blank Page

**Symptom**: Frontend loads but no content

**Cause**: Static build failed or Nginx misconfigured

**Solution**:
```bash
# Check frontend logs
docker-compose -f docker-compose.prod.yml logs frontend

# Verify static files exist
docker-compose -f docker-compose.prod.yml exec frontend ls -la /usr/share/nginx/html/dist/
```

## Scaling

### Horizontal Scaling (Multiple Backends)

To scale backend services:

```yaml
# docker-compose.prod.yml
services:
  backend-1:
    build: ./backend
    # ... backend config
  backend-2:
    build: ./backend
    # ... backend config (different container_name, expose port)

  nginx:
    # Update upstream:
    # upstream backend {
    #   server backend-1:8000;
    #   server backend-2:8000;
    # }
```

Use Nginx round-robin (default) to distribute traffic.

### Vertical Scaling (Resource Limits)

Adjust memory/CPU limits in `docker-compose.prod.yml`:

```yaml
deploy:
  resources:
    limits:
      memory: 2G
      cpus: '2'
```

## Security Best Practices

1. **Non-Root User**: Backend runs as `stock` user (UID 1000)
2. **Secrets**: Store credentials in `.env` (add to `.gitignore`)
3. **Health Checks**: Enable automatic restart on failure
4. **WebSocket Auth**: Set `WS_AUTH_TOKEN` for production (disable anonymous access)
5. **CORS**: Configure `CORS_ORIGINS` to trusted domains only
6. **Network**: Containers communicate via internal network (no port exposure)

## Performance Tuning

### Backend

- `uvloop`: Already enabled (10-40% faster than asyncio)
- `WS_THROTTLE_INTERVAL_MS`: Default 500ms (tune per load)
- Memory limits: Monitor via `docker stats`

### Frontend

- Build: Static bundle cached (immutable after build)
- Gzip: Enabled in Nginx (compression_level 6)
- Cache-Control: 1-hour expiry for versioned assets

### Nginx

- Connection pooling to backend (keepalive)
- Proxy timeouts: 60s (adjustable in nginx.conf)

## Production Checklist

- [ ] `.env` configured with real SSI credentials
- [ ] `CORS_ORIGINS` restricted to production domain
- [ ] `WS_AUTH_TOKEN` set (if needed)
- [ ] `DEBUG=false` in `.env`
- [ ] Health checks passing
- [ ] Logs configured for centralized collection
- [ ] Resource limits tested under load
- [ ] SSL/TLS configured (if using HTTPS)
- [ ] Backup/restore procedures documented

## Further Reading

- [System Architecture](./system-architecture.md) - Full deployment architecture diagram
- [Codebase Summary](./codebase-summary.md) - File inventory and structure
- [.env.example](./.env.example) - Full environment variable reference
