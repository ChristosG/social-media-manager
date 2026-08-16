package jwt

import (
	"crypto/ed25519"
	"encoding/base64"
	"errors"
	"fmt"
	"time"

	jwtlib "github.com/golang-jwt/jwt/v5"
)

// Manager handles JWT creation and validation using Ed25519 keys.
type Manager struct {
	privateKey ed25519.PrivateKey
	publicKey  ed25519.PublicKey
}

// NewManager creates a Manager capable of both signing and validating tokens.
// Both privateKeyB64 and publicKeyB64 must be standard base64-encoded Ed25519 keys.
func NewManager(privateKeyB64, publicKeyB64 string) (*Manager, error) {
	privBytes, err := base64.StdEncoding.DecodeString(privateKeyB64)
	if err != nil {
		return nil, fmt.Errorf("decode private key: %w", err)
	}
	if len(privBytes) != ed25519.PrivateKeySize {
		return nil, fmt.Errorf("invalid private key length: got %d, want %d", len(privBytes), ed25519.PrivateKeySize)
	}

	pubBytes, err := base64.StdEncoding.DecodeString(publicKeyB64)
	if err != nil {
		return nil, fmt.Errorf("decode public key: %w", err)
	}
	if len(pubBytes) != ed25519.PublicKeySize {
		return nil, fmt.Errorf("invalid public key length: got %d, want %d", len(pubBytes), ed25519.PublicKeySize)
	}

	return &Manager{
		privateKey: ed25519.PrivateKey(privBytes),
		publicKey:  ed25519.PublicKey(pubBytes),
	}, nil
}

// NewValidatorOnly creates a Manager that can only validate tokens (no signing).
// This is intended for the API gateway which only needs to verify incoming tokens.
func NewValidatorOnly(publicKeyB64 string) (*Manager, error) {
	pubBytes, err := base64.StdEncoding.DecodeString(publicKeyB64)
	if err != nil {
		return nil, fmt.Errorf("decode public key: %w", err)
	}
	if len(pubBytes) != ed25519.PublicKeySize {
		return nil, fmt.Errorf("invalid public key length: got %d, want %d", len(pubBytes), ed25519.PublicKeySize)
	}

	return &Manager{
		publicKey: ed25519.PublicKey(pubBytes),
	}, nil
}

// GenerateAccessToken creates a signed JWT with the given user information and TTL.
// Returns an error if the manager was created without a private key.
func (m *Manager) GenerateAccessToken(userID, email, tenantID string, roles, permissions []string, customClaims map[string]string, ttl time.Duration) (string, error) {
	if m.privateKey == nil {
		return "", errors.New("private key not available: manager is validator-only")
	}

	now := time.Now()
	tokenClaims := &Claims{
		RegisteredClaims: jwtlib.RegisteredClaims{
			Subject:   userID,
			IssuedAt:  jwtlib.NewNumericDate(now),
			ExpiresAt: jwtlib.NewNumericDate(now.Add(ttl)),
			NotBefore: jwtlib.NewNumericDate(now),
		},
		Email:       email,
		TenantID:    tenantID,
		Roles:       roles,
		Permissions: permissions,
		Custom:      customClaims,
	}

	token := jwtlib.NewWithClaims(jwtlib.SigningMethodEdDSA, tokenClaims)
	signed, err := token.SignedString(m.privateKey)
	if err != nil {
		return "", fmt.Errorf("sign token: %w", err)
	}

	return signed, nil
}

// ValidateToken parses and validates the given JWT string.
// Returns the decoded claims on success, or an error if the token is invalid or expired.
func (m *Manager) ValidateToken(tokenString string) (*Claims, error) {
	token, err := jwtlib.ParseWithClaims(tokenString, &Claims{}, func(t *jwtlib.Token) (interface{}, error) {
		if _, ok := t.Method.(*jwtlib.SigningMethodEd25519); !ok {
			return nil, fmt.Errorf("unexpected signing method: %v", t.Header["alg"])
		}
		return m.publicKey, nil
	})
	if err != nil {
		return nil, fmt.Errorf("parse token: %w", err)
	}

	claims, ok := token.Claims.(*Claims)
	if !ok || !token.Valid {
		return nil, errors.New("invalid token claims")
	}

	return claims, nil
}
