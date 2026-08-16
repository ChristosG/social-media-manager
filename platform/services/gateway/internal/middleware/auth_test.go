package middleware

import (
	"crypto/ed25519"
	"encoding/base64"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	pkgjwt "github.com/microservices-agents/platform/pkg/jwt"
)

func newTestManager(t *testing.T) *pkgjwt.Manager {
	t.Helper()
	pub, priv, err := ed25519.GenerateKey(nil)
	if err != nil {
		t.Fatalf("generate key: %v", err)
	}
	m, err := pkgjwt.NewManager(
		base64.StdEncoding.EncodeToString(priv),
		base64.StdEncoding.EncodeToString(pub),
	)
	if err != nil {
		t.Fatalf("new manager: %v", err)
	}
	return m
}

func doRequest(t *testing.T, m *pkgjwt.Manager, token string) int {
	t.Helper()
	var nextCalled bool
	h := Auth(m)(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		nextCalled = true
		w.WriteHeader(http.StatusOK)
	}))
	req := httptest.NewRequest(http.MethodGet, "/api/v1/auth/me", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code == http.StatusOK != nextCalled {
		t.Fatalf("nextCalled (%v) disagrees with status %d", nextCalled, rec.Code)
	}
	return rec.Code
}

// A normal access token (no mfa marker) must pass.
func TestAuth_AllowsFullAccessToken(t *testing.T) {
	m := newTestManager(t)
	tok, err := m.GenerateAccessToken("user-1", "u@example.com", "tid-1", []string{"member"}, nil, nil, time.Minute)
	if err != nil {
		t.Fatalf("token: %v", err)
	}
	if code := doRequest(t, m, tok); code != http.StatusOK {
		t.Fatalf("full token rejected: got %d, want 200", code)
	}
}

// A first-factor-only token (mfa:pending) is NOT a credential — the gateway must reject it,
// otherwise an MFA-enabled user bypasses their second factor entirely.
func TestAuth_RejectsPendingMFAToken(t *testing.T) {
	m := newTestManager(t)
	tok, err := m.GenerateAccessToken("user-1", "u@example.com", "", nil, nil,
		map[string]string{"mfa": "pending"}, 5*time.Minute)
	if err != nil {
		t.Fatalf("token: %v", err)
	}
	if code := doRequest(t, m, tok); code != http.StatusUnauthorized {
		t.Fatalf("pending-MFA token accepted: got %d, want 401", code)
	}
}
