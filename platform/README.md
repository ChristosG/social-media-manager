# Microservices Platform

A drop-in auth + gateway backend for fullstack projects. Built with Go, gRPC, PostgreSQL, and Redis.

## What's in the box

- **Auth Service** — Registration, login, JWT tokens, OAuth2 (Google/GitHub), TOTP MFA, password reset. Optional Redis integration for JWT blacklist, user cache, and refresh token cache.
- **API Gateway** — REST API that proxies to auth and chat services over gRPC, WebSocket proxy for LLM streaming, JWT validation, CORS. Optional Redis-backed rate limiting.
- **Redis 7** — JWT blacklist (instant token revocation), user/session cache, rate limiting (sliding window). All optional — services fall back to DB-only when `REDIS_ADDR` is empty.
- **PostgreSQL 18** — With pgvector and PostGIS extensions pre-installed. The single source of truth.

```
Client (browser/mobile)
    │ HTTP/REST
    ▼
┌──────────────┐         ┌──────────────┐
│   Gateway    │──gRPC──▶│ Auth Service  │
│   :8080      │         │   :50051      │
└──────────────┘         └──────┬───────┘
                                │
                                ▼
                         ┌──────────────┐      ┌──────────┐
                         │  PostgreSQL   │◀────▶│  Redis   │  (optional cache /
                         │    :5432      │      │  :6379   │   rate-limit / blacklist)
                         └──────────────┘      └──────────┘
```

## Quick Start

```bash
# 1. Clone the repo
git clone <repo-url> && cd platform

# 2. Generate Ed25519 JWT keys and MFA encryption key
./scripts/generate-keys.sh

# 3. Create .env and paste the keys from step 2
cp .env.example .env
# Edit .env and replace the JWT_PRIVATE_KEY, JWT_PUBLIC_KEY, and MFA_ENCRYPTION_KEY
# with the values printed by step 2

# 4. Start everything
make up

# 5. Test it
curl -X POST http://localhost:8080/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"MyPassword1","display_name":"Test"}'
```

### What you run manually vs. what's automatic

| Task | When | How |
|------|------|-----|
| Generate JWT + MFA keys | Once, before first startup | `./scripts/generate-keys.sh`, paste output into `.env` |
| Database migrations | Automatic | Auth service runs them on every startup |

**After a `make down-clean`** (which deletes all volumes): the database is wiped and migrations re-run automatically. Your `.env` keys are fine — no need to regenerate.

## REST API

Base URL: `http://localhost:8080`

### Public Endpoints

| Method | Path | Body | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/auth/register` | `{email, password, display_name, metadata?}` | Create account, returns tokens |
| `POST` | `/api/v1/auth/login` | `{email, password}` | Login, returns tokens (or `requires_mfa: true`) |
| `POST` | `/api/v1/auth/refresh` | `{refresh_token}` | Get new access + refresh tokens |
| `POST` | `/api/v1/auth/forgot-password` | `{email}` | Send password reset email (stubbed) |
| `POST` | `/api/v1/auth/reset-password` | `{token, new_password}` | Reset password using token |
| `POST` | `/api/v1/auth/verify-email` | `{token}` | Verify email address (stubbed) |
| `POST` | `/api/v1/auth/resend-verification` | `{email}` | Resend verification email (stubbed) |
| `GET` | `/api/v1/auth/oauth/{provider}` | query: `redirect_url` | Get OAuth authorization URL |
| `GET` | `/api/v1/auth/oauth/{provider}/callback` | query: `code, state` | OAuth callback, returns tokens |
| `POST` | `/api/v1/auth/mfa/verify` | `{mfa_token, code}` | Verify TOTP code during MFA login |
| `GET` | `/healthz` | — | Health check |
| `GET` | `/readyz` | — | Readiness check |

### Protected Endpoints (require `Authorization: Bearer <access_token>`)

| Method | Path | Body | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/auth/me` | — | Get current user profile |
| `POST` | `/api/v1/auth/logout` | `{refresh_token}` | Revoke refresh token |
| `POST` | `/api/v1/auth/mfa/enable` | — | Start MFA setup, returns TOTP secret + QR URL |
| `POST` | `/api/v1/auth/mfa/disable` | `{code}` | Disable MFA (requires current TOTP code) |

### Example Responses

**Register / Login:**
```json
{
  "access_token": "eyJhbG...",
  "refresh_token": "a1b2c3...",
  "user": {
    "id": "74e772ae-2e02-463a-a899-e9fb044f0913",
    "email": "test@test.com",
    "display_name": "Test",
    "email_verified": false,
    "mfa_enabled": false,
    "provider": "AUTH_PROVIDER_UNSPECIFIED",
    "created_at": "2026-02-21T03:32:02.780606Z",
    "updated_at": "2026-02-21T03:32:02.780606Z"
  }
}
```

