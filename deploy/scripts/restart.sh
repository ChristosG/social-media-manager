#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY="$SCRIPT_DIR/deploy.sh"
STACK="${1:-all}"

echo "==> Stopping ${STACK}..."
"$DEPLOY" down "$STACK"

echo "==> Building ${STACK}..."
"$DEPLOY" build "$STACK"

echo "==> Starting ${STACK}..."
"$DEPLOY" up "$STACK"

echo "==> Done. ${STACK} restarted."
