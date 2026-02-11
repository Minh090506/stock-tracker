#!/usr/bin/env bash
# deploy.sh — One-command production deployment for VN Stock Tracker
# Usage: ./scripts/deploy.sh [--build | --restart | --stop | --logs | --status]
set -euo pipefail

COMPOSE_FILE="docker-compose.prod.yml"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

cd "$PROJECT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[deploy]${NC} $*"; }
warn() { echo -e "${YELLOW}[deploy]${NC} $*"; }
err()  { echo -e "${RED}[deploy]${NC} $*" >&2; }

# ── Preflight checks ──────────────────────────────────────

preflight() {
    if ! command -v docker &>/dev/null; then
        err "Docker not found. Install Docker first."
        exit 1
    fi

    if ! docker compose version &>/dev/null; then
        err "Docker Compose v2 not found. Install docker-compose-plugin."
        exit 1
    fi

    if [ ! -f .env ]; then
        if [ -f .env.example ]; then
            warn ".env not found — copying from .env.example"
            cp .env.example .env
            warn "Edit .env with your SSI credentials, then re-run this script."
            exit 1
        else
            err ".env not found and no .env.example available."
            exit 1
        fi
    fi

    # Check required env vars
    if ! grep -q "SSI_CONSUMER_ID=.\+" .env 2>/dev/null; then
        err "SSI_CONSUMER_ID not set in .env"
        exit 1
    fi
    if ! grep -q "SSI_CONSUMER_SECRET=.\+" .env 2>/dev/null; then
        err "SSI_CONSUMER_SECRET not set in .env"
        exit 1
    fi

    log "Preflight checks passed"
}

# ── Commands ───────────────────────────────────────────────

cmd_up() {
    preflight

    log "Building and starting all services..."
    docker compose -f "$COMPOSE_FILE" up -d --build

    log "Waiting for backend health check..."
    local retries=0
    local max_retries=20
    while [ $retries -lt $max_retries ]; do
        if docker compose -f "$COMPOSE_FILE" exec -T backend \
            python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" &>/dev/null; then
            break
        fi
        retries=$((retries + 1))
        sleep 3
    done

    if [ $retries -ge $max_retries ]; then
        warn "Backend health check timed out (60s). Check logs:"
        warn "  docker compose -f $COMPOSE_FILE logs backend"
    else
        log "Backend is healthy"
    fi

    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║  VN Stock Tracker — Deployed                ║${NC}"
    echo -e "${CYAN}╠══════════════════════════════════════════════╣${NC}"
    echo -e "${CYAN}║  Dashboard:   ${NC}http://localhost${CYAN}               ║${NC}"
    echo -e "${CYAN}║  API:         ${NC}http://localhost/api/market/snapshot${CYAN} ║${NC}"
    echo -e "${CYAN}║  Health:      ${NC}http://localhost/health${CYAN}        ║${NC}"
    echo -e "${CYAN}║  Grafana:     ${NC}http://localhost:3000${CYAN}          ║${NC}"
    echo -e "${CYAN}║  Prometheus:  ${NC}http://localhost:9090${CYAN}          ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
    echo ""

    cmd_status
}

cmd_stop() {
    log "Stopping all services..."
    docker compose -f "$COMPOSE_FILE" down
    log "All services stopped"
}

cmd_restart() {
    log "Restarting all services..."
    docker compose -f "$COMPOSE_FILE" restart
    log "All services restarted"
}

cmd_build() {
    preflight
    log "Rebuilding images (no cache)..."
    docker compose -f "$COMPOSE_FILE" build --no-cache
    log "Images rebuilt. Run './scripts/deploy.sh' to start."
}

cmd_logs() {
    docker compose -f "$COMPOSE_FILE" logs -f --tail=100
}

cmd_status() {
    docker compose -f "$COMPOSE_FILE" ps
}

cmd_help() {
    echo "Usage: ./scripts/deploy.sh [command]"
    echo ""
    echo "Commands:"
    echo "  (none)      Build and start all services (default)"
    echo "  --build     Rebuild images without starting"
    echo "  --restart   Restart running services"
    echo "  --stop      Stop all services"
    echo "  --logs      Tail logs from all services"
    echo "  --status    Show container status"
    echo "  --help      Show this help"
}

# ── Main ───────────────────────────────────────────────────

case "${1:-}" in
    --build)   cmd_build ;;
    --restart) cmd_restart ;;
    --stop)    cmd_stop ;;
    --logs)    cmd_logs ;;
    --status)  cmd_status ;;
    --help)    cmd_help ;;
    "")        cmd_up ;;
    *)         err "Unknown command: $1"; cmd_help; exit 1 ;;
esac
