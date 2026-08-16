.PHONY: all build proto generate-keys up down logs clean test lint help

# Default target
all: proto build

## ── Build ──

build: build-auth build-gateway ## Build all services

build-auth: ## Build auth service
	cd services/auth && go build -o ../../bin/auth-server ./cmd/server

build-gateway: ## Build gateway service
	cd services/gateway && go build -o ../../bin/gateway-server ./cmd/server

## ── Protobuf ──

proto: ## Generate protobuf code
	./scripts/generate-proto.sh

## ── Docker ──

up: ## Start all services
	docker compose up --build -d

down: ## Stop all services
	docker compose down

down-clean: ## Stop all services and remove volumes
	docker compose down -v

logs: ## Tail all service logs
	docker compose logs -f

logs-auth: ## Tail auth service logs
	docker compose logs -f auth

logs-gateway: ## Tail gateway service logs
	docker compose logs -f gateway

## ── Keys ──

generate-keys: ## Generate Ed25519 JWT keys and MFA encryption key
	./scripts/generate-keys.sh

setup-env: generate-keys ## Generate keys and create .env from .env.example
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env from .env.example"; \
		echo "Run 'make generate-keys' and paste the output into .env"; \
	else \
		echo ".env already exists"; \
	fi

## ── Development ──

test: ## Run all tests
	cd pkg && go test ./...
	cd services/auth && go test ./...
	cd services/gateway && go test ./...

lint: ## Run linter
	cd pkg && go vet ./...
	cd services/auth && go vet ./...
	cd services/gateway && go vet ./...

tidy: ## Tidy all Go modules
	cd proto && go mod tidy
	cd pkg && go mod tidy
	cd services/auth && go mod tidy
	cd services/gateway && go mod tidy

## ── Help ──

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
