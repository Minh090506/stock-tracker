"""Tests for VN30F futures contract symbol resolution (KRX + legacy formats)."""

from datetime import datetime
from unittest.mock import patch

from app.services.futures_resolver import (
    get_futures_symbols,
    get_futures_symbols_legacy,
    get_primary_futures_symbol,
    is_vn30f_derivative,
    krx_to_legacy,
    parse_krx_symbol,
    to_krx_symbol,
    to_legacy_symbol,
)


class TestKrxFormatConversion:
    def test_to_krx_symbol_basic(self):
        assert to_krx_symbol(2026, 3) == "41I1G3000"
        assert to_krx_symbol(2026, 6) == "41I1G6000"
        assert to_krx_symbol(2025, 5) == "41I1F5000"

    def test_to_krx_symbol_october_november_december(self):
        assert to_krx_symbol(2026, 10) == "41I1GA000"
        assert to_krx_symbol(2026, 11) == "41I1GB000"
        assert to_krx_symbol(2026, 12) == "41I1GC000"

    def test_to_krx_symbol_year_letters_skip_iou(self):
        # 2028 should be J (skipping I after H=2027)
        assert to_krx_symbol(2028, 1) == "41I1J1000"
        # 2033 should be P (skipping O after N=2032)
        assert to_krx_symbol(2033, 1) == "41I1P1000"

    def test_to_legacy_symbol(self):
        assert to_legacy_symbol(2026, 3) == "VN30F2603"
        assert to_legacy_symbol(2026, 12) == "VN30F2612"

    def test_parse_krx_symbol(self):
        assert parse_krx_symbol("41I1G3000") == (2026, 3)
        assert parse_krx_symbol("41I1GC000") == (2026, 12)
        assert parse_krx_symbol("41I1F5000") == (2025, 5)

    def test_parse_krx_symbol_invalid(self):
        assert parse_krx_symbol("VN30F2603") is None
        assert parse_krx_symbol("41I1") is None
        assert parse_krx_symbol("") is None

    def test_krx_to_legacy(self):
        assert krx_to_legacy("41I1G3000") == "VN30F2603"
        assert krx_to_legacy("41I1GC000") == "VN30F2612"
        assert krx_to_legacy("VN30F2603") is None


class TestIsVn30fDerivative:
    def test_krx_format(self):
        assert is_vn30f_derivative("41I1G3000") is True
        assert is_vn30f_derivative("41I1F5000") is True

    def test_legacy_format(self):
        assert is_vn30f_derivative("VN30F2603") is True
        assert is_vn30f_derivative("VN30F2503") is True

    def test_non_derivative(self):
        assert is_vn30f_derivative("VNM") is False
        assert is_vn30f_derivative("HPG") is False
        assert is_vn30f_derivative("VN30") is False


