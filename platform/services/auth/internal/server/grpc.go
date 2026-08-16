package server

import (
	"fmt"
	"log/slog"
	"net"

	"google.golang.org/grpc"
	"google.golang.org/grpc/reflection"

	authv1 "github.com/microservices-agents/platform/proto/gen/go/auth/v1"
	"github.com/microservices-agents/platform/pkg/middleware"
	"github.com/microservices-agents/platform/services/auth/internal/handler"
)

// NewGRPCServer creates a new gRPC server with the auth service handler registered,
// along with request-ID propagation and panic recovery interceptors.
func NewGRPCServer(h *handler.AuthHandler, logger *slog.Logger) *grpc.Server {
	srv := grpc.NewServer(
		grpc.ChainUnaryInterceptor(
			middleware.UnaryRequestIDInterceptor(),
			middleware.UnaryRecoveryInterceptor(logger),
		),
	)

	authv1.RegisterAuthServiceServer(srv, h)
	reflection.Register(srv)

	return srv
}

// ListenAndServe binds the gRPC server to the given port and begins accepting connections.
// It blocks until the server is stopped or an error occurs.
func ListenAndServe(srv *grpc.Server, port int, logger *slog.Logger) error {
	lis, err := net.Listen("tcp", fmt.Sprintf(":%d", port))
	if err != nil {
		return fmt.Errorf("listen: %w", err)
	}

	logger.Info("gRPC server listening", "port", port)
	return srv.Serve(lis)
}
