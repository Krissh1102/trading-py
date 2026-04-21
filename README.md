# Binance Futures Testnet Trading Bot

A clean, production-ready Python trading bot for **Binance USDT-M Futures Testnet** with structured logging, full input validation, and a polished CLI experience.

---

## Features

| Category | Details |
|----------|---------|
| **Order Types** | MARKET, LIMIT, STOP\_MARKET *(bonus)*, STOP\_LIMIT *(bonus)* |
| **Sides** | BUY / SELL |
| **CLI** | `argparse` with subcommands + bonus interactive guided mode |
| **Logging** | Rotating JSON file log + coloured console output |
| **Validation** | Strict per-field validation with helpful error messages |
| **Error Handling** | Typed exceptions for API errors vs. network failures |
| **Testing** | 42 unit tests (100% pass), zero network calls in tests |
| **Transport** | Native `requests` with automatic retry on 5xx / 429 |

---

## Project Structure

```
trading_bot/
├── bot/
│   ├── __init__.py          # package marker + version
│   ├── client.py            # Binance REST client (signing, retries, error handling)
│   ├── orders.py            # Order construction + placement logic
│   ├── validators.py        # Pure-function input validation
│   └── logging_config.py   # JSON file logger + coloured console logger
├── tests/
│   ├── test_validators.py   # 30 unit tests for validation
│   └── test_orders.py       # 12 unit tests for order logic (mocked client)
├── logs/
│   └── trading_bot.log      # sample log from real testnet orders (JSON lines)
├── cli.py                   # CLI entry point (subcommands + interactive mode)
├── requirements.txt
└── README.md
```

---

## Setup

### 1. Clone / unzip the repository

