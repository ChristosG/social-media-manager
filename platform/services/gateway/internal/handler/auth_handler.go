package handler

import (
	"crypto/rand"
	"crypto/subtle"
	"encoding/base64"
	"encoding/json"
	"net/http"
	"net/url"

	"github.com/go-chi/chi/v5"
	authv1 "github.com/microservices-agents/platform/proto/gen/go/auth/v1"
	"github.com/microservices-agents/platform/services/gateway/internal/middleware"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

const oauthStateCookie = "oauth_state"

// newOAuthState returns an unguessable CSRF state token, or "" if the OS RNG fails.
func newOAuthState() string {
	b := make([]byte, 24)
	if _, err := rand.Read(b); err != nil {
		return ""
	}
	return base64.RawURLEncoding.EncodeToString(b)
}

// AuthHandler translates REST/HTTP requests into gRPC calls to the auth service.
type AuthHandler struct {
	client authv1.AuthServiceClient
}

// NewAuthHandler creates a new AuthHandler backed by the given gRPC client.
func NewAuthHandler(client authv1.AuthServiceClient) *AuthHandler {
	return &AuthHandler{client: client}
}

// ---------- request/response types ----------

type registerRequest struct {
	Email       string            `json:"email"`
	Password    string            `json:"password"`
	DisplayName string            `json:"display_name"`
	Metadata    map[string]string `json:"metadata,omitempty"`
}

type loginRequest struct {
	Email    string `json:"email"`
	Password string `json:"password"`
}

type refreshTokenRequest struct {
	RefreshToken string `json:"refresh_token"`
}

type logoutRequest struct {
	RefreshToken string `json:"refresh_token"`
}

type verifyMFARequest struct {
	MFAToken string `json:"mfa_token"`
	Code     string `json:"code"`
}

type disableMFARequest struct {
	Code string `json:"code"`
}

type forgotPasswordRequest struct {
	Email string `json:"email"`
}

type resetPasswordRequest struct {
	Token       string `json:"token"`
	NewPassword string `json:"new_password"`
}

type verifyEmailRequest struct {
	Token string `json:"token"`
}

type resendVerificationRequest struct {
	Email string `json:"email"`
}

// ---------- handlers ----------

// Register handles POST /api/v1/auth/register.
func (h *AuthHandler) Register(w http.ResponseWriter, r *http.Request) {
	var req registerRequest
	if err := readJSON(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	resp, err := h.client.Register(r.Context(), &authv1.RegisterRequest{
		Email:       req.Email,
		Password:    req.Password,
		DisplayName: req.DisplayName,
		Metadata:    req.Metadata,
	})
	if err != nil {
		grpcToHTTPError(w, err)
		return
	}

	writeJSON(w, http.StatusCreated, map[string]interface{}{
		"access_token":  resp.AccessToken,
		"refresh_token": resp.RefreshToken,
		"user":          userToMap(resp.User),
	})
}

// Login handles POST /api/v1/auth/login.
func (h *AuthHandler) Login(w http.ResponseWriter, r *http.Request) {
	var req loginRequest
	if err := readJSON(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	resp, err := h.client.Login(r.Context(), &authv1.LoginRequest{
		Email:    req.Email,
		Password: req.Password,
	})
	if err != nil {
		grpcToHTTPError(w, err)
		return
	}

	result := map[string]interface{}{
		"access_token":  resp.AccessToken,
		"refresh_token": resp.RefreshToken,
		"user":          userToMap(resp.User),
		"requires_mfa":  resp.RequiresMfa,
	}
	if resp.RequiresMfa {
		result["mfa_token"] = resp.MfaToken
	}

	writeJSON(w, http.StatusOK, result)
}

// RefreshToken handles POST /api/v1/auth/refresh.
func (h *AuthHandler) RefreshToken(w http.ResponseWriter, r *http.Request) {
	var req refreshTokenRequest
	if err := readJSON(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	resp, err := h.client.RefreshToken(r.Context(), &authv1.RefreshTokenRequest{
		RefreshToken: req.RefreshToken,
	})
	if err != nil {
		grpcToHTTPError(w, err)
		return
	}

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"access_token":  resp.AccessToken,
		"refresh_token": resp.RefreshToken,
	})
}

// Logout handles POST /api/v1/auth/logout (requires auth).
func (h *AuthHandler) Logout(w http.ResponseWriter, r *http.Request) {
	var req logoutRequest
	if err := readJSON(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	_, err := h.client.Logout(r.Context(), &authv1.LogoutRequest{
		RefreshToken: req.RefreshToken,
	})
	if err != nil {
		grpcToHTTPError(w, err)
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{"message": "logged out successfully"})
}

// GetMe handles GET /api/v1/auth/me (requires auth).
func (h *AuthHandler) GetMe(w http.ResponseWriter, r *http.Request) {
	userID, ok := r.Context().Value(middleware.UserIDKey).(string)
	if !ok || userID == "" {
		writeError(w, http.StatusUnauthorized, "user not authenticated")
		return
	}

	resp, err := h.client.GetUser(r.Context(), &authv1.GetUserRequest{
		UserId: userID,
	})
	if err != nil {
		grpcToHTTPError(w, err)
		return
	}

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"user": userToMap(resp.User),
	})
}

// OAuthURL handles GET /api/v1/auth/oauth/{provider}.
func (h *AuthHandler) OAuthURL(w http.ResponseWriter, r *http.Request) {
	provider := chi.URLParam(r, "provider")
	providerEnum := parseProvider(provider)

	redirectURL := r.URL.Query().Get("redirect_url")

	resp, err := h.client.OAuthURL(r.Context(), &authv1.OAuthURLRequest{
		Provider:    providerEnum,
		RedirectUrl: redirectURL,
	})
	if err != nil {
		grpcToHTTPError(w, err)
		return
	}

	// CSRF defence: mint a random state, stamp it onto the provider URL, and remember it in an HttpOnly
	// cookie. The provider echoes the state back to the callback, which we then match against the cookie —
	// so a login flow the user didn't start (or one stitched by an attacker) is rejected. SameSite=Lax so
	// the cookie still rides the top-level redirect back from the provider.
	state := newOAuthState()
	authURL := resp.Url
	if u, perr := url.Parse(authURL); perr == nil && state != "" {
		q := u.Query()
		q.Set("state", state)
		u.RawQuery = q.Encode()
		authURL = u.String()
	}
	http.SetCookie(w, &http.Cookie{
		Name: oauthStateCookie, Value: state, Path: "/", HttpOnly: true, Secure: true,
		SameSite: http.SameSiteLaxMode, MaxAge: 600,
	})

	writeJSON(w, http.StatusOK, map[string]string{
		"url": authURL,
	})
}

// OAuthCallback handles GET /api/v1/auth/oauth/{provider}/callback.
func (h *AuthHandler) OAuthCallback(w http.ResponseWriter, r *http.Request) {
	provider := chi.URLParam(r, "provider")
	providerEnum := parseProvider(provider)
	code := r.URL.Query().Get("code")
	state := r.URL.Query().Get("state")

	// CSRF defence: the state echoed by the provider must match the one we set in the cookie at start.
	cookie, cerr := r.Cookie(oauthStateCookie)
	if cerr != nil || cookie.Value == "" || state == "" ||
		subtle.ConstantTimeCompare([]byte(cookie.Value), []byte(state)) != 1 {
		writeError(w, http.StatusForbidden, "invalid OAuth state")
		return
	}
	// One-time: clear the state cookie so it can't be replayed.
	http.SetCookie(w, &http.Cookie{
		Name: oauthStateCookie, Value: "", Path: "/", HttpOnly: true, Secure: true,
		SameSite: http.SameSiteLaxMode, MaxAge: -1,
	})

	resp, err := h.client.OAuthLogin(r.Context(), &authv1.OAuthLoginRequest{
		Provider: providerEnum,
		Code:     code,
		State:    state,
	})
	if err != nil {
		grpcToHTTPError(w, err)
		return
	}

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"access_token":  resp.AccessToken,
		"refresh_token": resp.RefreshToken,
		"user":          userToMap(resp.User),
		"is_new_user":   resp.IsNewUser,
	})
}

