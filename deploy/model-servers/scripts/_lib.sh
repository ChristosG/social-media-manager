#!/usr/bin/env bash
# Shared helpers for the model-download scripts.
set -euo pipefail

# Resolve the Hugging Face CLI: prefer the new `hf`, fall back to `huggingface-cli`.
hf_cli() {
  if command -v hf >/dev/null 2>&1; then
    hf "$@"
  elif command -v huggingface-cli >/dev/null 2>&1; then
    huggingface-cli "$@"
  else
    echo "ERROR: neither 'hf' nor 'huggingface-cli' found." >&2
    echo "Install it with:  pip install -U 'huggingface_hub[cli]'" >&2
    exit 1
  fi
}

# Download a whole repo snapshot into a local dir.
#   hf_snapshot <repo_id> <local_dir> [extra args...]
hf_snapshot() {
  local repo="$1" dest="$2"; shift 2
  echo ">>> Downloading repo '$repo' -> $dest"
  mkdir -p "$dest"
  hf_cli download "$repo" --local-dir "$dest" "$@"
}

# Download a single file from a repo into a local dir, preserving nothing of the
# repo path (the file lands directly in <dest>).
#   hf_file <repo_id> <path/in/repo.safetensors> <dest_dir>
hf_file() {
  local repo="$1" path="$2" dest="$3"
  echo ">>> Downloading '$repo : $path' -> $dest/"
  mkdir -p "$dest"
  # --local-dir places the file under <dest>/<path>; we then flatten it.
  local tmp; tmp="$(mktemp -d)"
  hf_cli download "$repo" "$path" --local-dir "$tmp"
  mv -f "$tmp/$path" "$dest/$(basename "$path")"
  rm -rf "$tmp"
}

SERVERS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
