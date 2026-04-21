
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from decimal import Decimal
from unittest.mock import MagicMock, patch
import pytest

from bot.orders import build_order_params, place_order, OrderResult
from bot.client import BinanceAPIError, BinanceNetworkError


# ── build_order_params ────────────────────────────────────────────────────────

class TestBuildOrderParams:
    def test_market_order(self):
        params = build_order_params("BTCUSDT", "BUY", "MARKET", Decimal("0.001"))
        assert params["type"]     == "MARKET"
        assert params["quantity"] == "0.001"
        assert "price"       not in params
        assert "timeInForce" not in params

    def test_limit_order(self):
        params = build_order_params("BTCUSDT", "SELL", "LIMIT", Decimal("0.01"), price=Decimal("50000"))
        assert params["type"]        == "LIMIT"
        assert params["price"]       == "50000"
        assert params["timeInForce"] == "GTC"

    def test_stop_market_order(self):
        params = build_order_params("BTCUSDT", "SELL", "STOP_MARKET", Decimal("0.001"),
                                    stop_price=Decimal("45000"))
        assert params["stopPrice"] == "45000"
        assert "price" not in params

    def test_stop_limit_order(self):
        params = build_order_params("BTCUSDT", "BUY", "STOP_LIMIT", Decimal("0.001"),
                                    price=Decimal("68000"), stop_price=Decimal("67500"))
        assert params["price"]     == "68000"
        assert params["stopPrice"] == "67500"

    def test_reduce_only_flag(self):
        params = build_order_params("BTCUSDT", "SELL", "MARKET", Decimal("0.001"), reduce_only=True)
        assert params["reduceOnly"] == "true"

    def test_quantity_no_trailing_zeros(self):
        params = build_order_params("BTCUSDT", "BUY", "MARKET", Decimal("0.10000"))
        assert params["quantity"] == "0.1"


# ── OrderResult ───────────────────────────────────────────────────────────────

class TestOrderResult:
    SAMPLE_RAW = {
        "orderId": 123456,
        "symbol": "BTCUSDT",
        "status": "FILLED",
        "side": "BUY",
        "type": "MARKET",
        "origQty": "0.001",
        "executedQty": "0.001",
        "avgPrice": "42000.5",
        "price": "0",
        "stopPrice": "0",
        "timeInForce": "GTC",
        "clientOrderId": "abc123",
        "updateTime": 1705314181000,
    }

    def test_properties(self):
        r = OrderResult(self.SAMPLE_RAW)
        assert r.order_id == 123456
        assert r.is_filled()

    def test_not_filled(self):
        raw = {**self.SAMPLE_RAW, "status": "NEW"}
        r = OrderResult(raw)
        assert not r.is_filled()

    def test_summary_keys(self):
        r = OrderResult(self.SAMPLE_RAW)
        s = r.summary()
        for key in ("orderId", "symbol", "side", "type", "status", "executedQty", "avgPrice"):
            assert key in s


# ── place_order ───────────────────────────────────────────────────────────────

class TestPlaceOrder:
    def _make_client(self, return_value: dict) -> MagicMock:
        client = MagicMock()
        client.place_order.return_value = return_value
        return client

    def test_successful_market_order(self):
        raw = {
            "orderId": 999, "symbol": "BTCUSDT", "status": "FILLED",
            "side": "BUY", "type": "MARKET", "origQty": "0.001",
            "executedQty": "0.001", "avgPrice": "42000", "price": "0",
            "stopPrice": "0", "timeInForce": "GTC",
        }
        client = self._make_client(raw)
        result = place_order(client, "BTCUSDT", "BUY", "MARKET", Decimal("0.001"))
        assert result.order_id == 999
        assert result.is_filled()

    def test_api_error_propagates(self):
        client = MagicMock()
        client.place_order.side_effect = BinanceAPIError(-2010, "Account has insufficient balance.")
        with pytest.raises(BinanceAPIError):
            place_order(client, "BTCUSDT", "BUY", "MARKET", Decimal("0.001"))

    def test_network_error_propagates(self):
        client = MagicMock()
        client.place_order.side_effect = BinanceNetworkError("Connection timed out")
        with pytest.raises(BinanceNetworkError):
            place_order(client, "BTCUSDT", "BUY", "MARKET", Decimal("0.001"))
