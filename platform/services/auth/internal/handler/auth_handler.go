package handler

import (
	"context"
	"errors"
	"time"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/timestamppb"

	authv1 "github.com/microservices-agents/platform/proto/gen/go/auth/v1"
	"github.com/microservices-agents/platform/pkg/jwt"
	"github.com/microservices-agents/platform/services/auth/internal/model"
	"github.com/microservices-agents/platform/services/auth/internal/repository"
	"github.com/microservices-agents/platform/services/auth/internal/service"
)

// AuthHandler implements the authv1.AuthServiceServer gRPC interface.
type AuthHandler struct {
	authv1.UnimplementedAuthServiceServer
	authSvc    *service.AuthService
	tokenSvc   *service.TokenService
	oauthSvc   *service.OAuthService
	mfaSvc     *service.MFAService
	emailSvc   *service.EmailService
	roleRepo   repository.RoleRepository
	tenantRepo repository.TenantRepository
	jwt        *jwt.Manager
	accessTTL  time.Duration
	refreshTTL time.Duration
}

// NewAuthHandler creates a new AuthHandler with all required dependencies.
func NewAuthHandler(
	authSvc *service.AuthService,
	tokenSvc *service.TokenService,
	oauthSvc *service.OAuthService,
	mfaSvc *service.MFAService,
	emailSvc *service.EmailService,
	roleRepo repository.RoleRepository,
	tenantRepo repository.TenantRepository,
	jwtMgr *jwt.Manager,
	accessTTL, refreshTTL time.Duration,
) *AuthHandler {
	return &AuthHandler{
		authSvc:    authSvc,
		tokenSvc:   tokenSvc,
		oauthSvc:   oauthSvc,
		mfaSvc:     mfaSvc,
		emailSvc:   emailSvc,
		roleRepo:   roleRepo,
		tenantRepo: tenantRepo,
		jwt:        jwtMgr,
		accessTTL:  accessTTL,
		refreshTTL: refreshTTL,
	}
}

// generateUserAccessToken builds a JWT for the given user, including tenant/role/module claims if applicable.
func (h *AuthHandler) generateUserAccessToken(ctx context.Context, user *model.User) (string, error) {
	var tenantID string
	var roleNames []string
	var allPermissions []string
	var customClaims map[string]string

	if user.TenantID != nil {
		tenantID = *user.TenantID
		roles, err := h.roleRepo.GetRolesForUser(ctx, user.ID)
		if err == nil {
			seen := make(map[string]bool)
			for _, role := range roles {
				roleNames = append(roleNames, role.Name)
				for _, perm := range role.Permissions {
					if !seen[perm] {
						seen[perm] = true
						allPermissions = append(allPermissions, perm)
					}
				}
			}
		}

		// Include modules from tenant settings in custom claims.
		tenant, err := h.tenantRepo.GetByID(ctx, tenantID)
		if err == nil && tenant.Settings != nil {
			if modules, ok := tenant.Settings["modules"]; ok && modules != "" {
				customClaims = map[string]string{"modules": modules}
			}
		}
	}

	return h.jwt.GenerateAccessToken(user.ID, user.Email, tenantID, roleNames, allPermissions, customClaims, h.accessTTL)
}

// Register creates a new user account with email/password credentials,
// generates access and refresh tokens, and returns them along with the user profile.
func (h *AuthHandler) Register(ctx context.Context, req *authv1.RegisterRequest) (*authv1.RegisterResponse, error) {
	if req.GetEmail() == "" {
		return nil, status.Error(codes.InvalidArgument, "email is required")
	}
	if req.GetPassword() == "" {
		return nil, status.Error(codes.InvalidArgument, "password is required")
	}
	if req.GetDisplayName() == "" {
		return nil, status.Error(codes.InvalidArgument, "display_name is required")
	}

	user, err := h.authSvc.Register(ctx, req.GetEmail(), req.GetPassword(), req.GetDisplayName(), req.GetMetadata())
	if err != nil {
		if errors.Is(err, service.ErrEmailAlreadyExists) {
			return nil, status.Error(codes.AlreadyExists, "email already registered")
		}
		if errors.Is(err, service.ErrWeakPassword) {
			return nil, status.Error(codes.InvalidArgument, err.Error())
		}
		return nil, status.Errorf(codes.Internal, "register user: %v", err)
	}

	accessToken, err := h.generateUserAccessToken(ctx, user)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "generate access token: %v", err)
	}

	refreshToken, err := h.tokenSvc.CreateRefreshToken(ctx, user.ID, "")
	if err != nil {
		return nil, status.Errorf(codes.Internal, "create refresh token: %v", err)
	}

	return &authv1.RegisterResponse{
		AccessToken:  accessToken,
		RefreshToken: refreshToken,
		User:         userToProto(user),
	}, nil
}

