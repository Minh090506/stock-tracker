"""Pydantic models for backtest analysis results."""

from datetime import datetime

from pydantic import BaseModel


class CrossCorrelationResult(BaseModel):
    lag_minutes: int
    correlation: float
    sample_size: int


class CrossCorrelationReport(BaseModel):
    symbol: str
    date_from: datetime
    date_to: datetime
    results: list[CrossCorrelationResult]
    optimal_lag: int = 0
    optimal_correlation: float = 0.0


class ThresholdBin(BaseModel):
    imbalance_min: float
    imbalance_max: float
    sample_count: int
    price_up_probability: float
    avg_price_change: float
    avg_magnitude: float


class ThresholdReport(BaseModel):
    symbol: str
    lookahead_minutes: int
    date_from: datetime
    date_to: datetime
    bins: list[ThresholdBin]


class TimePatternEntry(BaseModel):
    hour: int
    session_phase: str  # "ato", "continuous", "atc"
    avg_correlation: float
    avg_imbalance: float
    sample_count: int


class PatternReport(BaseModel):
    symbol: str
    date_from: datetime
    date_to: datetime
    patterns: list[TimePatternEntry]


class BacktestSummary(BaseModel):
    """Combined daily pre-computed report."""
    computed_at: datetime
    data_days: int
    cross_correlation: CrossCorrelationReport
    threshold: ThresholdReport
    patterns: PatternReport
