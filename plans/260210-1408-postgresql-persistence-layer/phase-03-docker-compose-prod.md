# Phase 3: Docker Compose Prod - TimescaleDB

## Overview
- **Priority:** P2
- **Status:** complete
- **Est:** 30 min

Add TimescaleDB service to `docker-compose.prod.yml`. Currently prod compose has nginx, backend, frontend but no database -- backend expects an external DB. This phase makes prod self-contained.

## Key Insights
- Dev compose (`docker-compose.yml`) already has a working TimescaleDB service -- reuse pattern
- Prod compose uses nginx reverse proxy (different from dev which exposes backend port directly)
- Backend in prod uses `.env` file (not inline `environment:` block for secrets)
- Need `depends_on` with health check so backend waits for DB

## Related Code Files

**Modify:**
- `docker-compose.prod.yml` — add timescaledb service, pgdata volume, backend depends_on

**Reference (read-only):**
- `docker-compose.yml` — dev compose with working TimescaleDB config

## Implementation Steps

### Step 1: Add TimescaleDB service
Add to `docker-compose.prod.yml` services section:

```yaml
  timescaledb:
    image: timescale/timescaledb:latest-pg16
    container_name: stock-timescaledb
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-stock}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-stock}
      POSTGRES_DB: ${POSTGRES_DB:-stock_tracker}
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
        reservations:
          memory: 512M
    networks:
      - app-network
```

Note: Uses env var substitution for credentials with defaults, allowing override via `.env` without hardcoding.

### Step 2: Add pgdata volume
Add to `volumes:` section at bottom:

```yaml
volumes:
  pgdata:
```

### Step 3: Update backend depends_on
Add `timescaledb` dependency to backend service:

```yaml
  backend:
    depends_on:
      timescaledb:
        condition: service_healthy
    environment:
      - DATABASE_URL=postgresql://${POSTGRES_USER:-stock}:${POSTGRES_PASSWORD:-stock}@timescaledb:5432/${POSTGRES_DB:-stock_tracker}
```

Keep existing `env_file: - .env` for SSI credentials. The explicit `environment:` block overrides `DATABASE_URL` to use the internal Docker network hostname `timescaledb`.

### Step 4: Expose port conditionally
Do NOT expose TimescaleDB port 5432 to host in prod -- internal network only. Dev compose exposes it for local tooling; prod does not.

## Todo List
- [ ] Add `timescaledb` service to `docker-compose.prod.yml`
- [ ] Add `pgdata` volume
- [ ] Add `depends_on: timescaledb` + `DATABASE_URL` env to backend
- [ ] Verify `docker compose -f docker-compose.prod.yml config` validates

## Success Criteria
- `docker compose -f docker-compose.prod.yml config` parses without errors
- TimescaleDB starts with health check, backend waits for it
- No port 5432 exposed to host in prod
- DB credentials configurable via env vars (not hardcoded)

## Risk Assessment
- **Data persistence** — `pgdata` named volume survives `docker compose down` (only lost with `down -v`)
- **Init scripts** — `db/migrations/` mounted to `initdb.d` only runs on first DB creation (empty pgdata). For existing DBs, use Alembic (Phase 2)
