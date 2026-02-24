"""Utility functions for backtest analysis."""


def pearson(x: list[float], y: list[float]) -> float:
    """Pure Python Pearson correlation. Returns 0.0 on insufficient data."""
    n = len(x)
    if n < 3:
        return 0.0
    sum_x = sum(x)
    sum_y = sum(y)
    sum_xy = sum(a * b for a, b in zip(x, y))
    sum_x2 = sum(a * a for a in x)
    sum_y2 = sum(b * b for b in y)
    num = n * sum_xy - sum_x * sum_y
    den_sq = (n * sum_x2 - sum_x**2) * (n * sum_y2 - sum_y**2)
    if den_sq <= 0:  # zero variance or floating-point rounding
        return 0.0
    den = den_sq**0.5
    return max(-1.0, min(1.0, num / den))


def session_phase(hour: int, minute: int = 0) -> str:
    """Classify market hour into session phase (ato/continuous/atc)."""
    if hour == 9 and minute < 15:
        return "ato"
    if hour == 14 and minute >= 30:
        return "atc"
    return "continuous"
