---
title: "Production Docker Deployment"
description: "Multi-stage Dockerfiles, nginx reverse proxy, production-ready compose config"
status: complete
priority: P2
effort: 2h
branch: master
tags: [docker, nginx, deployment, production]
created: 2026-02-10
reviewed: 2026-02-10
---

# Production Docker Deployment

## Overview

Convert existing Docker setup to production-ready deployment with multi-stage builds, dedicated nginx reverse proxy, and proper environment configuration.

**Current:** Basic Dockerfiles with embedded proxy in frontend container
**Target:** Backend multi-stage + frontend static-only + dedicated nginx reverse proxy

## Architecture

```
nginx:80 (entry point)
├── / → frontend:80 (static files, no proxy)
├── /api/ → backend:8000 (FastAPI REST)
└── /ws → backend:8000 (WebSocket with upgrade headers)
```

## Files to Create/Modify

**Create:**
- `nginx/nginx.conf` - dedicated reverse proxy config
- `docker-compose.prod.yml` - production compose (no PostgreSQL/Redis)
- `backend/.dockerignore`
- `frontend/.dockerignore`
- `.env.example` - documented environment variables

**Modify:**
- `backend/Dockerfile` - multi-stage build
- `frontend/Dockerfile` - remove proxy config, static-only nginx
- `frontend/nginx.conf` - simplify to static serving only

## Implementation Steps

### 1. Backend Multi-stage Dockerfile

**File:** `backend/Dockerfile`

```dockerfile
# Builder stage: install dependencies
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install to site-packages
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Runtime stage: minimal production image
FROM python:3.12-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Production uvicorn: 4 workers, uvloop event loop
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4", \
     "--loop", "uvloop", \
     "--log-level", "info"]
```

**Rationale:**
- Multi-stage reduces image size (no gcc, build tools in runtime)
- 4 workers for production load (adjust based on CPU cores)
- uvloop for better async performance
- Non-root user for security

### 2. Frontend Static-only Dockerfile

**File:** `frontend/Dockerfile`

```dockerfile
# Build stage: compile React app
FROM node:20-slim AS build

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm ci --only=production=false

# Build production bundle
COPY . .
RUN npm run build

# Runtime stage: serve static files only
FROM nginx:alpine

# Copy built static files
COPY --from=build /app/dist /usr/share/nginx/html

# Simple nginx config for static files only
RUN echo 'server { \n\
    listen 80; \n\
    root /usr/share/nginx/html; \n\
    index index.html; \n\
    location / { \n\
        try_files $uri $uri/ /index.html; \n\
    } \n\
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

**Changes:**
- Remove proxy config (moved to dedicated nginx)
- `npm ci` for reproducible builds
- Inline simple static config (no COPY nginx.conf needed)

### 3. Dedicated Nginx Reverse Proxy

**File:** `nginx/nginx.conf`

```nginx
upstream backend {
    server backend:8000;
}

upstream frontend {
    server frontend:80;
}