**Login with MFA enabled:**
```json
{
  "requires_mfa": true,
  "mfa_token": "eyJhbG...",
  "access_token": "",
  "refresh_token": "",
  "user": null
}
```
Then call `POST /api/v1/auth/mfa/verify` with `{mfa_token, code}` to complete login.

**Errors:**
```json
{
  "error": "invalid credentials"
}
```

## JWT Details

- **Algorithm:** Ed25519 (EdDSA)
- **Access token TTL:** 15 minutes (configurable via `JWT_ACCESS_TOKEN_TTL`)
- **Refresh token TTL:** 7 days (configurable via `JWT_REFRESH_TOKEN_TTL`)
- Access tokens are stateless — the gateway validates them without hitting the database
- Refresh tokens are opaque random strings, stored as SHA-256 hashes in PostgreSQL
- Refresh token rotation: each use issues a new token and revokes the old one
- Replay detection: reusing an old refresh token revokes the entire token family

**Access token claims:**
```json
{
  "sub": "user-uuid",
  "email": "user@example.com",
  "exp": 1771645622,
  "iat": 1771644722,
  "nbf": 1771644722
}
```

## Events

The auth service has an **optional** domain-event hook (registration, login, token refresh, MFA, OAuth, password reset). It is **disabled by default** — there is no message broker in this system, so events are a no-op unless a sink is wired in. Failures never affect auth operations.

## Database Schema

**users**
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK, auto-generated |
| `email` | VARCHAR(255) | Unique |
| `email_verified` | BOOLEAN | Default false |
| `password_hash` | VARCHAR(255) | Nullable (OAuth-only users have no password) |
| `display_name` | VARCHAR(255) | |
| `mfa_enabled` | BOOLEAN | Default false |
| `mfa_secret` | BYTEA | AES-256-GCM encrypted TOTP secret |
| `metadata` | JSONB | Default `{}`, for project-specific data |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

**refresh_tokens**
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `user_id` | UUID | FK → users |
| `token_hash` | VARCHAR(64) | SHA-256 hash, unique |
| `family_id` | VARCHAR(64) | Groups tokens for replay detection |
| `expires_at` | TIMESTAMPTZ | |
| `revoked` | BOOLEAN | Default false |
| `created_at` | TIMESTAMPTZ | |

**password_resets**
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `user_id` | UUID | FK → users |
| `token_hash` | VARCHAR(64) | SHA-256 hash, unique |
| `expires_at` | TIMESTAMPTZ | 1 hour from creation |
| `used` | BOOLEAN | Default false |
| `created_at` | TIMESTAMPTZ | |

**oauth_accounts**
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `user_id` | UUID | FK → users |
| `provider` | VARCHAR(50) | `google` or `github` |
| `provider_user_id` | VARCHAR(255) | |
| `access_token` | TEXT | Encrypted |
| `refresh_token` | TEXT | Encrypted |

Unique constraint on `(provider, provider_user_id)`.

## Project Structure

```
platform/
├── go.work                         # Links all 4 Go modules
├── docker-compose.yml
├── Makefile
├── .env.example
│
├── proto/                          # Protobuf definitions (Go module)
│   ├── buf.yaml / buf.gen.yaml
│   ├── auth/v1/                    # Auth service protos
│   ├── chat/v1/                    # Chat service protos
│   ├── common/v1/                  # Shared types
│   └── gen/go/                     # Generated Go code
│
├── pkg/                            # Shared Go libraries (Go module)
│   ├── config/                     # Env-var loader
│   ├── logger/                     # Structured JSON logger (slog)
│   ├── jwt/                        # Ed25519 JWT sign/verify
│   ├── kafka/                      # Optional event-producer wrapper (disabled — no broker)
│   ├── middleware/                  # gRPC interceptors (recovery, request ID)
│   └── health/                     # Health check aggregator
│
├── services/
│   ├── auth/                       # Auth service (Go module)
│   │   ├── Dockerfile
│   │   ├── cmd/server/main.go
│   │   ├── migrations/             # SQL migrations (embedded, run on startup)
│   │   └── internal/
│   │       ├── config/             # Auth-specific config
│   │       ├── handler/            # gRPC handlers
│   │       ├── service/            # Business logic
│   │       ├── repository/         # Database access (pgx)
│   │       ├── model/              # Data models
│   │       ├── events/             # Optional domain-event hooks (disabled)
│   │       ├── crypto/             # Argon2id + TOTP
│   │       ├── redis/              # JWT blacklist, user cache, refresh cache
│   │       └── server/             # gRPC server setup
│   │
│   └── gateway/                    # API Gateway (Go module)
│       ├── Dockerfile
│       ├── cmd/server/main.go
│       └── internal/
│           ├── config/             # Gateway-specific config
│           ├── handler/            # REST handlers (HTTP → gRPC), WS proxy, chat handler
│           ├── middleware/         # JWT auth, rate limit, CORS, logging
│           ├── router/             # chi route definitions
│           ├── client/             # gRPC clients (auth)
│           └── server/             # HTTP server setup
│
├── infra/
│   └── postgres/Dockerfile         # PG18 + pgvector + PostGIS
│
└── scripts/
    ├── generate-keys.sh            # Generate Ed25519 + MFA keys
    ├── generate-proto.sh           # Run buf generate
    └── wait-for-it.sh              # TCP port wait utility
```

