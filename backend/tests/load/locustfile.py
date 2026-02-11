"""Main locustfile — imports all users for Locust discovery.

Run examples:
  # All users (web UI):
  locust -f backend/tests/load/locustfile.py --host http://localhost:8000

  # Specific scenario (headless):
  locust -f backend/tests/load/locustfile.py MarketStreamUser \
    --host http://localhost:8000 --headless -u 100 -r 10 -t 60s

  # Burst test with custom shape:
  locust -f backend/tests/load/locustfile.py BurstWsUser BurstRestUser \
    --host http://localhost:8000 --headless

Available users:
  - RestUser: General REST API load test
  - MarketStreamUser: WebSocket /ws/market streaming
  - ForeignFlowUser: REST /api/market/foreign-detail polling
  - BurstWsUser + BurstRestUser: Mixed burst simulation
  - ReconnectUser: WebSocket reconnect storm
"""

# Import assertions module to register event listeners
from backend.tests.load import assertions  # noqa: F401

# Import all user classes for Locust discovery
from backend.tests.load.rest_user import RestUser  # noqa: F401
from backend.tests.load.scenarios.market_stream import MarketStreamUser  # noqa: F401
from backend.tests.load.scenarios.foreign_flow import ForeignFlowUser  # noqa: F401
from backend.tests.load.scenarios.burst_test import (  # noqa: F401
    BurstWsUser,
    BurstRestUser,
    MarketOpenBurst,
)
from backend.tests.load.scenarios.reconnect_storm import ReconnectUser  # noqa: F401