class TestGetFuturesSymbols:
    def test_returns_four_symbols(self):
        symbols = get_futures_symbols()
        assert len(symbols) == 4

    def test_all_krx_format(self):
        for s in get_futures_symbols():
            assert s.startswith("41I1"), f"Expected KRX format, got: {s}"

    @patch("app.services.futures_resolver.datetime")
    def test_before_expiry_current_month_is_front(self, mock_dt):
        """Before third Thursday, front month = current month."""
        mock_dt.now.return_value = datetime(2026, 2, 10)
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
        symbols = get_futures_symbols()
        assert symbols[0] == "41I1G2000"  # Feb 2026
        assert symbols[1] == "41I1G3000"  # Mar 2026
        assert symbols[2] == "41I1G6000"  # Jun 2026
        assert symbols[3] == "41I1G9000"  # Sep 2026

    @patch("app.services.futures_resolver.datetime")
    def test_after_expiry_rolls_to_next_month(self, mock_dt):
        """After third Thursday, front month = next month."""
        mock_dt.now.return_value = datetime(2026, 2, 20)
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
        symbols = get_futures_symbols()
        assert symbols[0] == "41I1G3000"  # Mar 2026
        assert symbols[1] == "41I1G4000"  # Apr 2026
        assert symbols[2] == "41I1G6000"  # Jun 2026
        assert symbols[3] == "41I1G9000"  # Sep 2026

    @patch("app.services.futures_resolver.datetime")
    def test_december_rollover(self, mock_dt):
        """After December expiry, rolls to January of next year."""
        mock_dt.now.return_value = datetime(2026, 12, 20)
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
        symbols = get_futures_symbols()
        assert symbols[0] == "41I1H1000"  # Jan 2027 (H=2027)
        assert symbols[1] == "41I1H2000"  # Feb 2027
        assert symbols[2] == "41I1H3000"  # Mar 2027
        assert symbols[3] == "41I1H6000"  # Jun 2027

    @patch("app.services.futures_resolver.datetime")
    def test_december_before_expiry(self, mock_dt):
        """Before December expiry, front month is still December."""
        mock_dt.now.return_value = datetime(2026, 12, 10)
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
        symbols = get_futures_symbols()
        assert symbols[0] == "41I1GC000"  # Dec 2026 (C=month 12)
        assert symbols[1] == "41I1H1000"  # Jan 2027
        assert symbols[2] == "41I1H3000"  # Mar 2027
        assert symbols[3] == "41I1H6000"  # Jun 2027

    @patch("app.services.futures_resolver.datetime")
    def test_quarter_month_front_skips_self_for_quarterly(self, mock_dt):
        """When front month IS a quarter (March), quarterly picks Jun+Sep."""
        mock_dt.now.return_value = datetime(2026, 3, 10)
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
        symbols = get_futures_symbols()
        assert symbols[0] == "41I1G3000"  # Mar 2026
        assert symbols[1] == "41I1G4000"  # Apr 2026
        assert symbols[2] == "41I1G6000"  # Jun 2026
        assert symbols[3] == "41I1G9000"  # Sep 2026

    @patch("app.services.futures_resolver.settings")
    def test_override_returns_single(self, mock_settings):
        mock_settings.futures_override = "41I1G5000"
        symbols = get_futures_symbols()
        assert symbols == ["41I1G5000"]

    @patch("app.services.futures_resolver.settings")
    def test_no_override_returns_four(self, mock_settings):
        mock_settings.futures_override = ""
        symbols = get_futures_symbols()
        assert len(symbols) == 4


class TestGetFuturesSymbolsLegacy:
    @patch("app.services.futures_resolver.datetime")
    def test_returns_legacy_format(self, mock_dt):
        mock_dt.now.return_value = datetime(2026, 2, 20)
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
        symbols = get_futures_symbols_legacy()
        assert symbols[0] == "VN30F2603"
        assert symbols[1] == "VN30F2604"


class TestGetPrimaryFuturesSymbol:
    @patch("app.services.futures_resolver.datetime")
    def test_before_expiry_uses_current(self, mock_dt):
        """Before third Thursday, primary = current month."""
        mock_dt.now.return_value = datetime(2026, 2, 10)
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
        primary = get_primary_futures_symbol()
        assert primary == "41I1G2000"

    @patch("app.services.futures_resolver.datetime")
    def test_on_expiry_day_uses_current(self, mock_dt):
        """On third Thursday itself, primary = current (expires at close)."""
        mock_dt.now.return_value = datetime(2026, 2, 19)
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
        primary = get_primary_futures_symbol()
        assert primary == "41I1G2000"

    @patch("app.services.futures_resolver.datetime")
    def test_after_expiry_uses_next(self, mock_dt):
        """After third Thursday, primary = next month."""
        mock_dt.now.return_value = datetime(2026, 2, 20)
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
        primary = get_primary_futures_symbol()
        assert primary == "41I1G3000"

    @patch("app.services.futures_resolver.settings")
    def test_override_always_returns_override(self, mock_settings):
        mock_settings.futures_override = "41I1G5000"
        primary = get_primary_futures_symbol()
        assert primary == "41I1G5000"
