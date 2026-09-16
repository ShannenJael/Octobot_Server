#!/usr/bin/env sh
set -eu

missing=""

for cmd in docker git curl; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    missing="$missing $cmd"
  fi
done

if ! docker compose version >/dev/null 2>&1; then
  missing="$missing docker-compose-plugin"
fi

if [ -n "$missing" ]; then
  echo "Missing required tooling:$missing" >&2
  exit 1
fi

if [ ! -f .env ]; then
  echo "Missing .env. Copy deploy/bluehost-vps/.env.example to .env and edit it." >&2
  exit 1
fi

. ./.env

if [ "${HOST:-}" = "" ] || [ "$HOST" = "octobot.example.com" ]; then
  echo "HOST is not configured in .env" >&2
  exit 1
fi

echo "Docker: $(docker --version)"
echo "Compose: $(docker compose version)"
echo "Git: $(git --version)"
echo "Host: $HOST"
echo "Readiness checks passed."
