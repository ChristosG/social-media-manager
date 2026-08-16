FROM golang:1.23-alpine AS builder

RUN apk add --no-cache git

ENV GOWORK=off

WORKDIR /build

# Copy module files first for better caching
COPY proto/go.mod proto/go.sum proto/
COPY pkg/go.mod pkg/go.sum pkg/
COPY services/auth/go.mod services/auth/go.sum services/auth/

# Download dependencies
RUN cd services/auth && go mod download

# Copy source
COPY proto/ proto/
COPY pkg/ pkg/
COPY services/auth/ services/auth/

# Build
RUN cd services/auth && CGO_ENABLED=0 GOOS=linux go build -o /app/auth-server ./cmd/server

# Runtime
FROM alpine:3.21

RUN apk add --no-cache ca-certificates tzdata

WORKDIR /app

COPY --from=builder /app/auth-server .

EXPOSE 50051

CMD ["./auth-server"]
