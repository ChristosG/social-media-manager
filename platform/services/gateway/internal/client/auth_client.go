package client

import (
	"fmt"

	authv1 "github.com/microservices-agents/platform/proto/gen/go/auth/v1"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// AuthClient wraps a gRPC connection to the auth service.
type AuthClient struct {
	conn   *grpc.ClientConn
	Client authv1.AuthServiceClient
}

// NewAuthClient dials the auth service at the given address and returns a client wrapper.
func NewAuthClient(addr string) (*AuthClient, error) {
	conn, err := grpc.NewClient(addr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		return nil, fmt.Errorf("dial auth service: %w", err)
	}
	return &AuthClient{
		conn:   conn,
		Client: authv1.NewAuthServiceClient(conn),
	}, nil
}

// Close shuts down the underlying gRPC connection.
func (c *AuthClient) Close() error {
	return c.conn.Close()
}
