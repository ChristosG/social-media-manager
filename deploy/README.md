# deploy/

Deployment infrastructure for the microservices platform. Two modes: **production** (optimized Docker builds) and **dev** (source-mounted hot reload). Infrastructure containers (postgres, redis) are shared between both.

## Directory Layout

```
deploy/
├── services.yml                   # Service registry — stacks and their compose files
├── .env                           # Environment config (copied from .env.example)
├── scripts/
│   ├── deploy.sh                  # CLI wrapper for all operations
│   └── init-ssl.sh                # First-time SSL cert acquisition
├── stacks/
│   ├── infra/                     # postgres, redis, nightly db-backup
│   │   └── docker-compose.yml
│   ├── backend/                   # auth (gRPC), gateway (REST), agent-service (Python), email
│   │   ├── docker-compose.yml
│   │   ├── docker-compose.dev.yml
│   │   ├── air.auth.toml
│   │   └── air.gateway.toml
│   └── frontend/                  # webapp (Next.js) + nginx reverse proxy
│       ├── docker-compose.yml
│       ├── docker-compose.dev.yml
│       ├── Dockerfile.nextjs
│       └── nginx/
│           ├── nginx.conf
│           ├── templates/         # envsubst'd at container start
│           ├── snippets/          # security headers, ssl, gzip, proxy params
│           └── ssl.conf.template  # activated by init-ssl.sh
└── nginx-host/
    └── cgrigoriadis.online        # Host nginx vhost (see "Nginx" section)
```

## Quick Start

```bash
cd deploy
cp .env.example .env    # fill in JWT keys, passwords, domain

# Start everything
./scripts/deploy.sh build all
./scripts/deploy.sh up all

# App is at http://localhost:8880
```

## Services

The `services.yml` file is the service registry. `deploy.sh` reads it to compose the right files for each stack. Adding a new stack = adding an entry to `services.yml` + its compose file.

| Stack | Containers | Purpose |
|-------|------------|---------|
| **infra** | postgres, redis, db-backup | Shared infrastructure |
| **backend** | auth, gateway, agent-service, email-service | Go auth + gateway, Python agent, email |
| **frontend** | webapp, nginx-proxy | Next.js app + nginx reverse proxy |

Each stack runs as its own Docker Compose project. They share the `platform-net` bridge network.

### Dev Mode

