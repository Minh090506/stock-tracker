# Phase 3: Docker + Runner Script

## Context Links

- [docker-compose.yml](/Users/minh/Projects/stock-tracker/docker-compose.yml) — dev compose with backend, timescaledb, redis, frontend
- [docker-compose.prod.yml](/Users/minh/Projects/stock-tracker/docker-compose.prod.yml) — production compose with nginx
- [Phase 1 — Locust Core](./phase-01-locust-core-and-helpers.md) — locustfile entry point
- [Phase 2 — Scenarios](./phase-02-scenario-files.md) — scenario files + assertions

## Overview

- **Priority**: P1
- **Status**: pending
- **Effort**: 0.5h

Create `docker-compose.test.yml` for Locust container and a shell runner script for convenient execution.

## Key Insights

1. **Locust Docker image**: Official `locustio/locust` image available. Mount test files as volume.
2. **Network**: Locust container must join `app-network` to reach backend at `backend:8000`.
3. **Rate limit override**: Pass `WS_MAX_CONNECTIONS_PER_IP=10000` to backend service in test compose override.
4. **Results**: Locust can export CSV stats via `--csv` flag. Mount output directory for persistence.

## Requirements

### Functional
- `docker-compose.test.yml` with Locust service on same network as backend
- Runner script with scenario selection, user count, duration params
- CSV results output to `backend/tests/load/results/`

### Non-functional
- Script must be executable (`chmod +x`)
- Works with both local and Docker backend
- Clean error messages on missing dependencies

## Architecture

```
docker-compose.test.yml          # Locust service + backend override (rate limit off)
scripts/
└── run-load-test.sh             # CLI wrapper for locust headless/UI runs
backend/tests/load/results/      # CSV output (gitignored)
```

## Related Code Files

### Files to Create

| File | Purpose | LOC est. |
|------|---------|----------|
| `docker-compose.test.yml` | Locust container + backend rate limit override | ~45 |
| `scripts/run-load-test.sh` | Shell script for running load tests | ~80 |
| `backend/tests/load/results/.gitkeep` | Placeholder for results directory | 0 |

### Files to Modify

| File | Change |
|------|--------|
| `.gitignore` | Add `backend/tests/load/results/*.csv` |

## Implementation Steps

### Step 1: Create `docker-compose.test.yml`

```yaml
# Load testing compose — extends base docker-compose.yml
# Usage: docker compose -f docker-compose.yml -f docker-compose.test.yml up locust
services:
  backend:
    environment:
      # Disable rate limiting for load tests
      - WS_MAX_CONNECTIONS_PER_IP=10000
      - WS_AUTH_TOKEN=

  locust:
    image: locustio/locust:2.32.4
    container_name: stock-locust
    ports:
      - "8089:8089"
    volumes:
      - ./backend/tests:/tests:ro
    environment:
      - LOCUST_HOST=http://backend:8000
      - LOCUST_LOCUSTFILE=/tests/load/locustfile.py
      - LOCUST_USERS=${LOCUST_USERS:-100}
      - LOCUST_SPAWN_RATE=${LOCUST_SPAWN_RATE:-10}
      - LOCUST_RUN_TIME=${LOCUST_RUN_TIME:-2m}
      - WS_AUTH_TOKEN=
    depends_on:
      backend:
        condition: service_healthy
    networks:
      - app-network
```

**Notes**:
- Overrides backend's `WS_MAX_CONNECTIONS_PER_IP` to 10000 (effectively disabled)
- Clears `WS_AUTH_TOKEN` so WS connections succeed without token
- Mounts `backend/tests` read-only at `/tests` in container
- Locust web UI at `http://localhost:8089`
- Env vars for headless config (users, spawn rate, duration)

### Step 2: Create `scripts/run-load-test.sh`

