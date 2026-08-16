# CI/CD Pipeline — GitHub Actions + Self-Hosted Registry

## Context

The monorepo has 4 deployable services (auth, gateway, demo-app, postgres) plus a shared library (auth-ui). Currently everything is built and deployed manually via `deploy.sh`. We need a GitHub Actions pipeline that:

1. Detects which services changed on push
2. Builds only the changed Docker images
3. Pushes them to a self-hosted container registry on this machine
4. SSHes into the server and runs `docker compose pull && up -d` to deploy

## Self-Hosted Registry

Run a Docker registry on the server. The GitHub Actions runner pushes images to it, and docker compose pulls from it.

**New file:** `deploy/stacks/infra/docker-compose.registry.yml`
- `registry:2` image on port 5000
- Volume for persistent storage
- Only accessible from localhost (no auth needed since it's local)
- Separate compose so it's always running, independent of the app stacks

For GitHub Actions to push to it, we need the registry accessible from the internet. Two options:
- **(A) SSH tunnel in the workflow** — `ssh -L 5000:localhost:5000` then push to `localhost:5000`. No registry exposed to internet. Simpler security.
- **(B) Expose registry behind nginx with basic auth + TLS** — More complex but standard. Needed if we ever add more CI runners or machines.

**Recommendation: Option A** (SSH tunnel). Keeps it simple, no extra auth/TLS config, and we're already SSHing for deploy anyway.

## Pipeline Design

### Change Detection

Use `paths` filters in the workflow triggers + a detection job:

| Changed path | Images to rebuild |
|---|---|
| `platform/services/auth/**`, `platform/pkg/**`, `platform/proto/**` | auth |
| `platform/services/gateway/**`, `platform/pkg/**`, `platform/proto/**` | gateway |
| `auth-ui/**` | demo-app (auth-ui is baked into the demo-app image) |
| `demo-app/**` | demo-app |
| `platform/infra/postgres/**` | postgres |
| `deploy/**` | none (infra change, manual deploy) |

### Workflow

**New file:** `.github/workflows/deploy.yml`

```
on:
  push:
    branches: [main]

jobs:
  detect:
    # outputs which services changed

  build-auth:
    needs: detect
    if: needs.detect.outputs.auth == 'true'
    # build auth image, push to registry via SSH tunnel

  build-gateway:
    needs: detect
    if: needs.detect.outputs.gateway == 'true'
    # build gateway image, push to registry via SSH tunnel

  build-demo-app:
    needs: detect
    if: needs.detect.outputs.demo-app == 'true'
    # build demo-app image, push to registry via SSH tunnel

  build-postgres:
    needs: detect
    if: needs.detect.outputs.postgres == 'true'
    # build postgres image, push to registry via SSH tunnel

  deploy:
    needs: [build-auth, build-gateway, build-demo-app, build-postgres]
    if: always() && contains(needs.*.result, 'success')
    # SSH into server, docker compose pull, docker compose up -d
```

### Build Steps (per service)

1. Checkout repo
2. Set up Docker Buildx (for layer caching)
3. Open SSH tunnel to registry (`ssh -fN -L 5000:localhost:5000`)
4. `docker build` with appropriate context and Dockerfile
5. `docker tag` as `localhost:5000/platform/<service>:latest` and `:sha-<short>`
6. `docker push`

### Deploy Step

1. SSH into server
2. `cd deploy && docker compose pull && docker compose up -d --remove-orphans`

## Production Compose Changes

The production `docker-compose.yml` files currently use `build:` directives. For the pipeline, they need to use `image:` instead (pull pre-built images from the registry).

**Approach:** Add `image:` alongside `build:` in each service. When you `docker compose pull`, it uses the image. When you `docker compose build`, it builds locally. Both work.

**Modified files:**
- `deploy/stacks/backend/docker-compose.yml` — add `image: localhost:5000/platform/auth:latest` and `image: localhost:5000/platform/gateway:latest`
- `deploy/stacks/frontend/docker-compose.yml` — add `image: localhost:5000/platform/demo-app:latest`
- `deploy/stacks/infra/docker-compose.yml` — add `image: localhost:5000/platform/postgres:latest`

## GitHub Secrets Needed

| Secret | Purpose |
|---|---|
| `DEPLOY_SSH_KEY` | Private key for SSHing into the server |
| `DEPLOY_HOST` | Server IP/hostname |
| `DEPLOY_USER` | SSH user on the server |

## New Files Summary

| File | Purpose |
|---|---|
| `.github/workflows/deploy.yml` | Main CI/CD pipeline |
| `deploy/stacks/infra/docker-compose.registry.yml` | Self-hosted Docker registry |

## Modified Files Summary

| File | Change |
|---|---|
| `deploy/stacks/backend/docker-compose.yml` | Add `image:` fields for registry pull |
| `deploy/stacks/frontend/docker-compose.yml` | Add `image:` field for demo-app |
| `deploy/stacks/infra/docker-compose.yml` | Add `image:` field for postgres |
| `deploy/README.md` | Add CI/CD section |

## Verification

1. Start the registry: `docker compose -f stacks/infra/docker-compose.registry.yml up -d`
2. Manually test build+push: `docker build -t localhost:5000/platform/auth:test ../platform -f ../platform/services/auth/Dockerfile && docker push localhost:5000/platform/auth:test`
3. Verify pull works: `docker pull localhost:5000/platform/auth:test`
4. Push a change to GitHub `main` branch
5. Watch the Actions tab — only changed services should build
6. After deploy job runs, verify the new image is running: `docker compose ps`
