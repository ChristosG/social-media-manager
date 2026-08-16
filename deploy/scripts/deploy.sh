#!/bin/bash
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${DEPLOY_DIR}"

# Load .env if present
set -a
source .env 2>/dev/null || true
set +a

usage() {
  cat <<EOF
Usage: deploy.sh <command> [stack] [args]

Stacks: infra, backend, frontend, all (default: all)

Commands:
  up [stack]            Start services            deploy.sh up frontend
  down [stack]          Stop services              deploy.sh down infra
  build [stack]         Build images               deploy.sh build backend
  restart [svc]         Restart a service          deploy.sh restart webapp
  logs [svc]            Tail logs                  deploy.sh logs nginx
  status [stack]        Show all services          deploy.sh status
  update [svc]          Rebuild + restart           deploy.sh update webapp
  ssl                   Initialize SSL cert        deploy.sh ssl

  dev up [stack]        Start dev mode (hot reload) deploy.sh dev up frontend
  dev down [stack]      Stop dev mode               deploy.sh dev down
  dev logs [svc]        Tail dev logs               deploy.sh dev logs auth
  dev status [stack]    Show dev services           deploy.sh dev status
  dev restart [svc]     Restart dev service         deploy.sh dev restart auth
EOF
}

# Parse services.yml to get compose file for a stack
get_compose_files() {
  local stack="${1:-all}"
  local mode="${2:-prod}"
  local suffix_key="compose"
  [[ "$mode" == "dev" ]] && suffix_key="dev_compose"

  case "$stack" in
    infra|backend|frontend)
      # For a specific stack, find its compose file
      local file=""
      if [[ "$mode" == "dev" && "$stack" != "infra" ]]; then
        file=$(grep -A5 "^  ${stack}:" services.yml 2>/dev/null | grep "dev_compose:" | awk '{print $2}' | head -1)
      fi
      if [[ -z "$file" ]]; then
        file=$(grep -A5 "^  ${stack}:" services.yml 2>/dev/null | grep "compose:" | head -1 | awk '{print $2}')
      fi
      if [[ -z "$file" ]]; then
        echo "Unknown stack: $stack" >&2
        exit 1
      fi
      echo "$file"
      ;;
    all)
      # For "all", combine all compose files
      local files=""
      local current_stack=""
      while IFS= read -r line; do
        # Match stack name lines like "  infra:"
        if [[ "$line" =~ ^[[:space:]]{2}([a-z]+): ]]; then
          current_stack="${BASH_REMATCH[1]}"
        fi
        # Match compose file lines
        if [[ "$mode" == "dev" && "$line" =~ dev_compose:[[:space:]]*(.+) ]]; then
          files="$files -f ${BASH_REMATCH[1]}"
        elif [[ "$line" =~ ^[[:space:]]*compose:[[:space:]]*(.+) ]]; then
          files="$files -f ${BASH_REMATCH[1]}"
        fi
      done < services.yml

      # In dev mode, include infra (which has no dev_compose) plus dev files
      if [[ "$mode" == "dev" ]]; then
        files=""
        # Always include infra base
        files="$files -f stacks/infra/docker-compose.yml"
        # For backend and frontend, use dev_compose if available, else compose
        local stacks=("backend" "frontend")
        for s in "${stacks[@]}"; do
          local dev_file=$(grep -A5 "^  ${s}:" services.yml 2>/dev/null | grep "dev_compose:" | awk '{print $2}' | head -1)
          if [[ -n "$dev_file" ]]; then
            files="$files -f $dev_file"
          else
            local base_file=$(grep -A5 "^  ${s}:" services.yml 2>/dev/null | grep "compose:" | head -1 | awk '{print $2}')
            [[ -n "$base_file" ]] && files="$files -f $base_file"
          fi
        done
      fi
      echo "$files"
      ;;
    *) echo "Unknown stack: $stack" >&2; exit 1 ;;
  esac
}

run_compose() {
  local mode="$1"; shift
  local stack="${1:-all}"; shift

  if [[ "$stack" == "all" ]]; then
    # Run each stack separately to keep relative volume paths correct
    # (merging -f files makes Docker resolve paths from the first file's dir)
    local ordered_stacks=("infra" "backend" "frontend")
    # Reverse order for 'down'
    if [[ "${1:-}" == "down" ]]; then
      ordered_stacks=("frontend" "backend" "infra")
    fi
    for s in "${ordered_stacks[@]}"; do
      local file=$(get_compose_files "$s" "$mode")
      [[ -n "$file" ]] && docker compose -f "$file" "$@"
      # After infra is up, gate on Postgres readiness before the DB-dependent backend stack starts.
      if [[ "$s" == "infra" && "${1:-}" == "up" ]]; then
        wait_for_postgres
      fi
    done
  else
    local files=$(get_compose_files "$stack" "$mode")
    docker compose -f "$files" "$@"
  fi
}


