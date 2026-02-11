---
title: "Load Testing Suite for VN Stock Tracker"
description: "Locust-based load testing for REST + WebSocket endpoints with Docker integration"
status: complete
priority: P1
effort: 4h
branch: master
tags: [load-testing, locust, websocket, performance, phase-8, completed-2026-02-11]
created: 2026-02-11
completed: 2026-02-11
---

# Load Testing Suite — Implementation Plan

## Context

Phase 8 load testing for VN Stock Tracker backend. All REST and WS endpoints are in-memory (single-worker FastAPI), rate-limited at 5 WS connections/IP by default.

**Key constraint**: Rate limiter (`WS_MAX_CONNECTIONS_PER_IP=5`) must be bypassed during load tests. Single-worker means no Redis/shared state needed.

## Phase Overview

| # | Phase | Effort | Status |
|---|-------|--------|--------|
| 1 | [Locust core + helpers](#phase-1) | 1.5h | complete |
| 2 | [Scenario files](#phase-2) | 1.5h | complete |
| 3 | [Docker + runner](#phase-3) | 0.5h | complete |
| 4 | [CI integration (optional)](#phase-4) | 0.5h | complete |

## Dependencies

- Backend healthy (`/health` returns 200)
- `locust>=2.32` + `websockets>=14.0` (already in requirements.txt)
- Docker Compose for containerized runs

---

## Phase 1: Locust Core + Helpers

See: [phase-01-locust-core-and-helpers.md](./phase-01-locust-core-and-helpers.md)

## Phase 2: Scenario Files

See: [phase-02-scenario-files.md](./phase-02-scenario-files.md)

## Phase 3: Docker + Runner Script

See: [phase-03-docker-and-runner.md](./phase-03-docker-and-runner.md)

## Phase 4: CI Integration (Optional)

See: [phase-04-ci-integration.md](./phase-04-ci-integration.md)
