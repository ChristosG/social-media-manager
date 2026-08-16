package handler

import (
	"context"
	"errors"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	authv1 "github.com/microservices-agents/platform/proto/gen/go/auth/v1"
	"github.com/microservices-agents/platform/services/auth/internal/service"
)

// EnableMFA generates a new TOTP secret for the user and returns the secret
// and a QR code URL that the user can scan with an authenticator app.
func (h *AuthHandler) EnableMFA(ctx context.Context, req *authv1.EnableMFARequest) (*authv1.EnableMFAResponse, error) {
	if req.GetUserId() == "" {
		return nil, status.Error(codes.InvalidArgument, "user_id is required")
	}

	secret, qrCodeURL, err := h.mfaSvc.EnableMFA(ctx, req.GetUserId())
	if err != nil {
		return nil, status.Errorf(codes.Internal, "enable MFA: %v", err)
	}

	return &authv1.EnableMFAResponse{
		Secret:    secret,
		QrCodeUrl: qrCodeURL,
	}, nil
}

// VerifyMFA validates a TOTP code during the MFA login flow. It expects the
// short-lived MFA token (with "mfa":"pending" claim) issued during Login,
// plus the 6-digit TOTP code from the user's authenticator app.
// On success, it issues full access and refresh tokens.
func (h *AuthHandler) VerifyMFA(ctx context.Context, req *authv1.VerifyMFARequest) (*authv1.VerifyMFAResponse, error) {
	if req.GetMfaToken() == "" {
		return nil, status.Error(codes.InvalidArgument, "mfa_token is required")
	}
	if req.GetCode() == "" {
		return nil, status.Error(codes.InvalidArgument, "code is required")
	}

	// Validate the short-lived MFA token and ensure it carries the "mfa":"pending" claim.
	claims, err := h.jwt.ValidateToken(req.GetMfaToken())
	if err != nil {
		return nil, status.Error(codes.Unauthenticated, "invalid or expired MFA token")
	}

	if claims.Custom == nil || claims.Custom["mfa"] != "pending" {
		return nil, status.Error(codes.Unauthenticated, "token is not an MFA token")
	}

	userID := claims.Subject
	email := claims.Email

	// Validate the TOTP code against the user's stored secret.
	err = h.mfaSvc.ValidateCode(ctx, userID, req.GetCode())
	if err != nil {
		if errors.Is(err, service.ErrInvalidMFACode) {
			return nil, status.Error(codes.Unauthenticated, "invalid MFA code")
		}
		return nil, status.Errorf(codes.Internal, "validate MFA code: %v", err)
	}

	// MFA verification succeeded; fetch user for tenant/role context, then issue real tokens.
	user, userErr := h.authSvc.GetUser(ctx, userID)
	if userErr != nil {
		return nil, status.Errorf(codes.Internal, "get user: %v", userErr)
	}
	_ = email // user.Email used via generateUserAccessToken

	accessToken, err := h.generateUserAccessToken(ctx, user)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "generate access token: %v", err)
	}

	refreshToken, err := h.tokenSvc.CreateRefreshToken(ctx, userID, "")
	if err != nil {
		return nil, status.Errorf(codes.Internal, "create refresh token: %v", err)
	}

	return &authv1.VerifyMFAResponse{
		AccessToken:  accessToken,
		RefreshToken: refreshToken,
	}, nil
}

// DisableMFA turns off TOTP-based multi-factor authentication for the user.
func (h *AuthHandler) DisableMFA(ctx context.Context, req *authv1.DisableMFARequest) (*authv1.DisableMFAResponse, error) {
	if req.GetUserId() == "" {
		return nil, status.Error(codes.InvalidArgument, "user_id is required")
	}
	if req.GetCode() == "" {
		return nil, status.Error(codes.InvalidArgument, "code is required")
	}

	err := h.mfaSvc.DisableMFA(ctx, req.GetUserId(), req.GetCode())
	if err != nil {
		if errors.Is(err, service.ErrInvalidMFACode) {
			return nil, status.Error(codes.Unauthenticated, "invalid MFA code")
		}
		return nil, status.Errorf(codes.Internal, "disable MFA: %v", err)
	}

	return &authv1.DisableMFAResponse{}, nil
}
