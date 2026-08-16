module github.com/microservices-agents/platform/services/gateway

go 1.23.0

require (
	github.com/go-chi/chi/v5 v5.2.2
	github.com/go-chi/cors v1.2.1
	github.com/gorilla/websocket v1.5.3
	github.com/microservices-agents/platform/pkg v0.0.0
	github.com/microservices-agents/platform/proto v0.0.0
	golang.org/x/time v0.9.0
	google.golang.org/grpc v1.70.0
)

require (
	github.com/caarlos0/env/v11 v11.3.1 // indirect
	github.com/golang-jwt/jwt/v5 v5.2.2 // indirect
	golang.org/x/net v0.35.0 // indirect
	golang.org/x/sys v0.30.0 // indirect
	golang.org/x/text v0.22.0 // indirect
	google.golang.org/genproto/googleapis/rpc v0.0.0-20250218202821-56aae31c358a // indirect
	google.golang.org/protobuf v1.36.5 // indirect
)

replace (
	github.com/microservices-agents/platform/pkg => ../../pkg
	github.com/microservices-agents/platform/proto => ../../proto
)
