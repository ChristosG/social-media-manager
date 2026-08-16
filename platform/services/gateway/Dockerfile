FROM golang:1.23-alpine AS builder

RUN apk add --no-cache git

ENV GOWORK=off

WORKDIR /build

# Copy module files first for better caching
COPY proto/go.mod proto/go.sum proto/
COPY pkg/go.mod pkg/go.sum pkg/
COPY services/gateway/go.mod services/gateway/go.sum services/gateway/

# Download dependencies
RUN cd services/gateway && go mod download

# Copy source
COPY proto/ proto/
COPY pkg/ pkg/
COPY services/gateway/ services/gateway/

# Build
RUN cd services/gateway && CGO_ENABLED=0 GOOS=linux go build -o /app/gateway-server ./cmd/server

# Runtime
FROM alpine:3.21

RUN apk add --no-cache ca-certificates tzdata

WORKDIR /app

COPY --from=builder /app/gateway-server .

EXPOSE 8080

CMD ["./gateway-server"]
