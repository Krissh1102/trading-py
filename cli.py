#!/usr/bin/env python3
"""
cli.py — Command-line interface for the Binance Futures Testnet Trading Bot.

Usage examples
--------------
  # Market buy
  python cli.py place --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001

  # Limit sell
  python cli.py place --symbol ETHUSDT --side SELL --type LIMIT --quantity 0.01 --price 3500

  # Stop-limit buy (bonus order type)
  python cli.py place --symbol BTCUSDT --side BUY --type STOP_LIMIT \\
      --quantity 0.001 --price 68000 --stop-price 67500

  # Check account balances
  python cli.py account

  # List open orders
  python cli.py orders --symbol BTCUSDT

  # Cancel an order
  python cli.py cancel --symbol BTCUSDT --order-id 123456

  # Interactive mode (guided order placement with prompts)
  python cli.py interactive
"""

from __future__ import annotations

import os
import sys
import logging
import argparse
import json
from decimal import Decimal
from typing import Optional

# ── Bootstrap path so we can run `python cli.py` from project root ────────────
sys.path.insert(0, os.path.dirname(__file__))

from bot.logging_config import setup_logging
from bot.client import BinanceFuturesClient, BinanceAPIError, BinanceNetworkError
from bot.orders import place_order, OrderResult
from bot.validators import validate_all, ValidationError, VALID_ORDER_TYPES


# ── Colour helpers (no external deps) ────────────────────────────────────────

class C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    GREEN  = "\033[92m"
    RED    = "\033[91m"
    YELLOW = "\033[93m"
    CYAN   = "\033[96m"
    BLUE   = "\033[94m"
    WHITE  = "\033[97m"
    MAGENTA= "\033[95m"

def _c(text: str, *codes: str) -> str:
    return "".join(codes) + text + C.RESET

def _banner() -> None:
    lines = [
        "┌──────────────────────────────────────────────────────┐",
        "│  ▶  Binance Futures Testnet  ·  Trading Bot  v1.0   │",
        "│     USDT-M Perpetuals  ·  Testnet Only              │",
        "└──────────────────────────────────────────────────────┘",
    ]
    for line in lines:
        print(_c(line, C.CYAN, C.BOLD))
    print()

def _box(title: str, rows: list[tuple[str, str]], color: str = C.CYAN) -> None:
    """Print a bordered key-value box."""
    width = 54
    print(_c(f"  ╔{'═' * width}╗", color))
    print(_c(f"  ║  {title:<{width - 2}}║", color))
    print(_c(f"  ╠{'═' * width}╣", color))
    for key, val in rows:
        line = f"  {key:<20} {val}"
        print(_c(f"  ║  {line:<{width - 2}}║", color))
    print(_c(f"  ╚{'═' * width}╝", color))
    print()

def _ok(msg: str)   -> None: print(_c(f"  ✔  {msg}", C.GREEN, C.BOLD))
def _err(msg: str)  -> None: print(_c(f"  ✖  {msg}", C.RED, C.BOLD))
def _info(msg: str) -> None: print(_c(f"  ℹ  {msg}", C.CYAN))
def _warn(msg: str) -> None: print(_c(f"  ⚠  {msg}", C.YELLOW))


# ── Credential loader ─────────────────────────────────────────────────────────

def load_credentials() -> tuple[str, str]:
    """
    Load API key/secret from environment variables.
    BINANCE_API_KEY and BINANCE_API_SECRET must be set.
    """
    api_key    = os.environ.get("BINANCE_API_KEY", "").strip()
    api_secret = os.environ.get("BINANCE_API_SECRET", "").strip()

    if not api_key or not api_secret:
        _err("Missing API credentials.")
        print(
            _c("\n  Set these environment variables before running:\n", C.DIM) +
            _c("    export BINANCE_API_KEY='your_key'\n", C.YELLOW) +
            _c("    export BINANCE_API_SECRET='your_secret'\n", C.YELLOW)
        )
        sys.exit(1)

    return api_key, api_secret


# ── Result printer ────────────────────────────────────────────────────────────

