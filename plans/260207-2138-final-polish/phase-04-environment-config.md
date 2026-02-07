# Phase 4: Environment Config (Production)

## Context
- [config.py](/Users/minh/Projects/stock-tracker/backend/app/config.py) -- pydantic-settings, reads `.env`
- [.env.example](/Users/minh/Projects/stock-tracker/backend/.env.example) -- 5 vars: SSI creds, DB URL, channel interval, futures override
- [api-client.ts](/Users/minh/Projects/stock-tracker/frontend/src/utils/api-client.ts) -- hardcoded `BASE_URL = "/api"`
- [main.py](/Users/minh/Projects/stock-tracker/backend/app/main.py) -- CORS hardcoded to `http://localhost:5173`
- No `LOG_LEVEL` config exists
- No `.env.production` files exist

## Overview
- **Priority:** P2
- **Status:** pending
- **Effort:** 1h

Add production-ready config: CORS origins from env, log level config, frontend API base URL from Vite env, and `.env.production` templates.

## Key Insights
- CORS must be configurable (prod domain != localhost:5173)
- `LOG_LEVEL` controls verbosity in production (INFO by default, DEBUG for dev)
- Frontend uses Vite env vars (`VITE_*` prefix); `/api` relative path works with nginx proxy in Docker, so `VITE_API_BASE_URL` only needed for non-Docker dev
- Keep `.env.production` as templates (no secrets committed)

## Requirements

**Functional:**
- `CORS_ORIGINS` env var accepts comma-separated origins
- `LOG_LEVEL` env var configures Python logging
- Frontend `VITE_API_BASE_URL` overrides API base URL (optional, defaults to `/api`)
- `.env.production` files with production defaults

**Non-functional:**
- No secrets in committed files
- Backward compatible: existing `.env` still works

## Related Code Files

**Modify:**
- `backend/app/config.py` -- add `cors_origins`, `log_level`
- `backend/app/main.py` -- use `settings.cors_origins` for CORS, configure logging
- `frontend/src/utils/api-client.ts` -- read from `import.meta.env.VITE_API_BASE_URL`

**Create:**
- `backend/.env.production` -- production env template
- `frontend/.env.production` -- production Vite env

## Implementation Steps

### Step 1: Update backend config.py

Add new fields to Settings:

```python
class Settings(BaseSettings):
    # ... existing fields ...

    # CORS
    cors_origins: str = "http://localhost:5173"  # comma-separated

    # Logging
    log_level: str = "INFO"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
```

### Step 2: Update main.py CORS config

Replace hardcoded origin:

```python
import logging

# Configure logging early
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Step 3: Update frontend api-client.ts

```typescript
const BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";
```

This is backward compatible: defaults to `/api` (works with nginx proxy in Docker and Vite proxy in dev).

### Step 4: Create backend/.env.production

```env
# SSI FastConnect (required - fill in before deploying)
SSI_CONSUMER_ID=
SSI_CONSUMER_SECRET=

# Database
DATABASE_URL=postgresql://stock:stock@timescaledb:5432/stock_tracker

# CORS (comma-separated origins)
CORS_ORIGINS=http://localhost

# Logging
LOG_LEVEL=INFO

# Market config
CHANNEL_R_INTERVAL_MS=1000
FUTURES_OVERRIDE=
```

Note: `DATABASE_URL` uses `timescaledb` hostname (Docker service name).

### Step 5: Create frontend/.env.production

```env
# API base URL - defaults to /api (works with nginx proxy)
# Only override if API is on a different domain
# VITE_API_BASE_URL=/api
```

### Step 6: Update backend/.env.example

Add the new vars:

```env
SSI_CONSUMER_ID=your_consumer_id
SSI_CONSUMER_SECRET=your_consumer_secret
DATABASE_URL=postgresql://stock:stock@localhost:5432/stock_tracker
CORS_ORIGINS=http://localhost:5173
LOG_LEVEL=DEBUG
CHANNEL_R_INTERVAL_MS=1000
FUTURES_OVERRIDE=
```

## Todo List

- [ ] Add `cors_origins` and `log_level` to `config.py`
- [ ] Update `main.py` to use `settings.cors_origins_list` and configure logging
- [ ] Update `api-client.ts` to use `VITE_API_BASE_URL` env var
- [ ] Create `backend/.env.production`
- [ ] Create `frontend/.env.production`
- [ ] Update `backend/.env.example` with new vars

## Success Criteria
- `CORS_ORIGINS=http://a.com,http://b.com` results in both origins allowed
- `LOG_LEVEL=DEBUG` produces debug logs; `INFO` suppresses them
- Frontend works with default `/api` and with explicit `VITE_API_BASE_URL`
- No secrets in any committed file

## Risk Assessment
- **Low risk**: Additive config changes, all backward compatible
- **Edge case**: Empty `CORS_ORIGINS` should not crash; `cors_origins_list` filters empties
