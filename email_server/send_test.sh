#!/bin/bash
# Read the key from the environment — never hardcode it (this repo is public).
#   EMAIL_API_KEY=... ./send_test.sh     (or `set -a; . .env; set +a` first)
: "${EMAIL_API_KEY:?set EMAIL_API_KEY (e.g. export EMAIL_API_KEY=... or source email_server/.env) before running}"
API_KEY="$EMAIL_API_KEY"
TO="${TO:-cgrigoriadis@outlook.com}"
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

send "login_alert" \
  "{\"to\":\"$TO\",\"template\":\"login_alert\",\"data\":{\"timestamp\":\"2026-03-04 10:30 UTC\",\"ip\":\"203.0.113.42\"}}"

send "verify_email" \
  "{\"to\":\"$TO\",\"template\":\"verify_email\",\"data\":{\"name\":\"Chris\",\"verify_url\":\"https://example.com/verify?token=test123\"}}"

send "forgot_password" \
  "{\"to\":\"$TO\",\"template\":\"forgot_password\",\"data\":{\"name\":\"Chris\",\"reset_url\":\"https://example.com/reset?token=test456\"}}"

send "password_changed" \
  "{\"to\":\"$TO\",\"template\":\"password_changed\",\"data\":{\"name\":\"Chris\"}}"
