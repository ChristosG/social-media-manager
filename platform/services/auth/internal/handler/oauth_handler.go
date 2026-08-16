package handler

import (
	"context"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	authv1 "github.com/microservices-agents/platform/proto/gen/go/auth/v1"
)

// providerToString converts an AuthProvider enum to a lowercase string for the service layer.
func providerToString(p authv1.AuthProvider) string {
	switch p {
	case authv1.AuthProvider_AUTH_PROVIDER_GOOGLE:
		return "google"
	case authv1.AuthProvider_AUTH_PROVIDER_FACEBOOK:
		return "facebook"
	default:
		return ""
	}
}

// OAuthURL returns the authorization URL for the requested OAuth provider.
// The client should redirect the user to this URL to begin the OAuth flow.
func (h *AuthHandler) OAuthURL(ctx context.Context, req *authv1.OAuthURLRequest) (*authv1.OAuthURLResponse, error) {
	provider := providerToString(req.GetProvider())
	if provider == "" {
		return nil, status.Error(codes.InvalidArgument, "provider is required")
	}

	authURL, err := h.oauthSvc.GetAuthURL(provider, req.GetRedirectUrl())
	if err != nil {
		return nil, status.Errorf(codes.Internal, "get auth URL: %v", err)
	}

	return &authv1.OAuthURLResponse{
		Url: authURL,
	}, nil
}

// OAuthLogin completes the OAuth flow by exchanging the authorization code for user info,
// creating or linking the user account, and returning authentication tokens.
func (h *AuthHandler) OAuthLogin(ctx context.Context, req *authv1.OAuthLoginRequest) (*authv1.OAuthLoginResponse, error) {
	provider := providerToString(req.GetProvider())
	if provider == "" {
		return nil, status.Error(codes.InvalidArgument, "provider is required")
	}
	if req.GetCode() == "" {
		return nil, status.Error(codes.InvalidArgument, "code is required")
	}

	user, isNewUser, err := h.oauthSvc.HandleCallback(ctx, provider, req.GetCode())
	if err != nil {
		return nil, status.Errorf(codes.Internal, "oauth callback: %v", err)
	}

	accessToken, err := h.generateUserAccessToken(ctx, user)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "generate access token: %v", err)
	}

	refreshToken, err := h.tokenSvc.CreateRefreshToken(ctx, user.ID, "")
	if err != nil {
		return nil, status.Errorf(codes.Internal, "create refresh token: %v", err)
	}

	return &authv1.OAuthLoginResponse{
		AccessToken:  accessToken,
		RefreshToken: refreshToken,
		User:         userToProto(user),
		IsNewUser:    isNewUser,
	}, nil
}
