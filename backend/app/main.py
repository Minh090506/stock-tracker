import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.services.futures_resolver import get_futures_symbols
from app.services.ssi_auth_service import SSIAuthService
from app.services.ssi_market_service import SSIMarketService
from app.services.market_data_processor import MarketDataProcessor
from app.services.ssi_stream_service import SSIStreamService

logger = logging.getLogger(__name__)

# Service singletons — initialized in lifespan
auth_service = SSIAuthService()
market_service = SSIMarketService(auth_service)
stream_service = SSIStreamService(auth_service, market_service)
processor = MarketDataProcessor()

# Cached at startup
vn30_symbols: list[str] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    global vn30_symbols

    # 1. Authenticate with SSI
    await auth_service.authenticate()

    # 2. Fetch VN30 component stocks
    vn30_symbols = await market_service.fetch_vn30_components()

    # 3. Build channel list and connect stream
    futures_symbols = get_futures_symbols()
    channels = [
        "X-TRADE:ALL",
        "X-Quote:ALL",
        "R:ALL",
        "MI:VN30",
        "MI:VNINDEX",
        *[f"X:{fs}" for fs in futures_symbols],
        "B:ALL",
    ]
    # 4. Register data processing callbacks
    stream_service.on_quote(processor.handle_quote)
    stream_service.on_trade(processor.handle_trade)

    logger.info("Subscribing channels: %s", channels)
    await stream_service.connect(channels)

    yield

    # Shutdown
    await stream_service.disconnect()


app = FastAPI(
    title="VN Stock Tracker",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/vn30-components")
async def get_vn30():
    """Return cached VN30 component stock symbols."""
    return {"symbols": vn30_symbols}
