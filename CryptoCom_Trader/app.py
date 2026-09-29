"""Standalone Crypto.com AI Pro Trader & Strategy Hub Application."""

import os
import sys
import flask
from functools import wraps

# Ensure market_radar is in python path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from config import Config
from market_radar.crypto_com_trade import (
    CryptoComTraderService,
    CryptoComAPIError,
)
from market_radar.crypto_com_ai import CryptoComAIEngine

app = flask.Flask(
    __name__,
    template_folder=os.path.join(current_dir, "templates"),
    static_folder=os.path.join(current_dir, "static"),
)
app.config["SECRET_KEY"] = Config.SECRET_KEY

# Initialize singletons
service = CryptoComTraderService.get_instance()
ai_engine = CryptoComAIEngine(service)

# Apply pre-configured credentials if provided in .env
if Config.CRYPTO_COM_API_KEY and Config.CRYPTO_COM_API_SECRET:
    service.set_credentials(Config.CRYPTO_COM_API_KEY, Config.CRYPTO_COM_API_SECRET)

def auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not Config.AUTH_ENABLED:
            return f(*args, **kwargs)
        if flask.session.get("authenticated"):
            return f(*args, **kwargs)
        return flask.redirect(flask.url_for("login", next=flask.request.url))
    return decorated

# --- Authentication Routes ---

