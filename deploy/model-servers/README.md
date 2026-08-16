# Self-hosted model servers

The assistant runs **entirely on local GPUs** — no data leaves the box. Three model
servers sit behind the app, each an independent Docker Compose project that joins the
shared `platform-net` network so the app containers can reach them by name:

| Server | Model | Host port | In-cluster URL | Used for |
|---|---|---|---|---|
| `qwen-llm` | Qwen3.5-9B (vLLM, fp8) | `6888` | `http://qwen-vllm:6888/v1` | the agent's reasoning + tool-calling brain |
| `qwen-embedding` | Qwen3-Embedding-4B (vLLM, fp8) | `8090` | `http://qwen-emb-vllm:8090/v1` | RAG retrieval over org "living sources" (2560-dim → pgvector) |
| `flux` | FLUX.2-klein-4B (ComfyUI + FastAPI) | `8000` (api), `8188` (engine) | `http://flux-api:8000` or `host.docker.internal:8000` | text-to-image post visuals |

> **These are NOT started by `deploy.sh`.** They need an NVIDIA GPU + the
> [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html),
> and the weights are large, so they're a deliberate, separate step. The app degrades
> gracefully if a server is down (e.g. image generation just errors; chat still works).

## 1. Prerequisites

- Docker + Docker Compose, and the NVIDIA Container Toolkit (so `runtime: nvidia` works).
- The shared network must exist (the main stack creates it):
  ```bash
  cd deploy && ./scripts/deploy.sh up infra      # creates platform-net + Postgres/Redis/...
  # or just: docker network create platform-net
  ```
- The Hugging Face CLI for downloads: `pip install -U 'huggingface_hub[cli]'`.

## 2. Download the weights (once, ≈35 GB total)

```bash
cd deploy/model-servers
./scripts/download-all.sh           # or run the three individually:
./scripts/download-qwen-llm.sh      # Qwen/Qwen3.5-9B               -> qwen-llm/models/
./scripts/download-qwen-embedding.sh# Qwen/Qwen3-Embedding-4B       -> qwen-embedding/models/
./scripts/download-flux.sh          # FLUX.2-klein-4B (3 files)     -> flux/models/
```

Each script bind-mounts into the location its compose file expects by default; override
with `QWEN_LLM_MODEL_DIR`, `QWEN_EMB_MODEL_DIR`, `FLUX_MODELS_DIR` if your weights live
elsewhere. Weights are git-ignored — only the infra is committed.

## 3. Start the servers

```bash
docker compose -f qwen-llm/docker-compose.yml up -d
docker compose -f qwen-embedding/docker-compose.yml up -d
docker compose -f flux/docker-compose.yml up -d
```

Healthchecks:
```bash
curl -s http://localhost:6888/v1/models | jq .          # LLM ready
curl -s http://localhost:8090/v1/models | jq .          # embedder ready
curl -s http://localhost:8000/health | jq .             # FLUX/ComfyUI reachable
```

## GPU placement

Defaults assume a 2-GPU box: the LLM on GPU 0, the embedder + FLUX on GPU 1 (the smaller
card — and FLUX + embedder are tuned to run *one at a time* there). Re-pin with env vars:
`QWEN_LLM_GPU`, `QWEN_EMB_GPU`, `FLUX_GPU` (each a CUDA device index). On a single-GPU box,
set them all to `0` and watch total VRAM.

## Why fp8 / distilled

NPOs run on modest hardware. Everything here is sized to fit consumer GPUs: the LLM and
embedder are online-quantized to **fp8** (roughly halves VRAM), and FLUX is the **distilled
klein** variant that converges in ~4 steps. The trade-off is a small quality/latency hit
versus full-precision or the 9B image model — acceptable for a self-hosted, sovereign setup.

See each subdirectory for model-specific notes (e.g. `flux/` carries the full ComfyUI
wrapper, workflow graph, and gotchas).
