"""SSI FastConnect authentication service.

Handles JWT token acquisition via ssi-fc-data MarketDataClient.
Token is stored in-memory for stream authentication.
"""

import asyncio
import logging
from types import SimpleNamespace

from ssi_fc_data.fc_md_client import MarketDataClient
from ssi_fc_data.model.model import accessToken as SSIAccessTokenRequest

from app.config import settings

logger = logging.getLogger(__name__)


def _build_config() -> SimpleNamespace:
    """Build ssi-fc-data config object from app settings.

    ssi-fc-data v2.2.2 expects attribute access (config.consumerID),
    not dict access (config["consumerID"]).
    """
    return SimpleNamespace(
        auth_type="Bearer",
        consumerID=settings.ssi_consumer_id,
        consumerSecret=settings.ssi_consumer_secret,
        url=settings.ssi_base_url,
        stream_url=settings.ssi_stream_url,
    )


class SSIAuthService:
    """Manages SSI API authentication and token lifecycle."""

    def __init__(self):
        if not settings.ssi_consumer_id or not settings.ssi_consumer_secret:
            raise ValueError(
                "SSI credentials missing: set SSI_CONSUMER_ID and SSI_CONSUMER_SECRET in .env"
            )
        self.config = _build_config()
        self.client = MarketDataClient(self.config)
        self._token: str | None = None

    @property
    def token(self) -> str | None:
        return self._token

    async def authenticate(self) -> str:
        """Authenticate with SSI and store JWT token.

        ssi-fc-data is sync-only, so we run in a thread.
        Returns the access token string.
        """
        logger.info("Authenticating with SSI FastConnect...")
        req = SSIAccessTokenRequest(
            consumerID=settings.ssi_consumer_id,
            consumerSecret=settings.ssi_consumer_secret,
        )
        result = await asyncio.wait_for(
            asyncio.to_thread(self.client.access_token, req),
            timeout=15.0,
        )
        # result is typically {"data": {"accessToken": "..."}, "status": 200}
        if isinstance(result, dict):
            data = result.get("data", result)
            self._token = data.get("accessToken", "")
        else:
            self._token = str(result) if result else ""

        if self._token:
            logger.info("SSI authentication successful")
        else:
            logger.error("SSI authentication failed — no token received")
        return self._token