// EnableMFA handles POST /api/v1/auth/mfa/enable (requires auth).
func (h *AuthHandler) EnableMFA(w http.ResponseWriter, r *http.Request) {
	userID, ok := r.Context().Value(middleware.UserIDKey).(string)
	if !ok || userID == "" {
		writeError(w, http.StatusUnauthorized, "user not authenticated")
		return
	}

	resp, err := h.client.EnableMFA(r.Context(), &authv1.EnableMFARequest{
		UserId: userID,
	})
	if err != nil {
		grpcToHTTPError(w, err)
		return
	}

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"secret":          resp.Secret,
		"qr_code_url":    resp.QrCodeUrl,
		"recovery_codes": resp.RecoveryCodes,
	})
}

// VerifyMFA handles POST /api/v1/auth/mfa/verify.
func (h *AuthHandler) VerifyMFA(w http.ResponseWriter, r *http.Request) {
	var req verifyMFARequest
	if err := readJSON(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	resp, err := h.client.VerifyMFA(r.Context(), &authv1.VerifyMFARequest{
		MfaToken: req.MFAToken,
		Code:     req.Code,
	})
	if err != nil {
		grpcToHTTPError(w, err)
		return
	}

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"access_token":  resp.AccessToken,
		"refresh_token": resp.RefreshToken,
		"user":          userToMap(resp.User),
	})
}

