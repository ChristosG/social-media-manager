package middleware

import (
	"context"
	"net/http"
	"strings"

	pkgjwt "github.com/microservices-agents/platform/pkg/jwt"
)

// Auth returns middleware that validates JWT Bearer tokens from the
// Authorization header using the provided jwt.Manager. On success it stores
// the user ID and email in the request context. On failure it responds with
// 401 Unauthorized.
func Auth(jwtManager *pkgjwt.Manager) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			authHeader := r.Header.Get("Authorization")
			if authHeader == "" {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusUnauthorized)
				w.Write([]byte(`{"error":"missing authorization header"}`))
				return
			}

			parts := strings.SplitN(authHeader, " ", 2)
			if len(parts) != 2 || !strings.EqualFold(parts[0], "Bearer") {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusUnauthorized)
				w.Write([]byte(`{"error":"invalid authorization header format"}`))
				return
			}

			token := parts[1]
			claims, err := jwtManager.ValidateToken(token)
			if err != nil {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusUnauthorized)
				w.Write([]byte(`{"error":"invalid or expired token"}`))
				return
			}

			// A "mfa:pending" token is only the first factor — issued by /login so the client can
			// reach /mfa/verify (which takes the token in its body, not as a Bearer). It must never
			// be honored as a full credential on protected routes, or MFA is trivially bypassed.
			if claims.Custom["mfa"] == "pending" {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusUnauthorized)
				w.Write([]byte(`{"error":"MFA verification required"}`))
				return
			}

			ctx := r.Context()
			ctx = context.WithValue(ctx, UserIDKey, claims.Subject)
			ctx = context.WithValue(ctx, EmailKey, claims.Email)
			if claims.TenantID != "" {
				ctx = context.WithValue(ctx, TenantIDKey, claims.TenantID)
			}
			if len(claims.Roles) > 0 {
				ctx = context.WithValue(ctx, RolesKey, claims.Roles)
			}
			if len(claims.Permissions) > 0 {
				ctx = context.WithValue(ctx, PermissionsKey, claims.Permissions)
			}

			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}
