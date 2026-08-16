package middleware

import (
	"context"
	"crypto/rand"
	"fmt"

	"google.golang.org/grpc"
	"google.golang.org/grpc/metadata"
)

const requestIDKey = "x-request-id"

type contextKey string

const requestIDContextKey contextKey = "request_id"

// newUUIDv4 generates a UUID v4 using crypto/rand.
func newUUIDv4() (string, error) {
	var uuid [16]byte
	if _, err := rand.Read(uuid[:]); err != nil {
		return "", fmt.Errorf("generate uuid: %w", err)
	}
	// Set version 4 (bits 12-15 of time_hi_and_version)
	uuid[6] = (uuid[6] & 0x0f) | 0x40
	// Set variant bits (10xx)
	uuid[8] = (uuid[8] & 0x3f) | 0x80

	return fmt.Sprintf("%08x-%04x-%04x-%04x-%012x",
		uuid[0:4], uuid[4:6], uuid[6:8], uuid[8:10], uuid[10:16],
	), nil
}

// RequestIDFromContext extracts the request ID from the context.
func RequestIDFromContext(ctx context.Context) string {
	if id, ok := ctx.Value(requestIDContextKey).(string); ok {
		return id
	}
	return ""
}

// UnaryRequestIDInterceptor returns a gRPC unary server interceptor that
// assigns a UUID v4 request ID to each request. If the incoming metadata
// already contains a request ID, it is reused; otherwise a new one is generated.
// The request ID is stored in both the context and the outgoing gRPC metadata.
func UnaryRequestIDInterceptor() grpc.UnaryServerInterceptor {
	return func(
		ctx context.Context,
		req interface{},
		info *grpc.UnaryServerInfo,
		handler grpc.UnaryHandler,
	) (interface{}, error) {
		var reqID string

		// Check if a request ID was provided in incoming metadata.
		if md, ok := metadata.FromIncomingContext(ctx); ok {
			if ids := md.Get(requestIDKey); len(ids) > 0 && ids[0] != "" {
				reqID = ids[0]
			}
		}

		// Generate a new request ID if none was provided.
		if reqID == "" {
			id, err := newUUIDv4()
			if err != nil {
				reqID = "unknown"
			} else {
				reqID = id
			}
		}

		// Store in context for application use.
		ctx = context.WithValue(ctx, requestIDContextKey, reqID)

		// Add to outgoing gRPC metadata so downstream services can propagate it.
		ctx = metadata.AppendToOutgoingContext(ctx, requestIDKey, reqID)

		// Also set as response header so clients can see it.
		if err := grpc.SetHeader(ctx, metadata.Pairs(requestIDKey, reqID)); err != nil {
			// Non-fatal: log but continue processing.
			_ = err
		}

		return handler(ctx, req)
	}
}
