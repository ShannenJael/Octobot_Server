"""OctoBot Web Interface plug-in for Crypto.com Trader & Strategy Hub."""

import os
import flask

from market_radar.crypto_com_trade import (
    CryptoComTraderService,
    CryptoComAPIError,
)
from market_radar.crypto_com_ai import CryptoComAIEngine
import tentacles.Services.Interfaces.web_interface.enums as web_enums
import tentacles.Services.Interfaces.web_interface.login as login
import tentacles.Services.Interfaces.web_interface.models as models
from tentacles.Services.Interfaces.web_interface.plugins.abstract_plugin import AbstractWebInterfacePlugin


class CryptoComTraderPlugin(AbstractWebInterfacePlugin):
    NAME = "crypto_com_trader"
    URL_PREFIX = "/crypto-com"
    PLUGIN_ROOT_FOLDER = os.path.join(os.path.dirname(__file__), "crypto_com_trader_assets")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service = CryptoComTraderService.get_instance()
        self.ai_engine = CryptoComAIEngine(self.service)

    def get_tabs(self):
        return [
            models.WebInterfaceTab(
                "crypto_com_trader",
                "crypto_com_trader.index",
                "Crypto.com Trader",
                web_enums.TabsLocation.START,
            )
        ]

    def register_routes(self):
        @self.blueprint.route("/")
        @login.login_required_when_activated
        def index():
            return flask.render_template("crypto_com_trader.html", active_page="crypto_com_trader")

        @self.blueprint.route("/api/status")
        @login.login_required_when_activated
        def status():
            try:
                return flask.jsonify(self.service.get_status())
            except Exception as error:
                return flask.jsonify({"error": str(error)}), 500

        @self.blueprint.route("/api/mode", methods=["POST"])
        @login.login_required_when_activated
        def set_mode():
            body = flask.request.get_json(silent=True) or {}
            mode = str(body.get("mode", "paper"))
            try:
                res_mode = self.service.set_mode(mode)
                return flask.jsonify({"mode": res_mode})
            except ValueError as error:
                return flask.jsonify({"error": str(error)}), 400
            except Exception as error:
                return flask.jsonify({"error": str(error)}), 500

        @self.blueprint.route("/api/credentials", methods=["POST"])
        @login.login_required_when_activated
        def set_credentials():
            body = flask.request.get_json(silent=True) or {}
            api_key = str(body.get("api_key", ""))
            api_secret = str(body.get("api_secret", ""))
            if not api_key or not api_secret:
                return flask.jsonify({"error": "API Key and Secret are required"}), 400
            res = self.service.set_credentials(api_key, api_secret)
            return flask.jsonify(res)

        @self.blueprint.route("/api/portfolio")
        @login.login_required_when_activated
        def portfolio():
            try:
                return flask.jsonify(self.service.get_portfolio())
            except Exception as error:
                return flask.jsonify({"error": str(error)}), 500

        @self.blueprint.route("/api/market/<instrument>")
        @login.login_required_when_activated
        def market_overview(instrument):
            try:
                instrument = instrument.upper()
                return flask.jsonify(self.service.get_market_overview(instrument))
            except Exception as error:
                return flask.jsonify({"error": str(error)}), 500

        @self.blueprint.route("/api/candles/<instrument>")
        @login.login_required_when_activated
        def candles(instrument):
            timeframe = flask.request.args.get("timeframe", "1h")
            count = max(10, min(int(flask.request.args.get("count", 100)), 300))
            try:
                return flask.jsonify({
                    "candles": self.service.get_candles(instrument.upper(), timeframe, count)
                })
            except Exception as error:
                return flask.jsonify({"error": str(error)}), 500

        @self.blueprint.route("/api/order/create", methods=["POST"])
        @login.login_required_when_activated
        def create_order():
            body = flask.request.get_json(silent=True) or {}
            try:
                instrument = str(body.get("instrument", "")).upper()
                side = str(body.get("side", "")).upper()
                order_type = str(body.get("type", "MARKET")).upper()
                quantity = float(body.get("quantity", 0))
                price = float(body.get("price")) if body.get("price") is not None else None

                if not instrument or not side or quantity <= 0:
                    return flask.jsonify({"error": "Invalid instrument, side, or quantity"}), 400

                order = self.service.execute_order(
                    instrument=instrument,
                    side=side,
                    order_type=order_type,
                    quantity=quantity,
                    price=price,
                )
                return flask.jsonify({"status": "ok", "order": order})
            except ValueError as error:
                return flask.jsonify({"error": str(error)}), 400
            except CryptoComAPIError as error:
                return flask.jsonify({"error": str(error)}), 502
            except Exception as error:
                return flask.jsonify({"error": str(error)}), 500

        @self.blueprint.route("/api/order/cancel", methods=["POST"])
        @login.login_required_when_activated
        def cancel_order():
            body = flask.request.get_json(silent=True) or {}
            try:
                instrument = str(body.get("instrument", "")).upper()
                order_id = str(body.get("order_id", ""))
                if not order_id:
                    return flask.jsonify({"error": "order_id is required"}), 400
                res = self.service.cancel_order(instrument, order_id)
                return flask.jsonify({"status": "ok", "result": res})
            except Exception as error:
                return flask.jsonify({"error": str(error)}), 500

        @self.blueprint.route("/api/order/cancel-all", methods=["POST"])
        @login.login_required_when_activated
        def cancel_all():
            body = flask.request.get_json(silent=True) or {}
            instrument = str(body.get("instrument", "")).upper() or None
            try:
                res = self.service.cancel_all_orders(instrument)
                return flask.jsonify({"status": "ok", "result": res})
            except Exception as error:
                return flask.jsonify({"error": str(error)}), 500

        @self.blueprint.route("/api/orders/open")
        @login.login_required_when_activated
        def open_orders():
            instrument = flask.request.args.get("instrument")
            instrument = instrument.upper() if instrument else None
            try:
                return flask.jsonify({"open_orders": self.service.get_open_orders(instrument)})
            except Exception as error:
                return flask.jsonify({"error": str(error)}), 500

        @self.blueprint.route("/api/orders/history")
        @login.login_required_when_activated
        def order_history():
            instrument = flask.request.args.get("instrument")
            instrument = instrument.upper() if instrument else None
            try:
                return flask.jsonify({"history": self.service.get_order_history(instrument)})
            except Exception as error:
                return flask.jsonify({"error": str(error)}), 500

        @self.blueprint.route("/api/paper/reset", methods=["POST"])
        @login.login_required_when_activated
        def paper_reset():
            body = flask.request.get_json(silent=True) or {}
            usdt = float(body.get("amount", 10000.0))
            try:
                balances = self.service.paper.reset_balances(usdt)
                return flask.jsonify({"status": "ok", "balances": balances})
            except Exception as error:
                return flask.jsonify({"error": str(error)}), 500

        # --- Strategy Bot Routes ---

        @self.blueprint.route("/api/strategies")
        @login.login_required_when_activated
        def strategies():
            try:
                return flask.jsonify(self.service.strategy_mgr.get_status())
            except Exception as error:
                return flask.jsonify({"error": str(error)}), 500

        @self.blueprint.route("/api/strategies/grid/start", methods=["POST"])
        @login.login_required_when_activated
        def start_grid():
            body = flask.request.get_json(silent=True) or {}
            try:
                res = self.service.strategy_mgr.start_grid(
                    instrument=str(body.get("instrument", "BTC_USDT")).upper(),
                    lower_price=float(body.get("lower_price", 0)),
                    upper_price=float(body.get("upper_price", 0)),
                    grids=int(body.get("grids", 10)),
                    total_investment_usdt=float(body.get("total_investment", 100)),
                    is_live=(self.service.mode == "live"),
                )
                return flask.jsonify(res)
            except ValueError as error:
                return flask.jsonify({"error": str(error)}), 400
            except Exception as error:
                return flask.jsonify({"error": str(error)}), 500

        @self.blueprint.route("/api/strategies/grid/stop", methods=["POST"])
        @login.login_required_when_activated
        def stop_grid():
            try:
                return flask.jsonify(self.service.strategy_mgr.stop_grid())
            except Exception as error:
                return flask.jsonify({"error": str(error)}), 500

        @self.blueprint.route("/api/strategies/dca/start", methods=["POST"])
        @login.login_required_when_activated
        def start_dca():
            body = flask.request.get_json(silent=True) or {}
            try:
                res = self.service.strategy_mgr.start_dca(
                    instrument=str(body.get("instrument", "BTC_USDT")).upper(),
                    amount_usdt=float(body.get("amount_usdt", 25)),
                    interval_minutes=int(body.get("interval_minutes", 60)),
                    dip_multiplier_enabled=bool(body.get("dip_multiplier_enabled", True)),
                    is_live=(self.service.mode == "live"),
                )
                return flask.jsonify(res)
            except ValueError as error:
                return flask.jsonify({"error": str(error)}), 400
            except Exception as error:
                return flask.jsonify({"error": str(error)}), 500

        @self.blueprint.route("/api/strategies/dca/stop", methods=["POST"])
        @login.login_required_when_activated
        def stop_dca():
            try:
                return flask.jsonify(self.service.strategy_mgr.stop_dca())
            except Exception as error:
                return flask.jsonify({"error": str(error)}), 500

        @self.blueprint.route("/api/strategies/radar/start", methods=["POST"])
        @login.login_required_when_activated
        def start_radar():
            body = flask.request.get_json(silent=True) or {}
            try:
                instruments = [str(i).upper() for i in body.get("instruments", ["BTC_USDT", "ETH_USDT", "CRO_USDT"])]
                res = self.service.strategy_mgr.start_radar(
                    instruments=instruments,
                    min_buy_score=float(body.get("min_buy_score", 75.0)),
                    max_sell_score=float(body.get("max_sell_score", 40.0)),
                    order_size_usdt=float(body.get("order_size_usdt", 50.0)),
                    is_live=(self.service.mode == "live"),
                )
                return flask.jsonify(res)
            except Exception as error:
                return flask.jsonify({"error": str(error)}), 500

        @self.blueprint.route("/api/strategies/radar/stop", methods=["POST"])
        @login.login_required_when_activated
        def stop_radar():
            try:
                return flask.jsonify(self.service.strategy_mgr.stop_radar())
            except Exception as error:
                return flask.jsonify({"error": str(error)}), 500

        # --- AI Copilot & Radar Endpoints ---
        @self.blueprint.route("/api/ai/copilot", methods=["POST"])
        @login.login_required_when_activated
        def ai_copilot():
            body = flask.request.get_json(silent=True) or {}
            prompt = str(body.get("prompt", "")).strip()
            instrument = str(body.get("instrument", "BTC_USDT")).upper()
            if not prompt:
                return flask.jsonify({"error": "Prompt cannot be empty"}), 400
            try:
                res = self.ai_engine.process_copilot_message(
                    prompt=prompt,
                    active_instrument=instrument,
                )
                return flask.jsonify(res)
            except Exception as error:
                return flask.jsonify({"error": str(error)}), 500

        @self.blueprint.route("/api/ai/radar", methods=["GET"])
        @login.login_required_when_activated
        def ai_radar():
            instrument = flask.request.args.get("instrument", "BTC_USDT").upper()
            try:
                res = self.ai_engine.generate_radar_analysis(instrument=instrument)
                return flask.jsonify(res)
            except Exception as error:
                return flask.jsonify({"error": str(error)}), 500

        @self.blueprint.route("/api/ai/execute-action", methods=["POST"])
        @login.login_required_when_activated
        def ai_execute_action():
            body = flask.request.get_json(silent=True) or {}
            action = body.get("action_card") or body
            try:
                instrument = str(action.get("instrument", "BTC_USDT")).upper()
                side = str(action.get("side", "BUY")).upper()
                order_type = str(action.get("order_type", "MARKET")).upper()
                quantity = float(action.get("quantity", 0))
                price = float(action.get("price")) if action.get("price") is not None else None

                if not instrument or not side or quantity <= 0:
                    return flask.jsonify({"error": "Invalid action parameters"}), 400

                order = self.service.execute_order(
                    instrument=instrument,
                    side=side,
                    order_type=order_type,
                    quantity=quantity,
                    price=price,
                )
                return flask.jsonify({"status": "ok", "order": order})
            except Exception as error:
                return flask.jsonify({"error": str(error)}), 500
