package service

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"log/slog"
	"time"

	"github.com/microservices-agents/platform/services/auth/internal/model"
	"github.com/microservices-agents/platform/services/auth/internal/repository"
)

var (
	ErrTokenNotFound  = errors.New("refresh token not found")
	ErrTokenRevoked   = errors.New("refresh token revoked")
	ErrTokenExpired   = errors.New("refresh token expired")
	ErrReplayDetected = errors.New("token replay detected, family revoked")
)

// TokenService handles refresh token creation, rotation, and revocation.
type TokenService struct {
	tokenRepo repository.RefreshTokenRepository
	logger    *slog.Logger
	ttl       time.Duration
}

// NewTokenService creates a new TokenService.
func NewTokenService(tokenRepo repository.RefreshTokenRepository, logger *slog.Logger, ttl time.Duration) *TokenService {
	return &TokenService{
		tokenRepo: tokenRepo,
		logger:    logger,
		ttl:       ttl,
	}
}

// CreateRefreshToken generates a new refresh token pair (raw for client, hash stored in DB).
// familyID groups tokens for rotation detection. If empty, generates a new family.
func (s *TokenService) CreateRefreshToken(ctx context.Context, userID string, familyID string) (rawToken string, err error) {
	raw, hash, err := GenerateRandomToken()
	if err != nil {
		return "", fmt.Errorf("generate token: %w", err)
	}

	if familyID == "" {
		_, familyID, err = GenerateRandomToken()
		if err != nil {
			return "", fmt.Errorf("generate family id: %w", err)
		}
	}

	token := &model.RefreshToken{
		UserID:    userID,
		TokenHash: hash,
		FamilyID:  familyID,
		ExpiresAt: time.Now().Add(s.ttl),
	}

	if err := s.tokenRepo.Create(ctx, token); err != nil {
		return "", fmt.Errorf("store refresh token: %w", err)
	}

	s.logger.Debug("created refresh token", "user_id", userID, "family_id", familyID, "expires_at", token.ExpiresAt)
	return raw, nil
}

// RefreshToken validates and rotates a refresh token. Returns a new raw token, the user ID, and family ID.
// If the old token was already revoked (replay attack), the entire family is revoked.
func (s *TokenService) RefreshToken(ctx context.Context, rawToken string) (newRawToken string, userID string, familyID string, err error) {
	// Step 1: Hash the raw token to look it up.
	tokenHash := hashToken(rawToken)

	// Step 2: Look up the token in the database.
	stored, err := s.tokenRepo.GetByTokenHash(ctx, tokenHash)
	if err != nil {
		if errors.Is(err, repository.ErrRefreshTokenNotFound) {
			return "", "", "", ErrTokenNotFound
		}
		return "", "", "", fmt.Errorf("get token: %w", err)
	}

	// Step 3: If the token is already revoked, this is a replay attack.
	// Revoke the entire family and return an error.
	if stored.Revoked {
		s.logger.Warn("token replay detected, revoking family",
			"user_id", stored.UserID,
			"family_id", stored.FamilyID,
			"token_id", stored.ID,
		)
		if revokeErr := s.tokenRepo.RevokeByFamilyID(ctx, stored.FamilyID); revokeErr != nil {
			s.logger.Error("failed to revoke token family", "error", revokeErr, "family_id", stored.FamilyID)
		}
		return "", "", "", ErrReplayDetected
	}

	// Step 4: Check if the token is expired.
	if time.Now().After(stored.ExpiresAt) {
		return "", "", "", ErrTokenExpired
	}

	// Step 5: Revoke the old token.
	if err := s.tokenRepo.RevokeByID(ctx, stored.ID); err != nil {
		return "", "", "", fmt.Errorf("revoke old token: %w", err)
	}

	// Step 6: Create a new token with the same family_id.
	newRaw, err := s.CreateRefreshToken(ctx, stored.UserID, stored.FamilyID)
	if err != nil {
		return "", "", "", fmt.Errorf("create rotated token: %w", err)
	}

	return newRaw, stored.UserID, stored.FamilyID, nil
}

// RevokeToken revokes a single refresh token by its raw value.
func (s *TokenService) RevokeToken(ctx context.Context, rawToken string) error {
	tokenHash := hashToken(rawToken)

	stored, err := s.tokenRepo.GetByTokenHash(ctx, tokenHash)
	if err != nil {
		if errors.Is(err, repository.ErrRefreshTokenNotFound) {
			return ErrTokenNotFound
		}
		return fmt.Errorf("get token: %w", err)
	}

	if err := s.tokenRepo.RevokeByID(ctx, stored.ID); err != nil {
		return fmt.Errorf("revoke token: %w", err)
	}

	s.logger.Debug("revoked refresh token", "token_id", stored.ID, "user_id", stored.UserID)
	return nil
}

// RevokeAllForUser revokes all refresh tokens for a user.
func (s *TokenService) RevokeAllForUser(ctx context.Context, userID string) error {
	if err := s.tokenRepo.RevokeAllForUser(ctx, userID); err != nil {
		return fmt.Errorf("revoke all tokens: %w", err)
	}

	s.logger.Info("revoked all refresh tokens for user", "user_id", userID)
	return nil
}

// hashToken computes the SHA-256 hash of a raw token string and returns its hex representation.
func hashToken(raw string) string {
	h := sha256.Sum256([]byte(raw))
	return hex.EncodeToString(h[:])
}
