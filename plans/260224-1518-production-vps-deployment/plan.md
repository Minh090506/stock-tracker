# Production VPS Deployment Plan

**Created**: 2026-02-24
**Approach**: Hetzner VPS + Cloudflare SSL + GitHub Actions CD
**Cost**: ~EUR 4/mo (Hetzner CX22) + Cloudflare free tier
**Effort**: ~4 hours total (4 phases)

## Phase Overview

| # | Phase | Status | Est. | Files |
|---|-------|--------|------|-------|
| 1 | VPS Setup & Docker | Pending | 45min | Manual (SSH) |
| 2 | Domain + Cloudflare SSL | Pending | 30min | nginx.conf, docker-compose.prod.yml |
| 3 | GitHub Actions CD Pipeline | Pending | 1h | ci.yml, deploy-vps.sh |
| 4 | DB Backup + Production Hardening | Pending | 1h | backup.sh, docker-compose.prod.yml, .env |

## Phases

- [Phase 1: VPS Setup & Docker](./phase-01-vps-setup-docker.md)
- [Phase 2: Domain + Cloudflare SSL](./phase-02-domain-cloudflare-ssl.md)
- [Phase 3: GitHub Actions CD Pipeline](./phase-03-github-actions-cd.md)
- [Phase 4: DB Backup + Production Hardening](./phase-04-backup-hardening.md)

## Architecture (After Deployment)

```
User → Cloudflare (SSL/CDN) → Hetzner VPS :80
                                  │
                                  ├── Nginx → Frontend (static)
                                  ├── Nginx → Backend :8000 (REST + WS)
                                  ├── TimescaleDB :5432
                                  ├── Prometheus :9090
                                  └── Grafana :3000

GitHub push → CI tests → Build images → SSH deploy → docker compose up
                                                         │
Cron daily 15:35 VN → pg_dump → gzip → keep 7 days      │
```

## Key Decisions
- **No container registry** — build images directly on VPS (simpler, no registry cost)
- **Cloudflare proxy mode** — free SSL, DDoS protection, caching for static assets
- **SSH-based deploy** — GitHub Actions SSH into VPS, git pull, rebuild. Simple & reliable.
- **No Watchtower** — explicit deploys only (safer for a trading app)
- **Monitoring ports internal only** — Prometheus/Grafana not exposed to internet
