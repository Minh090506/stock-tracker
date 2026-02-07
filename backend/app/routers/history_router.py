"""REST endpoints for historical market data queries."""

from datetime import date

from fastapi import APIRouter, Query

from app.database.connection import db
from app.database.history_service import HistoryService

router = APIRouter(prefix="/api/history", tags=["history"])

# Lazily initialised — db pool available after lifespan startup
_svc: HistoryService | None = None


def _get_svc() -> HistoryService:
    global _svc
    if _svc is None:
        _svc = HistoryService(db)
    return _svc


@router.get("/{symbol}/candles")
async def get_candles(
    symbol: str,
    start: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end: date = Query(..., description="End date (YYYY-MM-DD)"),
):
    return await _get_svc().get_candles(symbol.upper(), start, end)


@router.get("/{symbol}/ticks")
async def get_ticks(
    symbol: str,
    start: date = Query(..., description="Start date"),
    end: date = Query(..., description="End date"),
    limit: int = Query(10000, le=50000),
):
    return await _get_svc().get_ticks(symbol.upper(), start, end, limit)


@router.get("/{symbol}/foreign")
async def get_foreign_flow(
    symbol: str,
    start: date = Query(..., description="Start date"),
    end: date = Query(..., description="End date"),
):
    return await _get_svc().get_foreign_flow(symbol.upper(), start, end)


@router.get("/{symbol}/foreign/daily")
async def get_foreign_daily(
    symbol: str,
    days: int = Query(30, le=365),
):
    return await _get_svc().get_foreign_flow_daily_summary(symbol.upper(), days)


@router.get("/index/{index_name}")
async def get_index_history(
    index_name: str,
    start: date = Query(..., description="Start date"),
    end: date = Query(..., description="End date"),
):
    return await _get_svc().get_index_history(index_name.upper(), start, end)


@router.get("/derivatives/{contract}")
async def get_derivatives_history(
    contract: str,
    start: date = Query(..., description="Start date"),
    end: date = Query(..., description="End date"),
):
    return await _get_svc().get_derivatives_history(contract.upper(), start, end)