def print_order_result(result: OrderResult) -> None:
    status_color = C.GREEN if result.is_filled() else C.YELLOW
    rows = [
        ("Order ID",      str(result.order_id)),
        ("Symbol",        result.symbol),
        ("Side",          _c(result.side, C.BOLD)),
        ("Type",          result.order_type),
        ("Status",        _c(result.status, status_color, C.BOLD)),
        ("Orig Qty",      result.orig_qty),
        ("Executed Qty",  result.executed_qty),
        ("Avg Price",     result.avg_price if result.avg_price != "0" else "—"),
        ("Limit Price",   result.price      if result.price != "0"    else "—"),
        ("Stop Price",    result.stop_price if result.stop_price != "0" else "—"),
        ("Time-in-Force", result.time_in_force or "—"),
    ]
    _box("ORDER CONFIRMATION", rows, color=C.GREEN)

    if result.is_filled():
        _ok(f"Order {result.order_id} filled immediately.")
    else:
        _info(f"Order {result.order_id} is {result.status} on the book.")
    print()


# ── Sub-command handlers ──────────────────────────────────────────────────────

def cmd_place(args: argparse.Namespace, client: BinanceFuturesClient) -> int:
    """Handle the `place` sub-command."""
    logger = logging.getLogger("cli.place")

    # ── Validate ──────────────────────────────────────────────────────────────
    try:
        validated = validate_all(
            symbol=args.symbol,
            side=args.side,
            order_type=args.type,
            quantity=args.quantity,
            price=args.price,
            stop_price=getattr(args, "stop_price", None),
        )
    except ValidationError as exc:
        _err(str(exc))
        return 1

    # ── Print request summary ─────────────────────────────────────────────────
    summary_rows = [
        ("Symbol",     validated["symbol"]),
        ("Side",       validated["side"]),
        ("Order Type", validated["order_type"]),
        ("Quantity",   str(validated["quantity"])),
        ("Price",      str(validated["price"])      if validated["price"]      else "—  (MARKET)"),
        ("Stop Price", str(validated["stop_price"]) if validated["stop_price"] else "—"),
    ]
    _box("ORDER REQUEST", summary_rows, color=C.BLUE)

    logger.info(
        "Order request validated",
        extra={"validated_params": {k: str(v) for k, v in validated.items()}},
    )

    # ── Place ─────────────────────────────────────────────────────────────────
    try:
        result = place_order(
            client=client,
            symbol=validated["symbol"],
            side=validated["side"],
            order_type=validated["order_type"],
            quantity=validated["quantity"],
            price=validated["price"],
            stop_price=validated["stop_price"],
        )
    except BinanceAPIError as exc:
        _err(f"Exchange rejected the order: [{exc.code}] {exc.msg}")
        return 1
    except BinanceNetworkError as exc:
        _err(f"Network failure: {exc}")
        return 1

    print_order_result(result)
    return 0


def cmd_account(args: argparse.Namespace, client: BinanceFuturesClient) -> int:
    """Display account balances."""
    logger = logging.getLogger("cli.account")
    _info("Fetching account data…")
    try:
        account = client.get_account()
    except (BinanceAPIError, BinanceNetworkError) as exc:
        _err(f"Failed to fetch account: {exc}")
        return 1

    assets = [a for a in account.get("assets", []) if float(a.get("walletBalance", 0)) > 0]
    if not assets:
        _warn("No assets with a non-zero balance found.")
        return 0

    rows = [(a["asset"], f"{float(a['walletBalance']):.4f}  (unrealised PnL: {float(a.get('unrealizedProfit', 0)):+.4f})")
            for a in assets]
    _box("ACCOUNT BALANCES", rows, color=C.MAGENTA)
    logger.info("Account fetched", extra={"asset_count": len(assets)})
    return 0


