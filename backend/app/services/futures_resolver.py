"""VN30F futures contract symbol resolution.

Determines current + next month contract symbols and identifies the primary
(most active) contract based on rollover logic (last Thursday of month).
"""

from typing import List

from calendar import monthrange
from datetime import datetime, timedelta

from app.config import settings


def get_futures_symbols() -> List[str]:
    """Return BOTH current and next month VN30F contract symbols.

    Near expiry (last Thursday of month), next month becomes the active
    contract. Subscribe to both to avoid missing data during rollover.

    If FUTURES_OVERRIDE env is set, use that as the sole contract.
    """
    if settings.futures_override:
        return [settings.futures_override]

    now = datetime.now()
    current = f"VN30F{now.strftime('%y%m')}"

    # Next month
    if now.month == 12:
        next_dt = now.replace(year=now.year + 1, month=1, day=1)
    else:
        next_dt = now.replace(month=now.month + 1, day=1)
    next_month = f"VN30F{next_dt.strftime('%y%m')}"

    return [current, next_month]


def get_primary_futures_symbol() -> str:
    """Return the most active contract symbol.

    During rollover week (from last Thursday of month onward),
    prefer next month's contract.
    """
    now = datetime.now()
    last_day = monthrange(now.year, now.month)[1]
    last_date = now.replace(day=last_day)
    # Walk back to Thursday (weekday=3)
    offset = (last_date.weekday() - 3) % 7
    last_thursday = last_date - timedelta(days=offset)

    symbols = get_futures_symbols()
    if len(symbols) == 1:
        return symbols[0]
    if now.date() >= last_thursday.date():
        return symbols[1]  # next month after rollover
    return symbols[0]
