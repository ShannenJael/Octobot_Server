"""Crypto.com Exchange Pro API Client, Paper Trading Engine, and Strategy Suite."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("CryptoComTrade")


class CryptoComAPIError(RuntimeError):
    """Raised when Crypto.com Exchange API returns an error."""
    pass


class CryptoComExchangeClient:
    """Production-ready client for Crypto.com Exchange Pro REST API (Public and Private v1)."""

    BASE_URL = "https://api.crypto.com/exchange/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        timeout: float = 10.0,
        retries: int = 2,
    ):
        self.api_key = api_key or os.getenv("CRYPTO_COM_API_KEY", "")
        self.api_secret = api_secret or os.getenv("CRYPTO_COM_API_SECRET", "")
        self.timeout = timeout
        self.retries = retries

    def set_credentials(self, api_key: str, api_secret: str) -> None:
        self.api_key = api_key.strip()
        self.api_secret = api_secret.strip()

    @property
    def has_credentials(self) -> bool:
        return bool(self.api_key and self.api_secret)

    @staticmethod
    def _serialize_params(params: Optional[Dict[str, Any]]) -> str:
        """Serializes params dictionary into canonical string for HMAC-SHA256 signing.
        Crypto.com specification: keys sorted alphabetically, key+val concatenated.
        """
        if not params:
            return ""
        items = []
        for key in sorted(params.keys()):
            val = params[key]
            if val is None:
                continue
            if isinstance(val, bool):
                items.append(f"{key}{'true' if val else 'false'}")
            elif isinstance(val, (int, float, str)):
                items.append(f"{key}{val}")
            elif isinstance(val, list):
                for elem in val:
                    if isinstance(elem, dict):
                        for subk in sorted(elem.keys()):
                            items.append(f"{subk}{elem[subk]}")
                    else:
                        items.append(f"{elem}")
            elif isinstance(val, dict):
                for subk in sorted(val.keys()):
                    items.append(f"{subk}{val[subk]}")
            else:
                items.append(f"{key}{val}")
        return "".join(items)

    @classmethod
    def sign_payload(
        cls,
        method: str,
        req_id: int,
        api_key: str,
        api_secret: str,
        params: Optional[Dict[str, Any]],
        nonce: int,
    ) -> str:
        """Computes the HMAC-SHA256 signature per Crypto.com Exchange API Pro specification."""
        param_str = cls._serialize_params(params)
        sig_payload = f"{method}{req_id}{api_key}{param_str}{nonce}"
        return hmac.new(
            api_secret.encode("utf-8"),
            sig_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _request(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        is_private: bool = False,
    ) -> Dict[str, Any]:
        params = params or {}
        req_id = int(time.time() * 1000)
        nonce = req_id

        if not is_private:
            query = urllib.parse.urlencode(params)
            url = f"{self.BASE_URL}/{method}" + (f"?{query}" if query else "")
            headers = {
                "Accept": "application/json",
                "User-Agent": "OctoBot-CryptoCom-Trader/1.0",
            }
            body = None
        else:
            if not self.has_credentials:
                raise CryptoComAPIError("API key and secret must be configured for private endpoints")
            url = f"{self.BASE_URL}/{method}"
            sig = self.sign_payload(
                method, req_id, self.api_key, self.api_secret, params, nonce
            )
            payload = {
                "id": req_id,
                "method": method,
                "api_key": self.api_key,
                "params": params,
                "nonce": nonce,
                "sig": sig,
            }
            body = json.dumps(payload).encode("utf-8")
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "OctoBot-CryptoCom-Trader/1.0",
            }

        last_err = None
        for attempt in range(self.retries + 1):
            try:
                req = urllib.request.Request(url, data=body, headers=headers)
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.load(resp)
                code = data.get("code", 0)
                if code != 0:
                    msg = data.get("message") or f"Code {code}"
                    raise CryptoComAPIError(f"Crypto.com error {code}: {msg}")
                return data.get("result") or {}
            except (OSError, urllib.error.URLError, ValueError, CryptoComAPIError) as err:
                last_err = err
                if attempt < self.retries and not isinstance(err, CryptoComAPIError):
                    time.sleep(0.3 * (2**attempt))
        raise CryptoComAPIError(f"Request failed ({method}): {last_err}")

    # --- Public Endpoints ---

    def get_instruments(self) -> List[Dict[str, Any]]:
        """List all trading pairs and specifications."""
        res = self._request("public/get-instruments")
        return list(res.get("data") or [])

    def get_tickers(self) -> List[Dict[str, Any]]:
        """List 24h ticker statistics for all markets."""
        res = self._request("public/get-tickers")
        return list(res.get("data") or [])

    def get_ticker(self, instrument: str) -> Optional[Dict[str, Any]]:
        """Fetch single instrument ticker."""
        res = self._request("public/get-tickers", {"instrument_name": instrument})
        data = res.get("data") or []
        return data[0] if data else None

    def get_book(self, instrument: str, depth: int = 20) -> Dict[str, Any]:
        """Fetch order book bids and asks."""
        res = self._request("public/get-book", {"instrument_name": instrument, "depth": depth})
        data = res.get("data") or []
        return data[0] if data else {"bids": [], "asks": []}

    def get_candlestick(
        self, instrument: str, timeframe: str = "1h", count: int = 100
    ) -> List[Dict[str, Any]]:
        """Fetch OHLCV candles."""
        res = self._request(
            "public/get-candlestick",
            {"instrument_name": instrument, "timeframe": timeframe, "count": count},
        )
        candles = list(res.get("data") or [])
        candles.sort(key=lambda c: int(c.get("t", 0)))
        return candles

    def get_trades(self, instrument: str, count: int = 40) -> List[Dict[str, Any]]:
        """Fetch recent public market trades."""
        res = self._request(
            "public/get-trades",
            {"instrument_name": instrument, "count": count},
        )
        return list(res.get("data") or [])

    # --- Private Endpoints ---

    def get_account_summary(self) -> Dict[str, Any]:
        """Retrieve user balances using Crypto.com Exchange API v1."""
        try:
            return self._request("private/user-balance", is_private=True)
        except Exception:
            return self._request("private/get-accounts", is_private=True)

    def create_order(
        self,
        instrument: str,
        side: str,  # 'BUY' or 'SELL'
        order_type: str,  # 'LIMIT' or 'MARKET'
        quantity: Optional[float] = None,
        price: Optional[float] = None,
        notional: Optional[float] = None,
        client_oid: Optional[str] = None,
        stop_loss: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Submit a new spot order to Crypto.com Exchange."""
        params: Dict[str, Any] = {
            "instrument_name": instrument,
            "side": side.upper(),
            "type": order_type.upper(),
        }
        if price is not None and order_type.upper() != "MARKET":
            params["price"] = str(price)
        if quantity is not None:
            params["quantity"] = str(quantity)
        if notional is not None and order_type.upper() == "MARKET" and side.upper() == "BUY":
            params["notional"] = str(notional)
        if client_oid:
            params["client_oid"] = str(client_oid)
        if stop_loss:
            params["stop_loss"] = str(stop_loss)

        return self._request("private/create-order", params=params, is_private=True)

    def cancel_order(self, instrument: str, order_id: str) -> Dict[str, Any]:
        """Cancel an open order."""
        return self._request(
            "private/cancel-order",
            {"instrument_name": instrument, "order_id": str(order_id)},
            is_private=True,
        )

    def cancel_all_orders(self, instrument: Optional[str] = None) -> Dict[str, Any]:
        """Cancel all open orders, optionally for a specific instrument."""
        params = {}
        if instrument:
            params["instrument_name"] = instrument
        return self._request("private/cancel-all-orders", params=params, is_private=True)

    def get_open_orders(self, instrument: Optional[str] = None) -> List[Dict[str, Any]]:
        """List currently open orders."""
        params = {}
        if instrument:
            params["instrument_name"] = instrument
        res = self._request("private/get-open-orders", params=params, is_private=True)
        return list(res.get("data") or [])

    def get_order_history(self, instrument: Optional[str] = None) -> List[Dict[str, Any]]:
        """List historic filled/canceled orders."""
        params = {}
        if instrument:
            params["instrument_name"] = instrument
        res = self._request("private/get-order-history", params=params, is_private=True)
        return list(res.get("data") or [])


