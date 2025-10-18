# Docker
## Install docker & docker compose
```
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
```

## Docker compose setup
### With SSL
- Create a .env file
```
HOST=your-domain.com
LETSENCRYPT_EMAIL=contact@your-domain.com
```

### Start
```
docker compose up -d
```

Notes:
- The OctoBot container listens on port 5001 internally. If you want to expose it on host port 5002, map the ports as follows in your `docker run` or `docker-compose` command:

```yaml
# docker-compose service snippet
services:
	octobot:
		image: drakkarsoftware/octobot:stable
		ports:
			- "5002:5001" # host:container
```
