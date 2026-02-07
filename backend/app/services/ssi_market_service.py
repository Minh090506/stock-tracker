"""SSI FastConnect market data REST service.

Fetches VN30 component list and securities snapshots via REST API.
Used at startup and for reconnect reconciliation.
"""

import asyncio
import logging

from ssi_fc_data.fc_md_client import MarketDataClient

from app.config import settings

logger = logging.getLogger(__name__)


class SSIMarketService:
    """REST API calls to SSI for market metadata and snapshots."""

    def __init__(self, auth_service):
        self._auth = auth_service
        self._config = auth_service.config
        self._client: MarketDataClient = auth_service.client

    async def fetch_vn30_components(self) -> list[str]:
        """Fetch current VN30 index component symbols.

        Uses IndexComponents API. Returns list like ["VNM", "HPG", "VCB", ...].
        """
        logger.info("Fetching VN30 component stocks...")
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    self._client.index_components,
                    self._config,
                    {"indexCode": "VN30", "pageSize": 50, "pageIndex": 1},
                ),
                timeout=15.0,
            )
            symbols = self._extract_symbols(result)
            logger.info("VN30 components: %d stocks — %s", len(symbols), symbols[:5])
            return symbols
        except Exception:
            logger.exception("Failed to fetch VN30 components")
            return []

    async def fetch_securities_snapshot(self) -> list[dict]:
        """Fetch current securities data via REST for reconnect reconciliation.

        Returns raw list of dicts with Symbol, FBuyVol, FSellVol, etc.
        """
        logger.info("Fetching securities snapshot for reconciliation...")
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    self._client.securities,
                    self._config,
                    {"market": "HOSE", "pageSize": 100, "pageIndex": 1},
                ),
                timeout=15.0,
            )
            data = self._extract_data_list(result)
            logger.info("Securities snapshot: %d items", len(data))
            return data
        except Exception:
            logger.exception("Failed to fetch securities snapshot")
            return []

    @staticmethod
    def _extract_symbols(result) -> list[str]:
        """Extract symbol list from SSI IndexComponents response."""
        if not isinstance(result, dict):
            return []
        data = result.get("data", [])
        if isinstance(data, list):
            return [item.get("StockSymbol", "") for item in data if item.get("StockSymbol")]
        return []

    @staticmethod
    def _extract_data_list(result) -> list[dict]:
        """Extract data list from SSI Securities response."""
        if not isinstance(result, dict):
            return []
        data = result.get("data", [])
        return data if isinstance(data, list) else []
