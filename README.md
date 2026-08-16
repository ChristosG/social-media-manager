# Social Studio — a self-hosted social-media assistant for nonprofits

An AI colleague for a nonprofit's marketing team. Through chat it **suggests and drafts on-brand
social posts**, **answers questions about the organization**, **learns and remembers corrections
across sessions**, and is **editable by a non-engineer** — no redeploy. It can also ingest the
org's website and past posts for grounding, generate images, plan multi-week campaigns, and publish
to Facebook/Instagram with a human approval gate.

Every model runs **on local GPUs** — the LLM, the embedder, and the image model. There's no per-token
bill and it runs on hardware you already have; as a bonus, no prompt, donor story, or draft has to leave
the box.

For the architecture rationale, trade-offs, and how a non-engineer extends it, see
**[`docs/DESIGN.md`](docs/DESIGN.md)**.

---

## Architecture

```
Browser ── HTTPS (Cloudflare) ─► nginx ─► Go Gateway :8080
                                            │  verifies Ed25519 JWT, CORS, rate-limit,
                                            │  STRIPS client identity headers, injects
                                            │  X-User-Id / X-Tenant-Id / X-Roles from claims
        ┌───────────────────────────────────┼───────────────────────────────┐
        ▼                                    ▼                               ▼
   Go Auth :50051                  Python agent-service :8085          Email service
   (tenants, OAuth,                (FastAPI + LangGraph)               (transactional mail)
    Ed25519 JWTs)                  │  graph: load_context → agent → tools
                                   │  tools: suggest/draft posts · brand voice · ledger ·
                                   │         answer_about_org · RAG search · image gen · publish
                                   │  per-org memory + capabilities injected each turn
                                   ▼
        Postgres + pgvector  ◄──────────────────────────────  self-hosted GPU models
        (per-tenant RLS, FORCE)        qwen-vllm :6888   Qwen3.5-9B   (reasoning + tools)
        Redis (cache / rate-limit)     qwen-emb :8090    Qwen3-Embedding-4B (RAG → pgvector)
        durable jobs / worker tier     flux-api :8000    FLUX.2-klein (text→image)
```

| Component | Tech | Role |
|---|---|---|
| `platform/services/gateway` | Go (chi) | Single entry point. Verifies the JWT, enforces CORS + per-IP rate limits, **strips client-supplied identity headers** and re-injects trusted ones from the token, proxies to the agent-service. |
| `platform/services/auth` | Go | Tenants, sessions, MFA, OAuth (Google/Facebook with CSRF-protected state), mints Ed25519 JWTs whose `tid` is the NPO org id. |
| `agent-service` | Python · FastAPI · LangGraph | The assistant: the graph, tools, memory, capabilities, RAG, image generation, social publishing, a durable jobs/worker tier, and observability. |
| `chatbot_webapp` | Next.js (bun) · Tailwind | The "Social Studio" UI: chat, dashboard, workspace (calendar, campaigns, insights), `/studio`, settings. |
| `email_server` | Python · FastAPI | Transactional email. |
| Postgres + pgvector | — | The single source of truth. Per-tenant isolation via `FORCE ROW LEVEL SECURITY`. |
| Redis | — | Optional cache / sliding-window rate-limit; services fall back to DB-only when unset. |
| `deploy/model-servers` | Docker + vLLM/ComfyUI | The three self-hosted GPU models. |

**Why polyglot:** this began as a small microservices platform (Go auth + gateway, a Next.js shell,
Postgres). The assistant is a **new Python `agent-service`** that became the brain and reused the
existing auth, gateway, and multi-tenancy rather than rebuilding them. There is no message broker —
Postgres is the source of truth and a durable jobs table drives background work.

---

## Run it

**Prerequisites:** Docker + Docker Compose. (The three GPU models are optional and run separately —
they need a CUDA GPU and ~35 GB of weights; the app degrades gracefully without them.)

```bash
cd deploy
cp .env.example .env          # set DB passwords, JWT keys, IMAGE_URL_SECRET, AGENT_PROXY_SECRET, etc.
./scripts/deploy.sh up        # infra → (waits for Postgres) → backend → frontend, in order
./scripts/deploy.sh status    # show all services
./scripts/deploy.sh down      # stop everything (reverse order)
```

Migrations run automatically on startup (with retry while the DB comes up). Open
**http://localhost:8880**, register an org, and start chatting. You can target one stack at a time:
`./scripts/deploy.sh up infra|backend|frontend`.

**Bring up the models (separately, on a GPU box):**
```bash
cd deploy/model-servers
docker compose -f qwen-llm/docker-compose.yml up -d        # Qwen3.5-9B (chat + tools)
docker compose -f qwen-embedding/docker-compose.yml up -d  # Qwen3-Embedding-4B (RAG)
docker compose -f flux/docker-compose.yml up -d            # FLUX.2-klein (images)
```

**Tests:**
```bash
cd agent-service && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest -q                         # backend: unit + empirical RLS isolation + agent + workers
cd ../platform && make test                 # Go: gateway + auth (incl. OAuth CSRF)
cd ../chatbot_webapp && bun install && bunx tsc --noEmit   # webapp type-check
```
A reproducible dependency pin lives at `agent-service/requirements.lock`.

---

## Features

- **Conversational drafting** — a real LangGraph tool-calling loop (not a form); suggests and drafts
  per-platform posts in the org's brand voice, handles corrections and shifting intent.
- **Learning that persists** — a correction like *"too corporate — we're warm and grassroots"* is
  written to the DB and shapes every later turn, this session and next.
- **Non-engineer editable** — `/studio` edits brand voice, banned topics, content pillars, mission,
  the post ledger, **and adds new skills** — all as data rows, effective on the next message.
- **Grounded answers with citations** — answers and suggestions carry click-through source chips
  (the org's own posts vs. cited web/news).
- **Living sources (RAG)** — ingest the org's website + socials into pgvector for grounding.
- **Human-in-the-loop publishing** — "post this to Instagram" pauses the graph and shows an editable
  preview to approve before anything goes live.
- **Calendar & agentic campaigns** — "plan a 2-week donation push" proposes a dated multi-post arc you
  approve and edit (inline, via a campaign-bound chat, by adding your own custom drafts, or deleting ones you
  don't like). A new plan also draws on your past campaigns — matched by topic and weighted by their real
  engagement — to avoid repeats and cite the related ones; best-time-to-post learns from your own engagement
  once there's history.
- **Insights** — reach/engagement/link-click trends, top posts, content mix and a drill-down, over both the
  posts you publish here and your connected accounts' **existing** posts, which are imported with their real
  engagement so the numbers reflect the whole account.
- **Observability & evaluation (nice-to-haves)** — self-hosted Langfuse tracing surfaced in-app, and an
  automated 7-step scenario eval with deterministic checks + an LLM-as-judge.

---

## Repository layout

```
agent-service/    Python FastAPI + LangGraph — the assistant (tools, memory, RAG, publish, workers)
platform/         Go gateway + auth services, shared JWT/proto
chatbot_webapp/   Next.js "Social Studio" UI
email_server/     Transactional email service
deploy/           docker-compose stacks (infra / backend / frontend / observability), scripts, model servers
docs/             DESIGN.md (architecture & rationale), setup notes, product screenshots
```
