package service

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"log/slog"

	"github.com/microservices-agents/platform/services/auth/internal/crypto"
	"github.com/microservices-agents/platform/services/auth/internal/email"
	"github.com/microservices-agents/platform/services/auth/internal/model"
	"github.com/microservices-agents/platform/services/auth/internal/repository"
)

var (
	ErrInvalidCredentials = errors.New("invalid credentials")
	ErrUserNotFound       = errors.New("user not found")
	ErrEmailAlreadyExists = errors.New("email already exists")
	ErrMFARequired        = errors.New("MFA required")
	ErrWeakPassword       = errors.New("password must be at least 8 characters")
)

type AuthService struct {
	userRepo repository.UserRepository
	logger   *slog.Logger
	sender   email.Sender
}

func NewAuthService(userRepo repository.UserRepository, logger *slog.Logger, sender email.Sender) *AuthService {
	return &AuthService{userRepo: userRepo, logger: logger, sender: sender}
}

// Register creates a new user with email/password.
func (s *AuthService) Register(ctx context.Context, email, password, displayName string, metadata map[string]string) (*model.User, error) {
	if len(password) < 8 {
		return nil, ErrWeakPassword
	}

	hash, err := crypto.HashPassword(password)
	if err != nil {
		return nil, fmt.Errorf("hash password: %w", err)
	}

	user := &model.User{
		Email:        email,
		PasswordHash: &hash,
		DisplayName:  displayName,
		Metadata:     metadata,
	}
	if user.Metadata == nil {
		user.Metadata = make(map[string]string)
	}

	if err := s.userRepo.Create(ctx, user); err != nil {
		if errors.Is(err, repository.ErrEmailAlreadyExists) {
			return nil, ErrEmailAlreadyExists
		}
		return nil, err
	}

	if err := s.sender.SendWelcome(ctx, user.Email, user.DisplayName); err != nil {
		s.logger.Error("failed to send welcome email", "email", user.Email, "error", err)
	}

	return user, nil
}

// Authenticate validates email/password and returns the user. Returns ErrMFARequired if MFA is enabled.
func (s *AuthService) Authenticate(ctx context.Context, email, password string) (*model.User, error) {
	user, err := s.userRepo.GetByEmail(ctx, email)
	if err != nil {
		if errors.Is(err, repository.ErrUserNotFound) {
			return nil, ErrInvalidCredentials
		}
		return nil, err
	}

	if user.PasswordHash == nil {
		return nil, ErrInvalidCredentials // OAuth-only user
	}

	valid, err := crypto.VerifyPassword(password, *user.PasswordHash)
	if err != nil || !valid {
		return nil, ErrInvalidCredentials
	}

	if user.MFAEnabled {
		return user, ErrMFARequired
	}

	return user, nil
}

// GetUser returns a user by ID.
func (s *AuthService) GetUser(ctx context.Context, userID string) (*model.User, error) {
	user, err := s.userRepo.GetByID(ctx, userID)
	if err != nil {
		if errors.Is(err, repository.ErrUserNotFound) {
			return nil, ErrUserNotFound
		}
		return nil, err
	}
	return user, nil
}

// GenerateRandomToken generates a cryptographically random token and its SHA-256 hash.
func GenerateRandomToken() (raw string, hash string, err error) {
	b := make([]byte, 32)
	if _, err := rand.Read(b); err != nil {
		return "", "", err
	}
	raw = hex.EncodeToString(b)
	h := sha256.Sum256([]byte(raw))
	hash = hex.EncodeToString(h[:])
	return raw, hash, nil
}
