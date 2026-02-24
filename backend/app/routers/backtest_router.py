"""REST endpoints for backtest analysis (cross-correlation, threshold, patterns)."""

import zoneinfo
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Request

from app.analytics.backtest_engine import BacktestEngine

router = APIRouter(prefix="/api/backtest", tags=["backtest"])

_VN_TZ = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")


def _get_engine(request: Request) -> BacktestEngine:
    """Return the shared BacktestEngine from app.state (set in lifespan)."""
    if not getattr(request.app.state, "db_available", False):
        raise HTTPException(status_code=503, detail="Database unavailable")
    engine: BacktestEngine | None = getattr(request.app.state, "backtest_engine", None)
    if engine is None:
        raise HTTPException(status_code=503, detail="Backtest engine not initialized")
    return engine


def _date_range(days: int) -> tuple[datetime, datetime]:
    """Convert lookback days to (date_from, date_to) datetime pair."""
    now = datetime.now(_VN_TZ)
    return now - timedelta(days=days), now


@router.get("/summary")
async def get_summary(request: Request):
    """Pre-computed daily backtest report (cached). 404 if not yet computed."""
    engine = _get_engine(request)
    report = engine.get_cached_report()
    if report is None:
        raise HTTPException(status_code=404, detail="No backtest report available yet")
    return report.model_dump(mode="json")


@router.get("/correlation")
async def get_correlation(
    request: Request,
    symbol: str = Query("VN30F2603", description="Futures symbol"),
    days: int = Query(20, ge=5, le=90, description="Lookback trading days"),
    max_lag: int = Query(10, ge=1, le=30, description="Max lag in minutes"),
):
    """On-demand cross-correlation (lead-lag) analysis."""
    engine = _get_engine(request)
    date_from, date_to = _date_range(days)
    result = await engine.run_cross_correlation(symbol.upper(), date_from, date_to, max_lag)
    return result.model_dump(mode="json")


@router.get("/threshold")
async def get_threshold(
    request: Request,
    symbol: str = Query("VN30F2603", description="Futures symbol"),
    days: int = Query(20, ge=5, le=90, description="Lookback trading days"),
    lookahead: int = Query(5, ge=1, le=30, description="Price lookahead minutes"),
    bins: int = Query(5, ge=3, le=10, description="Number of imbalance bins"),
):
    """On-demand threshold (imbalance → price direction) analysis."""
    engine = _get_engine(request)
    date_from, date_to = _date_range(days)
    result = await engine.run_threshold_analysis(
        symbol.upper(), date_from, date_to, lookahead, bins,
    )
    return result.model_dump(mode="json")


@router.get("/patterns")
async def get_patterns(
    request: Request,
    symbol: str = Query("VN30F2603", description="Futures symbol"),
    days: int = Query(20, ge=5, le=90, description="Lookback trading days"),
):
    """On-demand time-of-day pattern analysis."""
    engine = _get_engine(request)
    date_from, date_to = _date_range(days)
    result = await engine.run_pattern_analysis(symbol.upper(), date_from, date_to)
    return result.model_dump(mode="json")
