# Deployment Guide

## Quick Start

```bash
# Clone and configure
git clone <repo-url> && cd stock-tracker
cp .env.example .env
# Edit .env — set SSI_CONSUMER_ID and SSI_CONSUMER_SECRET

# Deploy everything (app + monitoring)
./scripts/deploy.sh

# Verify
curl http://localhost/health
```

## Architecture

```
Internet :80
    │
    ▼
┌─────────────────────────────────────────────────┐
│  Nginx (reverse proxy)                          │
│  / → Frontend | /api/* → Backend | /ws/* → WS   │
└───────┬──────────────────┬──────────────────────┘
        │                  │
   ┌────▼────┐      ┌─────▼──────┐
   │Frontend │      │  Backend   │──→ SSI FastConnect
   │React+Nginx│    │FastAPI 8000│
   │ 128MB   │      │  1GB max   │
   └─────────┘      └─────┬──────┘
                           │
                    ┌──────▼──────┐
                    │ TimescaleDB │
                    │  PG16 1GB   │
                    └─────────────┘

Monitoring:  Prometheus :9090 → Grafana :3000
             Node Exporter :9100
```

## Services

| Service | Image | Port | Memory | Health Check |
|---------|-------|------|--------|--------------|
| nginx | `nginx:alpine` | 80 (external) | — | `wget /health` every 10s |
| backend | `backend/Dockerfile` | 8000 (internal) | 512MB-1GB | `python urllib /health` every 15s |
| timescaledb | `timescale/timescaledb:latest-pg16` | 5432 (internal) | 512MB-1GB | `pg_isready` every 5s |
| frontend | `frontend/Dockerfile` | 80 (internal) | 64MB-128MB | — |
| prometheus | `prom/prometheus:v2.53.0` | 9090 (external) | 512MB | — |
| grafana | `grafana/grafana:11.1.0` | 3000 (external) | 256MB | — |
| node-exporter | `prom/node-exporter:v1.8.1` | 9100 (internal) | 64MB | — |

## Environment Variables

### Required

```bash
SSI_CONSUMER_ID=your_id_here
SSI_CONSUMER_SECRET=your_secret_here
```

### Database

```bash
DATABASE_URL=postgresql://stock:stock@timescaledb:5432/stock_tracker
POSTGRES_USER=stock           # TimescaleDB container user
POSTGRES_PASSWORD=stock       # TimescaleDB container password
POSTGRES_DB=stock_tracker     # TimescaleDB database name
DB_POOL_MIN=2
DB_POOL_MAX=10
```

### Application

```bash
APP_HOST=0.0.0.0
APP_PORT=8000
LOG_LEVEL=INFO                # DEBUG, INFO, WARNING, ERROR
DEBUG=false
CORS_ORIGINS=http://localhost,https://yourdomain.com
```

### WebSocket

```bash
WS_AUTH_TOKEN=                # Empty = no auth (dev only)
WS_MAX_CONNECTIONS_PER_IP=5
WS_THROTTLE_INTERVAL_MS=500
WS_HEARTBEAT_INTERVAL=30.0
WS_HEARTBEAT_TIMEOUT=10.0
WS_QUEUE_SIZE=50
```

### Market

```bash
CHANNEL_R_INTERVAL_MS=1000    # Foreign investor update frequency
FUTURES_OVERRIDE=             # Override active contract e.g. VN30F2603
```

### Monitoring

```bash
GF_SECURITY_ADMIN_USER=admin
GF_SECURITY_ADMIN_PASSWORD=admin    # Change in production!
GF_USERS_ALLOW_SIGN_UP=false
```

## Docker Commands

### Lifecycle

```bash
# Start all services (detached)
docker compose -f docker-compose.prod.yml up -d

# Stop all services
docker compose -f docker-compose.prod.yml down

# Stop + remove volumes (data loss!)
docker compose -f docker-compose.prod.yml down -v

# Restart single service
docker compose -f docker-compose.prod.yml restart backend
```

### Builds

```bash
# Rebuild all images
docker compose -f docker-compose.prod.yml build

# Rebuild without cache (after Dockerfile changes)
docker compose -f docker-compose.prod.yml build --no-cache

# Rebuild + restart
docker compose -f docker-compose.prod.yml up -d --build
```