class PaperTradingEngine:
    """Simulates spot trading ledger and order execution without risking real funds."""

    def __init__(self, storage_dir: Optional[Path] = None, initial_usdt: float = 10000.0):
        self.storage_dir = storage_dir or Path(os.getenv("MARKET_RADAR_DATA_DIR", "user/crypto_com_trader"))
        self.file_path = self.storage_dir / "paper_ledger.json"
        self._lock = threading.Lock()
        self.initial_usdt = initial_usdt
        self.balances: Dict[str, float] = {"USDT": self.initial_usdt}
        self.open_orders: List[Dict[str, Any]] = []
        self.order_history: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        try:
            if self.file_path.exists():
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.balances = data.get("balances", {"USDT": self.initial_usdt})
                    self.open_orders = data.get("open_orders", [])
                    self.order_history = data.get("order_history", [])
        except Exception as e:
            logger.warning("Failed to load paper trading ledger: %s", e)
            self.balances = {"USDT": self.initial_usdt}

    def _save(self) -> None:
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            temp = self.file_path.with_suffix(".tmp")
            with open(temp, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "balances": self.balances,
                        "open_orders": self.open_orders,
                        "order_history": self.order_history[-200:],  # keep last 200
                        "updated_at": int(time.time()),
                    },
                    f,
                    indent=2,
                )
            temp.replace(self.file_path)
        except Exception as e:
            logger.error("Failed to save paper trading ledger: %s", e)

    def reset_balances(self, usdt_amount: float = 10000.0) -> Dict[str, float]:
        with self._lock:
            self.balances = {"USDT": float(usdt_amount)}
            self.open_orders = []
            self.order_history = []
            self._save()
            return dict(self.balances)

    def get_portfolio(self, current_prices: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        with self._lock:
            prices = current_prices or {}
            total_usdt = 0.0
            breakdown = []
            for asset, qty in sorted(self.balances.items()):
                if qty <= 1e-7:
                    continue
                if asset == "USDT":
                    val = qty
                else:
                    px = prices.get(f"{asset}_USDT") or prices.get(asset, 0.0)
                    val = qty * px
                total_usdt += val
                breakdown.append({
                    "asset": asset,
                    "quantity": qty,
                    "value_usdt": round(val, 2),
                    "price": prices.get(f"{asset}_USDT", 1.0 if asset == "USDT" else 0.0),
                })
            return {
                "total_equity_usdt": round(total_usdt, 2),
                "unrealized_pnl_usdt": round(total_usdt - self.initial_usdt, 2),
                "unrealized_pnl_pct": round(((total_usdt - self.initial_usdt) / self.initial_usdt) * 100, 2),
                "breakdown": breakdown,
                "balances": dict(self.balances),
            }

    def execute_order(
        self,
        instrument: str,
        side: str,  # 'BUY' or 'SELL'
        order_type: str,  # 'MARKET' or 'LIMIT'
        quantity: float,
        price: Optional[float] = None,
        market_bid: Optional[float] = None,
        market_ask: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Executes a simulated paper order against live market prices."""
        with self._lock:
            base, quote = instrument.split("_")
            side = side.upper()
            order_type = order_type.upper()
            now = int(time.time())
            order_id = f"paper_{now}_{len(self.order_history) + 1}"

            # Validate execution price
            exec_price = price
            if order_type == "MARKET":
                if side == "BUY":
                    exec_price = market_ask or market_bid or price
                else:
                    exec_price = market_bid or market_ask or price

            if not exec_price or exec_price <= 0:
                raise ValueError(f"Unable to determine valid execution price for {instrument}")

            notional = round(quantity * exec_price, 4)
            fee_usdt = round(notional * 0.00075, 4)  # 0.075% maker/taker fee

            if side == "BUY":
                needed = notional + fee_usdt
                avail = self.balances.get(quote, 0.0)
                if avail < needed:
                    raise ValueError(f"Insufficient {quote} balance. Needed: {needed:.2f}, Available: {avail:.2f}")

                if order_type == "MARKET":
                    self.balances[quote] = avail - needed
                    self.balances[base] = self.balances.get(base, 0.0) + quantity
                    record = {
                        "order_id": order_id,
                        "instrument": instrument,
                        "side": side,
                        "type": order_type,
                        "quantity": quantity,
                        "price": exec_price,
                        "notional": notional,
                        "fee": fee_usdt,
                        "status": "FILLED",
                        "created_at": now,
                        "filled_at": now,
                    }
                    self.order_history.append(record)
                    self._save()
                    return record
                else:
                    # LIMIT BUY: lock quote funds and register open order
                    self.balances[quote] = avail - needed
                    order_obj = {
                        "order_id": order_id,
                        "instrument": instrument,
                        "side": side,
                        "type": order_type,
                        "quantity": quantity,
                        "price": exec_price,
                        "locked_funds": needed,
                        "status": "ACTIVE",
                        "created_at": now,
                    }
                    self.open_orders.append(order_obj)
                    self._save()
                    return order_obj

            elif side == "SELL":
                avail = self.balances.get(base, 0.0)
                if avail < quantity:
                    raise ValueError(f"Insufficient {base} balance. Needed: {quantity:.6f}, Available: {avail:.6f}")

                if order_type == "MARKET":
                    self.balances[base] = avail - quantity
                    credit = max(0.0, notional - fee_usdt)
                    self.balances[quote] = self.balances.get(quote, 0.0) + credit
                    record = {
                        "order_id": order_id,
                        "instrument": instrument,
                        "side": side,
                        "type": order_type,
                        "quantity": quantity,
                        "price": exec_price,
                        "notional": notional,
                        "fee": fee_usdt,
                        "status": "FILLED",
                        "created_at": now,
                        "filled_at": now,
                    }
                    self.order_history.append(record)
                    self._save()
                    return record
                else:
                    # LIMIT SELL: lock base asset
                    self.balances[base] = avail - quantity
                    order_obj = {
                        "order_id": order_id,
                        "instrument": instrument,
                        "side": side,
                        "type": order_type,
                        "quantity": quantity,
                        "price": exec_price,
                        "status": "ACTIVE",
                        "created_at": now,
                    }
                    self.open_orders.append(order_obj)
                    self._save()
                    return order_obj
            else:
                raise ValueError(f"Invalid order side: {side}")

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        with self._lock:
            idx = next((i for i, o in enumerate(self.open_orders) if o["order_id"] == order_id), None)
            if idx is None:
                raise ValueError("Order not found or already filled")
            order = self.open_orders.pop(idx)
            base, quote = order["instrument"].split("_")
            # Refund locked funds
            if order["side"] == "BUY":
                self.balances[quote] = self.balances.get(quote, 0.0) + order.get("locked_funds", 0.0)
            else:
                self.balances[base] = self.balances.get(base, 0.0) + order["quantity"]
            order["status"] = "CANCELED"
            order["canceled_at"] = int(time.time())
            self.order_history.append(order)
            self._save()
            return order

    def cancel_all(self, instrument: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            remaining = []
            canceled = []
            for order in self.open_orders:
                if not instrument or order["instrument"] == instrument:
                    base, quote = order["instrument"].split("_")
                    if order["side"] == "BUY":
                        self.balances[quote] = self.balances.get(quote, 0.0) + order.get("locked_funds", 0.0)
                    else:
                        self.balances[base] = self.balances.get(base, 0.0) + order["quantity"]
                    order["status"] = "CANCELED"
                    order["canceled_at"] = int(time.time())
                    self.order_history.append(order)
                    canceled.append(order)
                else:
                    remaining.append(order)
            self.open_orders = remaining
            self._save()
            return canceled

    def check_and_fill_limit_orders(self, current_prices: Dict[str, float]) -> List[Dict[str, Any]]:
        """Simulates limit order fills if price moves through order limits."""
        with self._lock:
            filled = []
            remaining = []
            now = int(time.time())
            for order in self.open_orders:
                inst = order["instrument"]
                px = current_prices.get(inst)
                if not px:
                    remaining.append(order)
                    continue
                base, quote = inst.split("_")
                limit_px = order["price"]
                qty = order["quantity"]

                if order["side"] == "BUY" and px <= limit_px:
                    # Buy filled at current price or limit price
                    fill_px = min(px, limit_px)
                    notional = round(qty * fill_px, 4)
                    fee = round(notional * 0.00075, 4)
                    # Locked funds were: limit_px * qty + fee_est
                    refund = max(0.0, order.get("locked_funds", 0.0) - (notional + fee))
                    self.balances[quote] = self.balances.get(quote, 0.0) + refund
                    self.balances[base] = self.balances.get(base, 0.0) + qty
                    order.update({
                        "status": "FILLED",
                        "price": fill_px,
                        "notional": notional,
                        "fee": fee,
                        "filled_at": now,
                    })
                    self.order_history.append(order)
                    filled.append(order)
                elif order["side"] == "SELL" and px >= limit_px:
                    fill_px = max(px, limit_px)
                    notional = round(qty * fill_px, 4)
                    fee = round(notional * 0.00075, 4)
                    credit = max(0.0, notional - fee)
                    self.balances[quote] = self.balances.get(quote, 0.0) + credit
                    order.update({
                        "status": "FILLED",
                        "price": fill_px,
                        "notional": notional,
                        "fee": fee,
                        "filled_at": now,
                    })
                    self.order_history.append(order)
                    filled.append(order)
                else:
                    remaining.append(order)
            if filled:
                self.open_orders = remaining
                self._save()
            return filled


class TradingStrategyManager:
    """Manages automation strategies: Grid Bot, DCA Bot, and Radar Momentum Auto-trader."""

    def __init__(self, client: CryptoComExchangeClient, paper: PaperTradingEngine):
        self.client = client
        self.paper = paper
        self._lock = threading.Lock()
        self.strategies: Dict[str, Dict[str, Any]] = {
            "grid": {"status": "STOPPED", "config": {}, "state": {}},
            "dca": {"status": "STOPPED", "config": {}, "state": {}},
            "radar": {"status": "STOPPED", "config": {}, "state": {}},
        }
        self.running = True
        self.worker_thread = threading.Thread(target=self._run_loop, daemon=True)
        self.worker_thread.start()

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                strat: {
                    "status": data["status"],
                    "config": data["config"],
                    "state": data["state"],
                }
                for strat, data in self.strategies.items()
            }

    # --- Grid Bot ---

    def start_grid(
        self,
        instrument: str,
        lower_price: float,
        upper_price: float,
        grids: int,
        total_investment_usdt: float,
        is_live: bool = False,
    ) -> Dict[str, Any]:
        with self._lock:
            if lower_price >= upper_price:
                raise ValueError("Lower price must be strictly less than upper price")
            if grids < 2 or grids > 50:
                raise ValueError("Grid count must be between 2 and 50")
            if total_investment_usdt <= 10.0:
                raise ValueError("Minimum investment is 10 USDT")

            # Calculate price levels
            step = (upper_price - lower_price) / grids
            levels = [round(lower_price + i * step, 4) for i in range(grids + 1)]
            per_grid_usdt = round(total_investment_usdt / grids, 2)

            self.strategies["grid"] = {
                "status": "RUNNING",
                "is_live": is_live,
                "config": {
                    "instrument": instrument,
                    "lower_price": lower_price,
                    "upper_price": upper_price,
                    "grids": grids,
                    "step": round(step, 4),
                    "levels": levels,
                    "total_investment": total_investment_usdt,
                    "per_grid_usdt": per_grid_usdt,
                },
                "state": {
                    "started_at": int(time.time()),
                    "fills_count": 0,
                    "grid_profit_usdt": 0.0,
                    "last_check_price": 0.0,
                    "orders": [],
                },
            }
            return self.strategies["grid"]

    def stop_grid(self) -> Dict[str, Any]:
        with self._lock:
            self.strategies["grid"]["status"] = "STOPPED"
            return self.strategies["grid"]

    # --- DCA Bot ---

    def start_dca(
        self,
        instrument: str,
        amount_usdt: float,
        interval_minutes: int,
        dip_multiplier_enabled: bool = True,
        is_live: bool = False,
    ) -> Dict[str, Any]:
        with self._lock:
            if amount_usdt < 5.0:
                raise ValueError("DCA amount must be at least 5 USDT")
            if interval_minutes < 1:
                raise ValueError("Interval must be at least 1 minute")

            self.strategies["dca"] = {
                "status": "RUNNING",
                "is_live": is_live,
                "config": {
                    "instrument": instrument,
                    "amount_usdt": amount_usdt,
                    "interval_seconds": interval_minutes * 60,
                    "dip_multiplier_enabled": dip_multiplier_enabled,
                },
                "state": {
                    "started_at": int(time.time()),
                    "last_execution": 0,
                    "total_invested_usdt": 0.0,
                    "total_accumulated_tokens": 0.0,
                    "executions_count": 0,
                    "average_price": 0.0,
                },
            }
            return self.strategies["dca"]

    def stop_dca(self) -> Dict[str, Any]:
        with self._lock:
            self.strategies["dca"]["status"] = "STOPPED"
            return self.strategies["dca"]

    # --- Radar Momentum Auto-Trader ---

    def start_radar(
        self,
        instruments: Optional[List[str]] = None,
        min_buy_score: float = 75.0,
        max_sell_score: float = 40.0,
        order_size_usdt: float = 50.0,
        is_live: bool = False,
    ) -> Dict[str, Any]:
        with self._lock:
            self.strategies["radar"] = {
                "status": "RUNNING",
                "is_live": is_live,
                "config": {
                    "instruments": instruments or ["BTC_USDT", "ETH_USDT", "CRO_USDT"],
                    "min_buy_score": min_buy_score,
                    "max_sell_score": max_sell_score,
                    "order_size_usdt": order_size_usdt,
                },
                "state": {
                    "started_at": int(time.time()),
                    "signals_detected": 0,
                    "trades_executed": 0,
                    "last_signal": None,
                },
            }
            return self.strategies["radar"]

    def stop_radar(self) -> Dict[str, Any]:
        with self._lock:
            self.strategies["radar"]["status"] = "STOPPED"
            return self.strategies["radar"]

    # --- Background Loop ---

    def _run_loop(self) -> None:
        while self.running:
            try:
                self._evaluate_strategies()
            except Exception as err:
                logger.error("Strategy manager loop error: %s", err)
            time.sleep(15)

    def _evaluate_strategies(self) -> None:
        now = time.time()
        with self._lock:
            grid_active = self.strategies["grid"]["status"] == "RUNNING"
            dca_active = self.strategies["dca"]["status"] == "RUNNING"
            radar_active = self.strategies["radar"]["status"] == "RUNNING"

        if not (grid_active or dca_active or radar_active):
            return

        # Fetch live tickers for pricing
        try:
            tickers = self.client.get_tickers()
            price_map = {
                str(t.get("i")): float(t.get("a") or t.get("b") or 0)
                for t in tickers
                if t.get("i")
            }
            # Fill limit orders in paper engine
            self.paper.check_and_fill_limit_orders(price_map)
        except Exception:
            return

        with self._lock:
            # 1. Grid Evaluation
            if self.strategies["grid"]["status"] == "RUNNING":
                cfg = self.strategies["grid"]["config"]
                st = self.strategies["grid"]["state"]
                inst = cfg["instrument"]
                px = price_map.get(inst, 0.0)
                if px > 0:
                    st["last_check_price"] = px

            # 2. DCA Evaluation
            if self.strategies["dca"]["status"] == "RUNNING":
                cfg = self.strategies["dca"]["config"]
                st = self.strategies["dca"]["state"]
                inst = cfg["instrument"]
                interval = cfg["interval_seconds"]
                last_exec = st["last_execution"]
                if now - last_exec >= interval:
                    px = price_map.get(inst, 0.0)
                    if px > 0:
                        buy_amt = cfg["amount_usdt"]
                        # Execute DCA order in paper engine
                        qty = round(buy_amt / px, 6)
                        try:
                            self.paper.execute_order(
                                instrument=inst,
                                side="BUY",
                                order_type="MARKET",
                                quantity=qty,
                                price=px,
                            )
                            st["last_execution"] = int(now)
                            st["total_invested_usdt"] = round(st["total_invested_usdt"] + buy_amt, 2)
                            st["total_accumulated_tokens"] = round(st["total_accumulated_tokens"] + qty, 6)
                            st["executions_count"] += 1
                            if st["total_accumulated_tokens"] > 0:
                                st["average_price"] = round(
                                    st["total_invested_usdt"] / st["total_accumulated_tokens"], 4
                                )
                        except Exception as e:
                            logger.warning("DCA buy failed: %s", e)


class SecondsScalpManager:
    """Manages ultra-short duration (seconds) scalping positions with real-time countdown, auto-settlement, and cashout."""

    def __init__(
        self,
        client: CryptoComExchangeClient,
        paper: PaperTradingEngine,
        storage_dir: Optional[Path] = None,
    ):
        self.client = client
        self.paper = paper
        self.storage_dir = storage_dir or Path(os.getenv("MARKET_RADAR_DATA_DIR", "user/crypto_com_trader"))
        self.file_path = self.storage_dir / "seconds_scalp_ledger.json"
        self._lock = threading.Lock()
        self.active_trades: List[Dict[str, Any]] = []
        self.history: List[Dict[str, Any]] = []
        self.running = True
        self.autopilot = {
            "enabled": False,
            "engine": "antigravity",  # 'antigravity', 'codex', 'consensus'
            "min_confidence": 72,
            "stake_usdt": 15.0,
            "duration_seconds": 30,
            "instrument": "BTC_USDT",
            "last_action": "Standby (Awaiting Activation)",
            "last_check_time": 0,
            "total_auto_trades": 0,
        }
        self._load()
        self.worker_thread = threading.Thread(target=self._expiry_monitor_loop, daemon=True)
        self.worker_thread.start()
        self.autopilot_thread = threading.Thread(target=self._autopilot_loop, daemon=True)
        self.autopilot_thread.start()

    def _load(self) -> None:
        try:
            if self.file_path.exists():
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.active_trades = data.get("active_trades", [])
                    self.history = data.get("history", [])
        except Exception as e:
            logger.warning("Failed to load seconds scalping ledger: %s", e)
            self.active_trades = []
            self.history = []

    def _save(self) -> None:
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            temp = self.file_path.with_suffix(".tmp")
            with open(temp, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "active_trades": self.active_trades,
                        "history": self.history[-200:],
                        "updated_at": int(time.time()),
                    },
                    f,
                    indent=2,
                )
            temp.replace(self.file_path)
        except Exception as e:
            logger.error("Failed to save seconds scalping ledger: %s", e)

    def _get_current_price(self, instrument: str, side: str = "BUY", use_mid: bool = True) -> float:
        try:
            book = self.client.get_book(instrument, depth=5)
            bids = book.get("bids", [])
            asks = book.get("asks", [])
            if use_mid and bids and asks:
                return round((float(bids[0][0]) + float(asks[0][0])) / 2.0, 4)
            if side.upper() == "BUY" and asks:
                return float(asks[0][0])
            elif side.upper() == "SELL" and bids:
                return float(bids[0][0])
            elif bids:
                return float(bids[0][0])
        except Exception:
            pass
        ticker = self.client.get_ticker(instrument)
        px = float(ticker.get("k") or ticker.get("a") or ticker.get("b") or 0.0)
        return px if px > 0 else 0.0

    def open_seconds_trade(
        self,
        instrument: str,
        direction: str,
        stake_usdt: float,
        duration_seconds: int = 30,
        is_live: bool = False,
        payout_ratio: float = 0.85,
        leverage: float = 10.0,
        ai_engine: str = "Manual",
    ) -> Dict[str, Any]:
        with self._lock:
            instrument = instrument.upper().strip()
            direction_clean = "CALL" if direction.upper() in ("CALL", "BUY", "LONG") else "PUT"
            stake = round(float(stake_usdt), 2)
            if stake <= 0:
                raise ValueError("Stake amount must be greater than 0 USDT")
            duration = int(duration_seconds)
            if duration not in (15, 30, 60, 120, 300):
                duration = max(10, min(duration, 600))

            entry_price = self._get_current_price(instrument, use_mid=True)
            if entry_price <= 0:
                raise ValueError(f"Unable to retrieve real-time market price for {instrument}")

            now = time.time()
            trade_id = f"sec_{int(now * 1000)}"

            # Balance verification & deduction
            if not is_live:
                avail_usdt = self.paper.balances.get("USDT", 0.0)
                if avail_usdt < stake:
                    raise ValueError(f"Insufficient virtual USDT. Needed: {stake:.2f}, Available: {avail_usdt:.2f}")
                self.paper.balances["USDT"] = round(avail_usdt - stake, 4)
                self.paper._save()
            else:
                if not self.client.has_credentials:
                    raise ValueError("Live trading requires configured Crypto.com API credentials")
                try:
                    qty = round(stake / entry_price, 6)
                    self.client.create_order(
                        instrument=instrument,
                        side="BUY" if direction_clean == "CALL" else "SELL",
                        order_type="MARKET",
                        quantity=qty,
                    )
                except Exception as e:
                    logger.warning("Live order execution note for seconds trade: %s", e)

            trade = {
                "trade_id": trade_id,
                "instrument": instrument,
                "direction": direction_clean,
                "stake_usdt": stake,
                "duration_seconds": duration,
                "entry_price": entry_price,
                "current_price": entry_price,
                "start_time": now,
                "expiry_time": now + duration,
                "is_live": is_live,
                "status": "ACTIVE",
                "payout_ratio": payout_ratio,
                "leverage": leverage,
                "ai_engine": ai_engine,
                "pnl_usdt": 0.0,
                "pnl_pct": 0.0,
                "remaining_seconds": float(duration),
                "exit_price": None,
                "closed_at": None,
                "reason": None,
            }
            self.active_trades.append(trade)
            self._save()
            return trade

    def close_seconds_trade(self, trade_id: str, early_exit: bool = False) -> Dict[str, Any]:
        with self._lock:
            idx = next((i for i, t in enumerate(self.active_trades) if t["trade_id"] == trade_id), None)
            if idx is None:
                raise ValueError(f"Trade {trade_id} not found or already settled")

            trade = self.active_trades.pop(idx)
            instrument = trade["instrument"]
            direction = trade["direction"]
            stake = trade["stake_usdt"]
            entry_px = trade["entry_price"]
            payout_ratio = trade.get("payout_ratio", 0.85)
            leverage = trade.get("leverage", 10.0)

            exit_px = self._get_current_price(instrument, use_mid=True)
            if exit_px <= 0:
                exit_px = trade.get("current_price") or entry_px

            if direction == "CALL":
                delta_pct = ((exit_px - entry_px) / entry_px) * 100.0
            else:
                delta_pct = ((entry_px - exit_px) / entry_px) * 100.0

            now = time.time()
            if early_exit:
                if delta_pct > 0:
                    secured_ratio = 0.65
                    pnl_usdt = round(stake * payout_ratio * secured_ratio, 2)
                    status = "CASHED_OUT_PROFIT"
                else:
                    loss_pct = min(100.0, abs(delta_pct) * leverage)
                    pnl_usdt = -round(stake * (loss_pct / 100.0) * 0.7, 2)
                    status = "CASHED_OUT_SAVED"
                reason = "EARLY_EXIT"
            else:
                if delta_pct > 0:
                    profit_pct = max(payout_ratio * 100.0, delta_pct * leverage)
                    pnl_usdt = round(stake * (profit_pct / 100.0), 2)
                    status = "WIN"
                elif delta_pct < 0:
                    pnl_usdt = -round(stake, 2)
                    status = "LOSS"
                else:
                    pnl_usdt = 0.0
                    status = "TIE"
                reason = "EXPIRED"

            pnl_pct = round((pnl_usdt / stake) * 100.0, 2) if stake > 0 else 0.0

            if not trade.get("is_live", False):
                credit = max(0.0, stake + pnl_usdt)
                self.paper.balances["USDT"] = round(self.paper.balances.get("USDT", 0.0) + credit, 4)
                self.paper._save()
            else:
                try:
                    qty = round(stake / exit_px, 6)
                    self.client.create_order(
                        instrument=instrument,
                        side="SELL" if direction == "CALL" else "BUY",
                        order_type="MARKET",
                        quantity=qty,
                    )
                except Exception as e:
                    logger.warning("Live counter-order error: %s", e)

            trade.update({
                "status": status,
                "exit_price": exit_px,
                "pnl_usdt": pnl_usdt,
                "pnl_pct": pnl_pct,
                "closed_at": int(now),
                "reason": reason,
                "remaining_seconds": 0,
            })
            self.history.insert(0, trade)
            if len(self.history) > 200:
                self.history = self.history[:200]
            self._save()
            return trade

    def _expiry_monitor_loop(self) -> None:
        while self.running:
            try:
                now = time.time()
                to_close = []
                with self._lock:
                    for trade in self.active_trades:
                        if now >= trade["expiry_time"]:
                            to_close.append(trade["trade_id"])
                for tid in to_close:
                    try:
                        self.close_seconds_trade(tid, early_exit=False)
                    except Exception as err:
                        logger.error("Error auto-closing seconds trade %s: %s", tid, err)
            except Exception as loop_err:
                logger.error("SecondsScalp monitor loop exception: %s", loop_err)
            time.sleep(0.25)

    def get_active_trades(self) -> List[Dict[str, Any]]:
        now = time.time()
        results = []
        with self._lock:
            for t in self.active_trades:
                copy_t = dict(t)
                rem = max(0.0, round(copy_t["expiry_time"] - now, 1))
                copy_t["remaining_seconds"] = rem
                entry_px = copy_t["entry_price"]
                direction = copy_t["direction"]
                stake = copy_t["stake_usdt"]
                payout_ratio = copy_t.get("payout_ratio", 0.85)

                cur_px = self._get_current_price(copy_t["instrument"], use_mid=True)
                if cur_px <= 0:
                    cur_px = entry_px
                copy_t["current_price"] = cur_px

                if direction == "CALL":
                    delta_pct = ((cur_px - entry_px) / entry_px) * 100.0
                else:
                    delta_pct = ((entry_px - cur_px) / entry_px) * 100.0

                if delta_pct > 0:
                    floating_pnl = round(stake * payout_ratio, 2)
                    floating_pct = round(payout_ratio * 100.0, 1)
                    cashout_val = round(stake + (floating_pnl * 0.65), 2)
                else:
                    floating_pnl = -round(stake, 2)
                    floating_pct = -100.0
                    cashout_val = max(0.0, round(stake * 0.35, 2))

                copy_t["delta_pct"] = round(delta_pct, 3)
                copy_t["floating_pnl_usdt"] = floating_pnl
                copy_t["floating_pnl_pct"] = floating_pct
                copy_t["cashout_value_usdt"] = cashout_val
                results.append(copy_t)
        return results

    def get_history(self) -> Dict[str, Any]:
        with self._lock:
            total_trades = len(self.history)
            wins = sum(1 for t in self.history if t.get("pnl_usdt", 0) > 0)
            losses = sum(1 for t in self.history if t.get("pnl_usdt", 0) < 0)
            total_pnl = sum(t.get("pnl_usdt", 0) for t in self.history)
            win_rate = round((wins / total_trades) * 100.0, 1) if total_trades > 0 else 0.0

            return {
                "total_trades": total_trades,
                "wins": wins,
                "losses": losses,
                "win_rate_pct": win_rate,
                "total_pnl_usdt": round(total_pnl, 2),
                "trades": self.history[:50],
            }

    def toggle_autopilot(
        self,
        enabled: bool,
        engine: Optional[str] = None,
        min_confidence: Optional[int] = None,
        stake: Optional[float] = None,
        duration: Optional[int] = None,
        instrument: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            self.autopilot["enabled"] = bool(enabled)
            if engine:
                self.autopilot["engine"] = engine.lower().strip()
            if min_confidence is not None:
                self.autopilot["min_confidence"] = int(min_confidence)
            if stake is not None:
                self.autopilot["stake_usdt"] = max(1.0, round(float(stake), 2))
            if duration is not None:
                self.autopilot["duration_seconds"] = int(duration)
            if instrument:
                self.autopilot["instrument"] = instrument.upper().strip()
            self.autopilot["last_action"] = "Auto-Pilot Active (Scanning)" if self.autopilot["enabled"] else "Auto-Pilot Stopped"
            return dict(self.autopilot)

    def get_autopilot_status(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self.autopilot)

    def _autopilot_loop(self) -> None:
        from market_radar.crypto_com_ai import CryptoComAIEngine
        from market_radar.crypto_com_trade import CryptoComTraderService
        ai_engine = CryptoComAIEngine(CryptoComTraderService.get_instance())
        last_eval_time = 0.0
        last_settle_time = 0.0

        while self.running:
            try:
                time.sleep(1.0)
                with self._lock:
                    is_enabled = self.autopilot["enabled"]
                    engine_name = self.autopilot["engine"]
                    min_conf = self.autopilot["min_confidence"]
                    stake = self.autopilot["stake_usdt"]
                    dur = self.autopilot["duration_seconds"]
                    pair = self.autopilot["instrument"]
                    has_active = len(self.active_trades) > 0

                if not is_enabled:
                    continue

                # Safety guard: strictly max 1 concurrent position
                if has_active:
                    last_settle_time = time.time()
                    with self._lock:
                        self.autopilot["last_action"] = "In-flight trade running; waiting for settlement"
                    continue

                now = time.time()
                # Cooldown period after trade closure to avoid overtrading in chop
                if now - last_settle_time < 8.0:
                    wait_rem = int(8.0 - (now - last_settle_time))
                    with self._lock:
                        self.autopilot["last_action"] = f"Post-trade cooldown ({wait_rem}s)..."
                    continue

                if now - last_eval_time < 6.0:
                    continue
                last_eval_time = now

                with self._lock:
                    self.autopilot["last_action"] = f"Scanning {pair} via {engine_name.upper()}..."
                    self.autopilot["last_check_time"] = int(now)

                advice = ai_engine.generate_seconds_advice(pair, provider=engine_name)
                direction = advice.get("direction", "CALL").upper()
                prob = int(advice.get("probability", 0))

                if prob >= min_conf and direction in ("CALL", "PUT"):
                    engine_label = "Codex AI" if "codex" in engine_name else ("Dual Consensus" if "consensus" in engine_name else "Antigravity AI")
                    try:
                        self.open_seconds_trade(
                            instrument=pair,
                            direction=direction,
                            stake_usdt=stake,
                            duration_seconds=dur,
                            is_live=False,  # default paper safety
                            ai_engine=engine_label,
                        )
                        with self._lock:
                            self.autopilot["total_auto_trades"] += 1
                            self.autopilot["last_action"] = f"Launched {direction} ({prob}%) via {engine_label}"
                        logger.info("Auto-Pilot executed %s %s on %s (Confidence: %d%%)", engine_label, direction, pair, prob)
                    except Exception as trade_err:
                        with self._lock:
                            self.autopilot["last_action"] = f"Trade trigger error: {trade_err}"
                else:
                    with self._lock:
                        self.autopilot["last_action"] = f"Filtered {direction} ({prob}%) < {min_conf}% trigger threshold"

            except Exception as loop_err:
                logger.debug("Autopilot loop error: %s", loop_err)


class CryptoComTraderService:
    """Singleton service bridging Crypto.com Exchange API, Paper Engine, and OctoBot."""

    _instance = None

    @classmethod
    def get_instance(cls) -> "CryptoComTraderService":
        if cls._instance is None:
            cls._instance = CryptoComTraderService()
        return cls._instance

    def __init__(self):
        self.client = CryptoComExchangeClient()
        self.paper = PaperTradingEngine()
        self.strategy_mgr = TradingStrategyManager(self.client, self.paper)
        self.seconds_mgr = SecondsScalpManager(self.client, self.paper)
        self.mode = "paper"  # 'paper' or 'live'
        self._lock = threading.Lock()

    def toggle_seconds_autopilot(self, **kwargs) -> Dict[str, Any]:
        return self.seconds_mgr.toggle_autopilot(**kwargs)

    def get_seconds_autopilot_status(self) -> Dict[str, Any]:
        return self.seconds_mgr.get_autopilot_status()

    def set_mode(self, mode: str) -> str:
        with self._lock:
            mode = mode.lower().strip()
            if mode not in ("paper", "live"):
                raise ValueError("Mode must be 'paper' or 'live'")
            if mode == "live" and not self.client.has_credentials:
                raise ValueError("Cannot switch to live mode without Crypto.com API credentials")
            self.mode = mode
            return self.mode

    def reset_paper(self, usdt_amount: float = 10000.0) -> Dict[str, Any]:
        res = self.paper.reset_balances(usdt_amount)
        if hasattr(self, "seconds_mgr") and self.seconds_mgr:
            with self.seconds_mgr._lock:
                self.seconds_mgr.active_trades = []
                self.seconds_mgr.history = []
                self.seconds_mgr.autopilot["total_auto_trades"] = 0
                self.seconds_mgr._save()
        return res

    def set_credentials(self, api_key: str, api_secret: str) -> Dict[str, Any]:
        self.client.set_credentials(api_key, api_secret)
        # Test credentials by calling account summary
        try:
            summary = self.client.get_account_summary()
            return {"valid": True, "accounts": summary.get("accounts", [])}
        except Exception as e:
            return {"valid": False, "error": str(e)}

    def get_status(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "has_credentials": self.client.has_credentials,
            "initial_virtual_balance": self.paper.initial_usdt,
            "strategies": self.strategy_mgr.get_status(),
        }

    def get_portfolio(self) -> Dict[str, Any]:
        tickers = self.client.get_tickers()
        prices = {
            str(t.get("i")): float(t.get("a") or t.get("b") or 0)
            for t in tickers
            if t.get("i")
        }
        if self.mode == "paper":
            portfolio = self.paper.get_portfolio(prices)
            portfolio["mode"] = "paper"
            return portfolio
        else:
            summary = self.client.get_account_summary()
            data_list = summary.get("data", [])
            total_usdt = 0.0
            breakdown = []
            if data_list:
                for record in data_list:
                    avail_usd = float(record.get("total_available_balance") or 0.0)
                    cash_usd = float(record.get("total_cash_balance") or 0.0)
                    if avail_usd > 0 or cash_usd > 0:
                        total_usdt += avail_usd
                        breakdown.append({
                            "asset": "USD",
                            "quantity": avail_usd,
                            "available": avail_usd,
                            "order": 0.0,
                            "value_usdt": round(avail_usd, 2),
                            "price": 1.0,
                        })
                    for pos in record.get("position_balances", []):
                        asset = pos.get("instrument_name", "")
                        qty = float(pos.get("quantity") or 0.0)
                        if qty <= 1e-7:
                            continue
                        px = 1.0 if asset in ("USDT", "USD") else prices.get(f"{asset}_USDT", 0.0)
                        val = qty * px
                        total_usdt += val
                        breakdown.append({
                            "asset": asset,
                            "quantity": qty,
                            "available": qty,
                            "order": 0.0,
                            "value_usdt": round(val, 2),
                            "price": px,
                        })
            else:
                accounts = summary.get("accounts", [])
                for acc in accounts:
                    asset = acc.get("currency", "")
                    qty = float(acc.get("balance", 0.0))
                    if qty <= 1e-7:
                        continue
                    px = 1.0 if asset in ("USDT", "USD") else prices.get(f"{asset}_USDT", 0.0)
                    val = qty * px
                    total_usdt += val
                    breakdown.append({
                        "asset": asset,
                        "quantity": qty,
                        "available": float(acc.get("available", 0.0)),
                        "order": float(acc.get("order", 0.0)),
                        "value_usdt": round(val, 2),
                        "price": px,
                    })
            return {
                "mode": "live",
                "total_equity_usdt": round(total_usdt, 2),
                "breakdown": breakdown,
            }

    def get_market_overview(self, instrument: str = "BTC_USDT") -> Dict[str, Any]:
        book = self.client.get_book(instrument, depth=15)
        ticker = self.client.get_ticker(instrument)
        trades = self.client.get_trades(instrument, count=25)
        return {
            "instrument": instrument,
            "ticker": ticker,
            "book": book,
            "trades": trades,
        }

    def get_candles(self, instrument: str, timeframe: str = "1h", count: int = 100) -> List[Dict[str, Any]]:
        return self.client.get_candlestick(instrument, timeframe, count)

    def execute_order(
        self,
        instrument: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
    ) -> Dict[str, Any]:
        if self.mode == "paper":
            book = self.client.get_book(instrument, depth=5)
            bids = book.get("bids", [])
            asks = book.get("asks", [])
            market_bid = float(bids[0][0]) if bids else None
            market_ask = float(asks[0][0]) if asks else None
            return self.paper.execute_order(
                instrument=instrument,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                market_bid=market_bid,
                market_ask=market_ask,
            )
        else:
            return self.client.create_order(
                instrument=instrument,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
            )

    def cancel_order(self, instrument: str, order_id: str) -> Dict[str, Any]:
        if self.mode == "paper":
            return self.paper.cancel_order(order_id)
        else:
            return self.client.cancel_order(instrument, order_id)

    def cancel_all_orders(self, instrument: Optional[str] = None) -> Any:
        if self.mode == "paper":
            return self.paper.cancel_all(instrument)
        else:
            return self.client.cancel_all_orders(instrument)

    def get_open_orders(self, instrument: Optional[str] = None) -> List[Dict[str, Any]]:
        if self.mode == "paper":
            with self.paper._lock:
                if not instrument:
                    return list(self.paper.open_orders)
                return [o for o in self.paper.open_orders if o["instrument"] == instrument]
        else:
            return self.client.get_open_orders(instrument)

    def get_order_history(self, instrument: Optional[str] = None) -> List[Dict[str, Any]]:
        if self.mode == "paper":
            with self.paper._lock:
                if not instrument:
                    return list(reversed(self.paper.order_history[-100:]))
                return list(reversed([o for o in self.paper.order_history if o["instrument"] == instrument][-100:]))
        else:
            return self.client.get_order_history(instrument)
