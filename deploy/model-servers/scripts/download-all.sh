#!/usr/bin/env bash
# Download all three self-hosted models (≈35 GB total). Run once on a fresh machine.
set -euo pipefail
HERE="$(dirname "${BASH_SOURCE[0]}")"
bash "$HERE/download-qwen-llm.sh"
bash "$HERE/download-qwen-embedding.sh"
bash "$HERE/download-flux.sh"
echo
echo "All models downloaded. Bring the servers up with:"
echo "  docker compose -f deploy/model-servers/qwen-llm/docker-compose.yml up -d"
echo "  docker compose -f deploy/model-servers/qwen-embedding/docker-compose.yml up -d"
echo "  docker compose -f deploy/model-servers/flux/docker-compose.yml up -d"
