"""Tests for VN30F futures contract symbol resolution."""

from datetime import datetime
from unittest.mock import patch

from app.services.futures_resolver import get_futures_symbols, get_primary_futures_symbol


class TestGetFuturesSymbols:
    def test_returns_two_symbols(self):
        symbols = get_futures_symbols()
        assert len(symbols) == 2

    def test_current_month_format(self):
        now = datetime.now()
        expected = f"VN30F{now.strftime('%y%m')}"
        symbols = get_futures_symbols()
        assert symbols[0] == expected

    def test_next_month_format(self):
        symbols = get_futures_symbols()
        # Second symbol should be next month
        assert symbols[1].startswith("VN30F")
        assert symbols[0] != symbols[1]

    @patch("app.services.futures_resolver.datetime")
    def test_december_rollover(self, mock_dt):
        """December should roll to January of next year."""
        mock_dt.now.return_value = datetime(2026, 12, 15)
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
        symbols = get_futures_symbols()
        assert symbols[0] == "VN30F2612"
        assert symbols[1] == "VN30F2701"

    @patch("app.services.futures_resolver.datetime")
    def test_january(self, mock_dt):
        mock_dt.now.return_value = datetime(2026, 1, 10)
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
        symbols = get_futures_symbols()
        assert symbols[0] == "VN30F2601"
        assert symbols[1] == "VN30F2602"

    @patch("app.services.futures_resolver.settings")
    def test_override_returns_single(self, mock_settings):
        mock_settings.futures_override = "VN30F2603"
        symbols = get_futures_symbols()
        assert symbols == ["VN30F2603"]

    @patch("app.services.futures_resolver.settings")
    def test_no_override_returns_two(self, mock_settings):
        mock_settings.futures_override = ""
        symbols = get_futures_symbols()
        assert len(symbols) == 2


class TestGetPrimaryFuturesSymbol:
    @patch("app.services.futures_resolver.datetime")
    def test_before_last_thursday_uses_current(self, mock_dt):
        """Before last Thursday, primary = current month."""
        mock_dt.now.return_value = datetime(2026, 2, 1)
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
        primary = get_primary_futures_symbol()
        assert primary == "VN30F2602"

    @patch("app.services.futures_resolver.datetime")
    def test_on_last_thursday_uses_next(self, mock_dt):
        """On last Thursday, primary switches to next month."""
        # Feb 2026: last Thursday is Feb 26
        mock_dt.now.return_value = datetime(2026, 2, 26)
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
        primary = get_primary_futures_symbol()
        assert primary == "VN30F2603"

    @patch("app.services.futures_resolver.datetime")
    def test_after_last_thursday_uses_next(self, mock_dt):
        """After last Thursday, primary = next month."""
        mock_dt.now.return_value = datetime(2026, 2, 27)
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
        primary = get_primary_futures_symbol()
        assert primary == "VN30F2603"

    @patch("app.services.futures_resolver.settings")
    def test_override_always_returns_override(self, mock_settings):
        mock_settings.futures_override = "VN30F2605"
        primary = get_primary_futures_symbol()
        assert primary == "VN30F2605"
