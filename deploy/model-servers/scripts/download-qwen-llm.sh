#!/usr/bin/env bash
# Download the assistant's "brain": Qwen3.5-9B (≈19 GB, bf16 weights).
# Lands in deploy/model-servers/qwen-llm/models/Qwen3.5-9B, which is exactly where
# qwen-llm/docker-compose.yml bind-mounts from by default.
#
#   ./download-qwen-llm.sh                 # default location
#   QWEN_LLM_MODEL_DIR=/data/qwen ./download-qwen-llm.sh   # custom location
#
# Source: https://huggingface.co/Qwen/Qwen3.5-9B  (Apache-2.0)
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

DEST="${QWEN_LLM_MODEL_DIR:-$SERVERS_DIR/qwen-llm/models/Qwen3.5-9B}"
hf_snapshot "Qwen/Qwen3.5-9B" "$DEST"

echo
echo "Done. ${DEST}"
echo "Start the server with:"
echo "  docker compose -f deploy/model-servers/qwen-llm/docker-compose.yml up -d"