def cmd_orders(args: argparse.Namespace, client: BinanceFuturesClient) -> int:
    """List open orders."""
    logger = logging.getLogger("cli.orders")
    symbol = args.symbol.upper() if args.symbol else None
    _info(f"Fetching open orders{' for ' + symbol if symbol else ''}…")
    try:
        orders = client.get_open_orders(symbol=symbol)
    except (BinanceAPIError, BinanceNetworkError) as exc:
        _err(f"Failed to fetch open orders: {exc}")
        return 1

    if not orders:
        _info("No open orders.")
        return 0

    for o in orders:
        rows = [
            ("Order ID",  str(o.get("orderId"))),
            ("Symbol",    o.get("symbol")),
            ("Side",      o.get("side")),
            ("Type",      o.get("type")),
            ("Qty",       o.get("origQty")),
            ("Price",     o.get("price")),
            ("Status",    o.get("status")),
        ]
        _box(f"OPEN ORDER", rows, color=C.YELLOW)

    logger.info("Open orders listed", extra={"count": len(orders)})
    return 0


def cmd_cancel(args: argparse.Namespace, client: BinanceFuturesClient) -> int:
    """Cancel an order by ID."""
    logger = logging.getLogger("cli.cancel")
    symbol   = args.symbol.upper()
    order_id = args.order_id
    _info(f"Cancelling order {order_id} for {symbol}…")
    try:
        result = client.cancel_order(symbol=symbol, order_id=order_id)
    except (BinanceAPIError, BinanceNetworkError) as exc:
        _err(f"Cancel failed: {exc}")
        return 1

    rows = [
        ("Order ID", str(result.get("orderId"))),
        ("Symbol",   result.get("symbol")),
        ("Status",   result.get("status")),
    ]
    _box("ORDER CANCELLED", rows, color=C.YELLOW)
    _ok(f"Order {order_id} cancelled successfully.")
    logger.info("Order cancelled", extra={"orderId": order_id, "symbol": symbol})
    return 0


