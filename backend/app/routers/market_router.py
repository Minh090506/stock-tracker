"""REST endpoints for real-time market data and analytics alerts.

Exposes MarketDataProcessor in-memory state via REST for frontend polling.
"""

from fastapi import APIRouter, HTTPException, Query, Request

from app.analytics.alert_models import AlertSeverity, AlertType
from app.database.history_service import HistoryService
from app.database.pool import db

router = APIRouter(prefix="/api/market", tags=["market"])

# Lazily initialised — db pool available after lifespan startup
_history_svc: HistoryService | None = None


def _get_history_svc(request: Request) -> HistoryService:
    global _history_svc
    if not getattr(request.app.state, "db_available", False):
        raise HTTPException(status_code=503, detail="Database unavailable")
    if _history_svc is None:
        _history_svc = HistoryService(db)
    return _history_svc


@router.get("/snapshot")
async def get_snapshot():
    """Full market snapshot: quotes + indices + foreign + derivatives."""
    from app.main import processor

    return processor.get_market_snapshot()


@router.get("/foreign-detail")
async def get_foreign_detail():
    """Per-symbol foreign investor data for heatmap/table."""
    from app.main import processor

    summary = processor.get_foreign_summary()
    stocks = list(processor.foreign_tracker.get_all().values())
    return {"summary": summary, "stocks": stocks}


@router.get("/volume-stats")
async def get_volume_stats():
    """Per-symbol active buy/sell session stats."""
    from app.main import processor

    stats = list(processor.aggregator.get_all_stats().values())
    return {"stats": stats}


@router.get("/basis-trend")
async def get_basis_trend(minutes: int = Query(30, ge=1, le=120)):
    """Historical basis points from in-memory DerivativesTracker."""
    from app.main import processor

    points = processor.derivatives_tracker.get_basis_trend(minutes)
    return [p.model_dump() for p in points]


@router.get("/alerts")
async def get_alerts(
    limit: int = Query(50, ge=1, le=200),
    type: AlertType | None = Query(None),
    severity: AlertSeverity | None = Query(None),
):
    """Recent analytics alerts, newest first. Filterable by type and severity."""
    from app.main import alert_service

    alerts = alert_service.get_recent_alerts(limit, type, severity)
    return [a.model_dump() for a in alerts]


# -- Velocity endpoints ----------------------------------------------------


@router.get("/velocity")
async def get_velocity():
    """Current real-time velocity snapshot (VN30F + basket + correlation)."""
    from app.main import processor

    snapshot = processor.get_market_snapshot()
    return snapshot.velocity


@router.get("/velocity/history")
async def get_velocity_history(
    request: Request,
    symbol: str = Query(..., min_length=1, max_length=20, description="Symbol (e.g., VN30F2603, VPB)"),
    minutes: int = Query(60, ge=1, le=480),
):
    """Per-symbol historical velocity from order_velocity_1m aggregate."""
    svc = _get_history_svc(request)
    return await svc.get_velocity_history(symbol.upper(), minutes)


@router.get("/velocity/basket-history")
async def get_basket_velocity_history(
    request: Request,
    minutes: int = Query(60, ge=1, le=480),
):
    """VN30 basket historical velocity from vn30_basket_velocity_1m view."""
    svc = _get_history_svc(request)
    return await svc.get_basket_velocity_history(minutes)