connect_triton() {
  # If Triton container exists, ensure it's on platform-net with alias "triton"
  if docker ps -q -f name=trt2501_krikri | grep -q .; then
    if ! docker network inspect platform-net --format '{{range .Containers}}{{.Name}} {{end}}' 2>/dev/null | grep -q trt2501_krikri; then
      echo "Connecting Triton to platform-net..."
      docker network connect --alias triton platform-net trt2501_krikri 2>/dev/null || true
    fi
  fi
}

connect_vllm() {
  # If vLLM container exists, ensure it's on platform-net with alias "vllm-srv"
  if docker ps -q -f name=vllm-srv | grep -q .; then
    if ! docker network inspect platform-net --format '{{range .Containers}}{{.Name}} {{end}}' 2>/dev/null | grep -q vllm-srv; then
      echo "Connecting vLLM to platform-net..."
      docker network connect --alias vllm-srv platform-net vllm-srv 2>/dev/null || true
    fi
  fi
}

connect_qwen() {
  # If Qwen vLLM container exists, ensure it's on platform-net with alias "qwen-vllm"
  if docker ps -q -f name=qwen35-vllm | grep -q .; then
    if ! docker network inspect platform-net --format '{{range .Containers}}{{.Name}} {{end}}' 2>/dev/null | grep -q qwen35-vllm; then
      echo "Connecting Qwen vLLM to platform-net..."
      docker network connect --alias qwen-vllm platform-net qwen35-vllm 2>/dev/null || true
    fi
  fi
}

wait_for_postgres() {
  # Block until Postgres is accepting connections before starting DB-dependent backend services, so a
  # cold start is deterministic instead of crash-looping. Prefers the compose health status; falls back
  # to pg_isready. ~3 min ceiling (a first-boot initdb can take a while), then continues (services retry).
  echo "⏳ Waiting for Postgres to be ready…"
  local tries=90
  while (( tries-- > 0 )); do
    local status
    status=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' postgres 2>/dev/null || echo missing)
    if [[ "$status" == "healthy" ]]; then echo "✅ Postgres healthy."; return 0; fi
    if [[ "$status" == "none" ]] && docker exec postgres pg_isready -U "${POSTGRES_USER:-platform}" >/dev/null 2>&1; then
      echo "✅ Postgres ready."; return 0
    fi
    sleep 2
  done
  echo "⚠️  Postgres not ready after timeout — continuing (services have restart policies and retry)." >&2
}

# Apply the SECURITY DEFINER cross-tenant scheduler readers as the platform superuser (idempotent
# CREATE OR REPLACE). They MUST be platform-owned to bypass FORCE RLS, so they can't live in the
# npo_owner migrations; this is their version-controlled application. The agent-service boot self-check
# (/readyz) asserts their presence regardless.
apply_db_functions() {
  echo "Applying SECURITY DEFINER scheduler functions (as ${POSTGRES_USER:-platform})…"
  local f
  for f in ../agent-service/scripts/setup_publish_fn.sql ../agent-service/scripts/setup_scheduler_fn.sql ../agent-service/scripts/setup_jobs_fn.sql; do
    if [[ -f "$f" ]]; then
      docker exec -i postgres psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-platform}" -d npo < "$f" \
        && echo "  ✓ $(basename "$f")" || echo "  ✗ $(basename "$f") FAILED" >&2
    fi
  done
}

case "${1:-help}" in
  up)
    run_compose prod "${2:-all}" up -d "${@:3}"
    connect_triton
    connect_vllm
    connect_qwen
    ;;
  db-functions)
    apply_db_functions
    ;;
  down)
    run_compose prod "${2:-all}" down "${@:3}"
    ;;
  build)
    run_compose prod "${2:-all}" build "${@:3}"
    ;;
  restart)
    run_compose prod all restart "${@:2}"
    ;;
  logs)
    run_compose prod all logs -f --tail 100 "${@:2}"
    ;;
  status)
    run_compose prod "${2:-all}" ps
    ;;
  update)
    SVC="${2:?Specify a service to update}"
    run_compose prod "${3:-all}" build "${SVC}"
    run_compose prod "${3:-all}" up -d --no-deps "${SVC}"
    # Agent-service migrations create the tables the SECURITY DEFINER readers reference; (re)apply them
    # idempotently after, so a fresh deploy is never silently missing them.
    if [[ "$SVC" == "agent-service" ]]; then apply_db_functions; fi
    ;;
  dev)
    case "${2:-up}" in
      up)
        run_compose dev "${3:-all}" up -d "${@:4}"
        ;;
      down)
        run_compose dev "${3:-all}" down "${@:4}"
        ;;
      logs)
        run_compose dev all logs -f --tail 100 "${@:3}"
        ;;
      status)
        run_compose dev "${3:-all}" ps
        ;;
      restart)
        run_compose dev all restart "${@:3}"
        ;;
      *)
        usage
        ;;
    esac
    ;;
  ssl)
    ./scripts/init-ssl.sh
    ;;
  *)
    usage
    ;;
esac
