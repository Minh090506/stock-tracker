import asyncio
import logging
import time as time_mod
import zoneinfo
from contextlib import asynccontextmanager
from datetime import datetime, time, timedelta

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from app.config import settings
from app.metrics import http_request_duration_seconds

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

from app.database.pool import db
from app.database.batch_writer import BatchWriter
from app.routers.history_router import router as history_router
from app.routers.market_router import router as market_router
from app.services.futures_resolver import get_futures_symbols
from app.services.ssi_auth_service import SSIAuthService
from app.services.ssi_market_service import SSIMarketService
from app.services.market_data_processor import MarketDataProcessor
from app.services.ssi_stream_service import SSIStreamService
from app.analytics import AlertService, PriceTracker
from app.websocket import ConnectionManager
from app.websocket.data_publisher import DataPublisher
from app.websocket.router import router as ws_router

logger = logging.getLogger(__name__)

# Service singletons — initialized in lifespan
auth_service = SSIAuthService()
market_service = SSIMarketService(auth_service)
stream_service = SSIStreamService(auth_service, market_service)
processor = MarketDataProcessor()
batch_writer = BatchWriter(db)
alert_service = AlertService()
price_tracker = PriceTracker(
    alert_service, processor.quote_cache,
    processor.foreign_tracker, processor.derivatives_tracker,
)
processor.price_tracker = price_tracker
market_ws_manager = ConnectionManager(channel="market")
foreign_ws_manager = ConnectionManager(channel="foreign")
index_ws_manager = ConnectionManager(channel="index")
alerts_ws_manager = ConnectionManager(channel="alerts")

# Cached at startup
vn30_symbols: list[str] = []

_VN_TZ = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
_RESET_TIME = time(15, 5)  # 15:05 VN — 5min after market close


async def _daily_reset_loop():
    """Reset all session data at 15:05 VN time daily."""
    while True:
        now = datetime.now(_VN_TZ)
        target = now.replace(hour=_RESET_TIME.hour, minute=_RESET_TIME.minute,
                             second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())
        processor.reset_session()
        alert_service.reset_daily()
        logger.info("Daily reset complete at %s", datetime.now(_VN_TZ).isoformat())


def _on_new_alert(alert):
    """Broadcast new alert to /ws/alerts clients."""
    if alerts_ws_manager.client_count > 0:
        alerts_ws_manager.broadcast(alert.model_dump_json())


@asynccontextmanager
async def lifespan(app: FastAPI):
    global vn30_symbols

    # 1. Try connecting database pool (app works without DB)
    db_available = False
    try:
        await db.connect()
        db_available = True
        logger.info("Database connected")
    except Exception:
        logger.warning(
            "Database unavailable — running without persistence", exc_info=True,
        )
    app.state.db_available = db_available

    # 2. Start batch writer only if DB is available
    if db_available:
        await batch_writer.start()

    # 3. Authenticate with SSI
    await auth_service.authenticate()

    # 4. Fetch VN30 component stocks and configure watchlist
    vn30_symbols = await market_service.fetch_vn30_components()
    watchlist = set(vn30_symbols) | {"VN30", "VNINDEX"}
    if settings.extra_symbols_list:
        watchlist |= set(settings.extra_symbols_list)
    processor.set_watchlist(watchlist)

    # 5. Build channel list and connect stream
    futures_symbols = get_futures_symbols()
    # SSI FastConnect valid channels: F (status), X (market data),
    # R (foreign room), MI (index), B (bar/OHLC).
    # Each channel type can only be subscribed ONCE.
    channels = [
        "X:ALL",
        "R:ALL",
        "MI:ALL",
        "B:ALL",
    ]

    # 6. Register data processing callbacks with persistence wiring
    async def _on_trade(msg):
        result = await processor.handle_trade(msg)
        if result is None:
            return
        classified, _stats, basis_point = result
        if db_available and classified:
            batch_writer.enqueue_tick(classified)
        if db_available and basis_point:
            batch_writer.enqueue_basis(basis_point)

    async def _on_foreign(msg):
        result = await processor.handle_foreign(msg)
        if db_available and result:
            batch_writer.enqueue_foreign(result)

    async def _on_index(msg):
        result = await processor.handle_index(msg)
        if db_available and result:
            batch_writer.enqueue_index(result)

    stream_service.on_quote(processor.handle_quote)
    stream_service.on_trade(_on_trade)
    stream_service.on_foreign(_on_foreign)
    stream_service.on_index(_on_index)

    logger.info("Subscribing channels: %s", channels)
    await stream_service.connect(channels)

    # 7. Start event-driven WebSocket publisher (replaces poll-based broadcast loop)
    publisher = DataPublisher(
        processor, market_ws_manager, foreign_ws_manager, index_ws_manager,
        alerts_mgr=alerts_ws_manager,
    )
    publisher.start()
    processor.subscribe(publisher.notify)

    # 8. Wire SSI disconnect/reconnect notifications
    stream_service.set_disconnect_callback(publisher.on_ssi_disconnect)
    stream_service.set_reconnect_callback(publisher.on_ssi_reconnect)
    logger.info("WebSocket data publisher started")

    # 9. Wire alert broadcasts to /ws/alerts channel
    alert_service.subscribe(_on_new_alert)

    # 10. Schedule daily reset at 15:05 VN time
    reset_task = asyncio.create_task(_daily_reset_loop())

    yield

    # Shutdown (reverse order)
    reset_task.cancel()
    alert_service.unsubscribe(_on_new_alert)
    processor.unsubscribe(publisher.notify)
    publisher.stop()
    await market_ws_manager.disconnect_all()
    await foreign_ws_manager.disconnect_all()
    await index_ws_manager.disconnect_all()
    await alerts_ws_manager.disconnect_all()
    await stream_service.disconnect()
    if app.state.db_available:
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


@app.middleware("http")
async def track_request_duration(request: Request, call_next):
    """Record HTTP request duration for Prometheus."""
    start = time_mod.monotonic()
    response: Response = await call_next(request)
    elapsed = time_mod.monotonic() - start
    # Skip /metrics and WebSocket upgrade requests
    if "websocket" in request.headers.get("upgrade", ""):
        return response
    # Use route template (e.g. /api/history/{symbol}/candles) to prevent label explosion
    route = request.scope.get("route")
    path = route.path if route else request.url.path
    if path != "/metrics":
        http_request_duration_seconds.labels(
            method=request.method,
            path=path,
            status_code=response.status_code,
        ).observe(elapsed)
    return response


@app.get("/metrics", include_in_schema=False)
async def prometheus_metrics():
    """Expose Prometheus metrics."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
async def health():
    db_ok = False
    if getattr(app.state, "db_available", False):
        db_ok = await db.health_check()
    return {"status": "ok", "database": "connected" if db_ok else "unavailable"}


@app.get("/api/vn30-components")
async def get_vn30():
    """Return cached VN30 component stock symbols."""
    return {"symbols": vn30_symbols}
