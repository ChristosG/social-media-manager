package service

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"log/slog"
	"time"

	"github.com/microservices-agents/platform/services/auth/internal/crypto"
	"github.com/microservices-agents/platform/services/auth/internal/email"
	"github.com/microservices-agents/platform/services/auth/internal/model"
	"github.com/microservices-agents/platform/services/auth/internal/repository"
)

var (
	ErrInvalidResetToken  = errors.New("invalid or expired reset token")
	ErrInvalidVerifyToken = errors.New("invalid or expired verification token")
)

// EmailService handles password reset and email verification flows.
type EmailService struct {
	userRepo          repository.UserRepository
	passwordResetRepo repository.PasswordResetRepository
	logger            *slog.Logger
	sender            email.Sender
	appURL            string
}

// NewEmailService creates a new EmailService.
func NewEmailService(userRepo repository.UserRepository, passwordResetRepo repository.PasswordResetRepository, logger *slog.Logger, sender email.Sender, appURL string) *EmailService {
	return &EmailService{
		userRepo:          userRepo,
		passwordResetRepo: passwordResetRepo,
		logger:            logger,
		sender:            sender,
		appURL:            appURL,
	}
}

// SendPasswordReset initiates the password reset flow for the given email.
// If the email is not found, it returns nil to avoid revealing whether the email exists.
func (s *EmailService) SendPasswordReset(ctx context.Context, email string) error {
	user, err := s.userRepo.GetByEmail(ctx, email)
	if err != nil {
		if errors.Is(err, repository.ErrUserNotFound) {
			// Don't reveal whether the email exists.
			s.logger.Info("password reset requested for unknown email", "email", email)
			return nil
		}
		return fmt.Errorf("lookup user: %w", err)
	}

	// Generate a random token and its SHA-256 hash.
	rawToken, tokenHash, err := GenerateRandomToken()
	if err != nil {
		return fmt.Errorf("generate reset token: %w", err)
	}

	// Store the hashed token with a 1-hour expiry.
	reset := &model.PasswordReset{
		UserID:    user.ID,
		TokenHash: tokenHash,
		ExpiresAt: time.Now().Add(1 * time.Hour),
	}
	if err := s.passwordResetRepo.Create(ctx, reset); err != nil {
		return fmt.Errorf("store reset token: %w", err)
	}

	resetURL := s.appURL + "/reset-password?token=" + rawToken
	if err := s.sender.SendForgotPassword(ctx, email, user.DisplayName, resetURL); err != nil {
		s.logger.Error("failed to send password reset email", "email", email, "error", err)
	}

	return nil
}

// ResetPassword completes the password reset flow by validating the token
// and updating the user's password.
func (s *EmailService) ResetPassword(ctx context.Context, token, newPassword string) error {
	if len(newPassword) < 8 {
		return ErrWeakPassword
	}

	// Hash the provided token to look it up.
	tokenHash := hashRawToken(token)

	reset, err := s.passwordResetRepo.GetByTokenHash(ctx, tokenHash)
	if err != nil {
		if errors.Is(err, repository.ErrPasswordResetNotFound) {
			return ErrInvalidResetToken
		}
		return fmt.Errorf("lookup reset token: %w", err)
	}

	// Check that the token is not expired and not already used.
	if reset.Used || time.Now().After(reset.ExpiresAt) {
		return ErrInvalidResetToken
	}

	// Hash the new password.
	passwordHash, err := crypto.HashPassword(newPassword)
	if err != nil {
		return fmt.Errorf("hash password: %w", err)
	}

	// Update the user's password.
	if err := s.userRepo.UpdatePassword(ctx, reset.UserID, passwordHash); err != nil {
		return fmt.Errorf("update password: %w", err)
	}

	// Mark the token as used.
	if err := s.passwordResetRepo.MarkUsed(ctx, reset.ID); err != nil {
		return fmt.Errorf("mark token used: %w", err)
	}

	// Send password changed notification.
	if user, err := s.userRepo.GetByID(ctx, reset.UserID); err == nil {
		if err := s.sender.SendPasswordChanged(ctx, user.Email, user.DisplayName); err != nil {
			s.logger.Error("failed to send password changed email", "user_id", reset.UserID, "error", err)
		}
	}

	s.logger.Info("password reset completed", "user_id", reset.UserID)
	return nil
}

// VerifyEmail confirms a user's email address using a verification token.
// This is currently a stub implementation.
func (s *EmailService) VerifyEmail(ctx context.Context, token string) error {
	s.logger.Info("STUB: would verify email", "token", token)
	return nil
}

// ResendVerification sends a new email verification link to the user.
// This is currently a stub implementation.
func (s *EmailService) ResendVerification(ctx context.Context, email string) error {
	s.logger.Info("STUB: would resend verification email", "email", email)
	return nil
}

// hashRawToken computes the SHA-256 hash of a raw token string and returns
// the hex-encoded hash.
func hashRawToken(raw string) string {
	h := sha256.Sum256([]byte(raw))
	return hex.EncodeToString(h[:])
}