// DisableMFA handles POST /api/v1/auth/mfa/disable (requires auth).
func (h *AuthHandler) DisableMFA(w http.ResponseWriter, r *http.Request) {
	userID, ok := r.Context().Value(middleware.UserIDKey).(string)
	if !ok || userID == "" {
		writeError(w, http.StatusUnauthorized, "user not authenticated")
		return
	}

	var req disableMFARequest
	if err := readJSON(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	_, err := h.client.DisableMFA(r.Context(), &authv1.DisableMFARequest{
		UserId: userID,
		Code:   req.Code,
	})
	if err != nil {
		grpcToHTTPError(w, err)
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{"message": "mfa disabled successfully"})
}

// ForgotPassword handles POST /api/v1/auth/forgot-password.
func (h *AuthHandler) ForgotPassword(w http.ResponseWriter, r *http.Request) {
	var req forgotPasswordRequest
	if err := readJSON(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	_, err := h.client.ForgotPassword(r.Context(), &authv1.ForgotPasswordRequest{
		Email: req.Email,
	})
	if err != nil {
		grpcToHTTPError(w, err)
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{"message": "password reset email sent"})
}

// ResetPassword handles POST /api/v1/auth/reset-password.
func (h *AuthHandler) ResetPassword(w http.ResponseWriter, r *http.Request) {
	var req resetPasswordRequest
	if err := readJSON(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	_, err := h.client.ResetPassword(r.Context(), &authv1.ResetPasswordRequest{
		Token:       req.Token,
		NewPassword: req.NewPassword,
	})
	if err != nil {
		grpcToHTTPError(w, err)
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{"message": "password reset successfully"})
}

// VerifyEmail handles POST /api/v1/auth/verify-email.
func (h *AuthHandler) VerifyEmail(w http.ResponseWriter, r *http.Request) {
	var req verifyEmailRequest
	if err := readJSON(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	_, err := h.client.VerifyEmail(r.Context(), &authv1.VerifyEmailRequest{
		Token: req.Token,
	})
	if err != nil {
		grpcToHTTPError(w, err)
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{"message": "email verified successfully"})
}

// ResendVerification handles POST /api/v1/auth/resend-verification.
func (h *AuthHandler) ResendVerification(w http.ResponseWriter, r *http.Request) {
	var req resendVerificationRequest
	if err := readJSON(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	_, err := h.client.ResendVerification(r.Context(), &authv1.ResendVerificationRequest{
		Email: req.Email,
	})
	if err != nil {
		grpcToHTTPError(w, err)
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{"message": "verification email resent"})
}

// ---------- helpers ----------

func readJSON(r *http.Request, v interface{}) error {
	defer r.Body.Close()
	return json.NewDecoder(r.Body).Decode(v)
}

func writeJSON(w http.ResponseWriter, statusCode int, v interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(statusCode)
	json.NewEncoder(w).Encode(v)
}

func writeError(w http.ResponseWriter, statusCode int, message string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(statusCode)
	json.NewEncoder(w).Encode(map[string]string{"error": message})
}

// grpcToHTTPError translates a gRPC error into an appropriate HTTP error response.
func grpcToHTTPError(w http.ResponseWriter, err error) {
	st, ok := status.FromError(err)
	if !ok {
		writeError(w, http.StatusInternalServerError, "internal server error")
		return
	}

	var httpStatus int
	switch st.Code() {
	case codes.InvalidArgument:
		httpStatus = http.StatusBadRequest
	case codes.Unauthenticated:
		httpStatus = http.StatusUnauthorized
	case codes.PermissionDenied:
		httpStatus = http.StatusForbidden
	case codes.NotFound:
		httpStatus = http.StatusNotFound
	case codes.AlreadyExists:
		httpStatus = http.StatusConflict
	case codes.ResourceExhausted:
		httpStatus = http.StatusTooManyRequests
	case codes.FailedPrecondition:
		httpStatus = http.StatusPreconditionFailed
	case codes.Unimplemented:
		httpStatus = http.StatusNotImplemented
	case codes.Unavailable:
		httpStatus = http.StatusServiceUnavailable
	case codes.DeadlineExceeded:
		httpStatus = http.StatusGatewayTimeout
	default:
		httpStatus = http.StatusInternalServerError
	}

	writeError(w, httpStatus, st.Message())
}

// parseProvider converts a URL path provider string to the protobuf enum.
func parseProvider(provider string) authv1.AuthProvider {
	switch provider {
	case "google":
		return authv1.AuthProvider_AUTH_PROVIDER_GOOGLE
	case "facebook":
		return authv1.AuthProvider_AUTH_PROVIDER_FACEBOOK
	default:
		return authv1.AuthProvider_AUTH_PROVIDER_UNSPECIFIED
	}
}

// userToMap converts a protobuf User message to a JSON-friendly map.
func userToMap(u *authv1.User) map[string]interface{} {
	if u == nil {
		return nil
	}

	result := map[string]interface{}{
		"id":             u.Id,
		"email":          u.Email,
		"email_verified": u.EmailVerified,
		"display_name":   u.DisplayName,
		"mfa_enabled":    u.MfaEnabled,
		"provider":       u.Provider.String(),
	}

	if u.Metadata != nil {
		result["metadata"] = u.Metadata
	}

	if u.CreatedAt != nil {
		result["created_at"] = u.CreatedAt.AsTime()
	}
	if u.UpdatedAt != nil {
		result["updated_at"] = u.UpdatedAt.AsTime()
	}

	return result
}
