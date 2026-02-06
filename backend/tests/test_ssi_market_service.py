"""Tests for SSI market service — static extraction methods."""

from app.services.ssi_market_service import SSIMarketService


class TestExtractSymbols:
    def test_valid_response(self):
        result = {
            "data": [
                {"StockSymbol": "VNM", "Exchange": "HOSE"},
                {"StockSymbol": "HPG", "Exchange": "HOSE"},
                {"StockSymbol": "VCB", "Exchange": "HOSE"},
            ]
        }
        symbols = SSIMarketService._extract_symbols(result)
        assert symbols == ["VNM", "HPG", "VCB"]

    def test_empty_data(self):
        assert SSIMarketService._extract_symbols({"data": []}) == []

    def test_missing_data_key(self):
        assert SSIMarketService._extract_symbols({"status": 200}) == []

    def test_non_dict_result(self):
        assert SSIMarketService._extract_symbols("invalid") == []
        assert SSIMarketService._extract_symbols(None) == []

    def test_filters_empty_symbols(self):
        result = {
            "data": [
                {"StockSymbol": "VNM"},
                {"StockSymbol": ""},
                {"Exchange": "HOSE"},  # no StockSymbol key
            ]
        }
        symbols = SSIMarketService._extract_symbols(result)
        assert symbols == ["VNM"]


class TestExtractDataList:
    def test_valid_response(self):
        result = {"data": [{"Symbol": "VNM"}, {"Symbol": "HPG"}]}
        data = SSIMarketService._extract_data_list(result)
        assert len(data) == 2

    def test_empty_data(self):
        assert SSIMarketService._extract_data_list({"data": []}) == []

    def test_data_not_list(self):
        assert SSIMarketService._extract_data_list({"data": "invalid"}) == []

    def test_non_dict_result(self):
        assert SSIMarketService._extract_data_list(42) == []
