# Crypto.com AI Pro Trader & Strategy Hub (Standalone Edition)

An autonomous, ultra-fast trading terminal and strategy studio for the **Crypto.com Exchange**. Completely severed and decoupled from OctoBot, running as a lightweight, independent Python application.

---

## Features

- **TradingView Live Charting**: Instant, responsive candle charts with indicators across BTC, ETH, SOL, DOGE, and more.
- **Fast-Cycle Seconds Scalper**: Micro-interval trading (15s, 30s, 60s, 120s, 300s) with floating PnL rings, cashout anytime, and automated expiration settlement.
- **Multi-AI Autonomous Auto-Pilot**:
  - **Antigravity AI**: Google Gemini 3.6 Flash / 2.5 Flash for high-speed technical synthesis and micro-momentum analysis.
  - **Codex AI**: OpenAI GPT-4o / GPT-5 Codex quant advisor for directional orderbook bias.
  - **Dual-AI Consensus**: Automated trades trigger only when both independent models agree.
- **Automated Trading Bots**:
  - **Grid Trading Bot**: Automated limit order grids within customizable price channels.
  - **DCA Accumulator**: Systematic Dollar-Cost Averaging with dynamic dip multipliers.
  - **Market Radar Momentum**: Multi-pair order book depth imbalance and spread scanner.
- **AI Copilot (Talk to Trade)**: Chat with your AI copilot to inspect live orderbooks, analyze portfolio holdings, or generate 1-click execution cards.
- **Dual Execution Modes**: Paper / Simulated trading ($10,000 virtual balance) and real live API order execution.

---

## Project Structure

```text
CryptoCom_Trader/
├── app.py                      # Standalone Flask app & REST API endpoints
├── config.py                   # Configuration & .env environment loader
├── requirements.txt            # Lightweight Python dependencies
├── .env.example                # Configuration template
├── Dockerfile                  # Slim production Docker image (~100MB)
├── docker-compose.yml          # Containerized deployment spec
├── market_radar/               # Trading engine, exchange client & AI micro-advisors
├── templates/
│   ├── base.html               # Clean dark theme layout & navigation
│   └── index.html              # Main Pro Trader & Seconds Scalper terminal
└── static/
    ├── css/
    │   └── crypto_com_trader.css
    └── js/
        └── crypto_com_trader.js
```

---

## Quick Start (Local)

### 1. Install Dependencies
```bash
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Environment
Copy `.env.example` to `.env` and fill in your keys:
```bash
cp .env.example .env
```

### 3. Run Application
```bash
python app.py
```
Open your browser at **[http://localhost:5050](http://localhost:5050)**.

---

## Deploy with Docker

### Local or VPS Docker Compose:
```bash
docker compose up -d --build
```
Check container status:
```bash
docker compose ps
docker compose logs -f
```

---

## VPS / Production Deployment

To run this on a separate VPS or subdomain (e.g. `trade.yourdomain.com`):
1. Clone or copy the `CryptoCom_Trader` folder to your server:
   ```bash
   scp -r CryptoCom_Trader user@your-server:/opt/cryptocom-trader
   ```
2. Set your production keys in `/opt/cryptocom-trader/.env`.
3. Launch with Docker Compose:
   ```bash
   cd /opt/cryptocom-trader
   docker compose up -d --build
   ```
4. Point Nginx or Traefik reverse proxy to port `5050`.
