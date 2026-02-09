import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

from app.database.connection import db
from app.database.batch_writer import BatchWriter
from app.routers.history_router import router as history_router
from app.routers.market_router import router as market_router
from app.services.futures_resolver import get_futures_symbols
from app.services.ssi_auth_service import SSIAuthService
from app.services.ssi_market_service import SSIMarketService
from app.services.market_data_processor import MarketDataProcessor
from app.services.ssi_stream_service import SSIStreamService
from app.websocket import ConnectionManager
from app.websocket.broadcast_loop import broadcast_loop
from app.websocket.router import router as ws_router

logger = logging.getLogger(__name__)

# Service singletons — initialized in lifespan
auth_service = SSIAuthService()
market_service = SSIMarketService(auth_service)
stream_service = SSIStreamService(auth_service, market_service)
processor = MarketDataProcessor()
batch_writer = BatchWriter(db)
market_ws_manager = ConnectionManager()
foreign_ws_manager = ConnectionManager()
index_ws_manager = ConnectionManager()

# Cached at startup
vn30_symbols: list[str] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    global vn30_symbols

    # 1. Connect database pool
    await db.connect()

    # 2. Start batch writer
    await batch_writer.start()

    # 3. Authenticate with SSI
    await auth_service.authenticate()

    # 4. Fetch VN30 component stocks
    vn30_symbols = await market_service.fetch_vn30_components()

    # 5. Build channel list and connect stream
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
    # 6. Register data processing callbacks
    stream_service.on_quote(processor.handle_quote)
    stream_service.on_trade(processor.handle_trade)
    stream_service.on_foreign(processor.handle_foreign)
    stream_service.on_index(processor.handle_index)

    logger.info("Subscribing channels: %s", channels)
    await stream_service.connect(channels)

    # 7. Start WebSocket broadcast loop (feeds 3 channels)
    broadcast_task = asyncio.create_task(
        broadcast_loop(processor, market_ws_manager, foreign_ws_manager, index_ws_manager)
    )
    logger.info("WebSocket broadcast loop started")

    yield

    # Shutdown (reverse order)
    broadcast_task.cancel()
    try:
        await broadcast_task
    except asyncio.CancelledError:
        pass
    await market_ws_manager.disconnect_all()
    await foreign_ws_manager.disconnect_all()
    await index_ws_manager.disconnect_all()
    await stream_service.disconnect()
    await batch_writer.stop()
    await db.disconnect()


app = FastAPI(
    title="VN Stock Tracker",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(history_router)
app.include_router(market_router)
app.include_router(ws_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/vn30-components")
async def get_vn30():
    """Return cached VN30 component stock symbols."""
    return {"symbols": vn30_symbols}