Mounts source code into containers. Go services rebuild on save via [air](https://github.com/air-verse/air), Next.js uses turbopack, auth-ui uses tsup watch + tailwindcss watch.

```bash
./scripts/deploy.sh dev up                # everything
./scripts/deploy.sh dev up backend        # just Go + Spring services
./scripts/deploy.sh dev up frontend       # just Next.js + auth-ui
./scripts/deploy.sh dev logs auth         # tail a service
./scripts/deploy.sh dev down              # stop everything
```

| Container | Image | What it runs |
|-----------|-------|-------------|
| auth-dev | golang:1.23-alpine | air watches `services/auth/`, `pkg/`, `proto/gen/` |
| gateway-dev | golang:1.23-alpine | air watches `services/gateway/`, `pkg/`, `proto/gen/` |
| webapp-dev | oven/bun:1-alpine | `next dev --turbopack` |
| auth-ui-dev | oven/bun:1-alpine | `tsup --watch` + `tailwindcss --watch` |

No nginx in dev mode — Next.js serves directly on port 3000.

### Production

Builds optimized Docker images. Go services compile to static binaries, Spring Boot builds a fat JAR, Next.js builds standalone output, nginx handles SSL/caching/rate-limiting.

```bash
./scripts/deploy.sh build all             # build all images
./scripts/deploy.sh up all                # start everything
./scripts/deploy.sh ssl                   # get Let's Encrypt cert (first time)
./scripts/deploy.sh update webapp         # rebuild + restart one service
./scripts/deploy.sh down all              # stop everything
```

## CLI Reference

```
deploy.sh <command> [stack]

Stacks: infra | backend | frontend | all (default)

Production:
  up [stack]              Start services
  down [stack]            Stop services
  build [stack]           Build images
  restart [svc]           Restart a single service
  logs [svc]              Tail logs
  status [stack]          Show running containers
  update [svc]            Rebuild + restart a single service
  ssl                     Initialize SSL certificate
  db-functions            (Re)apply the SECURITY DEFINER scheduler functions

Dev mode:
  dev up [stack]          Start with hot reload
  dev down [stack]        Stop
  dev logs [svc]          Tail logs
  dev status [stack]      Show running containers
  dev restart [svc]       Restart a single service
```

## Selecting the Frontend App

The `WEBAPP_DIR` env var controls which Next.js app gets built. Any app that uses `@platform/auth-ui` can be dropped in:

```bash
# In .env
WEBAPP_DIR=chatbot_webapp    # the chat app
WEBAPP_DIR=nextjs-starter    # the demo/starter app
WEBAPP_DIR=my-custom-app     # your own app
```

The `Dockerfile.nextjs` is generic — it copies `WEBAPP_DIR` and `auth-ui`, installs deps, and builds.

## Nginx — The Double Proxy Setup

Two nginx instances in production. This is intentional.

### Why two?

The host machine runs other services. A single host-level nginx on ports 80/443 handles all incoming traffic and routes by domain. Docker containers can't bind to 80/443 without conflicting with it.

```
Internet
  │
  ▼
Host nginx (port 80/443)         ← terminates SSL, routes by domain
  │
  ▼ proxy_pass http://127.0.0.1:8880
  │
Docker nginx (port 8880)         ← rate limiting, security headers, caching, WS
  │
  ├─ /api/v1/chat/*  ──▶ gateway:8080   (chat REST, SSE streaming)
  ├─ /ws/chat         ──▶ gateway:8080   (WebSocket proxy)
  ├─ /api/v1/auth/*   ──▶ webapp:3000    (BFF → gateway)
  └─ /*               ──▶ webapp:3000    (Next.js pages)
```

### Host nginx

Lives outside Docker. Routes domain traffic to Docker nginx on port 8880.

Config: `nginx-host/cgrigoriadis.online` → install to `/etc/nginx/sites-available/`.

### Docker nginx

Runs inside the `frontend` stack:
- Rate limiting (`RATE_LIMIT_RPS` / `RATE_LIMIT_BURST`)
- Security headers, gzip compression
- Long cache for `/_next/static/` assets
- WebSocket passthrough for `/ws/chat`
- SSE streaming support for `/api/v1/chat/` (proxy_buffering off)

### Standalone mode (no host nginx)

Set Docker nginx to bind directly to 80/443:
```
NGINX_HTTP_PORT=80
NGINX_HTTPS_PORT=443
```
Then run `./scripts/deploy.sh ssl` for Let's Encrypt.

## SSL

**With host nginx (shared machine):** SSL at host level with `certbot --nginx`. Docker nginx receives plain HTTP on port 8880.

**Standalone (dedicated machine):** `./scripts/deploy.sh ssl` bootstraps Let's Encrypt inside Docker. Enable auto-renewal with:
```bash
docker compose -f stacks/frontend/docker-compose.yml --profile ssl up -d
```

## Environment

All config lives in `.env`. See `.env.example` for the full list. Key variables:

| Variable | Purpose |
|----------|---------|
| `JWT_PRIVATE_KEY` / `JWT_PUBLIC_KEY` | Ed25519 raw key bytes, base64-encoded |
| `MFA_ENCRYPTION_KEY` | AES key for TOTP secrets at rest |
| `POSTGRES_PASSWORD` | Database password |
| `DOMAIN` | Your domain for nginx / SSL |
| `GATEWAY_CORS_ALLOWED_ORIGINS` | Must match where the frontend is served from |
| `REDIS_ADDR` | Redis address (default: `redis:6379`) |
| `LLM_PROVIDER` | Chat LLM provider: `mock`, `claude`, `openai` |
| `LLM_API_KEY` / `LLM_MODEL` | API key and model for the LLM provider |
| `WEBAPP_DIR` | Which Next.js app to build (`chatbot_webapp`, `nextjs-starter`) |

## Network

All stacks share Docker network `platform-net`. Services reference each other by container name (`postgres`, `redis`, `auth`, `gateway`, `agent-service`, `webapp`).

For multi-machine deployments, update `.env` to use real addresses:
```
AUTH_DB_HOST=10.0.0.1
GATEWAY_URL=https://api.example.com
```

## Adding a New Service

1. Add your service's compose file to a stack (or create a new stack directory)
2. Register it in `services.yml`:
   ```yaml
   my-stack:
     compose: stacks/my-stack/docker-compose.yml
     dev_compose: stacks/my-stack/docker-compose.dev.yml
   ```
3. `./scripts/deploy.sh build my-stack && ./scripts/deploy.sh up my-stack`