```bash
#!/usr/bin/env bash
# Run load tests against the stock-tracker backend.
#
# Usage:
#   scripts/run-load-test.sh [OPTIONS]
#
# Options:
#   --scenario SCENARIO   One of: all, rest, ws, burst, reconnect (default: all)
#   --users N             Number of concurrent users (default: 100)
#   --spawn-rate N        Users spawned per second (default: 10)
#   --duration TIME       Test duration, e.g. 2m, 60s (default: 2m)
#   --host URL            Target host (default: http://localhost:8000)
#   --web                 Launch Locust web UI instead of headless
#   --docker              Run via Docker Compose
#   --csv                 Export CSV results to backend/tests/load/results/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOAD_DIR="$PROJECT_DIR/backend/tests/load"
RESULTS_DIR="$LOAD_DIR/results"

# Defaults
SCENARIO="all"
USERS=100
SPAWN_RATE=10
DURATION="2m"
HOST="http://localhost:8000"
WEB_MODE=false
DOCKER_MODE=false
CSV_MODE=false

# Parse args
while [[ $# -gt 0 ]]; do
  case $1 in
    --scenario)  SCENARIO="$2";     shift 2 ;;
    --users)     USERS="$2";        shift 2 ;;
    --spawn-rate) SPAWN_RATE="$2";  shift 2 ;;
    --duration)  DURATION="$2";     shift 2 ;;
    --host)      HOST="$2";         shift 2 ;;
    --web)       WEB_MODE=true;     shift ;;
    --docker)    DOCKER_MODE=true;  shift ;;
    --csv)       CSV_MODE=true;     shift ;;
    *)           echo "Unknown option: $1"; exit 1 ;;
  esac
done

# Map scenario to locust class filter
case $SCENARIO in
  all)        CLASS_ARG="" ;;
  rest)       CLASS_ARG="RestUser" ;;
  ws)         CLASS_ARG="MarketStreamUser" ;;
  burst)      CLASS_ARG="BurstWsUser,BurstRestUser" ;;
  reconnect)  CLASS_ARG="ReconnectUser" ;;
  *)          echo "Unknown scenario: $SCENARIO"; exit 1 ;;
esac

echo "=== VN Stock Tracker Load Test ==="
echo "Scenario:   $SCENARIO"
echo "Users:      $USERS"
echo "Spawn rate: $SPAWN_RATE/s"
echo "Duration:   $DURATION"
echo "Host:       $HOST"
echo ""

if $DOCKER_MODE; then
  # Run via Docker Compose
  export LOCUST_USERS="$USERS"
  export LOCUST_SPAWN_RATE="$SPAWN_RATE"
  export LOCUST_RUN_TIME="$DURATION"

  if $WEB_MODE; then
    echo "Starting Locust web UI at http://localhost:8089"
    docker compose -f "$PROJECT_DIR/docker-compose.yml" \
                   -f "$PROJECT_DIR/docker-compose.test.yml" \
                   up locust
  else
    docker compose -f "$PROJECT_DIR/docker-compose.yml" \
                   -f "$PROJECT_DIR/docker-compose.test.yml" \
                   run --rm locust \
                   locust --headless \
                   -u "$USERS" -r "$SPAWN_RATE" -t "$DURATION"
  fi
  exit 0
fi

# Local mode — requires locust installed
if ! command -v locust &>/dev/null; then
  echo "Error: locust not found. Install: pip install locust>=2.32"
  exit 1
fi

# Override rate limit for local backend
export WS_MAX_CONNECTIONS_PER_IP=10000
export WS_AUTH_TOKEN=""

# Build locust command
CMD="locust -f $LOAD_DIR/locustfile.py --host $HOST"

if [[ -n "$CLASS_ARG" ]]; then
  CMD="$CMD --class-picker"
fi

if $CSV_MODE; then
  mkdir -p "$RESULTS_DIR"
  TIMESTAMP=$(date +%Y%m%d-%H%M%S)
  CMD="$CMD --csv $RESULTS_DIR/$SCENARIO-$TIMESTAMP"
fi

if $WEB_MODE; then
  echo "Starting Locust web UI at http://localhost:8089"
  eval "$CMD"
else
  CMD="$CMD --headless -u $USERS -r $SPAWN_RATE -t $DURATION"
  eval "$CMD"
fi
```

### Step 3: Create results directory

```bash
mkdir -p backend/tests/load/results
touch backend/tests/load/results/.gitkeep
```

### Step 4: Update `.gitignore`

Append:
```
# Load test results
backend/tests/load/results/*.csv
backend/tests/load/results/*.html
```

## Todo List

- [ ] Create `docker-compose.test.yml` (~45 LOC)
- [ ] Create `scripts/` directory
- [ ] Create `scripts/run-load-test.sh` (~80 LOC) and `chmod +x`
- [ ] Create `backend/tests/load/results/.gitkeep`
- [ ] Update `.gitignore` with load test results exclusion
- [ ] Test Docker mode: `scripts/run-load-test.sh --docker --users 10 --duration 30s`
- [ ] Test local mode: `scripts/run-load-test.sh --users 10 --duration 30s`

## Success Criteria

- `docker compose -f docker-compose.yml -f docker-compose.test.yml up locust` starts Locust UI
- `scripts/run-load-test.sh --users 10 --duration 30s` runs headless and exits cleanly
- `--csv` flag produces CSV files in `backend/tests/load/results/`
- Backend rate limit effectively disabled (10000 connections/IP)
- Locust web UI accessible at `http://localhost:8089` in Docker mode

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Locust Docker image version drift | Low | Pin `locustio/locust:2.32.4` in compose |
| Backend not healthy when locust starts | Medium | `depends_on` with `service_healthy` condition |
| Volume mount path mismatch | Low | Use absolute mount path `./backend/tests:/tests:ro` |

## Next Steps

After this phase, the full load testing suite is functional. Phase 4 (CI integration) is optional for automated regression.