def cmd_interactive(args: argparse.Namespace, client: BinanceFuturesClient) -> int:
    """
    Guided, menu-driven interactive mode.
    Walks the user through each parameter with prompts and inline validation.
    This is the BONUS enhanced CLI UX.
    """
    print(_c("\n  ═══  Interactive Order Mode  ═══\n", C.CYAN, C.BOLD))
    _info("Type values and press Enter. Press Ctrl+C to quit.\n")

    def prompt(label: str, default: str = "", hint: str = "") -> str:
        hint_str = f"  {_c(hint, C.DIM)}" if hint else ""
        default_str = f" [{_c(default, C.YELLOW)}]" if default else ""
        try:
            val = input(f"  {_c(label, C.WHITE, C.BOLD)}{default_str}{hint_str}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)
        return val or default

    def prompt_choice(label: str, choices: list[str]) -> str:
        choices_str = " / ".join(_c(c, C.YELLOW) for c in choices)
        while True:
            val = prompt(label, hint=f"({choices_str})")
            if val.upper() in choices:
                return val.upper()
            _err(f"Choose one of: {', '.join(choices)}")

    def prompt_decimal(label: str, allow_none: bool = False) -> Optional[Decimal]:
        while True:
            raw = prompt(label, hint="(number)" if not allow_none else "(number or leave blank)")
            if not raw and allow_none:
                return None
            try:
                d = Decimal(raw)
                if d <= 0:
                    raise ValueError
                return d
            except Exception:
                _err("Enter a positive number (e.g. 0.001)")

    print()
    symbol     = prompt("Symbol", default="BTCUSDT", hint="e.g. BTCUSDT, ETHUSDT")
    side       = prompt_choice("Side",       ["BUY", "SELL"])
    order_type = prompt_choice("Order Type", ["MARKET", "LIMIT", "STOP_MARKET", "STOP_LIMIT"])
    quantity   = prompt_decimal("Quantity")

    price = None
    if order_type in {"LIMIT", "STOP_LIMIT"}:
        price = prompt_decimal("Limit Price")

    stop_price = None
    if order_type in {"STOP_MARKET", "STOP_LIMIT"}:
        stop_price = prompt_decimal("Stop Price")

    # Re-use the place flow
    class _FakeArgs:
        pass
    fa = _FakeArgs()
    fa.symbol     = symbol
    fa.side       = side
    fa.type       = order_type
    fa.quantity   = str(quantity)
    fa.price      = str(price) if price else None
    fa.stop_price = str(stop_price) if stop_price else None

    print()
    return cmd_place(fa, client)


# ── Argument parser ───────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading_bot",
        description="Binance Futures Testnet Trading Bot — USDT-M Perpetuals",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py place --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001
  python cli.py place --symbol ETHUSDT --side SELL --type LIMIT --quantity 0.01 --price 3500
  python cli.py place --symbol BTCUSDT --side BUY --type STOP_LIMIT \\
      --quantity 0.001 --price 68000 --stop-price 67500
  python cli.py account
  python cli.py orders --symbol BTCUSDT
  python cli.py cancel --symbol BTCUSDT --order-id 123456
  python cli.py interactive
        """,
    )

    parser.add_argument(
        "--log-file", default="logs/trading_bot.log",
        help="Path to the log file (default: logs/trading_bot.log)",
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Console log verbosity (default: INFO)",
    )
    parser.add_argument(
        "--base-url", default=None,
        help="Override the Binance Futures base URL",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # ── place ─────────────────────────────────────────────────────────────────
    place_p = sub.add_parser("place", help="Place a new order")
    place_p.add_argument("--symbol",     required=True, help="Trading pair, e.g. BTCUSDT")
    place_p.add_argument("--side",       required=True, choices=["BUY", "SELL"],
                         type=str.upper, help="BUY or SELL")
    place_p.add_argument("--type",       required=True,
                         choices=list(VALID_ORDER_TYPES), type=str.upper,
                         help="MARKET | LIMIT | STOP_MARKET | STOP_LIMIT")
    place_p.add_argument("--quantity",   required=True, help="Order quantity in base asset")
    place_p.add_argument("--price",      default=None,  help="Limit price (required for LIMIT/STOP_LIMIT)")
    place_p.add_argument("--stop-price", dest="stop_price", default=None,
                         help="Stop trigger price (required for STOP_MARKET/STOP_LIMIT)")

    # ── account ───────────────────────────────────────────────────────────────
    sub.add_parser("account", help="Show account balances")

    # ── orders ────────────────────────────────────────────────────────────────
    orders_p = sub.add_parser("orders", help="List open orders")
    orders_p.add_argument("--symbol", default=None, help="Filter by symbol")

    # ── cancel ────────────────────────────────────────────────────────────────
    cancel_p = sub.add_parser("cancel", help="Cancel an open order")
    cancel_p.add_argument("--symbol",   required=True, help="Trading pair")
    cancel_p.add_argument("--order-id", dest="order_id", required=True, type=int,
                          help="Order ID to cancel")

    # ── interactive ───────────────────────────────────────────────────────────
    sub.add_parser("interactive", help="Guided interactive order placement (BONUS)")

    return parser


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = build_parser()
    args   = parser.parse_args()

    # ── Logging ───────────────────────────────────────────────────────────────
    import os as _os
    log_dir  = _os.path.dirname(args.log_file) or "logs"
    log_file = _os.path.basename(args.log_file)
    setup_logging(
        log_dir=log_dir,
        log_file=log_file,
        console_level=getattr(logging, args.log_level),
    )
    logger = logging.getLogger("cli")

    _banner()

    # ── Credentials + client ──────────────────────────────────────────────────
    api_key, api_secret = load_credentials()
    from bot.client import TESTNET_BASE_URL
    client = BinanceFuturesClient(
        api_key=api_key,
        api_secret=api_secret,
        base_url=args.base_url or TESTNET_BASE_URL,
    )

    # ── Connectivity check ────────────────────────────────────────────────────
    if not client.ping():
        _err("Cannot reach Binance Futures Testnet. Check your internet connection.")
        sys.exit(1)
    _ok("Connected to Binance Futures Testnet")
    print()

    # ── Dispatch ──────────────────────────────────────────────────────────────
    HANDLERS = {
        "place":       cmd_place,
        "account":     cmd_account,
        "orders":      cmd_orders,
        "cancel":      cmd_cancel,
        "interactive": cmd_interactive,
    }

    handler = HANDLERS.get(args.command)
    if handler is None:
        _err(f"Unknown command: {args.command}")
        sys.exit(1)

    logger.info("Command dispatched: %s", args.command)
    exit_code = handler(args, client)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
