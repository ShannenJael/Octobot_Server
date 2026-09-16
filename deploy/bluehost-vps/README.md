# Bluehost VPS Deployment

This deployment runs OctoBot on a Bluehost VPS or dedicated server with Docker and Docker
Compose. Bluehost shared hosting is not enough for OctoBot because it does not provide
Docker, Python 3.11, or a persistent Python app runner.

The production domain, `marketaioctobot.com`, should point at the VPS public IP. Traefik
terminates HTTPS with Let's Encrypt and forwards requests to the OctoBot container.

## Server Prerequisites

- Docker Engine
- Docker Compose plugin
- DNS `A` records for `marketaioctobot.com` and `www.marketaioctobot.com` pointing to the VPS public IP
- Ports `80` and `443` open for Traefik and Let's Encrypt
- SSH access to the VPS as `root` or a sudo-capable user

## Deploy

```bash
git clone https://github.com/ShannenJael/Octobot_Server.git /opt/octobot
cd /opt/octobot
cp deploy/bluehost-vps/.env.example .env
vi .env
docker compose -f docker-compose.yml -f docker-compose.https.yml up -d --build
```

OctoBot will run behind Traefik at `https://$HOST`.

## Migrate Existing State

Copy these local folders from the working machine to the VPS project directory before the
first production start if you want to preserve the current bot configuration:

- `user`
- `tentacles`
- `logs`
- `backtesting`

The `user` folder contains the current OctoBot configuration, including encrypted exchange
credentials and the web-login password hash. Treat it as sensitive.

## Verify

```bash
docker compose -f docker-compose.yml -f docker-compose.https.yml ps
docker compose -f docker-compose.yml -f docker-compose.https.yml logs -f octobot
curl -I https://$HOST
```

The expected unauthenticated response is a redirect to `/login?next=%2F` or the login page.

## DNS Cutover

After the VPS stack is healthy:

1. In Bluehost DNS, change `marketaioctobot.com` `A` record to the VPS public IP.
2. Change `www` to the same VPS public IP, or make it a CNAME to `marketaioctobot.com`.
3. Remove any old shared-hosting redirect only after `https://marketaioctobot.com` works.

## Runtime Data

The compose stack keeps OctoBot state in these folders:

- `user`
- `tentacles`
- `logs`
- `backtesting`
- `letsencrypt`

Back these up before replacing or rebuilding the server.

## Safety Note

If `user/config.json` contains enabled exchange credentials, starting the container can start
the configured trading workflow. For a first migration smoke test, disable live exchanges or
use a non-trading profile before running `up -d`.
