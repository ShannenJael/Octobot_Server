"""Unit tests for Crypto.com Trader & Strategy Hub."""

import hashlib
import hmac
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from market_radar.crypto_com_trade import (
    CryptoComExchangeClient,
    PaperTradingEngine,
    TradingStrategyManager,
    CryptoComTraderService,
)


class TestCryptoComExchangeClient(unittest.TestCase):
    def test_signature_generation(self):
        client = CryptoComExchangeClient()
        method = "private/create-order"
        req_id = 1700000000000
        nonce = 1700000000000
        api_key = "test_api_key"
        api_secret = "test_api_secret"
        params = {
            "instrument_name": "BTC_USDT",
            "side": "BUY",
            "type": "LIMIT",
            "price": "50000",
            "quantity": "0.01",
        }

        # Expected canonical params: sorted keys concatenated:
        # instrument_nameBTC_USDTprice50000quantity0.01sideBUYtypeLIMIT
        expected_param_str = (
            "instrument_nameBTC_USDTprice50000quantity0.01sideBUYtypeLIMIT"
        )
        self.assertEqual(client._serialize_params(params), expected_param_str)

        expected_sig_payload = f"{method}{req_id}{api_key}{expected_param_str}{nonce}"
        expected_sig = hmac.new(
            api_secret.encode("utf-8"),
            expected_sig_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        calculated_sig = client.sign_payload(
            method, req_id, api_key, api_secret, params, nonce
        )
        self.assertEqual(calculated_sig, expected_sig)

    def test_boolean_and_empty_serialization(self):
        client = CryptoComExchangeClient()
        self.assertEqual(client._serialize_params({}), "")
        self.assertEqual(client._serialize_params(None), "")
        self.assertEqual(client._serialize_params({"flag": True}), "flagtrue")
        self.assertEqual(client._serialize_params({"flag": False}), "flagfalse")


class TestPaperTradingEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.engine = PaperTradingEngine(storage_dir=Path(self.temp_dir), initial_usdt=10000.0)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initial_balance(self):
        portfolio = self.engine.get_portfolio()
        self.assertEqual(portfolio["total_equity_usdt"], 10000.0)
        self.assertEqual(self.engine.balances.get("USDT"), 10000.0)

    def test_market_buy_execution(self):
        # Buy 0.1 BTC at 50,000 USDT (5,000 USDT + fee)
        order = self.engine.execute_order(
            instrument="BTC_USDT",
            side="BUY",
            order_type="MARKET",
            quantity=0.1,
            price=50000.0,
        )
        self.assertEqual(order["status"], "FILLED")
        self.assertEqual(self.engine.balances.get("BTC"), 0.1)
        expected_fee = round(5000.0 * 0.00075, 4)
        expected_usdt = round(10000.0 - 5000.0 - expected_fee, 4)
        self.assertAlmostEqual(self.engine.balances.get("USDT"), expected_usdt, places=2)

    def test_limit_order_and_fill(self):
        # Place LIMIT BUY at 40,000 for 0.1 BTC
        order = self.engine.execute_order(
            instrument="BTC_USDT",
            side="BUY",
            order_type="LIMIT",
            quantity=0.1,
            price=40000.0,
        )
        self.assertEqual(order["status"], "ACTIVE")
        self.assertEqual(len(self.engine.open_orders), 1)

        # Price is at 45,000 -> Should NOT fill
        filled = self.engine.check_and_fill_limit_orders({"BTC_USDT": 45000.0})
        self.assertEqual(len(filled), 0)
        self.assertEqual(len(self.engine.open_orders), 1)

        # Price drops to 39,500 -> Should fill!
        filled = self.engine.check_and_fill_limit_orders({"BTC_USDT": 39500.0})
        self.assertEqual(len(filled), 1)
        self.assertEqual(len(self.engine.open_orders), 0)
        self.assertEqual(self.engine.balances.get("BTC"), 0.1)

    def test_cancel_order(self):
        order = self.engine.execute_order(
            instrument="BTC_USDT",
            side="BUY",
            order_type="LIMIT",
            quantity=0.1,
            price=40000.0,
        )
        canceled = self.engine.cancel_order(order["order_id"])
        self.assertEqual(canceled["status"], "CANCELED")
        self.assertEqual(len(self.engine.open_orders), 0)
        self.assertAlmostEqual(self.engine.balances.get("USDT"), 10000.0, places=2)

    def test_reset_balances(self):
        self.engine.execute_order(
            instrument="BTC_USDT",
            side="BUY",
            order_type="MARKET",
            quantity=0.05,
            price=50000.0,
        )
        self.assertNotEqual(self.engine.balances.get("USDT"), 10000.0)
        self.engine.reset_balances(10000.0)
        self.assertEqual(self.engine.balances.get("USDT"), 10000.0)
        self.assertEqual(len(self.engine.open_orders), 0)


class TestTradingStrategyManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.client = CryptoComExchangeClient()
        self.paper = PaperTradingEngine(storage_dir=Path(self.temp_dir))
        self.mgr = TradingStrategyManager(self.client, self.paper)

    def tearDown(self):
        self.mgr.running = False
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_grid_bot_lifecycle(self):
        res = self.mgr.start_grid(
            instrument="BTC_USDT",
            lower_price=50000.0,
            upper_price=60000.0,
            grids=10,
            total_investment_usdt=500.0,
        )
        self.assertEqual(res["status"], "RUNNING")
        self.assertEqual(len(res["config"]["levels"]), 11)
        self.assertEqual(res["config"]["step"], 1000.0)

        stopped = self.mgr.stop_grid()
        self.assertEqual(stopped["status"], "STOPPED")

    def test_dca_bot_lifecycle(self):
        res = self.mgr.start_dca(
            instrument="ETH_USDT",
            amount_usdt=50.0,
            interval_minutes=60,
        )
        self.assertEqual(res["status"], "RUNNING")
        stopped = self.mgr.stop_dca()
        self.assertEqual(stopped["status"], "STOPPED")

    def test_radar_bot_lifecycle(self):
        res = self.mgr.start_radar(
            instruments=["BTC_USDT", "ETH_USDT"],
            min_buy_score=80.0,
        )
        self.assertEqual(res["status"], "RUNNING")
        stopped = self.mgr.stop_radar()
        self.assertEqual(stopped["status"], "STOPPED")


if __name__ == "__main__":
    unittest.main()
