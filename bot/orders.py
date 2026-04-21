

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from .client import BinanceFuturesClient, BinanceAPIError, BinanceNetworkError

logger = logging.getLogger(__name__)


# ── Result dataclass (plain dict-friendly) ────────────────────────────────────

class OrderResult:
    """Wraps a raw Binance order response with convenience properties."""

    def __init__(self, raw: dict):
        self.raw = raw

    # Core fields
    @property
    def order_id(self)      -> int:            return self.raw.get("orderId", 0)
    @property
    def symbol(self)        -> str:            return self.raw.get("symbol", "")
    @property
    def status(self)        -> str:            return self.raw.get("status", "")
    @property
    def side(self)          -> str:            return self.raw.get("side", "")
    @property
    def order_type(self)    -> str:            return self.raw.get("type", "")
    @property
    def orig_qty(self)      -> str:            return self.raw.get("origQty", "0")
    @property
    def executed_qty(self)  -> str:            return self.raw.get("executedQty", "0")
    @property
    def avg_price(self)     -> str:            return self.raw.get("avgPrice", "0")
    @property
    def price(self)         -> str:            return self.raw.get("price", "0")
    @property
    def stop_price(self)    -> str:            return self.raw.get("stopPrice", "0")
    @property
    def time_in_force(self) -> str:            return self.raw.get("timeInForce", "")
    @property
    def client_order_id(self) -> str:         return self.raw.get("clientOrderId", "")
    @property
    def update_time(self)   -> int:            return self.raw.get("updateTime", 0)

    def is_filled(self) -> bool:
        return self.status == "FILLED"

    def summary(self) -> dict:
        """Return a clean dict suitable for printing / logging."""
        return {
            "orderId":      self.order_id,
            "symbol":       self.symbol,
            "side":         self.side,
            "type":         self.order_type,
            "status":       self.status,
            "origQty":      self.orig_qty,
            "executedQty":  self.executed_qty,
            "avgPrice":     self.avg_price,
            "price":        self.price,
            "stopPrice":    self.stop_price,
            "timeInForce":  self.time_in_force,
        }


# ── Order builder ─────────────────────────────────────────────────────────────

def _fmt(value: Optional[Decimal]) -> Optional[str]:
    """Convert Decimal → string with no unnecessary trailing zeros, or None."""
    if value is None:
        return None
    # Normalize removes trailing zeros while preserving the value correctly.
    # e.g. Decimal("50000") → "50000", Decimal("0.10000") → "0.1"
    normalized = value.normalize()
    # Avoid scientific notation for large/small values (e.g. 1E+4 → 50000)
    sign, digits, exp = normalized.as_tuple()
    if exp >= 0:
        return str(int(value))
    return f"{normalized:f}"


def build_order_params(
    symbol:     str,
    side:       str,
    order_type: str,
    quantity:   Decimal,
    price:      Optional[Decimal] = None,
    stop_price: Optional[Decimal] = None,
    time_in_force: str = "GTC",
    reduce_only: bool = False,
) -> dict:
    """
    Construct the parameter dict to send to the Binance /fapi/v1/order endpoint.
    Does NOT call the API — purely data transformation.
    """
    params: dict = {
        "symbol":   symbol,
        "side":     side,
        "type":     order_type,
        "quantity": _fmt(quantity),
    }

    if order_type == "LIMIT":
        params["price"]       = _fmt(price)
        params["timeInForce"] = time_in_force

    elif order_type == "STOP_MARKET":
        params["stopPrice"] = _fmt(stop_price)

    elif order_type == "STOP_LIMIT":
        params["price"]       = _fmt(price)
        params["stopPrice"]   = _fmt(stop_price)
        params["timeInForce"] = time_in_force

    # MARKET — no extra params needed

    if reduce_only:
        params["reduceOnly"] = "true"

    return params


# ── High-level placement function ─────────────────────────────────────────────

def place_order(
    client:     BinanceFuturesClient,
    symbol:     str,
    side:       str,
    order_type: str,
    quantity:   Decimal,
    price:      Optional[Decimal] = None,
    stop_price: Optional[Decimal] = None,
    time_in_force: str = "GTC",
    reduce_only:   bool = False,
) -> OrderResult:
    """
    Build and submit an order, returning a structured OrderResult.

    Raises
    ------
    BinanceAPIError     — exchange rejected the request
    BinanceNetworkError — transport-level failure
    """
    params = build_order_params(
        symbol=symbol,
        side=side,
        order_type=order_type,
        quantity=quantity,
        price=price,
        stop_price=stop_price,
        time_in_force=time_in_force,
        reduce_only=reduce_only,
    )

    logger.info(
        "Placing %s %s order",
        side,
        order_type,
        extra={"order_params": {k: v for k, v in params.items()}},
    )

    try:
        raw = client.place_order(**params)
    except BinanceAPIError as exc:
        logger.error(
            "Order rejected by exchange: [%s] %s",
            exc.code,
            exc.msg,
            extra={"error_code": exc.code, "error_msg": exc.msg},
        )
        raise
    except BinanceNetworkError as exc:
        logger.error("Network failure while placing order: %s", exc)
        raise

    result = OrderResult(raw)
    logger.info(
        "Order placed successfully: id=%s status=%s",
        result.order_id,
        result.status,
        extra={"order_summary": result.summary()},
    )
    return result
