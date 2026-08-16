package service

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/url"
	"strings"

	"github.com/microservices-agents/platform/services/auth/internal/model"
	"github.com/microservices-agents/platform/services/auth/internal/repository"
)

var (
	ErrUnsupportedProvider = errors.New("unsupported OAuth provider")
	ErrOAuthExchangeFailed = errors.New("failed to exchange OAuth code for token")
	ErrOAuthUserInfo       = errors.New("failed to fetch user info from OAuth provider")
)

// OAuthConfig holds OAuth2 client credentials for supported providers.
type OAuthConfig struct {
	GoogleClientID       string
	GoogleClientSecret   string
	GoogleRedirectURL    string
	FacebookClientID     string
	FacebookClientSecret string
	FacebookRedirectURL  string
}

// OAuthService handles OAuth2 authorization flows for external identity providers.
type OAuthService struct {
	config   OAuthConfig
	userRepo repository.UserRepository
	logger   *slog.Logger
	client   *http.Client
}

// NewOAuthService creates a new OAuthService.
func NewOAuthService(cfg OAuthConfig, userRepo repository.UserRepository, logger *slog.Logger) *OAuthService {
	return &OAuthService{
		config:   cfg,
		userRepo: userRepo,
		logger:   logger,
		client:   &http.Client{},
	}
}

// GetAuthURL returns the OAuth authorization URL for the given provider.
func (s *OAuthService) GetAuthURL(provider, state string) (string, error) {
	switch provider {
	case "google":
		params := url.Values{
			"client_id":     {s.config.GoogleClientID},
			"redirect_uri":  {s.config.GoogleRedirectURL},
			"response_type": {"code"},
			"scope":         {"openid email profile"},
			"state":         {state},
			"access_type":   {"offline"},
		}
		return "https://accounts.google.com/o/oauth2/v2/auth?" + params.Encode(), nil

	case "facebook":
		params := url.Values{
			"client_id":     {s.config.FacebookClientID},
			"redirect_uri":  {s.config.FacebookRedirectURL},
			"response_type": {"code"},
			"scope":         {"email,public_profile"},
			"state":         {state},
		}
		return "https://www.facebook.com/v21.0/dialog/oauth?" + params.Encode(), nil

	default:
		return "", ErrUnsupportedProvider
	}
}

// HandleCallback exchanges the authorization code for user info and creates or links the account.
// Returns the user and whether it is a newly created user.
func (s *OAuthService) HandleCallback(ctx context.Context, provider, code string) (*model.User, bool, error) {
	switch provider {
	case "google":
		return s.handleGoogleCallback(ctx, code)
	case "facebook":
		return s.handleFacebookCallback(ctx, code)
	default:
		return nil, false, ErrUnsupportedProvider
	}
}

// --- Google ---

type googleTokenResponse struct {
	AccessToken string `json:"access_token"`
	TokenType   string `json:"token_type"`
	ExpiresIn   int    `json:"expires_in"`
	IDToken     string `json:"id_token"`
}

type googleUserInfo struct {
	ID            string `json:"id"`
	Email         string `json:"email"`
	VerifiedEmail bool   `json:"verified_email"`
	Name          string `json:"name"`
	Picture       string `json:"picture"`
}

func (s *OAuthService) handleGoogleCallback(ctx context.Context, code string) (*model.User, bool, error) {
	// Step 1: Exchange the authorization code for an access token.
	tokenResp, err := s.exchangeGoogleCode(ctx, code)
	if err != nil {
		return nil, false, err
	}

	// Step 2: Fetch user info from Google.
	userInfo, err := s.fetchGoogleUserInfo(ctx, tokenResp.AccessToken)
	if err != nil {
		return nil, false, err
	}

	// Step 3: Find or create the user.
	return s.findOrCreateOAuthUser(ctx, "google", userInfo.ID, userInfo.Email, userInfo.Name)
}

func (s *OAuthService) exchangeGoogleCode(ctx context.Context, code string) (*googleTokenResponse, error) {
	data := url.Values{
		"code":          {code},
		"client_id":     {s.config.GoogleClientID},
		"client_secret": {s.config.GoogleClientSecret},
		"redirect_uri":  {s.config.GoogleRedirectURL},
		"grant_type":    {"authorization_code"},
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, "https://oauth2.googleapis.com/token", strings.NewReader(data.Encode()))
	if err != nil {
		return nil, fmt.Errorf("create google token request: %w", err)
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")

	resp, err := s.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrOAuthExchangeFailed, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("%w: status %d, body: %s", ErrOAuthExchangeFailed, resp.StatusCode, string(body))
	}

	var tokenResp googleTokenResponse
	if err := json.NewDecoder(resp.Body).Decode(&tokenResp); err != nil {
		return nil, fmt.Errorf("decode google token response: %w", err)
	}
	return &tokenResp, nil
}

func (s *OAuthService) fetchGoogleUserInfo(ctx context.Context, accessToken string) (*googleUserInfo, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, "https://www.googleapis.com/oauth2/v2/userinfo", nil)
	if err != nil {
		return nil, fmt.Errorf("create google userinfo request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+accessToken)

	resp, err := s.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrOAuthUserInfo, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("%w: status %d, body: %s", ErrOAuthUserInfo, resp.StatusCode, string(body))
	}

	var userInfo googleUserInfo
	if err := json.NewDecoder(resp.Body).Decode(&userInfo); err != nil {
		return nil, fmt.Errorf("decode google user info: %w", err)
	}
	return &userInfo, nil
}

// --- Facebook ---

type facebookTokenResponse struct {
	AccessToken string `json:"access_token"`
	TokenType   string `json:"token_type"`
}