// Login authenticates a user with email/password. If MFA is enabled on the account,
// it returns a short-lived MFA token and requires_mfa=true instead of full tokens.
func (h *AuthHandler) Login(ctx context.Context, req *authv1.LoginRequest) (*authv1.LoginResponse, error) {
	if req.GetEmail() == "" {
		return nil, status.Error(codes.InvalidArgument, "email is required")
	}
	if req.GetPassword() == "" {
		return nil, status.Error(codes.InvalidArgument, "password is required")
	}

	user, err := h.authSvc.Authenticate(ctx, req.GetEmail(), req.GetPassword())
	if err != nil {
		if errors.Is(err, service.ErrMFARequired) {
			// User has MFA enabled: issue a short-lived MFA token with a "mfa":"pending" claim
			// so the client can proceed to the VerifyMFA step.
			mfaClaims := map[string]string{"mfa": "pending"}
			mfaToken, tokenErr := h.jwt.GenerateAccessToken(user.ID, user.Email, "", nil, nil, mfaClaims, 5*time.Minute)
			if tokenErr != nil {
				return nil, status.Errorf(codes.Internal, "generate MFA token: %v", tokenErr)
			}
			return &authv1.LoginResponse{
				RequiresMfa: true,
				MfaToken:    mfaToken,
			}, nil
		}
		if errors.Is(err, service.ErrInvalidCredentials) {
			return nil, status.Error(codes.Unauthenticated, "invalid email or password")
		}
		return nil, status.Errorf(codes.Internal, "authenticate: %v", err)
	}

	accessToken, err := h.generateUserAccessToken(ctx, user)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "generate access token: %v", err)
	}

	refreshToken, err := h.tokenSvc.CreateRefreshToken(ctx, user.ID, "")
	if err != nil {
		return nil, status.Errorf(codes.Internal, "create refresh token: %v", err)
	}

	return &authv1.LoginResponse{
		AccessToken:  accessToken,
		RefreshToken: refreshToken,
		User:         userToProto(user),
	}, nil
}

// RefreshToken rotates a refresh token and issues a new access token.
// The old refresh token is revoked, and a new one is returned alongside a fresh access token.
func (h *AuthHandler) RefreshToken(ctx context.Context, req *authv1.RefreshTokenRequest) (*authv1.RefreshTokenResponse, error) {
	if req.GetRefreshToken() == "" {
		return nil, status.Error(codes.InvalidArgument, "refresh_token is required")
	}

	newRefreshToken, userID, _, err := h.tokenSvc.RefreshToken(ctx, req.GetRefreshToken())
	if err != nil {
		if errors.Is(err, service.ErrTokenNotFound) {
			return nil, status.Error(codes.Unauthenticated, "invalid refresh token")
		}
		if errors.Is(err, service.ErrTokenRevoked) || errors.Is(err, service.ErrReplayDetected) {
			return nil, status.Error(codes.Unauthenticated, "refresh token revoked")
		}
		if errors.Is(err, service.ErrTokenExpired) {
			return nil, status.Error(codes.Unauthenticated, "refresh token expired")
		}
		return nil, status.Errorf(codes.Internal, "refresh token: %v", err)
	}

	// Fetch the user to populate the access token email claim.
	user, err := h.authSvc.GetUser(ctx, userID)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "get user: %v", err)
	}

	accessToken, err := h.generateUserAccessToken(ctx, user)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "generate access token: %v", err)
	}

	return &authv1.RefreshTokenResponse{
		AccessToken:  accessToken,
		RefreshToken: newRefreshToken,
	}, nil
}

// ValidateToken parses and validates a JWT access token, returning its claims.
func (h *AuthHandler) ValidateToken(ctx context.Context, req *authv1.ValidateTokenRequest) (*authv1.ValidateTokenResponse, error) {
	if req.GetToken() == "" {
		return nil, status.Error(codes.InvalidArgument, "token is required")
	}

	claims, err := h.jwt.ValidateToken(req.GetToken())
	if err != nil {
		return &authv1.ValidateTokenResponse{
			Valid: false,
		}, nil
	}

	// Convert custom claims map to the response format.
	claimsMap := make(map[string]string)
	for k, v := range claims.Custom {
		claimsMap[k] = v
	}

	return &authv1.ValidateTokenResponse{
		Valid:  true,
		UserId: claims.Subject,
		Email:  claims.Email,
		Claims: claimsMap,
	}, nil
}

