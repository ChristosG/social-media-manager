#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROTO_DIR="$SCRIPT_DIR/../proto"

echo "Generating protobuf code..."

cd "$PROTO_DIR"

# Clean old generated code
rm -rf gen/

# Generate using buf
if command -v buf &> /dev/null; then
    buf generate
    echo "Protobuf generation complete (buf)."
else
    echo "buf not found. Installing..."
    go install github.com/bufbuild/buf/cmd/buf@latest
    buf generate
    echo "Protobuf generation complete (buf)."
fi

echo "Generated files:"
find gen/ -name "*.go" -type f
