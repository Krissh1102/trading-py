
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Optional


# ── Constants ────────────────────────────────────────────────────────────────

VALID_SIDES       = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_MARKET", "STOP_LIMIT"}

# Binance symbol pattern: all-caps letters+digits, typically ending with USDT/BUSD/BTC …
_SYMBOL_RE = re.compile(r"^[A-Z0-9]{3,20}$")


# ── Exceptions ───────────────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised when user-supplied order parameters fail validation."""


# ── Helpers ──────────────────────────────────────────────────────────────────

def _to_decimal(value: str | float | Decimal, field: str) -> Decimal:
    try:
        d = Decimal(str(value))
    except InvalidOperation:
        raise ValidationError(f"'{field}' must be a valid number, got: {value!r}")
    return d


# ── Public validators ────────────────────────────────────────────────────────

def validate_symbol(symbol: str) -> str:
    symbol = symbol.strip().upper()
    if not _SYMBOL_RE.match(symbol):
        raise ValidationError(
            f"Invalid symbol '{symbol}'. Expected uppercase letters/digits, e.g. BTCUSDT."
        )
    return symbol


def validate_side(side: str) -> str:
    side = side.strip().upper()
    if side not in VALID_SIDES:
        raise ValidationError(
            f"Invalid side '{side}'. Choose from: {', '.join(sorted(VALID_SIDES))}."
        )
    return side


def validate_order_type(order_type: str) -> str:
    order_type = order_type.strip().upper()
    if order_type not in VALID_ORDER_TYPES:
        raise ValidationError(
            f"Invalid order type '{order_type}'. "
            f"Choose from: {', '.join(sorted(VALID_ORDER_TYPES))}."
        )
    return order_type


def validate_quantity(quantity: str | float) -> Decimal:
    qty = _to_decimal(quantity, "quantity")
    if qty <= 0:
        raise ValidationError(f"Quantity must be positive, got: {qty}.")
    return qty


def validate_price(price: Optional[str | float], order_type: str) -> Optional[Decimal]:
    """Price is required for LIMIT / STOP_LIMIT, forbidden for MARKET / STOP_MARKET."""
    if order_type in {"LIMIT", "STOP_LIMIT"}:
        if price is None:
            raise ValidationError(f"Price is required for {order_type} orders.")
        p = _to_decimal(price, "price")
        if p <= 0:
            raise ValidationError(f"Price must be positive, got: {p}.")
        return p
    else:
        if price is not None:
            raise ValidationError(
                f"Price must NOT be supplied for {order_type} orders (it is ignored by the exchange)."
            )
        return None


def validate_stop_price(stop_price: Optional[str | float], order_type: str) -> Optional[Decimal]:
    """Stop price required for STOP_MARKET / STOP_LIMIT."""
    if order_type in {"STOP_MARKET", "STOP_LIMIT"}:
        if stop_price is None:
            raise ValidationError(f"--stop-price is required for {order_type} orders.")
        sp = _to_decimal(stop_price, "stop_price")
        if sp <= 0:
            raise ValidationError(f"Stop price must be positive, got: {sp}.")
        return sp
    return None


def validate_all(
    *,
    symbol: str,
    side: str,
    order_type: str,
    quantity: str | float,
    price: Optional[str | float] = None,
    stop_price: Optional[str | float] = None,
) -> dict:
    """
    Run all validators and return a clean dict of validated parameters.
    Raises ValidationError on the first problem found.
    """
    v_symbol     = validate_symbol(symbol)
    v_side       = validate_side(side)
    v_type       = validate_order_type(order_type)
    v_qty        = validate_quantity(quantity)
    v_price      = validate_price(price, v_type)
    v_stop_price = validate_stop_price(stop_price, v_type)

    return {
        "symbol":     v_symbol,
        "side":       v_side,
        "order_type": v_type,
        "quantity":   v_qty,
        "price":      v_price,
        "stop_price": v_stop_price,
    }
