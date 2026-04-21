
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from decimal import Decimal
import pytest

from bot.validators import (
    validate_symbol,
    validate_side,
    validate_order_type,
    validate_quantity,
    validate_price,
    validate_stop_price,
    validate_all,
    ValidationError,
)


# ── Symbol ────────────────────────────────────────────────────────────────────

class TestValidateSymbol:
    def test_valid_symbol(self):
        assert validate_symbol("btcusdt") == "BTCUSDT"

    def test_strips_whitespace(self):
        assert validate_symbol("  ETHUSDT  ") == "ETHUSDT"

    def test_short_symbol(self):
        with pytest.raises(ValidationError):
            validate_symbol("BT")

    def test_lowercase_normalized(self):
        assert validate_symbol("solusdt") == "SOLUSDT"

    def test_invalid_chars(self):
        with pytest.raises(ValidationError):
            validate_symbol("BTC-USDT")


# ── Side ──────────────────────────────────────────────────────────────────────

class TestValidateSide:
    def test_buy(self):
        assert validate_side("buy") == "BUY"

    def test_sell(self):
        assert validate_side("SELL") == "SELL"

    def test_invalid_side(self):
        with pytest.raises(ValidationError):
            validate_side("LONG")


# ── Order type ────────────────────────────────────────────────────────────────

class TestValidateOrderType:
    def test_market(self):
        assert validate_order_type("market") == "MARKET"

    def test_limit(self):
        assert validate_order_type("LIMIT") == "LIMIT"

    def test_stop_market(self):
        assert validate_order_type("stop_market") == "STOP_MARKET"

    def test_stop_limit(self):
        assert validate_order_type("STOP_LIMIT") == "STOP_LIMIT"

    def test_invalid_type(self):
        with pytest.raises(ValidationError):
            validate_order_type("TWAP")


# ── Quantity ──────────────────────────────────────────────────────────────────

class TestValidateQuantity:
    def test_positive_float_string(self):
        assert validate_quantity("0.001") == Decimal("0.001")

    def test_zero_raises(self):
        with pytest.raises(ValidationError):
            validate_quantity("0")

    def test_negative_raises(self):
        with pytest.raises(ValidationError):
            validate_quantity("-1")

    def test_non_numeric_raises(self):
        with pytest.raises(ValidationError):
            validate_quantity("lots")


# ── Price ─────────────────────────────────────────────────────────────────────

class TestValidatePrice:
    def test_required_for_limit(self):
        with pytest.raises(ValidationError):
            validate_price(None, "LIMIT")

    def test_valid_for_limit(self):
        assert validate_price("50000", "LIMIT") == Decimal("50000")

    def test_not_required_for_market(self):
        assert validate_price(None, "MARKET") is None

    def test_rejected_for_market(self):
        with pytest.raises(ValidationError):
            validate_price("50000", "MARKET")

    def test_zero_price_raises(self):
        with pytest.raises(ValidationError):
            validate_price("0", "LIMIT")


# ── Stop price ────────────────────────────────────────────────────────────────

class TestValidateStopPrice:
    def test_required_for_stop_market(self):
        with pytest.raises(ValidationError):
            validate_stop_price(None, "STOP_MARKET")

    def test_valid_for_stop_limit(self):
        assert validate_stop_price("45000", "STOP_LIMIT") == Decimal("45000")

    def test_not_needed_for_market(self):
        assert validate_stop_price(None, "MARKET") is None


# ── validate_all ──────────────────────────────────────────────────────────────

class TestValidateAll:
    def test_market_order(self):
        result = validate_all(
            symbol="btcusdt", side="buy", order_type="market", quantity="0.001"
        )
        assert result["symbol"]     == "BTCUSDT"
        assert result["side"]       == "BUY"
        assert result["order_type"] == "MARKET"
        assert result["quantity"]   == Decimal("0.001")
        assert result["price"]      is None

    def test_limit_order(self):
        result = validate_all(
            symbol="ETHUSDT", side="SELL", order_type="LIMIT",
            quantity="0.01", price="3500"
        )
        assert result["price"] == Decimal("3500")

    def test_limit_without_price_raises(self):
        with pytest.raises(ValidationError):
            validate_all(symbol="BTCUSDT", side="BUY", order_type="LIMIT", quantity="0.001")

    def test_stop_limit_full(self):
        result = validate_all(
            symbol="BTCUSDT", side="BUY", order_type="STOP_LIMIT",
            quantity="0.001", price="68000", stop_price="67500"
        )
        assert result["stop_price"] == Decimal("67500")

    def test_stop_limit_missing_stop_raises(self):
        with pytest.raises(ValidationError):
            validate_all(
                symbol="BTCUSDT", side="BUY", order_type="STOP_LIMIT",
                quantity="0.001", price="68000"
            )
