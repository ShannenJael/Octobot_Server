"""OctoBot Web Interface plug-in for the advisory Market Radar."""

import os

import flask

from market_radar import MarketRadarService
from market_radar.crypto_com import MarketDataError
import tentacles.Services.Interfaces.web_interface.enums as web_enums
import tentacles.Services.Interfaces.web_interface.login as login
import tentacles.Services.Interfaces.web_interface.models as models
from tentacles.Services.Interfaces.web_interface.plugins.abstract_plugin import AbstractWebInterfacePlugin


class MarketRadarPlugin(AbstractWebInterfacePlugin):
    NAME = "market_radar"
    URL_PREFIX = "/market-radar"
    PLUGIN_ROOT_FOLDER = os.path.join(os.path.dirname(__file__), "market_radar_assets")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service = MarketRadarService()

    def get_tabs(self):
        return [
            models.WebInterfaceTab(
                "market_radar",
                "market_radar.index",
                "Market Radar",
                web_enums.TabsLocation.START,
            )
        ]

    def register_routes(self):
        @self.blueprint.route("/")
        @login.login_required_when_activated
        def index():
            return flask.render_template("market_radar.html", active_page="market_radar")

        @self.blueprint.route("/api/scan")
        @login.login_required_when_activated
        def scan():
            try:
                limit = max(3, min(int(flask.request.args.get("limit", 12)), 20))
                force = flask.request.args.get("force", "false").lower() == "true"
                return flask.jsonify(self.service.scan(limit=limit, force=force))
            except (MarketDataError, ValueError, OSError) as error:
                return flask.jsonify({"status": "unavailable", "error": str(error)}), 503

        @self.blueprint.route("/api/detail/<instrument>")
        @login.login_required_when_activated
        def detail(instrument):
            try:
                return flask.jsonify(self.service.detail(instrument.upper()))
            except (MarketDataError, ValueError, OSError) as error:
                return flask.jsonify({"status": "unavailable", "error": str(error)}), 404

        @self.blueprint.route("/api/watchlist", methods=["POST"])
        @login.login_required_when_activated
        def watchlist():
            body = flask.request.get_json(silent=True) or {}
            instrument = str(body.get("instrument", "")).upper()
            if not instrument.endswith("_USDT") or not instrument.replace("_", "").isalnum():
                return flask.jsonify({"error": "Invalid instrument"}), 400
            return flask.jsonify({"watchlist": self.service.update_watchlist(instrument, bool(body.get("enabled")))})

        @self.blueprint.route("/api/paper-candidates", methods=["POST"])
        @login.login_required_when_activated
        def paper_candidate():
            body = flask.request.get_json(silent=True) or {}
            try:
                return flask.jsonify(self.service.queue_paper(str(body.get("signal_id", ""))))
            except PermissionError as error:
                return flask.jsonify({"error": str(error)}), 403
            except ValueError as error:
                return flask.jsonify({"error": str(error)}), 400

        @self.blueprint.route("/api/train", methods=["POST"])
        @login.login_required_when_activated
        def train():
            body = flask.request.get_json(silent=True) or {}
            bootstrap = bool(body.get("bootstrap", True))
            try:
                return flask.jsonify(self.service.train_model(bootstrap_if_empty=bootstrap))
            except Exception as error:
                return flask.jsonify({"error": str(error)}), 500

        @self.blueprint.route("/api/model-status")
        @login.login_required_when_activated
        def model_status():
            try:
                return flask.jsonify(self.service.get_model_status())
            except Exception as error:
                return flask.jsonify({"error": str(error)}), 500

        @self.blueprint.route("/api/optimize", methods=["POST"])
        @login.login_required_when_activated
        def optimize():
            body = flask.request.get_json(silent=True) or {}
            instrument = str(body.get("instrument", "BTC_USDT")).upper()
            try:
                return flask.jsonify(self.service.optimize_strategy(instrument=instrument))
            except Exception as error:
                return flask.jsonify({"error": str(error)}), 500

        @self.blueprint.route("/api/strategy-params")
        @login.login_required_when_activated
        def strategy_params():
            try:
                return flask.jsonify(self.service.get_strategy_params())
            except Exception as error:
                return flask.jsonify({"error": str(error)}), 500

        @self.blueprint.route("/api/sentiment")
        @login.login_required_when_activated
        def sentiment():
            symbol = flask.request.args.get("symbol")
            try:
                return flask.jsonify(self.service.get_sentiment(symbol=symbol))
            except Exception as error:
                return flask.jsonify({"error": str(error)}), 500

        @self.blueprint.route("/api/news")
        @login.login_required_when_activated
        def news():
            symbol = flask.request.args.get("symbol")
            limit = max(5, min(int(flask.request.args.get("limit", 20)), 50))
            try:
                return flask.jsonify({"news": self.service.get_news(limit=limit, symbol=symbol)})
            except Exception as error:
                return flask.jsonify({"error": str(error)}), 500

