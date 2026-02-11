# Phase 4: CI Integration (Optional)

## Context Links

- [CI Workflow](/Users/minh/Projects/stock-tracker/.github/workflows/ci.yml) — existing 3-job pipeline
- [Phase 3 — Docker + Runner](./phase-03-docker-and-runner.md) — `docker-compose.test.yml`, runner script
- [Phase 2 — Assertions](./phase-02-scenario-files.md) — `assertions.py` with threshold checks

## Overview

- **Priority**: P3
- **Status**: pending
- **Effort**: 0.5h

Optional GitHub Actions job that runs a lightweight smoke-level load test on PRs. Full load tests remain manual (too resource-intensive for CI).

## Key Insights

1. **CI runners have limited resources** — GitHub Actions runners have 2 vCPU, 7GB RAM. Cannot run 500+ concurrent users.
2. **Smoke test only**: Run 10 REST users + 5 WS users for 30s. Validates load test code works, not production capacity.
3. **Existing CI has 3 jobs**: backend, frontend, docker-build. Load test would be job 4, depends on docker-build.
4. **Assertions still apply**: Even at 10 users, p95/p99 thresholds should hold on healthy code.

## Requirements

### Functional
- New `load-test` job in CI pipeline
- Runs after docker-build succeeds
- Starts backend container, runs Locust headless with minimal users
- Fails build if assertions breach thresholds

### Non-functional
- Job timeout: 5 minutes max
- No secrets needed (auth disabled, no SSI credentials for load test)
- Runs only on `master`/`main` push (skip PRs to save CI minutes)

## Architecture

```
.github/workflows/ci.yml
  └── job: load-test (depends: docker-build)
      ├── Start backend via docker compose
      ├── Wait for health check
      ├── Run locust headless (10 users, 30s)
      └── Check exit code (assertions.py)
```

## Implementation Steps

### Step 1: Add load-test job to `ci.yml`

Append after `docker-build` job:

```yaml
  load-test:
    name: Load Test (Smoke)
    runs-on: ubuntu-latest
    needs: docker-build
    if: github.ref == 'refs/heads/master' || github.ref == 'refs/heads/main'
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4

      - name: Start backend
        run: |
          docker compose -f docker-compose.yml up -d backend timescaledb redis
        env:
          WS_MAX_CONNECTIONS_PER_IP: 10000
          WS_AUTH_TOKEN: ""
          SSI_CONSUMER_ID: "test"
          SSI_CONSUMER_SECRET: "test"

      - name: Wait for backend health
        run: |
          for i in $(seq 1 30); do
            if curl -sf http://localhost:8000/health; then
              echo "Backend healthy"
              exit 0
            fi
            sleep 2
          done
          echo "Backend failed to start"
          exit 1

      - name: Install locust
        run: pip install locust>=2.32 websockets>=14.0

      - name: Run smoke load test
        run: |
          locust -f backend/tests/load/locustfile.py \
            --host http://localhost:8000 \
            --headless \
            -u 10 -r 5 -t 30s \
            --csv backend/tests/load/results/ci-smoke
        env:
          WS_MAX_CONNECTIONS_PER_IP: 10000

      - name: Upload results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: load-test-results
          path: backend/tests/load/results/

      - name: Cleanup
        if: always()
        run: docker compose down -v
```

**Notes**:
- `SSI_CONSUMER_ID/SECRET` set to dummy values — backend starts but SSI stream fails gracefully (no live data, endpoints return empty snapshots)
- `needs: docker-build` ensures images exist
- `if: github.ref == 'refs/heads/master'` — only on merge to main, not PRs
- Results uploaded as artifact for debugging

## Todo List

- [ ] Add `load-test` job to `.github/workflows/ci.yml`
- [ ] Test locally: `act -j load-test` (or manual push to branch)
- [ ] Verify job skips on PR, runs on master push
- [ ] Confirm assertions.py exit code propagates to CI

## Success Criteria

- CI job runs in < 3 minutes
- Locust stats CSV uploaded as artifact
- Job passes with 10 users / 30s (no threshold breaches)
- Job does not run on PRs (saves CI minutes)

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Backend fails without SSI credentials | Medium | Backend designed for graceful startup without SSI — endpoints return empty data. Load test measures infra, not data. |
| CI runner resource exhaustion | Low | Only 10 users for 30s — minimal load |
| Flaky due to CI environment variance | Medium | Generous thresholds (100ms WS, 200ms REST) should hold on CI runners |

## Security Considerations

- Dummy SSI credentials in CI — never real secrets
- No auth token needed for load test
- Results artifact contains latency stats only, no sensitive data
