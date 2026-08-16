#!/usr/bin/env bash
set -euo pipefail

# Generate Ed25519 key pair for JWT signing
# Outputs base64-encoded raw key bytes suitable for .env file

TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

# Generate Ed25519 private key in PEM format
openssl genpkey -algorithm Ed25519 -out "$TMPDIR/private.pem" 2>/dev/null

# Extract public key in PEM format
openssl pkey -in "$TMPDIR/private.pem" -pubout -out "$TMPDIR/public.pem" 2>/dev/null

# Extract raw private key bytes (64 bytes) from DER encoding
# Ed25519 private key DER: 30 2e 02 01 00 30 05 06 03 2b 65 70 04 22 04 20 [32-byte seed]
# The raw Ed25519 private key is seed(32) + public(32) = 64 bytes
openssl pkey -in "$TMPDIR/private.pem" -outform DER -out "$TMPDIR/private.der" 2>/dev/null
openssl pkey -in "$TMPDIR/private.pem" -pubout -outform DER -out "$TMPDIR/public.der" 2>/dev/null

# Extract the 32-byte seed from private key DER (last 32 bytes of the 48-byte DER)
SEED=$(tail -c 32 "$TMPDIR/private.der" | xxd -p | tr -d '\n')

# Extract the 32-byte public key from public key DER (last 32 bytes of the 44-byte DER)
PUB=$(tail -c 32 "$TMPDIR/public.der" | xxd -p | tr -d '\n')

# Combine seed + public = 64-byte private key (Ed25519 convention)
PRIV_HEX="${SEED}${PUB}"

# Convert to raw bytes and base64 encode
PRIVATE_KEY=$(echo "$PRIV_HEX" | xxd -r -p | base64 -w 0)
PUBLIC_KEY=$(echo "$PUB" | xxd -r -p | base64 -w 0)

echo "# Add these to your .env file:"
echo "JWT_PRIVATE_KEY=$PRIVATE_KEY"
echo "JWT_PUBLIC_KEY=$PUBLIC_KEY"
echo ""

# Generate MFA encryption key (32 bytes for AES-256)
MFA_KEY=$(openssl rand -base64 32)
echo "MFA_ENCRYPTION_KEY=$MFA_KEY"
