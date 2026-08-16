package service

import (
	"context"
	"errors"
	"fmt"
	"log/slog"

	"github.com/microservices-agents/platform/services/auth/internal/crypto"
	"github.com/microservices-agents/platform/services/auth/internal/repository"
)

var (
	ErrMFAAlreadyEnabled = errors.New("MFA is already enabled")
	ErrMFANotEnabled     = errors.New("MFA is not enabled")
	ErrMFANotSetup       = errors.New("MFA secret not set up; call EnableMFA first")
	ErrInvalidMFACode    = errors.New("invalid MFA code")
)

// MFAService handles MFA enrollment, activation, validation, and disabling.
type MFAService struct {
	userRepo      repository.UserRepository
	logger        *slog.Logger
	encryptionKey string
	issuer        string
}

// NewMFAService creates a new MFAService.
func NewMFAService(userRepo repository.UserRepository, logger *slog.Logger, encryptionKey, issuer string) *MFAService {
	return &MFAService{
		userRepo:      userRepo,
		logger:        logger,
		encryptionKey: encryptionKey,
		issuer:        issuer,
	}
}

// EnableMFA generates a TOTP secret, encrypts it, and stores it on the user record.
// MFA is not activated until VerifyAndActivateMFA is called with a valid code.
// Returns the plaintext secret and a QR provisioning URL for the user to scan.
func (s *MFAService) EnableMFA(ctx context.Context, userID string) (secret, qrURL string, err error) {
	user, err := s.userRepo.GetByID(ctx, userID)
	if err != nil {
		if errors.Is(err, repository.ErrUserNotFound) {
			return "", "", ErrUserNotFound
		}
		return "", "", fmt.Errorf("get user: %w", err)
	}

	if user.MFAEnabled {
		return "", "", ErrMFAAlreadyEnabled
	}

	// Generate a new TOTP secret.
	secret, qrURL, err = crypto.GenerateTOTPSecret(s.issuer, user.Email)
	if err != nil {
		return "", "", fmt.Errorf("generate TOTP secret: %w", err)
	}

	// Encrypt the secret for storage.
	encrypted, err := crypto.EncryptSecret(secret, s.encryptionKey)
	if err != nil {
		return "", "", fmt.Errorf("encrypt secret: %w", err)
	}

	// Store the encrypted secret but keep MFA disabled until verification.
	if err := s.userRepo.UpdateMFA(ctx, userID, false, encrypted); err != nil {
		return "", "", fmt.Errorf("store MFA secret: %w", err)
	}

	s.logger.Info("MFA setup initiated", "user_id", userID)
	return secret, qrURL, nil
}

// VerifyAndActivateMFA validates a TOTP code against the stored (but not yet active) secret
// and activates MFA for the user.
func (s *MFAService) VerifyAndActivateMFA(ctx context.Context, userID string, code string) error {
	user, err := s.userRepo.GetByID(ctx, userID)
	if err != nil {
		if errors.Is(err, repository.ErrUserNotFound) {
			return ErrUserNotFound
		}
		return fmt.Errorf("get user: %w", err)
	}

	if user.MFAEnabled {
		return ErrMFAAlreadyEnabled
	}

	if len(user.MFASecret) == 0 {
		return ErrMFANotSetup
	}

	// Decrypt the stored secret.
	secret, err := crypto.DecryptSecret(user.MFASecret, s.encryptionKey)
	if err != nil {
		return fmt.Errorf("decrypt MFA secret: %w", err)
	}

	// Validate the provided code.
	if !crypto.ValidateTOTPCode(code, secret) {
		return ErrInvalidMFACode
	}

	// Activate MFA, keeping the same encrypted secret.
	if err := s.userRepo.UpdateMFA(ctx, userID, true, user.MFASecret); err != nil {
		return fmt.Errorf("activate MFA: %w", err)
	}

	s.logger.Info("MFA activated", "user_id", userID)
	return nil
}

// ValidateCode checks a TOTP code against the user's stored and active MFA secret.
func (s *MFAService) ValidateCode(ctx context.Context, userID string, code string) error {
	user, err := s.userRepo.GetByID(ctx, userID)
	if err != nil {
		if errors.Is(err, repository.ErrUserNotFound) {
			return ErrUserNotFound
		}
		return fmt.Errorf("get user: %w", err)
	}

	if !user.MFAEnabled {
		return ErrMFANotEnabled
	}

	if len(user.MFASecret) == 0 {
		return ErrMFANotSetup
	}

	secret, err := crypto.DecryptSecret(user.MFASecret, s.encryptionKey)
	if err != nil {
		return fmt.Errorf("decrypt MFA secret: %w", err)
	}

	if !crypto.ValidateTOTPCode(code, secret) {
		return ErrInvalidMFACode
	}

	return nil
}

// DisableMFA disables MFA for a user after validating the provided TOTP code.
func (s *MFAService) DisableMFA(ctx context.Context, userID string, code string) error {
	// First validate the code to prove the user has the authenticator.
	if err := s.ValidateCode(ctx, userID, code); err != nil {
		return err
	}

	// Disable MFA and clear the stored secret.
	if err := s.userRepo.UpdateMFA(ctx, userID, false, nil); err != nil {
		return fmt.Errorf("disable MFA: %w", err)
	}

	s.logger.Info("MFA disabled", "user_id", userID)
	return nil
}
