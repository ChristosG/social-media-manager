package handler

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// The OAuth callback must reject a state that doesn't match the cookie set when the flow began — without
// that, login is CSRF-able. The 403 path returns before any gRPC call, so a nil client is fine here.

func TestOAuthCallbackRejectsMissingStateCookie(t *testing.T) {
	h := &AuthHandler{}
	req := httptest.NewRequest(http.MethodGet, "/api/v1/auth/oauth/google/callback?code=x&state=abc", nil)
	w := httptest.NewRecorder()
	h.OAuthCallback(w, req)
	if w.Code != http.StatusForbidden {
		t.Fatalf("missing state cookie: want 403, got %d", w.Code)
	}
}

func TestOAuthCallbackRejectsMismatchedState(t *testing.T) {
	h := &AuthHandler{}
	req := httptest.NewRequest(http.MethodGet, "/api/v1/auth/oauth/google/callback?code=x&state=abc", nil)
	req.AddCookie(&http.Cookie{Name: oauthStateCookie, Value: "a-different-state"})
	w := httptest.NewRecorder()
	h.OAuthCallback(w, req)
	if w.Code != http.StatusForbidden {
		t.Fatalf("mismatched state: want 403, got %d", w.Code)
	}
}

func TestNewOAuthStateIsRandomAndLong(t *testing.T) {
	a, b := newOAuthState(), newOAuthState()
	if a == "" || b == "" || a == b || len(a) < 24 {
		t.Fatalf("weak oauth state: %q vs %q", a, b)
	}
}
