ARG OCTOBOT_IMAGE=drakkarsoftware/octobot:stable
FROM ${OCTOBOT_IMAGE}

ENV WEB_PORT=5001
ENV PORT=5001
ENV OCTOBOT_STANDALONE=true

EXPOSE 5001

HEALTHCHECK --start-period=5m --interval=30s --timeout=10s --retries=5 CMD curl -fsS http://127.0.0.1:5001 || exit 1
