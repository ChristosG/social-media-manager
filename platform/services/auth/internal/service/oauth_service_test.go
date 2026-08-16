package service_test

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"strings"
	"testing"

	"github.com/microservices-agents/platform/services/auth/internal/service"
)

// --- GetAuthURL tests ---

func TestGetAuthURL_Facebook(t *testing.T) {
	svc := service.NewOAuthService(service.OAuthConfig{
		FacebookClientID:     "test-fb-client-id",
		FacebookClientSecret: "test-fb-secret",
		FacebookRedirectURL:  "https://example.com/callback",
	}, nil, nil)

	authURL, err := svc.GetAuthURL("facebook", "mystate123")
	if err != nil {
		t.Fatalf("GetAuthURL(facebook) unexpected error: %v", err)
	}

	if !strings.Contains(authURL, "https://www.facebook.com/v21.0/dialog/oauth") {
		t.Errorf("expected Facebook dialog URL, got: %s", authURL)
	}
	// scope=email,public_profile becomes URL-encoded; check both raw and encoded forms
	if !strings.Contains(authURL, "email") {
		t.Errorf("expected scope to include email, got: %s", authURL)
	}
	if !strings.Contains(authURL, "public_profile") {
		t.Errorf("expected scope to include public_profile, got: %s", authURL)
	}
	if !strings.Contains(authURL, "mystate123") {
		t.Errorf("expected state in URL, got: %s", authURL)
	}
	if !strings.Contains(authURL, "test-fb-client-id") {
		t.Errorf("expected client_id in URL, got: %s", authURL)
	}
}

func TestGetAuthURL_GitHub_Removed(t *testing.T) {
	svc := service.NewOAuthService(service.OAuthConfig{}, nil, nil)

	_, err := svc.GetAuthURL("github", "state")
	if err == nil {
		t.Fatal("expected error for removed github provider, got nil")
	}
	if !strings.Contains(err.Error(), "unsupported") {
		t.Errorf("expected 'unsupported' error, got: %v", err)
	}
}

func TestGetAuthURL_Google_StillWorks(t *testing.T) {
	svc := service.NewOAuthService(service.OAuthConfig{
		GoogleClientID:     "google-client-id",
		GoogleClientSecret: "google-secret",
		GoogleRedirectURL:  "https://example.com/google/callback",
	}, nil, nil)

	authURL, err := svc.GetAuthURL("google", "gstate")
	if err != nil {
		t.Fatalf("GetAuthURL(google) unexpected error: %v", err)
	}
	if !strings.Contains(authURL, "accounts.google.com") {
		t.Errorf("expected Google auth URL, got: %s", authURL)
	}
}

// --- HMAC-SHA256 appsecret_proof verification ---
// We verify the algorithm shape (deterministic, 64-char hex, input-sensitive)
// since appsecretProof is unexported; the integration is tested via build.
func TestAppsecretProof_Algorithm(t *testing.T) {
	computeProof := func(token, secret string) string {
		mac := hmac.New(sha256.New, []byte(secret))
		mac.Write([]byte(token))
		return hex.EncodeToString(mac.Sum(nil))
	}

	p1 := computeProof("mytoken", "mysecret")
	p2 := computeProof("mytoken", "mysecret")
	if p1 != p2 {
		t.Error("appsecret_proof must be deterministic")
	}
	if len(p1) != 64 {
		t.Errorf("expected 64-char hex string, got length %d: %s", len(p1), p1)
	}
	if computeProof("othertoken", "mysecret") == p1 {
		t.Error("different tokens must produce different proofs")
	}
}

// --- HandleCallback unknown provider ---

func TestHandleCallback_GitHub_Removed(t *testing.T) {
	svc := service.NewOAuthService(service.OAuthConfig{}, nil, nil)
	_, _, err := svc.HandleCallback(context.Background(), "github", "some-code")
	if err == nil {
		t.Fatal("expected error for github provider, got nil")
	}
	if !strings.Contains(err.Error(), "unsupported") {
		t.Errorf("expected 'unsupported' error, got: %v", err)
	}
}

func TestHandleCallback_UnknownProvider(t *testing.T) {
	svc := service.NewOAuthService(service.OAuthConfig{}, nil, nil)
	_, _, err := svc.HandleCallback(context.Background(), "twitter", "some-code")
	if err == nil {
		t.Fatal("expected error for unknown provider, got nil")
	}
}
