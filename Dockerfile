FROM python:3.10-slim-bookworm AS base

WORKDIR /

# requires git to install requirements with git+https
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential git gcc binutils libffi-dev libssl-dev libxml2-dev libxslt1-dev libxslt-dev libjpeg62-turbo-dev zlib1g-dev \
    && python -m venv /opt/venv \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# skip cryptography rust compilation (required for armv7 builds)
ENV CRYPTOGRAPHY_DONT_BUILD_RUST=1

# Make sure we use the virtualenv:
ENV PATH="/opt/venv/bin:$PATH"

COPY . .
RUN pip install -U setuptools wheel "pip>=20.0.0" \
    && pip install --no-cache-dir --prefer-binary -r requirements.txt \
    && python setup.py install

FROM python:3.10-slim-bookworm

ARG TENTACLES_URL_TAG=""
ENV TENTACLES_URL_TAG=$TENTACLES_URL_TAG

WORKDIR /octobot

# Import python dependencies
COPY --from=base /opt/venv /opt/venv

# Add default config files
COPY octobot/config /octobot/octobot/config

COPY docker/* /octobot/

# 1. Install requirements
# 2. Add cloudflare gpg key and add cloudflare repo in apt repositories (from https://pkg.cloudflare.com/index.html)
# 3. Install required packages
# 4. Finish env setup
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && mkdir -p /usr/share/keyrings \
    && chmod 0755 /usr/share/keyrings \
    && curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null \
    && echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared bookworm main' | tee /etc/apt/sources.list.d/cloudflared.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends curl cloudflared libxslt-dev libxcb-xinput0 libjpeg62-turbo-dev zlib1g-dev libblas-dev liblapack-dev libatlas-base-dev libopenjp2-7 libtiff-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /opt/venv/bin/OctoBot OctoBot \
    && sed -i 's/\r$//' docker-entrypoint.sh \
    && sed -i 's/\r$//' tunnel.sh \
    && chmod +x docker-entrypoint.sh \
    && chmod +x tunnel.sh

VOLUME /octobot/backtesting
VOLUME /octobot/logs
VOLUME /octobot/tentacles
VOLUME /octobot/user

EXPOSE 5002

HEALTHCHECK --interval=15s --timeout=10s --retries=5 CMD ["sh", "-c", "curl -sS http://127.0.0.1:${WEB_PORT:-5002} || exit 1"]

ENTRYPOINT ["./docker-entrypoint.sh"]
