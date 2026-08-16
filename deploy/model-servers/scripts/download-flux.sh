#!/usr/bin/env bash
# Download the 3 model files for FLUX.2-klein-4B (text-to-image), into the ComfyUI
# models layout that flux/docker-compose.yml bind-mounts (deploy/model-servers/flux/models):
#
#   models/diffusion_models/flux-2-klein-4b-fp8.safetensors   (~3.8 GB, fp8)
#   models/text_encoders/qwen_3_4b.safetensors                (~7.5 GB, bf16 — FLUX-specific encoder)
#   models/vae/flux2-vae.safetensors                          (~0.3 GB)
#
#   ./download-flux.sh
#   FLUX_MODELS_DIR=/data/flux-models ./download-flux.sh
#
# Sources (per the ComfyUI FLUX.2-klein tutorial, https://docs.comfy.org/tutorials/flux/flux-2-klein):
#   diffusion : https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8   (Apache-2.0)
#   enc + vae : https://huggingface.co/Comfy-Org/vae-text-encorder-for-flux-klein-4b
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

MODELS="${FLUX_MODELS_DIR:-$SERVERS_DIR/flux/models}"

hf_file "black-forest-labs/FLUX.2-klein-4b-fp8" \
        "flux-2-klein-4b-fp8.safetensors" "$MODELS/diffusion_models"

hf_file "Comfy-Org/vae-text-encorder-for-flux-klein-4b" \
        "split_files/text_encoders/qwen_3_4b.safetensors" "$MODELS/text_encoders"

hf_file "Comfy-Org/vae-text-encorder-for-flux-klein-4b" \
        "split_files/vae/flux2-vae.safetensors" "$MODELS/vae"

echo
echo "Done. ${MODELS}"
echo "Start the server with:"
echo "  docker compose -f deploy/model-servers/flux/docker-compose.yml up -d"
