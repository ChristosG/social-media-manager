# FLUX.2-klein-4B image servlet

Headless **ComfyUI** (distilled FLUX.2-klein-4B-fp8) behind a thin **FastAPI** wrapper.
Distilled → ~4 steps, ~14 s @ 1024². The agent-service calls `flux-api` to render post visuals.

- `flux-api` → http://localhost:8000 (the REST API the app calls)
- `comfyui`  → http://localhost:8188 (engine + web UI for manual tweaking)

## Run

```bash
../scripts/download-flux.sh          # one-time: fetch the 3 model files into ./models
docker compose up -d                 # start both services
docker compose logs -f comfyui       # watch boot
docker compose ps
```

## `POST /generate`

| Field | Type | Default | Notes |
|---|---|---|---|
| `prompt` | string | — (required) | Dense, narrative prompts work well (Qwen3 text encoder). |
| `seed` | int | random | Set for reproducibility. |
| `width` / `height` | int | 1024 | Multiple of 16; patched on both the latent and `Flux2Scheduler`. |
| `steps` | int | 4 | Distilled is tuned for ~4; 4–8 useful range. |
| `cfg` | float | 1.0 | Distilled tuned for 1.0. |
| `sampler_name` | string | euler | Any from `GET /samplers`. |
| `return_base64` | bool | false | false → PNG bytes; true → JSON `{filename, image_base64}`. |

```bash
curl --fail-with-body -X POST http://localhost:8000/generate \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"a red fox in a snowy forest, cinematic"}' --output out.png
```

## Models (downloaded into `./models`, git-ignored)

```
models/diffusion_models/flux-2-klein-4b-fp8.safetensors   (~3.8 GB)  black-forest-labs/FLUX.2-klein-4b-fp8
models/text_encoders/qwen_3_4b.safetensors                (~7.5 GB)  Comfy-Org/vae-text-encorder-for-flux-klein-4b
models/vae/flux2-vae.safetensors                          (~0.3 GB)  Comfy-Org/vae-text-encorder-for-flux-klein-4b
```

## How the wrapper works

`api/flux_api.py` loads the API-format graph (`workflows/flux2_klein_t2i_api.json`) once,
deep-copies it per request, patches fields by finding nodes via `class_type` (so it
survives workflow re-exports), submits to ComfyUI `/prompt`, polls `/history/{id}`, and
returns the PNG from `/view`. Change defaults by editing the workflow JSON (bind-mounted,
no rebuild); changing `flux_api.py` needs `docker compose build flux-api && up -d flux-api`.

### Gotchas
- **Size lives in two nodes** (`EmptySD3LatentImage` *and* `Flux2Scheduler`) — the wrapper
  syncs both automatically.
- **The text encoder is model-specific** — this exact `qwen_3_4b.safetensors`; the LLM /
  embedding Qwen checkpoints can't substitute.
- **VRAM** ~9 GB of 12 GB at 1024². If OOM at larger sizes, append `--normalvram` then
  `--lowvram` to the `comfyui` service `command:` in `docker-compose.yml`.
- **CUDA** image uses cu124 wheels (forward-compatible with newer host drivers); `torchaudio`
  is pinned to the cu124 build to match torch.
