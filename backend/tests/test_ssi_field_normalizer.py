"""Tests for SSI field normalization and message parsing."""

import pytest

from app.services.ssi_field_normalizer import (
    extract_content,
    normalize_fields,
    parse_message,
)
from app.models.ssi_messages import (
    SSIBarMessage,
    SSIForeignMessage,
    SSIIndexMessage,
    SSIQuoteMessage,
    SSITradeMessage,
)


class TestNormalizeFields:
    def test_maps_pascal_to_snake(self):
        raw = {"Symbol": "VNM", "LastPrice": 85000, "LastVol": 100}
        result = normalize_fields(raw)
        assert result == {"symbol": "VNM", "last_price": 85000, "last_vol": 100}

    def test_ignores_unmapped_fields(self):
        raw = {"Symbol": "VNM", "UnknownField": "ignored", "RType": "Trade"}
        result = normalize_fields(raw)
        assert result == {"symbol": "VNM"}

    def test_empty_dict(self):
        assert normalize_fields({}) == {}

    def test_all_trade_fields(self):
        raw = {
            "Symbol": "HPG", "Exchange": "HOSE",
            "LastPrice": 25500, "LastVol": 200,
            "TotalVol": 1500000, "TotalVal": 38250000000,
            "Change": 500, "RatioChange": 2.0,
            "TradingSession": "LO",
        }
        result = normalize_fields(raw)
        assert result["symbol"] == "HPG"
        assert result["last_vol"] == 200
        assert result["trading_session"] == "LO"
        assert len(result) == 9

    def test_foreign_fields(self):
        raw = {"Symbol": "VCB", "FBuyVol": 500, "FSellVol": 300, "TotalRoom": 100000}
        result = normalize_fields(raw)
        assert result["f_buy_vol"] == 500
        assert result["f_sell_vol"] == 300
        assert result["total_room"] == 100000

    def test_index_fields(self):
        raw = {
            "IndexId": "VN30", "IndexValue": 1234.56,
            "PriorIndexValue": 1230.0, "Advances": 20, "Declines": 8,
        }
        result = normalize_fields(raw)
        assert result["index_id"] == "VN30"
        assert result["index_value"] == 1234.56
        assert result["advances"] == 20

    def test_stock_symbol_alias(self):
        """StockSymbol maps to 'symbol' (alternative key from IndexComponents)."""
        raw = {"StockSymbol": "FPT"}
        result = normalize_fields(raw)
        assert result["symbol"] == "FPT"


class TestExtractContent:
    def test_json_string_with_content_key(self):
        raw = '{"Content": {"RType": "Trade", "Symbol": "VNM"}}'
        result = extract_content(raw)
        assert result == {"RType": "Trade", "Symbol": "VNM"}

    def test_dict_with_content_key(self):
        raw = {"Content": {"RType": "Quote", "Symbol": "HPG"}}
        result = extract_content(raw)
        assert result == {"RType": "Quote", "Symbol": "HPG"}

    def test_dict_with_lowercase_content_key(self):
        raw = {"content": {"RType": "R", "Symbol": "FPT"}}
        result = extract_content(raw)
        assert result == {"RType": "R", "Symbol": "FPT"}

    def test_flat_dict_no_content_wrapper(self):
        raw = {"RType": "MI", "IndexId": "VN30"}
        result = extract_content(raw)
        assert result == {"RType": "MI", "IndexId": "VN30"}

    def test_invalid_json_string(self):
        assert extract_content("not json") is None

    def test_non_dict_non_string(self):
        assert extract_content(42) is None
        assert extract_content(None) is None

    def test_empty_string(self):
        assert extract_content("") is None


class TestParseMessage:
    def test_trade_message(self):
        content = {
            "RType": "Trade", "Symbol": "VNM", "Exchange": "HOSE",
            "LastPrice": 85000, "LastVol": 100, "TotalVol": 50000,
            "TotalVal": 4250000000, "Change": 1.5, "RatioChange": 1.8,
            "TradingSession": "LO",
        }
        result = parse_message(content)
        assert result is not None
        rtype, msg = result
        assert rtype == "Trade"
        assert isinstance(msg, SSITradeMessage)
        assert msg.symbol == "VNM"
        assert msg.last_vol == 100
        assert msg.trading_session == "LO"

    def test_quote_message(self):
        content = {
            "RType": "Quote", "Symbol": "HPG", "Exchange": "HOSE",
            "Ceiling": 27000, "Floor": 23000, "RefPrice": 25000,
            "BidPrice1": 25400, "BidVol1": 1000,
            "AskPrice1": 25500, "AskVol1": 800,
        }
        result = parse_message(content)
        assert result is not None
        rtype, msg = result
        assert rtype == "Quote"
        assert isinstance(msg, SSIQuoteMessage)
        assert msg.bid_price_1 == 25400
        assert msg.ask_vol_1 == 800

    def test_foreign_message(self):
        content = {
            "RType": "R", "Symbol": "VCB",
            "FBuyVol": 500, "FSellVol": 300,
            "FBuyVal": 50000000, "FSellVal": 30000000,
        }
        result = parse_message(content)
        assert result is not None
        rtype, msg = result
        assert rtype == "R"
        assert isinstance(msg, SSIForeignMessage)
        assert msg.f_buy_vol == 500
        assert msg.f_sell_vol == 300

    def test_index_message(self):
        content = {
            "RType": "MI", "IndexId": "VN30",
            "IndexValue": 1234.56, "PriorIndexValue": 1230.0,
            "Change": 4.56, "RatioChange": 0.37,
            "Advances": 20, "Declines": 8, "NoChanges": 2,
        }
        result = parse_message(content)
        assert result is not None
        rtype, msg = result
        assert rtype == "MI"
        assert isinstance(msg, SSIIndexMessage)
        assert msg.index_id == "VN30"
        assert msg.advances == 20

    def test_bar_message(self):
        content = {
            "RType": "B", "Symbol": "VNM",
            "Time": "14:30:00", "Open": 84000, "High": 85500,
            "Low": 83500, "Close": 85000, "Volume": 100000,
        }
        result = parse_message(content)
        assert result is not None
        rtype, msg = result
        assert rtype == "B"
        assert isinstance(msg, SSIBarMessage)
        assert msg.close == 85000
        assert msg.volume == 100000

    def test_unknown_rtype_returns_none(self):
        assert parse_message({"RType": "Unknown"}) is None

    def test_missing_rtype_returns_none(self):
        assert parse_message({"Symbol": "VNM"}) is None

    def test_empty_rtype_returns_none(self):
        assert parse_message({"RType": ""}) is None

    def test_defaults_for_missing_optional_fields(self):
        """Trade message with only required RType + Symbol should use defaults."""
        content = {"RType": "Trade", "Symbol": "FPT"}
        result = parse_message(content)
        assert result is not None
        _, msg = result
        assert msg.symbol == "FPT"
        assert msg.last_price == 0.0
        assert msg.last_vol == 0