// Logout revokes the provided refresh token, effectively ending the session.
func (h *AuthHandler) Logout(ctx context.Context, req *authv1.LogoutRequest) (*authv1.LogoutResponse, error) {
	if req.GetRefreshToken() == "" {
		return nil, status.Error(codes.InvalidArgument, "refresh_token is required")
	}

	err := h.tokenSvc.RevokeToken(ctx, req.GetRefreshToken())
	if err != nil {
		if errors.Is(err, service.ErrTokenNotFound) {
			// Token not found is not an error from the client's perspective;
			// the session is effectively ended either way.
			return &authv1.LogoutResponse{}, nil
		}
		return nil, status.Errorf(codes.Internal, "revoke token: %v", err)
	}

	return &authv1.LogoutResponse{}, nil
}

// GetUser returns the user profile for the given user ID.
func (h *AuthHandler) GetUser(ctx context.Context, req *authv1.GetUserRequest) (*authv1.GetUserResponse, error) {
	if req.GetUserId() == "" {
		return nil, status.Error(codes.InvalidArgument, "user_id is required")
	}

	user, err := h.authSvc.GetUser(ctx, req.GetUserId())
	if err != nil {
		if errors.Is(err, service.ErrUserNotFound) {
			return nil, status.Error(codes.NotFound, "user not found")
		}
		return nil, status.Errorf(codes.Internal, "get user: %v", err)
	}

	return &authv1.GetUserResponse{
		User: userToProto(user),
	}, nil
}

// ForgotPassword initiates the password reset flow by generating a reset token
// and sending it to the user's email address.
func (h *AuthHandler) ForgotPassword(ctx context.Context, req *authv1.ForgotPasswordRequest) (*authv1.ForgotPasswordResponse, error) {
	if req.GetEmail() == "" {
		return nil, status.Error(codes.InvalidArgument, "email is required")
	}

	// SendPasswordReset returns nil even if email not found to avoid revealing existence.
	_ = h.emailSvc.SendPasswordReset(ctx, req.GetEmail())

	return &authv1.ForgotPasswordResponse{}, nil
}

// ResetPassword completes the password reset flow by validating the reset token
// and updating the user's password.
func (h *AuthHandler) ResetPassword(ctx context.Context, req *authv1.ResetPasswordRequest) (*authv1.ResetPasswordResponse, error) {
	if req.GetToken() == "" {
		return nil, status.Error(codes.InvalidArgument, "token is required")
	}
	if req.GetNewPassword() == "" {
		return nil, status.Error(codes.InvalidArgument, "new_password is required")
	}

	err := h.emailSvc.ResetPassword(ctx, req.GetToken(), req.GetNewPassword())
	if err != nil {
		return nil, status.Error(codes.InvalidArgument, "invalid or expired reset token")
	}

	return &authv1.ResetPasswordResponse{}, nil
}

// VerifyEmail confirms a user's email address using the verification token.
func (h *AuthHandler) VerifyEmail(ctx context.Context, req *authv1.VerifyEmailRequest) (*authv1.VerifyEmailResponse, error) {
	if req.GetToken() == "" {
		return nil, status.Error(codes.InvalidArgument, "token is required")
	}

	err := h.emailSvc.VerifyEmail(ctx, req.GetToken())
	if err != nil {
		return nil, status.Error(codes.InvalidArgument, "invalid or expired verification token")
	}

	return &authv1.VerifyEmailResponse{}, nil
}

// ResendVerification sends a new email verification link to the user.
func (h *AuthHandler) ResendVerification(ctx context.Context, req *authv1.ResendVerificationRequest) (*authv1.ResendVerificationResponse, error) {
	if req.GetEmail() == "" {
		return nil, status.Error(codes.InvalidArgument, "email is required")
	}

	// ResendVerification returns nil even if email not found to avoid revealing existence.
	_ = h.emailSvc.ResendVerification(ctx, req.GetEmail())

	return &authv1.ResendVerificationResponse{}, nil
}

// userToProto converts an internal User model to the protobuf User message.
func userToProto(user *model.User) *authv1.User {
	if user == nil {
		return nil
	}

	metadata := make(map[string]string)
	for k, v := range user.Metadata {
		metadata[k] = v
	}

	return &authv1.User{
		Id:            user.ID,
		Email:         user.Email,
		EmailVerified: user.EmailVerified,
		DisplayName:   user.DisplayName,
		MfaEnabled:    user.MFAEnabled,
		Metadata:      metadata,
		CreatedAt:     timestamppb.New(user.CreatedAt),
		UpdatedAt:     timestamppb.New(user.UpdatedAt),
	}
}
