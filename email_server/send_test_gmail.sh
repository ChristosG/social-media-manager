#!/bin/bash
# Read the key from the environment — never hardcode it (this repo is public).
#   EMAIL_API_KEY=... ./send_test_gmail.sh     (or `set -a; . .env; set +a` first)
: "${EMAIL_API_KEY:?set EMAIL_API_KEY (e.g. export EMAIL_API_KEY=... or source email_server/.env) before running}"
API_KEY="$EMAIL_API_KEY"
TO="${TO:-you@example.com}"
URL="http://localhost:8025/send"

send() {
  local label="$1"
  local payload="$2"
  echo "--- $label ---"
  curl -s -X POST "$URL" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d "$payload" | python3 -m json.tool
  echo
}

send "welcome" \
  "{\"to\":\"$TO\",\"template\":\"welcome\",\"data\":{\"name\":\"Chris\"}}"