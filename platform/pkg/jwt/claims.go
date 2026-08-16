package jwt

import jwtlib "github.com/golang-jwt/jwt/v5"

// Claims represents the custom JWT claims used across the platform.
type Claims struct {
	jwtlib.RegisteredClaims
	Email       string            `json:"email"`
	TenantID    string            `json:"tid,omitempty"`
	Roles       []string          `json:"roles,omitempty"`
	Permissions []string          `json:"permissions,omitempty"`
	Custom      map[string]string `json:"custom,omitempty"`
}