@app.route("/login", methods=["GET", "POST"])
def login():
    if not Config.AUTH_ENABLED or flask.session.get("authenticated"):
        return flask.redirect(flask.url_for("index"))
    
    error = None
    if flask.request.method == "POST":
        password = flask.request.form.get("password", "")
        if password == Config.APP_PASSWORD:
            flask.session["authenticated"] = True
            next_url = flask.request.args.get("next") or flask.url_for("index")
            return flask.redirect(next_url)
        error = "Invalid application password"
        
    return flask.render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Crypto.com Trader Login</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@4.6.2/dist/css/bootstrap.min.css">
        <style>
            body { background: #07090e; color: #fff; height: 100vh; display: flex; align-items: center; justify-content: center; }
            .card { background: #0e121a; border: 1px solid rgba(212,175,55,0.3); border-radius: 12px; width: 100%; max-width: 400px; }
            .btn-gold { background: #d4af37; color: #000; font-weight: 700; border: none; }
            .btn-gold:hover { background: #f5d77f; }
        </style>
    </head>
    <body>
        <div class="card p-4 shadow">
            <h4 class="text-center font-weight-bold mb-3" style="color: #d4af37;">⚡ Crypto.com Pro Trader</h4>
            {% if error %}<div class="alert alert-danger py-2 small">{{ error }}</div>{% endif %}
            <form method="POST">
                <div class="form-group">
                    <label class="small text-muted">Application Password</label>
                    <input type="password" name="password" class="form-control" style="background: #090c10; color: #fff; border-color: #333;" required autofocus>
                </div>
                <button type="submit" class="btn btn-gold btn-block mt-3">Access Terminal</button>
            </form>
        </div>
    </body>
    </html>
    """, error=error)

@app.route("/logout")
def logout():
    flask.session.pop("authenticated", None)
    return flask.redirect(flask.url_for("login"))

# --- Health / Ping ---

@app.route("/healthz")
@app.route("/ping")
def health():
    return flask.jsonify({"status": "ok", "app": "CryptoCom_Trader", "version": "1.0.0"})

# --- Main UI Page ---

@app.route("/")
@app.route("/crypto-com/")
@auth_required
def index():
    return flask.render_template("index.html")

# --- Core Trading API Endpoints ---

@app.route("/api/status")
@app.route("/crypto-com/api/status")
@auth_required
def status():
    try:
        return flask.jsonify(service.get_status())
    except Exception as error:
        return flask.jsonify({"error": str(error)}), 500

@app.route("/api/mode", methods=["POST"])
@app.route("/crypto-com/api/mode", methods=["POST"])
@auth_required
def set_mode():
    body = flask.request.get_json(silent=True) or {}
    mode = str(body.get("mode", "paper"))
    try:
        res_mode = service.set_mode(mode)
        return flask.jsonify({"mode": res_mode})
    except ValueError as error:
        return flask.jsonify({"error": str(error)}), 400
    except Exception as error:
        return flask.jsonify({"error": str(error)}), 500

@app.route("/api/paper/reset", methods=["POST"])
@app.route("/crypto-com/api/paper/reset", methods=["POST"])
@auth_required
def reset_paper():
    try:
        body = flask.request.get_json(silent=True) or {}
        amount = float(body.get("amount", 10000.0))
        return flask.jsonify(service.reset_paper(amount))
    except Exception as error:
        return flask.jsonify({"error": str(error)}), 500

@app.route("/api/credentials", methods=["POST"])
@app.route("/crypto-com/api/credentials", methods=["POST"])
@auth_required
def set_credentials():
    body = flask.request.get_json(silent=True) or {}
    api_key = str(body.get("api_key", ""))
    api_secret = str(body.get("api_secret", ""))
    if not api_key or not api_secret:
        return flask.jsonify({"error": "API Key and Secret are required"}), 400
    res = service.set_credentials(api_key, api_secret)
    return flask.jsonify(res)

@app.route("/api/portfolio")
@app.route("/crypto-com/api/portfolio")
@auth_required
def portfolio():
    try:
        return flask.jsonify(service.get_portfolio())
    except Exception as error:
        return flask.jsonify({"error": str(error)}), 500

@app.route("/api/market/<instrument>")
@app.route("/crypto-com/api/market/<instrument>")
@auth_required
def market_overview(instrument):
    try:
        instrument = instrument.upper()
        return flask.jsonify(service.get_market_overview(instrument))
    except Exception as error:
        return flask.jsonify({"error": str(error)}), 500

@app.route("/api/candles/<instrument>")
@app.route("/crypto-com/api/candles/<instrument>")
@auth_required
def candles(instrument):
    timeframe = flask.request.args.get("timeframe", "1h")
    count = max(10, min(int(flask.request.args.get("count", 100)), 300))
    try:
        return flask.jsonify({
            "candles": service.get_candles(instrument.upper(), timeframe, count)
        })
    except Exception as error:
        return flask.jsonify({"error": str(error)}), 500

@app.route("/api/order/create", methods=["POST"])
@app.route("/crypto-com/api/order/create", methods=["POST"])
@auth_required
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

        order = service.execute_order(
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

@app.route("/api/order/cancel", methods=["POST"])
@app.route("/crypto-com/api/order/cancel", methods=["POST"])
@auth_required
def cancel_order():
    body = flask.request.get_json(silent=True) or {}
    try:
        instrument = str(body.get("instrument", "")).upper()
        order_id = str(body.get("order_id", ""))
        if not order_id:
            return flask.jsonify({"error": "order_id is required"}), 400
        res = service.cancel_order(instrument, order_id)
        return flask.jsonify({"status": "ok", "result": res})
    except Exception as error:
        return flask.jsonify({"error": str(error)}), 500

@app.route("/api/order/cancel-all", methods=["POST"])
@app.route("/crypto-com/api/order/cancel-all", methods=["POST"])
@auth_required
def cancel_all():
    body = flask.request.get_json(silent=True) or {}
    instrument = str(body.get("instrument", "")).upper() or None
    try:
        res = service.cancel_all_orders(instrument)
        return flask.jsonify({"status": "ok", "result": res})
    except Exception as error:
        return flask.jsonify({"error": str(error)}), 500

@app.route("/api/orders/open")
@app.route("/crypto-com/api/orders/open")
@auth_required
def open_orders():
    instrument = flask.request.args.get("instrument")
    instrument = instrument.upper() if instrument else None
    try:
        return flask.jsonify({"open_orders": service.get_open_orders(instrument)})
    except Exception as error:
        return flask.jsonify({"error": str(error)}), 500

@app.route("/api/orders/history")
@app.route("/crypto-com/api/orders/history")
@auth_required
def order_history():
    instrument = flask.request.args.get("instrument")
    instrument = instrument.upper() if instrument else None
    try:
        return flask.jsonify({"history": service.get_order_history(instrument)})
    except Exception as error:
        return flask.jsonify({"error": str(error)}), 500

# --- Strategy Bot Routes ---

@app.route("/api/strategies")
@app.route("/crypto-com/api/strategies")
@auth_required
def strategies():
    try:
        return flask.jsonify(service.strategy_mgr.get_status())
    except Exception as error:
        return flask.jsonify({"error": str(error)}), 500

@app.route("/api/strategy/grid/start", methods=["POST"])
@app.route("/crypto-com/api/strategy/grid/start", methods=["POST"])
@auth_required
def start_grid():
    body = flask.request.get_json(silent=True) or {}
    try:
        res = service.strategy_mgr.start_grid(
            instrument=str(body.get("instrument", "BTC_USDT")).upper(),
            lower_price=float(body.get("lower_price", 0)),
            upper_price=float(body.get("upper_price", 0)),
            grids=int(body.get("grids", 10)),
            total_investment_usdt=float(body.get("total_investment", 100)),
            is_live=(service.mode == "live"),
        )
        return flask.jsonify(res)
    except ValueError as error:
        return flask.jsonify({"error": str(error)}), 400
    except Exception as error:
        return flask.jsonify({"error": str(error)}), 500

@app.route("/api/strategy/grid/stop", methods=["POST"])
@app.route("/crypto-com/api/strategy/grid/stop", methods=["POST"])
@auth_required
def stop_grid():
    try:
        return flask.jsonify(service.strategy_mgr.stop_grid())
    except Exception as error:
        return flask.jsonify({"error": str(error)}), 500

@app.route("/api/strategy/dca/start", methods=["POST"])
@app.route("/crypto-com/api/strategy/dca/start", methods=["POST"])
@auth_required
def start_dca():
    body = flask.request.get_json(silent=True) or {}
    try:
        res = service.strategy_mgr.start_dca(
            instrument=str(body.get("instrument", "BTC_USDT")).upper(),
            amount_usdt=float(body.get("amount_usdt", 25)),
            interval_minutes=int(body.get("interval_minutes", 60)),
            dip_multiplier_enabled=bool(body.get("dip_multiplier_enabled", True)),
            is_live=(service.mode == "live"),
        )
        return flask.jsonify(res)
    except ValueError as error:
        return flask.jsonify({"error": str(error)}), 400
    except Exception as error:
        return flask.jsonify({"error": str(error)}), 500

@app.route("/api/strategy/dca/stop", methods=["POST"])
@app.route("/crypto-com/api/strategy/dca/stop", methods=["POST"])
@auth_required
def stop_dca():
    try:
        return flask.jsonify(service.strategy_mgr.stop_dca())
    except Exception as error:
        return flask.jsonify({"error": str(error)}), 500

@app.route("/api/strategy/radar/start", methods=["POST"])
@app.route("/crypto-com/api/strategy/radar/start", methods=["POST"])
@auth_required
def start_radar():
    body = flask.request.get_json(silent=True) or {}
    try:
        instruments = [str(i).upper() for i in body.get("instruments", ["BTC_USDT", "ETH_USDT", "CRO_USDT"])]
        res = service.strategy_mgr.start_radar(
            instruments=instruments,
            min_buy_score=float(body.get("min_buy_score", 75.0)),
            max_sell_score=float(body.get("max_sell_score", 40.0)),
            order_size_usdt=float(body.get("order_size_usdt", 50.0)),
            is_live=(service.mode == "live"),
        )
        return flask.jsonify(res)
    except Exception as error:
        return flask.jsonify({"error": str(error)}), 500

@app.route("/api/strategy/radar/stop", methods=["POST"])
@app.route("/crypto-com/api/strategy/radar/stop", methods=["POST"])
@auth_required
def stop_radar():
    try:
        return flask.jsonify(service.strategy_mgr.stop_radar())
    except Exception as error:
        return flask.jsonify({"error": str(error)}), 500

# --- AI Copilot & Radar Endpoints ---

@app.route("/api/copilot/chat", methods=["POST"])
@app.route("/api/ai/copilot", methods=["POST"])
@app.route("/crypto-com/api/copilot/chat", methods=["POST"])
@auth_required
def ai_copilot():
    body = flask.request.get_json(silent=True) or {}
    prompt = str(body.get("prompt", "")).strip()
    instrument = str(body.get("instrument", "BTC_USDT")).upper()
    if not prompt:
        return flask.jsonify({"error": "Prompt cannot be empty"}), 400
    try:
        res = ai_engine.process_copilot_message(
            prompt=prompt,
            active_instrument=instrument,
        )
        return flask.jsonify(res)
    except Exception as error:
        return flask.jsonify({"error": str(error)}), 500

@app.route("/api/ai/radar", methods=["GET"])
@app.route("/crypto-com/api/ai/radar", methods=["GET"])
@auth_required
def ai_radar():
    instrument = flask.request.args.get("instrument", "BTC_USDT").upper()
    try:
        res = ai_engine.generate_radar_analysis(instrument=instrument)
        return flask.jsonify(res)
    except Exception as error:
        return flask.jsonify({"error": str(error)}), 500

@app.route("/api/ai/execute-action", methods=["POST"])
@app.route("/crypto-com/api/ai/execute-action", methods=["POST"])
@auth_required
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

        order = service.execute_order(
            instrument=instrument,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
        )
        return flask.jsonify({"status": "ok", "order": order})
    except Exception as error:
        return flask.jsonify({"error": str(error)}), 500

# --- Seconds Scalper Endpoints ---

@app.route("/api/seconds/advice", methods=["GET"])
@app.route("/crypto-com/api/seconds/advice", methods=["GET"])
@auth_required
def seconds_advice():
    instrument = flask.request.args.get("instrument", "BTC_USDT").upper()
    provider = flask.request.args.get("provider", "auto").lower()
    try:
        res = ai_engine.generate_seconds_advice(instrument=instrument, provider=provider)
        return flask.jsonify(res)
    except Exception as error:
        return flask.jsonify({"error": str(error)}), 500

@app.route("/api/seconds/trade", methods=["POST"])
@app.route("/crypto-com/api/seconds/trade", methods=["POST"])
@auth_required
def seconds_trade():
    body = flask.request.get_json(silent=True) or {}
    instrument = str(body.get("instrument", "BTC_USDT")).upper()
    direction = str(body.get("direction", "CALL")).upper()
    ai_eng = str(body.get("ai_engine", "Manual"))
    try:
        stake = float(body.get("stake_usdt", 10.0))
        duration = int(body.get("duration_seconds", 30))
        is_live = (service.mode == "live")
        res = service.seconds_mgr.open_seconds_trade(
            instrument=instrument,
            direction=direction,
            stake_usdt=stake,
            duration_seconds=duration,
            is_live=is_live,
            ai_engine=ai_eng,
        )
        return flask.jsonify({"status": "ok", "trade": res})
    except ValueError as val_err:
        return flask.jsonify({"error": str(val_err)}), 400
    except Exception as error:
        return flask.jsonify({"error": str(error)}), 500

@app.route("/api/seconds/active", methods=["GET"])
@app.route("/crypto-com/api/seconds/active", methods=["GET"])
@auth_required
def seconds_active():
    try:
        active = service.seconds_mgr.get_active_trades()
        return flask.jsonify({"active_trades": active})
    except Exception as error:
        return flask.jsonify({"error": str(error)}), 500

@app.route("/api/seconds/cashout", methods=["POST"])
@app.route("/crypto-com/api/seconds/cashout", methods=["POST"])
@auth_required
def seconds_cashout():
    body = flask.request.get_json(silent=True) or {}
    trade_id = str(body.get("trade_id", "")).strip()
    if not trade_id:
        return flask.jsonify({"error": "trade_id is required"}), 400
    try:
        res = service.seconds_mgr.close_seconds_trade(trade_id=trade_id, early_exit=True)
        return flask.jsonify({"status": "ok", "trade": res})
    except ValueError as val_err:
        return flask.jsonify({"error": str(val_err)}), 400
    except Exception as error:
        return flask.jsonify({"error": str(error)}), 500

@app.route("/api/seconds/history", methods=["GET"])
@app.route("/crypto-com/api/seconds/history", methods=["GET"])
@auth_required
def seconds_history():
    try:
        return flask.jsonify(service.seconds_mgr.get_history())
    except Exception as error:
        return flask.jsonify({"error": str(error)}), 500

@app.route("/api/seconds/autopilot/status", methods=["GET"])
@app.route("/crypto-com/api/seconds/autopilot/status", methods=["GET"])
@auth_required
def seconds_autopilot_status():
    try:
        return flask.jsonify(service.get_seconds_autopilot_status())
    except Exception as error:
        return flask.jsonify({"error": str(error)}), 500

@app.route("/api/seconds/autopilot/toggle", methods=["POST"])
@app.route("/crypto-com/api/seconds/autopilot/toggle", methods=["POST"])
@auth_required
def seconds_autopilot_toggle():
    body = flask.request.get_json(silent=True) or {}
    enabled = bool(body.get("enabled", False))
    eng = body.get("engine")
    min_confidence = body.get("min_confidence")
    stake = body.get("stake_usdt")
    duration = body.get("duration_seconds")
    instrument = body.get("instrument")
    try:
        res = service.toggle_seconds_autopilot(
            enabled=enabled,
            engine=eng,
            min_confidence=min_confidence,
            stake=stake,
            duration=duration,
            instrument=instrument,
        )
        return flask.jsonify({"status": "ok", "autopilot": res})
    except Exception as error:
        return flask.jsonify({"error": str(error)}), 500

if __name__ == "__main__":
    print(f"🚀 Starting Crypto.com Standalone Trader on http://{Config.HOST}:{Config.PORT}")
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
