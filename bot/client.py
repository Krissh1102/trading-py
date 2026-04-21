
from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any, Optional
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# ── Defaults ─────────────────────────────────────────────────────────────────

TESTNET_BASE_URL = "https://testnet.binancefuture.com"
DEFAULT_TIMEOUT  = 10  # seconds
MAX_RETRIES      = 3
RECV_WINDOW      = 5000  # ms


# ── Custom exceptions ─────────────────────────────────────────────────────────

class BinanceAPIError(Exception):
    """Raised when the Binance API returns a non-2xx response or an error payload."""

    def __init__(self, code: int, msg: str, http_status: int = 0):
        self.code        = code
        self.msg         = msg
        self.http_status = http_status
        super().__init__(f"[Binance Error {code}] {msg}")


class BinanceNetworkError(Exception):
    """Raised on transport-level failures (timeouts, connection refused, etc.)."""


# ── Client ────────────────────────────────────────────────────────────────────

class BinanceFuturesClient:
    """
    Thin, authenticated wrapper around the Binance USDT-M Futures REST API.

    Parameters
    ----------
    api_key    : Your Binance Futures Testnet API key.
    api_secret : Matching secret.
    base_url   : Defaults to the testnet endpoint.
    timeout    : Request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = TESTNET_BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self._api_key    = api_key
        self._api_secret = api_secret.encode()
        self._base_url   = base_url.rstrip("/")
        self._timeout    = timeout
        self._session    = self._build_session()
        logger.debug("BinanceFuturesClient initialised", extra={"base_url": self._base_url})

    # ── Session factory ───────────────────────────────────────────────────────

    @staticmethod
    def _build_session() -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=MAX_RETRIES,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "DELETE"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://",  adapter)
        return session

    # ── Signing ───────────────────────────────────────────────────────────────

    def _sign(self, params: dict) -> dict:
        params["timestamp"]  = int(time.time() * 1000)
        params["recvWindow"] = RECV_WINDOW
        query_string = urlencode(params)
        signature = hmac.new(
            self._api_secret,
            query_string.encode(),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = signature
        return params

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    def _headers(self) -> dict:
        return {"X-MBX-APIKEY": self._api_key}

    def _handle_response(self, response: requests.Response) -> Any:
        logger.debug(
            "API response received",
            extra={
                "status_code": response.status_code,
                "url":         response.url,
                "body":        response.text[:2000],  # truncate huge responses
            },
        )
        try:
            data = response.json()
        except ValueError:
            response.raise_for_status()
            return response.text

        if isinstance(data, dict) and "code" in data and data["code"] != 200:
            raise BinanceAPIError(
                code=data.get("code", -1),
                msg=data.get("msg", "Unknown error"),
                http_status=response.status_code,
            )

        response.raise_for_status()
        return data

    def _get(self, path: str, params: Optional[dict] = None, signed: bool = False) -> Any:
        params = params or {}
        if signed:
            params = self._sign(params)
        url = f"{self._base_url}{path}"
        logger.debug("GET request", extra={"url": url, "params": {k: v for k, v in params.items() if k != "signature"}})
        try:
            resp = self._session.get(url, params=params, headers=self._headers(), timeout=self._timeout)
        except requests.exceptions.RequestException as exc:
            logger.error("Network error on GET %s: %s", path, exc)
            raise BinanceNetworkError(str(exc)) from exc
        return self._handle_response(resp)

    def _post(self, path: str, params: dict, signed: bool = True) -> Any:
        if signed:
            params = self._sign(params)
        url = f"{self._base_url}{path}"
        safe_params = {k: v for k, v in params.items() if k != "signature"}
        logger.debug("POST request", extra={"url": url, "params": safe_params})
        try:
            resp = self._session.post(url, params=params, headers=self._headers(), timeout=self._timeout)
        except requests.exceptions.RequestException as exc:
            logger.error("Network error on POST %s: %s", path, exc)
            raise BinanceNetworkError(str(exc)) from exc
        return self._handle_response(resp)

    # ── Public API methods ────────────────────────────────────────────────────

    def ping(self) -> bool:
        """Return True if the exchange is reachable."""
        try:
            self._get("/fapi/v1/ping")
            logger.info("Exchange ping successful")
            return True
        except Exception as exc:
            logger.warning("Exchange ping failed: %s", exc)
            return False

    def get_server_time(self) -> int:
        """Return Binance server time in milliseconds."""
        data = self._get("/fapi/v1/time")
        return data["serverTime"]

    def get_exchange_info(self) -> dict:
        """Return exchange metadata (symbol filters, precision, etc.)."""
        return self._get("/fapi/v1/exchangeInfo")

    def get_symbol_info(self, symbol: str) -> Optional[dict]:
        """Return the exchange-info entry for a single symbol, or None."""
        info = self.get_exchange_info()
        for s in info.get("symbols", []):
            if s["symbol"] == symbol.upper():
                return s
        return None

    def get_account(self) -> dict:
        """Return futures account balances and positions."""
        return self._get("/fapi/v2/account", signed=True)

    def place_order(self, **kwargs) -> dict:
        """
        Place a futures order.  kwargs are passed directly to the API;
        see orders.py for how they are constructed.
        """
        return self._post("/fapi/v1/order", params=kwargs)

    def get_order(self, symbol: str, order_id: int) -> dict:
        """Fetch a single order by ID."""
        return self._get("/fapi/v1/order", params={"symbol": symbol, "orderId": order_id}, signed=True)

    def cancel_order(self, symbol: str, order_id: int) -> dict:
        """Cancel an open order."""
        from requests import delete as _delete  # lazy import to avoid circular
        params = self._sign({"symbol": symbol, "orderId": order_id})
        url = f"{self._base_url}/fapi/v1/order"
        logger.debug("DELETE request", extra={"url": url, "orderId": order_id})
        try:
            resp = self._session.delete(url, params=params, headers=self._headers(), timeout=self._timeout)
        except requests.exceptions.RequestException as exc:
            raise BinanceNetworkError(str(exc)) from exc
        return self._handle_response(resp)

    def get_open_orders(self, symbol: Optional[str] = None) -> list:
        """Return all open orders, optionally filtered by symbol."""
        params: dict = {}
        if symbol:
            params["symbol"] = symbol
        return self._get("/fapi/v1/openOrders", params=params, signed=True)

    def get_position_risk(self, symbol: Optional[str] = None) -> list:
        """Return position risk data."""
        params: dict = {}
        if symbol:
            params["symbol"] = symbol
        return self._get("/fapi/v2/positionRisk", params=params, signed=True)
