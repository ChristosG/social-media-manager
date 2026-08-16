#!/usr/bin/env bash
set -euo pipefail

# Usage: wait-for-it.sh host:port [-t timeout] [-- command]

HOST=""
PORT=""
TIMEOUT=30
CMD=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        -t)
            TIMEOUT="$2"
            shift 2
            ;;
        --)
            shift
            CMD="$*"
            break
            ;;
        *)
            if [[ -z "$HOST" ]]; then
                HOST="${1%%:*}"
                PORT="${1##*:}"
            fi
            shift
            ;;
    esac
done

if [[ -z "$HOST" || -z "$PORT" ]]; then
    echo "Usage: wait-for-it.sh host:port [-t timeout] [-- command]"
    exit 1
fi

echo "Waiting for $HOST:$PORT (timeout: ${TIMEOUT}s)..."

start=$(date +%s)
while ! (echo > /dev/tcp/"$HOST"/"$PORT") 2>/dev/null; do
    now=$(date +%s)
    elapsed=$((now - start))
    if [[ $elapsed -ge $TIMEOUT ]]; then
        echo "Timeout waiting for $HOST:$PORT after ${TIMEOUT}s"
        exit 1
    fi
    sleep 1
done

echo "$HOST:$PORT is available"

if [[ -n "$CMD" ]]; then
    exec $CMD
fi