type facebookUserInfo struct {
	ID    string `json:"id"`
	Name  string `json:"name"`
	Email string `json:"email"`
}

func (s *OAuthService) handleFacebookCallback(ctx context.Context, code string) (*model.User, bool, error) {
	// Step 1: Exchange the authorization code for an access token.
	tokenResp, err := s.exchangeFacebookCode(ctx, code)
	if err != nil {
		return nil, false, err
	}

	// Step 2: Fetch user info from Facebook.
	userInfo, err := s.fetchFacebookUserInfo(ctx, tokenResp.AccessToken)
	if err != nil {
		return nil, false, err
	}

	// Email is required — Facebook users who denied email scope cannot log in.
	if userInfo.Email == "" {
		return nil, false, fmt.Errorf("facebook login requires email permission: user did not grant email access")
	}

	// Step 3: Find or create the user.
	return s.findOrCreateOAuthUser(ctx, "facebook", userInfo.ID, userInfo.Email, userInfo.Name)
}

func (s *OAuthService) exchangeFacebookCode(ctx context.Context, code string) (*facebookTokenResponse, error) {
	data := url.Values{
		"code":          {code},
		"client_id":     {s.config.FacebookClientID},
		"client_secret": {s.config.FacebookClientSecret},
		"redirect_uri":  {s.config.FacebookRedirectURL},
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, "https://graph.facebook.com/v21.0/oauth/access_token", strings.NewReader(data.Encode()))
	if err != nil {
		return nil, fmt.Errorf("create facebook token request: %w", err)
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")

	resp, err := s.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrOAuthExchangeFailed, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		s.logger.Error("facebook token exchange failed", "status", resp.StatusCode, "body", string(body))
		return nil, fmt.Errorf("facebook token exchange failed: status %d", resp.StatusCode)
	}

	var tokenResp facebookTokenResponse
	if err := json.NewDecoder(resp.Body).Decode(&tokenResp); err != nil {
		return nil, fmt.Errorf("decode facebook token response: %w", err)
	}

	if tokenResp.AccessToken == "" {
		return nil, fmt.Errorf("%w: empty access token in response", ErrOAuthExchangeFailed)
	}

	return &tokenResp, nil
}

// appsecretProof computes HMAC-SHA256(accessToken, appSecret) as a hex string.
// Facebook requires this for server-side Graph API calls when appsecret_proof is enabled.
func appsecretProof(accessToken, appSecret string) string {
	mac := hmac.New(sha256.New, []byte(appSecret))
	mac.Write([]byte(accessToken))
	return hex.EncodeToString(mac.Sum(nil))
}

func (s *OAuthService) fetchFacebookUserInfo(ctx context.Context, accessToken string) (*facebookUserInfo, error) {
	proof := appsecretProof(accessToken, s.config.FacebookClientSecret)
	params := url.Values{
		"fields":          {"id,name,email"},
		"appsecret_proof": {proof},
	}
	reqURL := "https://graph.facebook.com/me?" + params.Encode()

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, reqURL, nil)
	if err != nil {
		return nil, fmt.Errorf("create facebook userinfo request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+accessToken)

	resp, err := s.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrOAuthUserInfo, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		s.logger.Error("facebook user info fetch failed", "status", resp.StatusCode, "body", string(body))
		return nil, fmt.Errorf("facebook user info fetch failed: status %d", resp.StatusCode)
	}

	var userInfo facebookUserInfo
	if err := json.NewDecoder(resp.Body).Decode(&userInfo); err != nil {
		return nil, fmt.Errorf("decode facebook user info: %w", err)
	}
	return &userInfo, nil
}

// --- Shared user resolution ---

// findOrCreateOAuthUser resolves an OAuth identity to a platform user.
// It checks for an existing OAuth link via user metadata, then by email, and finally creates a new user.
func (s *OAuthService) findOrCreateOAuthUser(ctx context.Context, provider, providerID, email, displayName string) (*model.User, bool, error) {
	metaKey := "oauth_" + provider + "_id"

	// Check if a user with this email already exists.
	existingUser, err := s.userRepo.GetByEmail(ctx, email)
	if err != nil && !errors.Is(err, repository.ErrUserNotFound) {
		return nil, false, fmt.Errorf("lookup user by email: %w", err)
	}

	if existingUser != nil {
		// User with this email exists. Check if the OAuth account is already linked.
		if existingUser.Metadata[metaKey] == providerID {
			// Already linked, just return the user.
			return existingUser, false, nil
		}

		// Link the OAuth account to this existing user.
		if existingUser.Metadata == nil {
			existingUser.Metadata = make(map[string]string)
		}
		existingUser.Metadata[metaKey] = providerID

		if err := s.userRepo.Update(ctx, existingUser); err != nil {
			return nil, false, fmt.Errorf("link OAuth account: %w", err)
		}

		s.logger.Info("linked OAuth account to existing user",
			"user_id", existingUser.ID, "provider", provider)
		return existingUser, false, nil
	}

	// No existing user found. Create a new OAuth-only user (no password).
	newUser := &model.User{
		Email:         email,
		EmailVerified: true, // OAuth providers verify email.
		DisplayName:   displayName,
		Metadata: map[string]string{
			metaKey: providerID,
		},
	}

	if err := s.userRepo.Create(ctx, newUser); err != nil {
		// Handle the race condition where the email was just created by another request.
		if errors.Is(err, repository.ErrEmailAlreadyExists) {
			return s.findOrCreateOAuthUser(ctx, provider, providerID, email, displayName)
		}
		return nil, false, fmt.Errorf("create OAuth user: %w", err)
	}

	s.logger.Info("created new user via OAuth", "user_id", newUser.ID, "provider", provider)
	return newUser, true, nil
}