### Logs

```bash
# All services
docker compose -f docker-compose.prod.yml logs -f

# Single service (last 100 lines)
docker compose -f docker-compose.prod.yml logs -f --tail=100 backend

# Check container status
docker compose -f docker-compose.prod.yml ps
```

## Health Checks

```bash
# Application health (includes DB status)
curl http://localhost/health
# → {"status": "healthy", "database": "connected", "uptime_seconds": 3600}

# API endpoint
curl http://localhost/api/market/snapshot | head -c 200

# Prometheus targets
curl http://localhost:9090/api/v1/targets

# Grafana health
curl http://localhost:3000/api/health
```

## Startup Order

Docker Compose enforces this dependency chain:

```
1. timescaledb   (waits: pg_isready)
2. backend       (waits: timescaledb healthy)
3. frontend      (starts immediately)
4. nginx         (waits: backend healthy + frontend started)
5. prometheus    (starts immediately, scrapes backend /metrics)
6. grafana       (waits: prometheus)
7. node-exporter (starts immediately)
```

Backend starts without DB (graceful degradation) — real-time features work, history endpoints return 503.

## Nginx Routing

| Path | Upstream | Notes |
|------|----------|-------|
| `/` | `frontend:80` | React SPA (static files) |
| `/api/*` | `backend:8000` | REST endpoints, 60s timeout |
| `/ws/*` | `backend:8000` | WebSocket upgrade, 24h timeout |
| `/health` | `backend:8000` | No access log |

## SSL/TLS (Production)

For HTTPS, add to `nginx/nginx.conf`:

```nginx
server {
    listen 443 ssl;
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    # ... existing location blocks ...
}

server {
    listen 80;
    return 301 https://$host$request_uri;
}
```

Mount certificates in `docker-compose.prod.yml`:
```yaml
nginx:
  volumes:
    - ./ssl:/etc/nginx/ssl:ro
```

## Volumes

| Volume | Service | Purpose |
|--------|---------|---------|
| `pgdata` | timescaledb | PostgreSQL data (persistent) |
| `prometheus-data` | prometheus | Metrics (15d retention) |
| `grafana-data` | grafana | Dashboards + settings |

## Troubleshooting

### Backend won't start

```bash
docker compose -f docker-compose.prod.yml logs backend
# Common: missing SSI credentials, port conflict, DB connection
```

### 502 Bad Gateway

Backend not ready yet. Check health:
```bash
docker compose -f docker-compose.prod.yml exec backend \
  python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
```

### WebSocket connection fails

1. Verify Nginx includes upgrade headers (check `nginx/nginx.conf`)
2. Check `WS_AUTH_TOKEN` — empty means no auth required
3. Check rate limit: `WS_MAX_CONNECTIONS_PER_IP`

### Database connection issues

```bash
# Check TimescaleDB logs
docker compose -f docker-compose.prod.yml logs timescaledb

# Test connection
docker compose -f docker-compose.prod.yml exec timescaledb \
  psql -U stock -d stock_tracker -c "SELECT 1"
```

### Frontend blank page

```bash
docker compose -f docker-compose.prod.yml exec frontend \
  ls -la /usr/share/nginx/html/dist/
```

## Production Checklist

- [ ] `.env` configured with real SSI credentials
- [ ] `CORS_ORIGINS` set to production domain
- [ ] `WS_AUTH_TOKEN` set for WebSocket security
- [ ] `DEBUG=false`
- [ ] `GF_SECURITY_ADMIN_PASSWORD` changed from default
- [ ] SSL/TLS configured
- [ ] Firewall: only expose ports 80/443 externally
- [ ] TimescaleDB password changed from default
- [ ] Backup strategy for `pgdata` volume
- [ ] Log aggregation configured
- [ ] Resource limits tested under load

## Load Testing

```bash
# Quick test (10 users, 30s)
./scripts/run-load-test.sh --users 10 --duration 30

# Full test via Docker (Locust UI at :8089)
docker compose -f docker-compose.test.yml up --scale locust-worker=4
```

See [monitoring.md](monitoring.md) for dashboards and alerting.
