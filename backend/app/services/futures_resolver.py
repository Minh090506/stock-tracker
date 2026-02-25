"""VN30F futures contract symbol resolution — supports both legacy and KRX formats.

Legacy format (pre-KRX, before May 5 2025): VN30F{YY}{MM}  e.g. VN30F2603
KRX format (post May 5 2025):               41I1{Y}{M}000  e.g. 41I1G3000

KRX structure: 4=derivative, 1=futures, I1=VN30, {year}{month}, 000=identifier.

Year encoding (0→W, skipping I/O/U):
  0-9 = 2010-2019, A=2020..F=2025, G=2026, H=2027, J=2028, K=2029,
  L=2030..N=2032, P=2033..T=2037, V=2038, W=2039

Month encoding: 1-9 = Jan-Sep, A=Oct, B=Nov, C=Dec

HNX always lists 4 contracts: 2 near-month + 2 nearest quarter-end.
"""

from datetime import datetime, timedelta

from app.config import settings

_QUARTER_MONTHS = {3, 6, 9, 12}

# Year letters: 2010→0, 2011→1, ... 2019→9, 2020→A, ... 2039→W (skip I, O, U)
_YEAR_LETTERS = "0123456789ABCDEFGHJKLMNPQRSTVW"
_YEAR_BASE = 2010  # _YEAR_LETTERS[0] = 2010

# Month codes: 1→'1', ... 9→'9', 10→'A', 11→'B', 12→'C'
_MONTH_CODES = {
    1: "1", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6",
    7: "7", 8: "8", 9: "9", 10: "A", 11: "B", 12: "C",
}

# Reverse lookups for parsing KRX codes
_LETTER_TO_YEAR = {ch: _YEAR_BASE + i for i, ch in enumerate(_YEAR_LETTERS)}
_CODE_TO_MONTH = {v: k for k, v in _MONTH_CODES.items()}


def _third_thursday(year: int, month: int) -> datetime:
    """Find the third Thursday of a given month (VN30F expiry day)."""
    first = datetime(year, month, 1)
    offset = (3 - first.weekday()) % 7
    first_thursday = first.replace(day=1 + offset)
    return first_thursday + timedelta(days=14)


def _advance_month(year: int, month: int, n: int = 1) -> tuple[int, int]:
    """Advance by n months, handling year rollover."""
    month += n
    while month > 12:
        month -= 12
        year += 1
    return year, month


def to_krx_symbol(year: int, month: int) -> str:
    """Convert (year, month) to KRX derivative code: 41I1{Y}{M}000."""
    year_idx = year - _YEAR_BASE
    if year_idx < 0 or year_idx >= len(_YEAR_LETTERS):
        raise ValueError(f"Year {year} out of KRX range (2010-2039)")
    return f"41I1{_YEAR_LETTERS[year_idx]}{_MONTH_CODES[month]}000"


def to_legacy_symbol(year: int, month: int) -> str:
    """Convert (year, month) to legacy code: VN30F{YY}{MM}."""
    return f"VN30F{year % 100:02d}{month:02d}"


def is_vn30f_derivative(symbol: str) -> bool:
    """Check if a symbol is a VN30 derivative in ANY format (KRX or legacy)."""
    return symbol.startswith("VN30F") or symbol.startswith("41I1")


def parse_krx_symbol(symbol: str) -> tuple[int, int] | None:
    """Parse KRX code (e.g. 41I1G3000) → (year, month) or None."""
    if not symbol.startswith("41I1") or len(symbol) != 9:
        return None
    year_ch = symbol[4]
    month_ch = symbol[5]
    year = _LETTER_TO_YEAR.get(year_ch)
    month = _CODE_TO_MONTH.get(month_ch)
    if year is None or month is None:
        return None
    return year, month


def krx_to_legacy(symbol: str) -> str | None:
    """Convert KRX symbol to legacy format. Returns None if not parseable."""
    parsed = parse_krx_symbol(symbol)
    if parsed is None:
        return None
    return to_legacy_symbol(*parsed)


def _get_active_year_months() -> list[tuple[int, int]]:
    """Return (year, month) pairs for all 4 active contracts."""
    if settings.futures_override:
        # Try to parse override as KRX format, then legacy
        parsed = parse_krx_symbol(settings.futures_override)
        if parsed:
            return [parsed]
        # Legacy format: VN30F{YY}{MM}
        if settings.futures_override.startswith("VN30F") and len(settings.futures_override) == 9:
            yy = int(settings.futures_override[5:7])
            mm = int(settings.futures_override[7:9])
            return [(2000 + yy, mm)]
        return []

    now = datetime.now()
    expiry = _third_thursday(now.year, now.month)

    # Determine front month
    if now.date() > expiry.date():
        front_y, front_m = _advance_month(now.year, now.month, 1)
    else:
        front_y, front_m = now.year, now.month

    # Second month
    sec_y, sec_m = _advance_month(front_y, front_m, 1)

    monthly = [(front_y, front_m), (sec_y, sec_m)]
    monthly_set = set(monthly)

    # Nearest 2 quarter-end months not already in the monthly pair
    quarterly: list[tuple[int, int]] = []
    y, m = sec_y, sec_m
    while len(quarterly) < 2:
        if m in _QUARTER_MONTHS and (y, m) not in monthly_set:
            quarterly.append((y, m))
        y, m = _advance_month(y, m, 1)

    return monthly + quarterly


def get_futures_symbols() -> list[str]:
    """Return all active VN30F contracts in KRX format (41I1{Y}{M}000).

    After expiry (third Thursday), front month rolls forward.
    If FUTURES_OVERRIDE env is set, returns that single contract only.
    """
    if settings.futures_override:
        return [settings.futures_override]

    return [to_krx_symbol(y, m) for y, m in _get_active_year_months()]


def get_futures_symbols_legacy() -> list[str]:
    """Return active contracts in legacy format (VN30FYYMM) for historical queries."""
    return [to_legacy_symbol(y, m) for y, m in _get_active_year_months()]


def get_primary_futures_symbol() -> str:
    """Return the front-month contract in KRX format."""
    symbols = get_futures_symbols()
    return symbols[0] if symbols else ""