server {
    listen 80;
    server_name _;

    # Frontend static files
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Backend REST API
    location /api/ {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Increase timeouts for long-running requests
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # WebSocket endpoints
    location /ws {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # WebSocket timeout: 24 hours
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }

    # Health check endpoint (no auth required)
    location = /health {
        proxy_pass http://backend;
        access_log off;
    }
}
```

**Features:**
- Upstream definitions for better load balancing
- WebSocket upgrade headers for /ws paths
- 24-hour WS timeout (persistent connections)
- Separate timeouts for API vs WS
- Health check bypass for monitoring

### 4. Production Docker Compose

**File:** `docker-compose.prod.yml`

```yaml
version: '3.8'

services:
  nginx:
    image: nginx:alpine
    container_name: stock-tracker-nginx
    ports:
      - "80:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      backend:
        condition: service_healthy
      frontend:
        condition: service_started
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost/health"]
      interval: 10s
      timeout: 5s
      retries: 3
    networks:
      - app-network

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: stock-tracker-backend
    expose:
      - "8000"
    env_file:
      - .env
    environment:
      - APP_HOST=0.0.0.0
      - APP_PORT=8000
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 15s
      timeout: 5s
      retries: 3
      start_period: 30s
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 512M
    networks:
      - app-network

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: stock-tracker-frontend
    expose:
      - "80"
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 128M
        reservations:
          memory: 64M
    networks:
      - app-network

networks:
  app-network:
    driver: bridge
```

**Key Differences from Dev Compose:**
- No PostgreSQL/Redis services (external DB in production)
- nginx service as entry point on port 80
- Backend/frontend use `expose` (not `ports`) - only nginx is public
- Resource limits and reservations
- Health checks with proper start_period
- Single `.env` file at root (not backend/.env)

### 5. Backend .dockerignore

**File:** `backend/.dockerignore`

```
__pycache__
*.pyc
*.pyo
*.pyd
.Python
*.so
*.egg
*.egg-info
dist
build
venv
.venv
env
ENV
.env
.env.*
.git
.gitignore
.pytest_cache
.coverage
htmlcov
.mypy_cache
.ruff_cache
*.log
*.db
*.sqlite
*.sqlite3
.DS_Store
tests
docs
*.md
```

### 6. Frontend .dockerignore

**File:** `frontend/.dockerignore`

```
node_modules
dist
.git
.gitignore
.env
.env.*
*.log
.DS_Store
.vscode
.idea
coverage
*.test.ts
*.test.tsx
*.spec.ts
*.spec.tsx
README.md
```

### 7. Root Environment Example

**File:** `.env.example`

```bash
# ============================================
# SSI FastConnect (REQUIRED)
# ============================================
SSI_CONSUMER_ID=your_consumer_id_here
SSI_CONSUMER_SECRET=your_consumer_secret_here
SSI_BASE_URL=https://fc-data.ssi.com.vn/
SSI_STREAM_URL=https://fc-data.ssi.com.vn/

# ============================================
# Database (REQUIRED in production)
# ============================================
# Format: postgresql://user:password@host:port/database
DATABASE_URL=postgresql://stock:stock@timescaledb:5432/stock_tracker

# ============================================
# Application
# ============================================
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=false
LOG_LEVEL=INFO

# ============================================
# CORS (comma-separated origins)
# ============================================
CORS_ORIGINS=http://localhost,https://yourdomain.com

# ============================================
# Market Data Settings
# ============================================
# Channel R (foreign investor) update interval for speed calculation
CHANNEL_R_INTERVAL_MS=1000

# Force specific futures contract (leave empty for auto-detection)
# Example: VN30F2603
FUTURES_OVERRIDE=

# ============================================
# WebSocket Configuration
# ============================================
# Per-channel throttle interval (milliseconds)
WS_THROTTLE_INTERVAL_MS=500

# Heartbeat settings (seconds)
WS_HEARTBEAT_INTERVAL=30.0
WS_HEARTBEAT_TIMEOUT=10.0

# Per-client message queue size
WS_QUEUE_SIZE=50

# ============================================
# WebSocket Security
# ============================================
# Optional token for WS authentication (empty = disabled)
# Generate with: openssl rand -hex 32
WS_AUTH_TOKEN=

# Max concurrent WebSocket connections per IP
WS_MAX_CONNECTIONS_PER_IP=5
```

### 8. Simplify Frontend nginx.conf (Optional Cleanup)

Since proxy is now in dedicated nginx, remove proxy config from `frontend/nginx.conf`:

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    # SPA fallback for client-side routing
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

Or remove this file entirely and use inline config in Dockerfile (as shown in step 2).

## Todo List

- [x] Update `backend/Dockerfile` with multi-stage build
- [x] Update `frontend/Dockerfile` to static-only nginx
- [x] Create `nginx/nginx.conf` for reverse proxy
- [x] Create `docker-compose.prod.yml` with nginx service
- [x] Create `backend/.dockerignore`
- [x] Create `frontend/.dockerignore`
- [x] Create root `.env.example` with all vars documented
- [x] Code review completed (see reports/code-review-260210-1048-docker-deployment.md)
- [x] Verify uvloop in backend/requirements.txt (✅ included in uvicorn[standard])
- [ ] Test build: `docker-compose -f docker-compose.prod.yml build`
- [ ] Test run: `docker-compose -f docker-compose.prod.yml up`
- [ ] Verify nginx routing: curl http://localhost/ (frontend)
- [ ] Verify API routing: curl http://localhost/api/health
- [ ] Verify WS routing: wscat -c ws://localhost/ws/market
- [ ] Check container logs for errors
- [ ] Verify resource limits: `docker stats`
- [ ] Add gzip + cache headers to frontend/nginx.conf (performance optimization)
- [ ] Document deployment steps in README or deployment guide

**Progress:** 9/17 tasks (53%) — All code deliverables complete, testing + optimizations pending

## Success Criteria

**Build:**
- All images build without errors
- Multi-stage backend image < 200MB
- Frontend image < 50MB

**Runtime:**
- nginx accessible on port 80
- Frontend serves React app at /
- API endpoints respond at /api/*
- WebSocket connects at /ws/*
- Health checks pass for all services
- No CORS errors in browser console

**Security:**
- Backend runs as non-root user
- No .env files in images (verified with `docker history`)
- WS auth token enforced if configured
- Rate limiting works (max connections per IP)

**Performance:**
- 4 uvicorn workers handle concurrent load
- WebSocket stays connected for > 1 hour
- nginx reverse proxy adds < 5ms latency

## Production Deployment Steps

1. Copy `.env.example` to `.env` and fill in secrets
2. Build images: `docker-compose -f docker-compose.prod.yml build`
3. Start services: `docker-compose -f docker-compose.prod.yml up -d`
4. Check logs: `docker-compose -f docker-compose.prod.yml logs -f`
5. Verify health: `curl http://localhost/health`
6. Monitor: `docker stats stock-tracker-nginx stock-tracker-backend stock-tracker-frontend`

## Security Considerations

**Environment Variables:**
- Never commit `.env` to git (already in `.gitignore`)
- Use secure SSI credentials in production
- Generate strong `WS_AUTH_TOKEN` for WebSocket auth
- Restrict `CORS_ORIGINS` to production domains only

**Container Security:**
- Backend runs as non-root user (UID 1000)
- nginx runs as nginx user (default in alpine image)
- Resource limits prevent DoS via memory exhaustion
- Health checks enable auto-restart on failures

**Network Security:**
- Only nginx exposes port 80 to host
- Backend/frontend use internal Docker network
- WebSocket rate limiting per IP
- API timeout prevents hanging connections

## Next Steps

After deployment verified:
- Add HTTPS with Let's Encrypt (nginx SSL config)
- Set up log aggregation (mount volumes for nginx/uvicorn logs)
- Configure monitoring (Prometheus + Grafana)
- Add backup strategy for PostgreSQL (if self-hosted)
- Document scaling strategy (horizontal: more backend replicas)