```bash
git clone https://github.com/<your-username>/trading-bot.git
cd trading-bot
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Get Testnet API credentials

1. Visit [https://testnet.binancefuture.com](https://testnet.binancefuture.com)
2. Log in with your GitHub account
3. Navigate to **API Key** and generate a key pair
4. Copy your **API Key** and **Secret Key**

### 5. Set environment variables

```bash
export BINANCE_API_KEY="your_api_key_here"
export BINANCE_API_SECRET="your_api_secret_here"
```

> **Windows (PowerShell):**
> ```powershell
> $env:BINANCE_API_KEY="your_api_key_here"
> $env:BINANCE_API_SECRET="your_api_secret_here"
> ```

---

## Usage

All commands share these optional global flags:

```
--log-file PATH      Path to log file     (default: logs/trading_bot.log)
--log-level LEVEL    Console verbosity    (default: INFO; options: DEBUG INFO WARNING ERROR)
--base-url URL       Override base URL    (default: https://testnet.binancefuture.com)
```

---

### Place a Market Order

```bash
# BUY 0.001 BTC at market price
python cli.py place --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001

# SELL 0.1 ETH at market price
python cli.py place --symbol ETHUSDT --side SELL --type MARKET --quantity 0.1
```

### Place a Limit Order

```bash
# BUY 0.001 BTC at $42,000 (resting limit)
python cli.py place --symbol BTCUSDT --side BUY --type LIMIT --quantity 0.001 --price 42000

# SELL 0.01 ETH at $3,500
python cli.py place --symbol ETHUSDT --side SELL --type LIMIT --quantity 0.01 --price 3500
```

### Place a Stop-Market Order *(bonus)*

```bash
# SELL 0.001 BTC as market when price drops to $40,000
python cli.py place --symbol BTCUSDT --side SELL --type STOP_MARKET \
    --quantity 0.001 --stop-price 40000
```

### Place a Stop-Limit Order *(bonus)*

```bash
# BUY 0.001 BTC with limit $68,000 triggered when price hits $67,500
python cli.py place --symbol BTCUSDT --side BUY --type STOP_LIMIT \
    --quantity 0.001 --price 68000 --stop-price 67500
```

---

### View Account Balances

```bash
python cli.py account
```

### List Open Orders

```bash
# All symbols
python cli.py orders

# Single symbol
python cli.py orders --symbol BTCUSDT
```

### Cancel an Order

```bash
python cli.py cancel --symbol BTCUSDT --order-id 3281950148
```

---

### Interactive Mode *(bonus)*

Guided, prompt-driven order placement — no flags required:

```bash
python cli.py interactive
```

You will be prompted step by step for symbol, side, order type, quantity, and price. Each field is validated inline with immediate feedback.

---

## Running the Tests

```bash
python -m pytest tests/ -v
```

Expected output: **42 passed**.

Tests are fully isolated — no API keys or network access required.

---

## Log File

Logs are written to `logs/trading_bot.log` in **JSON Lines** format (one JSON object per line), making them trivially parseable by tools like `jq`, Splunk, Datadog, or any log aggregator.

```bash
# Pretty-print the last 5 log entries
tail -5 logs/trading_bot.log | python -m json.tool

# Filter only ERROR entries
grep '"level": "ERROR"' logs/trading_bot.log | python -m json.tool
```

The console uses coloured, human-readable output while the file captures full structured detail including order parameters and API responses.

---

## Design Decisions & Assumptions

### No `python-binance` library
The bot uses raw `requests` calls. This avoids a heavy dependency with its own abstractions, gives full control over retry logic, and makes the signing process explicit and auditable.

### Decimal arithmetic throughout
All prices and quantities use Python's `decimal.Decimal` (not `float`) to avoid IEEE 754 rounding surprises — critical when constructing financial order parameters.

### Separation of concerns
| Layer | File | Knows about |
|-------|------|-------------|
| Transport | `client.py` | HTTP, signing, retries, auth |
| Business logic | `orders.py` | What to send, how to format results |
| Validation | `validators.py` | What constitutes valid input |
| Presentation | `cli.py` | How to talk to the user |
| Plumbing | `logging_config.py` | How to record events |

No layer reaches into another layer's responsibility.

### Retry strategy
The `requests.Session` is configured with `urllib3.Retry` to automatically back off and retry on HTTP 429 (rate limit) and 5xx server errors. Connection-level failures raise `BinanceNetworkError`; exchange-level rejections raise `BinanceAPIError` — both are distinct types so callers can handle them separately.

### Testnet base URL
All API calls target `https://testnet.binancefuture.com`. This can be overridden with `--base-url` for flexibility, but the default is always the testnet endpoint.

---

## Dependencies

```
requests>=2.31.0   # HTTP client with retry support
urllib3>=2.0.0     # Underlying transport (used by requests)
```

Dev / test only (not in requirements.txt):
```
pytest             # Test runner
```

---

## Example Terminal Output

```
┌──────────────────────────────────────────────────────┐
│  ▶  Binance Futures Testnet  ·  Trading Bot  v1.0   │
│     USDT-M Perpetuals  ·  Testnet Only              │
└──────────────────────────────────────────────────────┘

  ✔  Connected to Binance Futures Testnet

  ╔══════════════════════════════════════════════════════╗
  ║  ORDER REQUEST                                       ║
  ╠══════════════════════════════════════════════════════╣
  ║  Symbol               BTCUSDT                       ║
  ║  Side                 BUY                           ║
  ║  Order Type           MARKET                        ║
  ║  Quantity             0.001                         ║
  ║  Price                —  (MARKET)                  ║
  ║  Stop Price           —                             ║
  ╚══════════════════════════════════════════════════════╝

  ╔══════════════════════════════════════════════════════╗
  ║  ORDER CONFIRMATION                                  ║
  ╠══════════════════════════════════════════════════════╣
  ║  Order ID             3281950148                    ║
  ║  Symbol               BTCUSDT                       ║
  ║  Side                 BUY                           ║
  ║  Type                 MARKET                        ║
  ║  Status               FILLED                        ║
  ║  Orig Qty             0.001                         ║
  ║  Executed Qty         0.001                         ║
  ║  Avg Price            42680.10                      ║
  ╚══════════════════════════════════════════════════════╝

  ✔  Order 3281950148 filled immediately.
```
#   t r a d i n g - p y  
 