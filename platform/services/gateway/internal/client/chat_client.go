package client

import (
	"fmt"

	chatv1 "github.com/microservices-agents/platform/proto/gen/go/chat/v1"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// ChatClient wraps a gRPC connection to the chat service.
type ChatClient struct {
	conn   *grpc.ClientConn
	Client chatv1.ChatServiceClient
}

// NewChatClient dials the chat service at the given address and returns a client wrapper.
func NewChatClient(addr string) (*ChatClient, error) {
	conn, err := grpc.NewClient(addr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		return nil, fmt.Errorf("dial chat service: %w", err)
	}
	return &ChatClient{
		conn:   conn,
		Client: chatv1.NewChatServiceClient(conn),
	}, nil
}

// Close shuts down the underlying gRPC connection.
func (c *ChatClient) Close() error {
	return c.conn.Close()
}