## Configuration

Everything is configured via environment variables. See [`.env.example`](.env.example) for the full list.

Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_PORT` | `5432` | Host port for PostgreSQL |
| `JWT_PRIVATE_KEY` | — | Base64-encoded raw Ed25519 private key (64 bytes) |
| `JWT_PUBLIC_KEY` | — | Base64-encoded raw Ed25519 public key (32 bytes) |
| `JWT_ACCESS_TOKEN_TTL` | `15m` | Access token lifetime |
| `JWT_REFRESH_TOKEN_TTL` | `168h` | Refresh token lifetime (7 days) |
| `MFA_ENCRYPTION_KEY` | — | Base64-encoded 32-byte key for AES-256-GCM |
| `GATEWAY_HTTP_PORT` | `8080` | Gateway HTTP port |
| `GATEWAY_RATE_LIMIT_RPS` | `100` | Per-IP requests per second |
| `GATEWAY_CORS_ALLOWED_ORIGINS` | `localhost:3000,5173` | Comma-separated origins |
| `REDIS_ADDR` | (empty) | Redis address (e.g. `redis:6379`). Empty = disabled, all ops fall through to DB |
| `GATEWAY_CHAT_SERVICE_ADDR` | (empty) | Chat service gRPC address. Empty = chat routes disabled |
| `GATEWAY_CHAT_SERVICE_WS_URL` | (empty) | Chat service WebSocket URL (e.g. `chat-service:8081`) |
| `OAUTH_GOOGLE_CLIENT_ID` | — | Leave empty to disable Google OAuth |
| `OAUTH_GITHUB_CLIENT_ID` | — | Leave empty to disable GitHub OAuth |

## Make Targets

```
make up                  Start all services (builds images)
make down                Stop all services
make down-clean          Stop and remove volumes (resets DB)
make logs                Tail all logs
make logs-auth           Tail auth service logs
make logs-gateway        Tail gateway logs
make generate-keys       Generate JWT + MFA keys
make proto               Regenerate protobuf Go code
make build               Build binaries locally (requires Go)
make test                Run tests (requires Go)
make tidy                Run go mod tidy on all modules
make help                Show all targets
```

## Adding New Services

This platform is designed to have more services slot in behind the gateway. To add a new service:

1. Create a new module under `services/your-service/` with its own `go.mod`
2. Add it to `go.work`
3. Define its protobuf API under `proto/your-service/v1/`
4. Add a gRPC client in the gateway under `internal/client/`
5. Add REST handlers and routes in the gateway
6. Add a Dockerfile and add the service to `docker-compose.yml`

The `users.metadata` JSONB column is available for storing per-project user data without modifying the auth service schema.

## Stubs / Not Yet Implemented

- **Email sending** — `ForgotPassword`, `VerifyEmail`, and `ResendVerification` log to stdout instead of sending real emails. Integrate SendGrid/SES/etc by implementing the email service interface.
- **OAuth providers** — The flows are implemented but require real client credentials in `.env` to work. Leave the OAuth env vars empty to disable.

## Tech Stack

| Component | Version |
|-----------|---------|
| Go | 1.23 |
| PostgreSQL | 18 (pgvector + PostGIS) |
| Redis | 7 (Alpine) |
| gRPC / Protobuf | grpc 1.70, protobuf 1.36 |
| chi (HTTP router) | 5.2 |
| gorilla/websocket | 1.5 |
| go-redis | 9.7 |
| pgx (Postgres driver) | 5.7 |
| golang-migrate | 4.18 |
| golang-jwt | 5.2 |
| buf (protobuf tooling) | latest |
