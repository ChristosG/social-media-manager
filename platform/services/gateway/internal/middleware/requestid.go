package middleware

import (
	"context"
	"crypto/rand"
	"fmt"
	"net/http"
)

type contextKey string

const (
	// UserIDKey is the context key for the authenticated user's ID.
	UserIDKey contextKey = "user_id"
	// EmailKey is the context key for the authenticated user's email.
	EmailKey contextKey = "email"
	// TenantIDKey is the context key for the authenticated user's tenant ID.
	TenantIDKey contextKey = "tenant_id"
	// RolesKey is the context key for the authenticated user's roles.
	RolesKey contextKey = "roles"
	// PermissionsKey is the context key for the authenticated user's permissions.
	PermissionsKey contextKey = "permissions"
	// RequestIDKey is the context key for the request ID.
	RequestIDKey contextKey = "request_id"
)

const requestIDHeader = "X-Request-ID"

// RequestID is middleware that generates a UUID v4 request ID for each request,
// stores it in the request context, and sets it as a response header.
func RequestID(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		id := r.Header.Get(requestIDHeader)
		if id == "" {
			id = newUUID()
		}

		ctx := context.WithValue(r.Context(), RequestIDKey, id)
		w.Header().Set(requestIDHeader, id)
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

// newUUID generates a UUID v4 using crypto/rand.
func newUUID() string {
	var uuid [16]byte
	_, _ = rand.Read(uuid[:])
	uuid[6] = (uuid[6] & 0x0f) | 0x40 // version 4
	uuid[8] = (uuid[8] & 0x3f) | 0x80 // variant 10
	return fmt.Sprintf("%08x-%04x-%04x-%04x-%012x",
		uuid[0:4], uuid[4:6], uuid[6:8], uuid[8:10], uuid[10:16])
}
