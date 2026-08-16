#!/usr/bin/env bash
# Download the retrieval embedder: Qwen3-Embedding-4B (≈8 GB, bf16; served fp8).
# Lands in deploy/model-servers/qwen-embedding/models/Qwen3-Embedding-4B, where
# qwen-embedding/docker-compose.yml bind-mounts from by default.
#
#   ./download-qwen-embedding.sh
#   QWEN_EMB_MODEL_DIR=/data/emb ./download-qwen-embedding.sh
#
# Source: https://huggingface.co/Qwen/Qwen3-Embedding-4B  (Apache-2.0)
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

DEST="${QWEN_EMB_MODEL_DIR:-$SERVERS_DIR/qwen-embedding/models/Qwen3-Embedding-4B}"
hf_snapshot "Qwen/Qwen3-Embedding-4B" "$DEST"

echo
echo "Done. ${DEST}"
echo "Start the server with:"
echo "  docker compose -f deploy/model-servers/qwen-embedding/docker-compose.yml up -d"
