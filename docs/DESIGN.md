# Design — Social Studio

A short tour of *why* the system is built the way it is, the trade-offs I weighed, how a non-engineer
extends it, and what I'd do next. (For what it does and how to run it, see the [README](../README.md).)

## Architecture, and why

**Everything runs on local GPUs — the LLM, the embedder, and the image model — with Postgres as the
single source of truth.** The honest reasons are cost and convenience: no per-token bill, on hardware I
already have. Keeping a nonprofit's words — donor stories, draft messaging, brand voice — on its own box
is a genuine bonus, not the dogma; the design stays open to a frontier backend when an org wants the
quality (see *what's next*). The rest follows from running locally.

- **A real agent, not a form or a RAG endpoint.** The assistant is a LangGraph `load_context → agent →
  tools` loop with genuine tool-calling. A marketer corrects "too corporate," then says "now adapt it
  for Instagram," then "actually, is that on-brand?" — multi-turn intent that a form or a single
  retrieval call can't follow. Conversation state is owned by LangGraph; the org's identity is loaded
  into the system prompt each turn.

- **Skills and memory are *data*, not code.** Brand voice, banned topics, content pillars, and new
  "skills" live in Postgres rows (`memory_entries`, a capability registry) and are injected into the
  system prompt per turn. This is what makes the assistant **editable by a non-engineer with no
  redeploy** — and it keeps the prompt grounded in *this* org rather than generic copy.

- **Postgres is the spine; there is no message broker.** Per-tenant isolation is enforced with
  `FORCE ROW LEVEL SECURITY` and a runtime DB role that can't bypass it — every query is scoped by
  `SET LOCAL app.org` to the JWT's tenant id. Background work (publishing, campaign fill, metric polls)
  runs on a **durable jobs table** with atomic claim + lease + heartbeat + reaper + retry→dead-letter,
  which gives exactly-once publishing without Kafka/RabbitMQ.

- **Defense in depth at the edge.** The Go gateway verifies the Ed25519 JWT, **strips any
  client-supplied identity headers**, and re-injects trusted ones from the token; the agent-service
  re-validates the token and enforces a network ACL; OAuth login is CSRF-protected with a state cookie.
  RLS is the backstop if any handler forgets a check.

- **Self-hosting made honest.** The app degrades gracefully when a model server is down (it doesn't
  pretend), publishing is idempotent, signed image URLs fail closed without their secret, and a boot
  config check refuses to start in production with placeholder secrets.

## Trade-offs I considered

- **Local 9B model vs. a frontier API.** A self-hosted Qwen3.5-9B won't match GPT-class raw quality.
  I accepted that for zero per-token cost and running on my own hardware (privacy is the bonus), then
  narrowed the gap where it matters: a heuristic auto-enables "thinking" on hard turns (corrections,
  comparisons) with no manual toggle, and the hard work (grounding, brand voice, dedup, scheduling) is
  done by deterministic tools, not left to the model. An opt-in frontier backend (see *what's next*) is
  the escape hatch when an org would rather trade some privacy for top-end quality.
- **Postgres-as-everything vs. a broker + cache-everywhere.** A broker would scale further on paper. At
  this scale, a durable jobs table with claim/lease/reaper buys exactly-once semantics with far less
  operational surface, and keeps the source of truth in one place. Redis is optional (rate-limit/cache);
  the system runs DB-only without it.
- **Reuse the existing polyglot platform vs. greenfield.** Building a new Python brain *around* the
  existing Go auth/gateway/multi-tenancy shipped a working, secure multi-tenant product faster than
  rebuilding identity from scratch — at the cost of a polyglot repo.
- **Eval bias.** The 7-step scenario eval uses an LLM-as-judge, which can flatter the same model family;
  I pair it with deterministic checks (voice persistence, dedup, ledger truth) so the score isn't purely
  self-graded.
- **Prompt-injection surface.** The assistant ingests untrusted external text (scraped pages, comments).
  Those are fenced as data in prompts, durable-memory writes triggered in a turn that saw untrusted
  content are quarantined for human review, and auto-replies pass a deterministic banned-topic gate plus
  a conservative classifier — accepting some false-positives over a wrong public reply.

## How a non-engineer extends it

Everything below happens in the **`/studio`** UI and takes effect on the *next message* — no deploy.

- **Edit the assistant's memory.** In *Studio → Knowledge*, edit brand voice ("warm, grassroots, never
  corporate"), add banned topics, define content pillars, set the mission, or correct a fact. Each is a
  row in `memory_entries`; `load_context` reads them and writes them into the system prompt every turn.
  You can also just *tell it in chat* ("remember we never say 'clients', we say 'neighbours'") and the
  agent writes the memory itself (quarantined for review if the turn also touched untrusted web text).
- **Add a new skill.** In *Studio → Capabilities*, add a capability as a row: a name, a trigger, and the
  instruction/prompt it should follow. The agent picks it up as a registered capability — **a new skill
  is data, not a code change.** That's the design constraint that keeps the system safe to edit (no
  arbitrary code, RLS-scoped to the org) while still being genuinely extensible by the marketing team.

## What I'd do with more time

- **Close the analytics loop fully:** Insights now reflect the *real* account — the connected pages' existing
  posts and engagement are imported, not just what the app published — on top of per-post metrics, best-time,
  content-mix and exemplars fed back into drafting, and campaign planning that grounds a new plan in your past
  campaigns weighted by their real engagement. Next is engagement-aware caption A/B and a campaign
  retrospective auto-written from the numbers.
- **More generative media:** a text-to-video model to craft Reels and short video from a campaign, and a
  music model (Suno-style) to score them — so a post can ship as a finished reel, not just a caption and a
  still image.
- **Pluggable model backends:** an opt-in to route chat or image generation to an external/frontier API per
  org. Local GPUs stay the default (cheap, on my own hardware); anyone who'd rather trade a little privacy
  for top-end quality can flip it on.
- **Breadth & polish:** fix the mobile layout, harden the newer campaign and insights flows with more
  real-world testing, and go deeper on the platform APIs — fuller Meta coverage and adding LinkedIn.
- **Trust & safety as product:** a global "pause all automation" switch, a last-mile moderation re-check
  at publish time, and an always-on audit log of every automated action.
- **Hardening:** CSP script nonces (today's policy is permissive for Next.js), pgBackRest PITR (today is
  nightly logical dumps), and per-tenant LLM-token quotas.
- **Scale & reliability:** HA replicas behind a build-before-swap deploy; a webapp test suite + CI (the
  backend has ~560 tests; the UI is type-checked only today). Chat streaming already resumes after a reload
  or restart via a Redis-backed turn buffer.
