#!/usr/bin/env sh
set -eu

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required. Use a Bluehost VPS/dedicated server, not shared hosting." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose plugin is required." >&2
  exit 1
fi

if [ ! -f .env ]; then
  cp deploy/bluehost-vps/.env.example .env
  echo "Created .env from deploy/bluehost-vps/.env.example. Edit HOST and LETSENCRYPT_EMAIL, then rerun." >&2
  exit 1
fi

docker compose -f docker-compose.yml -f docker-compose.https.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.https.yml ps
