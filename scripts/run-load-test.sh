#!/bin/bash
# Load test runner script for VN Stock Tracker
# Usage: ./scripts/run-load-test.sh [scenario] [options]
#
# Scenarios:
#   rest        - REST API load test (RestUser)
#   market      - WebSocket /ws/market streaming (MarketStreamUser)
#   foreign     - REST foreign flow polling (ForeignFlowUser)
#   burst       - Mixed burst simulation (BurstWsUser + BurstRestUser)
#   reconnect   - WebSocket reconnect storm (ReconnectUser)
#   all         - All scenarios combined (default)
#
# Options:
#   -u, --users     Number of concurrent users (default: 100)
#   -r, --rate      Spawn rate per second (default: 10)
#   -t, --time      Test duration (default: 60s)
#   -h, --host      Target host (default: http://localhost:8000)
#   --headless      Run without web UI
#   --web           Run with web UI on port 8089
#   --docker        Run via docker-compose.test.yml

set -euo pipefail

# Defaults
SCENARIO="all"
USERS=100
SPAWN_RATE=10
DURATION="60s"
HOST="http://localhost:8000"
MODE="headless"
USE_DOCKER=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        rest|market|foreign|burst|reconnect|all)
            SCENARIO="$1"
            shift
            ;;
        -u|--users)
            USERS="$2"
            shift 2
            ;;
        -r|--rate)
            SPAWN_RATE="$2"
            shift 2
            ;;
        -t|--time)
            DURATION="$2"
            shift 2
            ;;
        -h|--host)
            HOST="$2"
            shift 2
            ;;
        --headless)
            MODE="headless"
            shift
            ;;
        --web)
            MODE="web"
            shift
            ;;
        --docker)
            USE_DOCKER=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Map scenario to Locust user classes
case $SCENARIO in
    rest)
        USERS_ARG="RestUser"
        ;;
    market)
        USERS_ARG="MarketStreamUser"
        ;;
    foreign)
        USERS_ARG="ForeignFlowUser"
        ;;
    burst)
        USERS_ARG="BurstWsUser BurstRestUser"
        ;;
    reconnect)
        USERS_ARG="ReconnectUser"
        ;;
    all)
        USERS_ARG=""  # Use all discovered users
        ;;
esac

# Project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOCUSTFILE="$PROJECT_ROOT/backend/tests/load/locustfile.py"
RESULTS_DIR="$PROJECT_ROOT/backend/tests/load/results"

# Ensure results directory exists
mkdir -p "$RESULTS_DIR"

echo "=== VN Stock Tracker Load Test ==="
echo "Scenario: $SCENARIO"
echo "Users: $USERS"
echo "Spawn rate: $SPAWN_RATE/s"
echo "Duration: $DURATION"
echo "Host: $HOST"
echo "Mode: $MODE"
echo ""

if $USE_DOCKER; then
    echo "Starting Docker load test stack..."
    cd "$PROJECT_ROOT"
    docker compose -f docker-compose.test.yml up --build --scale locust-worker=4
    exit 0
fi

# Build Locust command
CMD="locust -f $LOCUSTFILE"

if [[ -n "$USERS_ARG" ]]; then
    CMD="$CMD $USERS_ARG"
fi

CMD="$CMD --host $HOST"

if [[ "$MODE" == "headless" ]]; then
    TIMESTAMP=$(date +%Y%m%d-%H%M%S)
    CSV_PREFIX="$RESULTS_DIR/${SCENARIO}-${TIMESTAMP}"

    CMD="$CMD --headless"
    CMD="$CMD -u $USERS -r $SPAWN_RATE -t $DURATION"
    CMD="$CMD --csv=$CSV_PREFIX"
    CMD="$CMD --html=$RESULTS_DIR/${SCENARIO}-${TIMESTAMP}.html"

    echo "Results will be saved to: $RESULTS_DIR"
    echo ""
fi

echo "Running: $CMD"
echo ""

# Change to project root for correct imports
cd "$PROJECT_ROOT"

# Add backend to Python path
export PYTHONPATH="${PYTHONPATH:-}:$PROJECT_ROOT"

# Run Locust
eval "$CMD"

# Check exit code for threshold failures
EXIT_CODE=$?
if [[ $EXIT_CODE -ne 0 ]]; then
    echo ""
    echo "Load test FAILED (exit code: $EXIT_CODE)"
    echo "Check assertions in the log output above."
    exit $EXIT_CODE
fi

echo ""
echo "Load test completed successfully."
