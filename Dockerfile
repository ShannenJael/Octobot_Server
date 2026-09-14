ARG OCTOBOT_IMAGE=drakkarsoftware/octobot:stable
FROM ${OCTOBOT_IMAGE}

ENV WEB_PORT=5001
ENV PORT=5001
ENV OCTOBOT_STANDALONE=true

# Add the auditable scanner and its Web Interface plug-in to the upstream image.
COPY market_radar /octobot/market_radar
COPY tentacles/Services/Interfaces/web_interface/plugins/__init__.py /octobot/tentacles/Services/Interfaces/web_interface/plugins/__init__.py
COPY tentacles/Services/Interfaces/web_interface/plugins/market_radar_plugin.py /octobot/tentacles/Services/Interfaces/web_interface/plugins/market_radar_plugin.py
COPY tentacles/Services/Interfaces/web_interface/plugins/market_radar_assets /octobot/tentacles/Services/Interfaces/web_interface/plugins/market_radar_assets
COPY tentacles/Evaluator/Strategies/market_radar_strategy_evaluator /octobot/tentacles/Evaluator/Strategies/market_radar_strategy_evaluator

EXPOSE 5001

HEALTHCHECK --start-period=5m --interval=30s --timeout=10s --retries=5 CMD curl -fsS -o /dev/null http://127.0.0.1:5001 || exit 1
